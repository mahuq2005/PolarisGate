"""Cohere proxy routes — requests flow through the safety pipeline to Cohere."""
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse

from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.circuit_breaker import call_with_circuit_breaker

from ..providers import CohereProvider, ProviderRequest, get_provider
from ..helpers import load_blocklist

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cohere", tags=["Cohere"])
security = HTTPBearer(auto_error=False)

_provider = CohereProvider()


def _merge_results(keyword_result: dict, remote_result: Optional[dict]) -> dict:
    """Merge keyword-based and remote guardrail results."""
    result = dict(keyword_result)
    if remote_result:
        result["toxic"] = result.get("toxic", False) or remote_result.get("toxic", False)
        result["toxic_score"] = max(result.get("toxic_score", 0) or 0, remote_result.get("toxic_score", 0) or 0)
        if remote_result.get("toxic") and not result.get("reason"):
            result["reason"] = remote_result.get("reason")
        result["pii_detected"] = result.get("pii_detected", False) or remote_result.get("pii_detected", False)
        result["pii_types"] = list(set((result.get("pii_types") or []) + (remote_result.get("pii_types") or [])))
    return result


async def _check_text(text: str, current_user: dict, request: Request, credentials=None) -> dict:
    """Run the full guardrails check on a piece of text."""
    from ..constants import detect_injection, redact_text, _category_keywords as _cat_kw
    from ..helpers import load_policies_from_file

    text_lower = text.lower()
    policy_data = load_policies_from_file()
    saved_policies = policy_data.get("policies", [])
    enabled_tox = {p.get("category", "") for p in saved_policies if p.get("type") == "toxicity" and p.get("enabled", True)}

    # Keyword toxicity
    toxic, toxic_score, toxic_reason = False, 0.0, None
    for cat, kws in _cat_kw.items():
        if cat in enabled_tox:
            for kw in kws:
                if kw in text_lower:
                    toxic, toxic_score, toxic_reason = True, 0.85, "Keyword match"
                    break

    # PII
    pii_detected = False
    pii_types = []
    redacted = redact_text(text)
    if redacted != text:
        pii_detected = True
        from ..constants import PII_PATTERNS
        for pattern, ptype, _ in PII_PATTERNS:
            if pattern.search(text):
                pii_types.append(ptype)

    # Injection
    inj_detected, inj_score, inj_matches = detect_injection(text)

    # Blocklist
    blocklist_words = load_blocklist()
    blocklisted = bool(blocklist_words and any(w in text_lower for w in blocklist_words))
    if blocklisted:
        matched_word = next((w for w in blocklist_words if w in text_lower), "unknown")
        await log_audit(current_user.get("sub", "system"), "blocklist_hit", resource_type="cohere_route", details={"word": matched_word, "text": text[:50]}, request=request)

    # Canary check
    try:
        from ..routers.canary import check_canary
        canary_result = await check_canary(text)
    except Exception:
        canary_result = None

    return {
        "toxic": toxic,
        "toxic_score": toxic_score,
        "reason": toxic_reason,
        "pii_detected": pii_detected,
        "pii_types": pii_types,
        "injection_detected": inj_detected,
        "injection_score": round(inj_score, 2),
        "blocklisted": blocklisted,
        "canary_triggered": canary_result is not None,
        "canary_label": canary_result["label"] if canary_result else None,
        "redacted_text": redacted,
    }


@router.post("/chat")
async def cohere_chat(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a chat completion through the safety pipeline to Cohere.

    Request body uses Cohere's native format:
        {"message": "Hello", "model": "command-r", "preamble": "...", ...}

    The gateway:
        1. Runs guardrails on the input
        2. Sends to Cohere
        3. Runs guardrails on the output
        4. Returns the response with safety metadata
    """
    body = await request.json()

    # 1. Normalize + check input
    req_data = _provider.normalize_request(body)
    input_check = await _check_text(req_data.prompt_text, current_user, request, credentials)

    # 2. Call Cohere
    try:
        response = await _provider.chat(req_data)
    except Exception as e:
        logger.error("Cohere API call failed: %s", e)
        raise HTTPException(502, f"Cohere API error: {str(e)}")

    # 3. Check output
    output_check = await _check_text(response.text, current_user, request, credentials)

    # 4. Log audit
    await log_audit(current_user.get("sub", "cohere_chat"), action="cohere_chat", resource_type="cohere", details={
        "model": req_data.model,
        "input_toxic": input_check["toxic"],
        "output_toxic": output_check["toxic"],
        "output_pii": output_check["pii_detected"],
    }, request=request)

    return {
        "text": response.text if not output_check["blocklisted"] else output_check["redacted_text"],
        "model": req_data.model,
        "safety": {
            "input": {"toxic": input_check["toxic"], "toxic_score": input_check["toxic_score"], "injection_detected": input_check["injection_detected"]},
            "output": {"toxic": output_check["toxic"], "toxic_score": output_check["toxic_score"], "pii_detected": output_check["pii_detected"], "pii_types": output_check["pii_types"], "blocklisted": output_check["blocklisted"], "canary_triggered": output_check["canary_triggered"]},
        },
        "usage": response.usage,
    }


@router.post("/chat/stream")
async def cohere_chat_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a streaming chat completion through the safety pipeline to Cohere."""
    body = await request.json()
    req_data = _provider.normalize_request(body)

    # Input check (pre-stream)
    input_check = await _check_text(req_data.prompt_text, current_user, request, credentials)

    if input_check["blocklisted"] or input_check["injection_detected"]:
        raise HTTPException(403, "Input blocked by safety policy")

    async def event_generator():
        full_text = ""
        try:
            async for chunk in _provider.chat_stream(req_data):
                full_text += chunk
                # Stream each chunk as SSE
                event = json.dumps({"type": "content", "text": chunk})
                yield f"data: {event}\n\n"
        except Exception as e:
            logger.error("Cohere stream failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            return

        # Output check (post-stream) — run guardrails on full response
        output_check = await _check_text(full_text, current_user, request, credentials)
        event = json.dumps({
            "type": "safety",
            "toxic": output_check["toxic"],
            "pii_detected": output_check["pii_detected"],
            "blocklisted": output_check["blocklisted"],
            "canary_triggered": output_check["canary_triggered"],
        })
        yield f"data: {event}\n\n"

        await log_audit(current_user.get("sub", "cohere_chat"), action="cohere_chat_stream", resource_type="cohere", details={
            "model": req_data.model, "input_injection": input_check["injection_detected"], "output_toxic": output_check["toxic"],
        }, request=request)

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
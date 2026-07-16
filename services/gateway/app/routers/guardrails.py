"""Guardrails endpoints — toxicity/PII/injection check, batch, streaming."""
import json
import logging
import os
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.circuit_breaker import call_with_circuit_breaker
from shared.schemas import GuardrailCheckRequest

from ..constants import (
    detect_injection,
    redact_text,
    TOXIC_KEYWORDS,
    INJECTION_PATTERNS,
    PII_PATTERNS,
)
from ..helpers import (
    load_blocklist,
    load_policies_from_file,
    detect_language,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/guardrails", tags=["Guardrails"])
security = HTTPBearer(auto_error=False)

GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://guardrails:8005")
MAX_PROMPT_LENGTH = 32_768  # ~32KB max — prevents DoS via massive input

_category_keywords = {
    "hate_speech": ["hate", "racist", "sexist"],
    "harassment": ["stupid", "idiot", "dumb", "ugly", "loser", "trash"],
    "threat": ["kill", "attack", "destroy", "die", "death", "threat", "violence"],
    "profanity": ["damn", "crap", "hell", "bastard", "jerk", "asshole"],
}


def sanitize_prompt(text: str) -> str:
    """Sanitize user input before guardrail checking.

    - Truncates to MAX_PROMPT_LENGTH to prevent DoS
    - Strips non-printable control characters (except \\n, \\t)
    - Unicode NFKC normalization to prevent homoglyph bypass
    """
    if not text:
        return ""
    text = text[:MAX_PROMPT_LENGTH]
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    text = unicodedata.normalize("NFKC", text)
    return text


def _check_toxicity(
    text_lower: str, enabled_categories: set[str]
) -> tuple[bool, float, Optional[str]]:
    for category, keywords in _category_keywords.items():
        if category in enabled_categories:
            for kw in keywords:
                if kw in text_lower:
                    return (True, 0.85, "Keyword match")
    return (False, 0.0, None)


@router.post("/check")
async def guardrails_check(
    request: Request,
    payload: GuardrailCheckRequest,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    text = sanitize_prompt(payload.text or "")
    text_lower = text.lower()

    policy_data = load_policies_from_file()
    saved_policies = policy_data.get("policies", [])
    enabled_tox = {
        p.get("category", "")
        for p in saved_policies
        if p.get("type") == "toxicity" and p.get("enabled", True)
    }
    toxic, toxic_score, toxic_reason = _check_toxicity(text_lower, enabled_tox)

    pii_detected = False
    pii_types: list[str] = []
    redacted = redact_text(text)
    if redacted != text:
        pii_detected = True
        for pattern, ptype, _ in PII_PATTERNS:
            if pattern.search(text):
                pii_types.append(ptype)

    auth_headers = (
        {"Authorization": f"Bearer {credentials.credentials}"} if credentials else {}
    )
    remote_result = None
    try:
        remote_result = await call_with_circuit_breaker(
            service_name="guardrails",
            method="POST",
            url=f"{GUARDRAILS_URL}/api/v1/check",
            json={"text": text},
            headers=auth_headers,
            timeout=30.0,
        )
    except Exception as exc:
        logger.warning("Guardrails service unavailable, using keyword fallback: %s", exc)

    result = {
        "toxic": toxic,
        "toxic_score": toxic_score,
        "reason": toxic_reason,
        "pii_detected": pii_detected,
        "pii_types": pii_types,
    }
    if remote_result:
        result["toxic"] = result["toxic"] or remote_result.get("toxic", False)
        result["toxic_score"] = max(
            result["toxic_score"], remote_result.get("toxic_score", 0.0)
        )
        if remote_result.get("toxic") and not result["reason"]:
            result["reason"] = remote_result.get("reason")
        result["pii_detected"] = result["pii_detected"] or remote_result.get(
            "pii_detected", False
        )
        result["pii_types"] = list(
            set(result["pii_types"] + remote_result.get("pii_types", []))
        )

    if not result["toxic"]:
        result["toxic_score"] = max(result["toxic_score"], 0.05)
        result["reason"] = result.get("reason") or None

    inj_detected, inj_score, inj_matches = detect_injection(text)
    result["injection_detected"] = inj_detected
    result["injection_score"] = round(inj_score, 2)
    result["injection_matches"] = inj_matches

    blocklist_words = load_blocklist()
    is_blocklisted = bool(blocklist_words and any(w in text_lower for w in blocklist_words))
    result["blocklisted"] = is_blocklisted
    if is_blocklisted:
        matched_word = next((w for w in blocklist_words if w in text_lower), "unknown")
        await log_audit(
            current_user.get("sub", "system"),
            "blocklist_hit",
            resource_type="guardrails",
            details={"word": matched_word, "text": text[:50]},
            request=request,
        )

    result["redacted_text"] = redacted
    result["pii_masked"] = pii_detected
    return result


@router.post("/batch")
async def guardrails_batch(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    body = await request.json()
    texts = body.get("texts", [])
    results = []
    for text in texts[:100]:
        payload = GuardrailCheckRequest(text=text)
        r = await guardrails_check(request, payload, current_user, credentials)
        results.append(r)
    return {"results": results, "total": len(results)}


@router.post("/check/stream")
async def guardrails_check_stream(
    request: Request,
    payload: GuardrailCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    text = sanitize_prompt(payload.text or "")
    words = text.split()
    detected_lang = detect_language(text)
    blocklist_words = set(w.lower() for w in load_blocklist())

    def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'total_tokens': len(words), 'language': detected_lang})}\n\n"
        for i, word in enumerate(words):
            word_clean = word.strip(".,!?;:")
            wl = word_clean.lower()
            is_toxic = wl in TOXIC_KEYWORDS
            is_blocklisted = wl in blocklist_words
            has_pii = any(p.search(word) for p, _, _ in PII_PATTERNS)
            is_injection = any(p.search(word) for p, _ in INJECTION_PATTERNS)
            yield f"data: {json.dumps({'index': i, 'token': word_clean, 'toxic': is_toxic, 'blocklisted': is_blocklisted, 'pii': has_pii, 'injection': is_injection})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'total_tokens': len(words)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
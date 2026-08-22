"""Guardrails endpoints — toxicity/PII/injection check, batch, streaming."""
import json
import logging
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.schemas import GuardrailCheckRequest

from ..constants import (
    TOXIC_KEYWORDS,
    INJECTION_PATTERNS,
    PII_PATTERNS,
)
from ..helpers import (
    load_blocklist,
    detect_language,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/guardrails", tags=["Guardrails"])
security = HTTPBearer(auto_error=False)

MAX_PROMPT_LENGTH = 32_768  # ~32KB max — prevents DoS via massive input


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


@router.post("/check")
async def guardrails_check(
    request: Request,
    payload: GuardrailCheckRequest,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Run all safety checks via the interface and return a unified verdict.

    Delegates detection to :func:`safety.pipeline.run_input_guardrails`,
    which routes toxicity/PII/injection through the SafetyProvider interface
    (real ML), while blocklist + canary stay inline.
    """
    text = sanitize_prompt(payload.text or "")

    from ..safety.pipeline import run_input_guardrails
    check = await run_input_guardrails(text, current_user, request)

    result = {
        "toxic": check["toxic"],
        "toxic_score": check["toxic_score"],
        "reason": check["reason"],
        "pii_detected": check["pii_detected"],
        "pii_types": check["pii_types"],
        "injection_detected": check["injection_detected"],
        "injection_score": check["injection_score"],
        "injection_matches": check["injection_matches"],
        "blocklisted": check["blocklisted"],
        "redacted_text": check["redacted_text"],
        "pii_masked": check["pii_detected"],
    }

    if check["blocklisted"]:
        await log_audit(
            current_user.get("sub", "system"),
            "blocklist_hit",
            resource_type="guardrails",
            details={"text": text[:50]},
            request=request,
        )

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
"""Shared safety pipeline — used by chat, proxy, and cohere routes.

This module extracts the guardrail logic that was duplicated in
``cohere_routes.py``.  Every LLM interaction (input + output) runs
through this pipeline so that guardrails are applied consistently
regardless of which provider or route is used.

Pipeline order:
    1. Input guardrails (toxicity, PII, injection, blocklist, canary)
    2. Forward to provider
    3. Output guardrails (toxicity, PII, blocklist, canary)
    4. Audit log
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request

from ..helpers import load_blocklist
from ..providers import BaseProvider, ProviderRequest, ProviderResponse, get_provider

# DB pool import — use same path as main.py
# Import at module level to avoid circular import issues during async execution
import sys, os as _os
_app_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

async def _get_db_pool_safe():
    """Safely get DB pool for guardrail persistence. Returns None if unavailable."""
    try:
        from shared.db import get_pool
        return await get_pool()
    except Exception as exc:
        logger.debug("DB pool unavailable for guardrail persistence: %s", exc)
        return None

logger = logging.getLogger(__name__)

# ── Public API ────────────────────────────────────────────────────────────────


async def _get_safety_provider(http_request: Request):
    """Resolve the SafetyProvider from app.state, falling back to the factory."""
    try:
        sp = getattr(http_request.app.state, "safety_provider", None)
        if sp is not None:
            return sp
    except Exception:
        pass
    from shared.provider_factory import create_safety_provider
    return create_safety_provider()


async def run_input_guardrails(
    text: str,
    current_user: dict,
    request: Request,
) -> dict:
    """Run all guardrail checks on user input text.

    Delegates to the SafetyProvider interface (toxicity/PII/injection go to
    the real ML services), while keeping the cheap blocklist + canary checks
    inline (they are config/token checks, not ML).

    Returns a dict with boolean flags and scores.
    """
    safety = await _get_safety_provider(request)

    # Toxicity — via the interface (guardrails BERT/Presidio)
    tox = await safety.detect_toxicity(text)
    toxic = tox.toxic
    toxic_score = tox.score
    toxic_reason = tox.reason

    # PII — via the interface
    pii = await safety.detect_pii(text)
    redacted_pii = await safety.redact_pii(text)
    pii_detected = pii.detected
    pii_types: list[str] = list(pii.types or [])
    redacted = redacted_pii.redacted_text or text

    # Injection — via the interface (shared.injection cascade)
    inj = await safety.detect_injection(text)
    inj_detected = inj.detected
    inj_score = inj.score
    inj_matches = len(inj.patterns_matched or [])  # int count (SDK contract)
    inj_category = inj.category
    inj_severity = inj.severity

    # Blocklist (cheap config check — stays inline)
    text_lower = text.lower()
    blocklist_words = load_blocklist()
    blocklisted = bool(blocklist_words and any(w in text_lower for w in blocklist_words))

    # Canary (token check — stays inline, best-effort)
    canary_result: Optional[dict] = None
    try:
        from ..routers.canary import check_canary

        canary_result = await check_canary(text)
    except Exception:
        pass

    return {
        "toxic": toxic,
        "toxic_score": toxic_score,
        "reason": toxic_reason,
        "pii_detected": pii_detected,
        "pii_types": pii_types,
        "injection_detected": inj_detected,
        "injection_score": round(inj_score, 2),
        "injection_matches": inj_matches,
        "injection_category": inj_category,
        "injection_severity": inj_severity,
        "blocklisted": blocklisted,
        "canary_triggered": canary_result is not None,
        "canary_label": canary_result["label"] if canary_result else None,
        "redacted_text": redacted,
    }


async def forward_to_provider(
    provider_name: str,
    req: ProviderRequest,
    api_key_override: Optional[str] = None,
) -> ProviderResponse:
    """Resolve a provider and forward the request.

    If ``api_key_override`` is provided it is injected into the
    ``ProviderRequest.api_key`` field (used when the org's DB‑stored key
    should be used instead of whatever the client sent).
    """
    provider = get_provider(provider_name)
    if api_key_override:
        req.api_key = api_key_override
    return await provider.chat(req)

async def run_full_pipeline(
    provider_name: str,
    request_body: dict,
    current_user: dict,
    http_request: Request,
    api_key_override: Optional[str] = None,
) -> dict:
    """Run the complete safety pipeline: input -> forwarding -> output -> audit.

    Thin wrapper over :class:`SafetyPipelineService` (Gap 20 - the application
    service that orchestrates the stages).
    """
    from .pipeline_service import SafetyPipelineService

    return await SafetyPipelineService().run(
        provider_name, request_body, current_user, http_request, api_key_override
    )

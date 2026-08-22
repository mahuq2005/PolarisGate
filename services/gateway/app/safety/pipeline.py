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
import uuid
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
    """Run the complete safety pipeline: input → forwarding → output → audit.

    This is the single entry-point used by :mod:`routers.chat` and
    :mod:`routers.proxy`.

    Returns a dict suitable for JSON serialisation.
    """
    provider = get_provider(provider_name)
    req = provider.normalize_request(request_body)

    # Override API key from DB if the org has configured one
    if api_key_override:
        req.api_key = api_key_override

    # 1. Input guardrails
    input_check = await run_input_guardrails(req.prompt_text, current_user, http_request)

    # Block immediately if injection or blocklist triggers
    if input_check["blocklisted"] or input_check["injection_detected"]:
        # Persist the blocked trace even though the request will be rejected
        try:
            pool = await _get_db_pool_safe()
            if pool is not None:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO guardrail_results
                           (trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted,
                            injection_detected, injection_score, injection_category, injection_severity, timestamp)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())""",
                        str(uuid.uuid4()),
                        input_check.get("toxic", False),
                        input_check.get("toxic_score", 0.0),
                        input_check.get("reason"),
                        input_check.get("pii_detected", False),
                        ",".join(input_check.get("pii_types", [])) if input_check.get("pii_types") else None,
                        input_check.get("blocklisted", False),
                        input_check.get("injection_detected", False),
                        input_check.get("injection_score", 0.0),
                        input_check.get("injection_category"),
                        input_check.get("injection_severity", 0),
                    )
        except Exception as exc:
            logger.warning("Failed to persist blocked injection trace: %s", exc)

        from shared.audit import log_audit

        await log_audit(
            current_user.get("sub", "system"),
            "chat_blocked",
            resource_type="safety_pipeline",
            details={
                "provider": provider_name,
                "model": req.model,
                "reason": "blocklist" if input_check["blocklisted"] else "injection",
                "input_snippet": req.prompt_text[:80],
            },
            request=http_request,
        )
        raise HTTPException(
            403,
            "Input blocked by safety policy. "
            f"Reason: {'blocklisted word' if input_check['blocklisted'] else 'prompt injection detected'}.",
        )

    # 1b. Budget pre-check (hard cutoff)
    team_id = getattr(http_request.state, "team_id", None) or current_user.get("sub", "default")
    try:
        from shared.quota_enforcer import check_quota
        quota = await check_quota(team_id)
        if not quota.get("allowed", True):
            raise HTTPException(402, f"Budget exceeded: {quota.get('reason', 'team budget exhausted')}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Budget pre-check unavailable (fail-open): %s", exc)

    # 2. Forward to provider
    try:
        response = await provider.chat(req)
    except Exception as exc:
        logger.error(
            "Provider %s call failed: %r (%s)",
            provider_name, exc, type(exc).__name__,
        )
        raise HTTPException(502, f"LLM provider error ({provider_name}): {exc!r}")

    # 2b. Record usage (post-call)
    try:
        from shared.token_counter import get_token_counter
        usage = response.usage or {}
        await get_token_counter().record_usage(
            user_id=current_user.get("sub", "system"),
            team_id=team_id,
            provider=provider_name,
            model=req.model,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            cost_usd=0.0,
        )
    except Exception as exc:
        logger.warning("Usage recording unavailable: %s", exc)

    # 3. Output guardrails
    output_check = await run_input_guardrails(response.text, current_user, http_request)

    # 3b. Hallucination check (output — the #1 spear, now wired in)
    hallucination = None
    try:
        safety = await _get_safety_provider(http_request)
        hallucination = await safety.detect_hallucination(response.text, req.prompt_text)
    except Exception as exc:
        logger.warning("Hallucination check unavailable: %s", exc)

    # 4. Write to guardrail_results (for dashboard visibility — both input + output)
    try:
        pool = await _get_db_pool_safe()
        if pool is None:
            raise RuntimeError("DB pool not available")
        async with pool.acquire() as conn:
            # Write ALL flagged traces (toxic, PII, injection — always persisted)
            has_input = input_check.get("toxic") or input_check.get("pii_detected") or input_check.get("injection_detected")
            has_output = output_check.get("toxic") or output_check.get("pii_detected") or output_check.get("blocklisted") or output_check.get("injection_detected")
            
            if has_input or has_output:
                await conn.execute(
                    """INSERT INTO guardrail_results
                       (trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted,
                        injection_detected, injection_score, injection_category, injection_severity, timestamp)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())""",
                    str(uuid.uuid4()),
                    input_check.get("toxic") if has_input else output_check.get("toxic"),
                    input_check.get("toxic_score") if has_input else output_check.get("toxic_score"),
                    input_check.get("reason") if has_input else output_check.get("reason"),
                    input_check.get("pii_detected") if has_input else output_check.get("pii_detected"),
                    (input_check.get("pii_types") or []) if has_input else (output_check.get("pii_types") or []),
                    input_check.get("blocklisted") if has_input else output_check.get("blocklisted"),
                    input_check.get("injection_detected") if has_input else output_check.get("injection_detected"),
                    input_check.get("injection_score") if has_input else output_check.get("injection_score"),
                    input_check.get("injection_category") if has_input else output_check.get("injection_category"),
                    input_check.get("injection_severity") if has_input else output_check.get("injection_severity"),
                )
    except Exception as exc:
        logger.error("Failed to write guardrail result: %s", exc)

    # Invalidate dashboard cache so new PII/toxic flags appear immediately
    try:
        from shared.redis_client import get_redis

        redis = await get_redis()
        if redis:
            await redis.delete("dashboard_summary")
            await redis.delete("dashboard_incidents")
    except Exception as exc:
        logger.debug("Failed to invalidate dashboard cache: %s", exc)

    # 5. Audit log
    from shared.audit import log_audit

    await log_audit(
        (current_user or {}).get("sub", "system"),
        "chat_completed",
        resource_type="safety_pipeline",
        details={
            "provider": provider_name,
            "model": req.model,
            "input_toxic": input_check["toxic"],
            "output_toxic": output_check["toxic"],
            "output_pii": output_check["pii_detected"],
            "blocked": False,
        },
        request=http_request,
    )

    # 6. Build response
    response_text = response.text
    if output_check["blocklisted"]:
        response_text = output_check.get("redacted_text", response_text)

    return {
        "text": response_text,
        "model": req.model,
        "provider": provider_name,
        "safety": {
            "input": {
                "toxic": input_check["toxic"],
                "toxic_score": input_check["toxic_score"],
                "pii_detected": input_check["pii_detected"],
                "pii_types": input_check["pii_types"],
                "injection_detected": input_check["injection_detected"],
            },
            "output": {
                "toxic": output_check["toxic"],
                "toxic_score": output_check["toxic_score"],
                "pii_detected": output_check["pii_detected"],
                "pii_types": output_check["pii_types"],
                "blocklisted": output_check["blocklisted"],
                "canary_triggered": output_check["canary_triggered"],
                "hallucinated": bool(hallucination.hallucinated) if hallucination else False,
                "hallucination_confidence": float(hallucination.confidence) if hallucination else 0.0,
            },
        },
        "budget": {
            "team_id": team_id,
            "allowed": quota.get("allowed", True),
            "reason": quota.get("reason", "ok"),
        },
        "usage": response.usage,
    }
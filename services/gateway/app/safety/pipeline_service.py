"""SafetyPipelineService — the application-service orchestrator (Gap 20).

Previously the pipeline logic was a single inline function
``run_full_pipeline()``.  Extracting it into a service gives the request path a
named, unit-testable orchestration point:

    input guardrails → block → budget → forward → usage →
    output guardrails → hallucination → audit → response

The gateway's ``run_full_pipeline`` is now a thin wrapper that delegates here.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, Request

from ..providers import get_provider
from shared.guardrail_repository import GuardrailEvent, guardrail_repository

logger = logging.getLogger(__name__)


class SafetyPipelineService:
    """Orchestrates one chat request through the full safety pipeline."""

    async def run(
        self,
        provider_name: str,
        request_body: dict,
        current_user: dict,
        http_request: Request,
        api_key_override: Optional[str] = None,
    ) -> dict:
        # Lazy import to avoid a circular import: pipeline.py delegates to this
        # service, and these helpers live in pipeline.py.
        from .pipeline import (
            _get_safety_provider,
            run_input_guardrails,
        )

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
                await guardrail_repository.record(
                    GuardrailEvent(
                        trace_id=str(uuid.uuid4()),
                        toxic=input_check.get("toxic", False),
                        toxic_score=input_check.get("toxic_score", 0.0),
                        reason=input_check.get("reason"),
                        pii_detected=input_check.get("pii_detected", False),
                        pii_types=input_check.get("pii_types", []),
                        blocklisted=input_check.get("blocklisted", False),
                        injection_detected=input_check.get("injection_detected", False),
                        injection_score=input_check.get("injection_score", 0.0),
                        injection_category=input_check.get("injection_category"),
                        injection_severity=input_check.get("injection_severity"),
                    )
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
            # Write ALL flagged traces (toxic, PII, injection — always persisted)
            has_input = input_check.get("toxic") or input_check.get("pii_detected") or input_check.get("injection_detected")
            has_output = output_check.get("toxic") or output_check.get("pii_detected") or output_check.get("blocklisted") or output_check.get("injection_detected")

            if has_input or has_output:
                await guardrail_repository.record(
                    GuardrailEvent(
                        trace_id=str(uuid.uuid4()),
                        toxic=input_check.get("toxic") if has_input else output_check.get("toxic"),
                        toxic_score=input_check.get("toxic_score") if has_input else output_check.get("toxic_score"),
                        reason=input_check.get("reason") if has_input else output_check.get("reason"),
                        pii_detected=input_check.get("pii_detected") if has_input else output_check.get("pii_detected"),
                        pii_types=(input_check.get("pii_types") or []) if has_input else (output_check.get("pii_types") or []),
                        blocklisted=input_check.get("blocklisted") if has_input else output_check.get("blocklisted"),
                        injection_detected=input_check.get("injection_detected") if has_input else output_check.get("injection_detected"),
                        injection_score=input_check.get("injection_score") if has_input else output_check.get("injection_score"),
                        injection_category=input_check.get("injection_category") if has_input else output_check.get("injection_category"),
                        injection_severity=input_check.get("injection_severity") if has_input else output_check.get("injection_severity"),
                    )
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

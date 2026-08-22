"""Local Safety Provider — wraps existing PolarisGate safety capabilities.

ON-PREM implementation of the SafetyProvider interface.  All safety checks
run locally via HTTP calls to the guardrails (:8005) and hallucination
(:8008) services — no cloud API calls, no internet required.

This is the HYBRID topology: the gateway stays lightweight and delegates the
heavy ML (BERT / Presidio / DeBERTa NLI / injection pipeline) to the
dedicated services over HTTP, behind this interface.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from shared.interfaces.safety import (
    SafetyProvider,
    SafetyProviderType,
    ToxicityResult,
    PIIResult,
    InjectionResult,
    HallucinationResult,
    BiasResult,
)

logger = logging.getLogger(__name__)

GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://guardrails:8005")
HALLUCINATION_URL = os.getenv("HALLUCINATION_URL", "http://hallucination-detector:8008")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")
HTTP_TIMEOUT = float(os.getenv("SAFETY_HTTP_TIMEOUT", "30"))

# Module-level cache of the last health probe result, so get_capabilities()
# (sync) can reflect the async probe without blocking.
_last_health: Dict[str, Any] = {
    "guardrails": True,
    "hallucination": True,
}


class LocalSafetyProvider(SafetyProvider):
    """On-prem / local implementation of all safety checks.

    Delegates to the dedicated ML services over HTTP:
      - toxicity / PII  -> guardrails service (:8005) — BERT + Presidio + Canada
      - injection       -> shared.injection pipeline (regex -> LLM judge)
      - hallucination   -> hallucination-detector (:8008) — DeBERTa NLI
      - bias            -> disabled (demoted; slot retained)
    """

    def __init__(self, models_dir: str = "", thresholds: Optional[Dict[str, float]] = None):
        self._models_dir = models_dir
        self._thresholds = thresholds or {
            "toxicity": 0.5, "pii": 0.0, "injection": 0.5,
            "hallucination": 0.5, "bias": 0.3,
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────

    async def _post_json(self, url: str, payload: dict, service: str) -> Optional[dict]:
        """POST JSON to a downstream service with service-token auth.

        Returns parsed JSON, or None on failure (fail-open for safety checks
        so the gateway never hard-fails when a safety service is down).
        """
        headers = {"Content-Type": "application/json"}
        if SERVICE_TOKEN:
            headers["X-Service-Token"] = SERVICE_TOKEN
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("%s service call failed: %s", service, exc)
            return None

    async def _check_guardrails(self, text: str) -> Optional[dict]:
        """Run the guardrails service check (toxicity + PII in one call)."""
        return await self._post_json(
            f"{GUARDRAILS_URL}/api/v1/check", {"text": text}, "guardrails"
        )

    async def detect_toxicity(self, text: str, context: Optional[dict] = None) -> ToxicityResult:
        start = time.perf_counter()
        if not text or not text.strip():
            return ToxicityResult(toxic=False, score=0.0, latency_ms=0.0)
        result = await self._check_guardrails(text)
        if result is None:
            return ToxicityResult(toxic=False, score=0.0, reason="service unavailable",
                                  latency_ms=round((time.perf_counter() - start) * 1000, 2))
        categories = list((result.get("label_details") or {}).keys())
        return ToxicityResult(
            toxic=bool(result.get("toxic", False)),
            score=float(result.get("toxic_score", 0.0)),
            categories=categories,
            reason=result.get("reason"),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def detect_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        start = time.perf_counter()
        if not text:
            return PIIResult(detected=False, types=[], latency_ms=0.0)
        result = await self._check_guardrails(text)
        if result is None:
            return PIIResult(detected=False, types=[],
                             latency_ms=round((time.perf_counter() - start) * 1000, 2))
        return PIIResult(
            detected=bool(result.get("pii_detected", False)),
            types=list(result.get("pii_types") or []),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def redact_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        start = time.perf_counter()
        if not text:
            return PIIResult(detected=False, types=[], redacted_text=text, latency_ms=0.0)
        # Redaction: use the gateway's redact_text if available, else minimal regex.
        # (Gap 2: move to a Presidio anonymizer endpoint on the guardrails service.)
        try:
            from services.gateway.app.constants import redact_text, PII_PATTERNS
        except ImportError:
            try:
                from app.constants import redact_text, PII_PATTERNS
            except ImportError:
                redact_text = PII_PATTERNS = None
        if redact_text is not None:
            redacted = redact_text(text)
            detected = redacted != text
            types = []
            if detected and PII_PATTERNS:
                for p, pt, _ in PII_PATTERNS:
                    if p.search(text):
                        types.append(pt)
        else:
            redacted, detected, types = text, False, []
            import re as _re
            email_pat = _re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
            if email_pat.search(text):
                detected, types = True, ["email"]
                redacted = email_pat.sub("[EMAIL_REDACTED]", redacted)
        return PIIResult(detected=detected, types=list(set(types)),
                         redacted_text=redacted,
                         latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def detect_injection(self, text: str, context: Optional[dict] = None) -> InjectionResult:
        start = time.perf_counter()
        if not text:
            return InjectionResult(detected=False, score=0.0, latency_ms=0.0)
        try:
            from shared.injection import get_pipeline
            result = await get_pipeline().run(text)
            severity = result.severity.value if getattr(result, "severity", None) else "none"
            return InjectionResult(
                detected=bool(result.detected),
                score=round(float(result.score), 2),
                patterns_matched=list(result.patterns_matched or []),
                category=result.category,
                severity=severity,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            )
        except Exception as exc:
            logger.warning("injection pipeline failed: %s", exc)
            return InjectionResult(detected=False, score=0.0, patterns_matched=[],
                                   latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def detect_hallucination(self, claim: str, source: Optional[str] = None) -> HallucinationResult:
        start = time.perf_counter()
        if not claim or not claim.strip():
            return HallucinationResult(hallucinated=False, confidence=0.0, latency_ms=0.0)
        payload = {
            "context": source or "",
            "response": claim,
            "domain": "general",
        }
        result = await self._post_json(
            f"{HALLUCINATION_URL}/api/v1/hallucination/detect", payload, "hallucination"
        )
        if result is None:
            return HallucinationResult(hallucinated=False, confidence=0.0,
                                       model_used="service_unavailable",
                                       latency_ms=round((time.perf_counter() - start) * 1000, 2))
        score = float(result.get("hallucination_score", 0.0))
        threshold = self._thresholds.get("hallucination", 0.5)
        return HallucinationResult(
            hallucinated=score >= threshold,
            confidence=round(float(result.get("confidence", score)), 3),
            model_used="deberta_nli",
            evidence=result.get("reason"),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def check_bias(self, text: str, context: Optional[dict] = None) -> BiasResult:
        return BiasResult(biased=False, dimensions={}, latency_ms=0.0)

    async def health_check(self) -> Dict[str, Any]:
        global _last_health
        statuses = {}
        for name, url in [("guardrails", GUARDRAILS_URL), ("hallucination", HALLUCINATION_URL)]:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url}/health")
                    statuses[name] = resp.status_code == 200
            except Exception:
                statuses[name] = False
        _last_health = statuses
        ok = all(statuses.values())
        return {
            "status": "ok" if ok else "degraded",
            "provider": "local",
            "services": statuses,
            "capabilities": {
                c.value: {"available": statuses.get(self._cap_service(c), False),
                          "model": "local"}
                for c in self.get_capabilities()
            },
        }

    @staticmethod
    def _cap_service(cap: SafetyProviderType) -> str:
        if cap in (SafetyProviderType.TOXICITY, SafetyProviderType.PII_DETECTION,
                   SafetyProviderType.PII_REDACTION):
            return "guardrails"
        if cap == SafetyProviderType.HALLUCINATION:
            return "hallucination"
        return "guardrails"

    def get_capabilities(self) -> Dict[SafetyProviderType, bool]:
        # Reflect real availability from the last health probe.
        # BIAS is intentionally disabled (demoted to offline evals).
        g = _last_health.get("guardrails", True)
        h = _last_health.get("hallucination", True)
        return {
            SafetyProviderType.TOXICITY: g,
            SafetyProviderType.PII_DETECTION: g,
            SafetyProviderType.PII_REDACTION: g,
            SafetyProviderType.INJECTION: g,
            SafetyProviderType.HALLUCINATION: h,
            SafetyProviderType.BIAS: False,
        }

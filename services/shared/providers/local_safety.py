"""Local Safety Provider — wraps existing PolarisGate safety capabilities.

ON-PREM implementation of the SafetyProvider interface.
All safety checks run locally — no cloud API calls, no internet required.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

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

_category_keywords: Dict[str, List[str]] = {
    "hate_speech": ["hate", "racist", "sexist"],
    "harassment": ["stupid", "idiot", "dumb", "ugly", "loser", "trash"],
    "threat": ["kill", "attack", "destroy", "die", "death", "threat", "violence"],
    "profanity": ["damn", "crap", "bastard", "jerk", "asshole"],
}


class LocalSafetyProvider(SafetyProvider):
    """On-prem / local implementation of all safety checks."""

    def __init__(self, models_dir: str = "", thresholds: Optional[Dict[str, float]] = None):
        self._models_dir = models_dir
        self._thresholds = thresholds or {
            "toxicity": 0.5, "pii": 0.0, "injection": 0.5,
            "hallucination": 0.5, "bias": 0.3,
        }

    async def detect_toxicity(self, text: str, context: Optional[dict] = None) -> ToxicityResult:
        start = time.perf_counter()
        if not text or not text.strip():
            return ToxicityResult(toxic=False, score=0.0, latency_ms=0.0)
        text_lower = text.lower()
        toxic, toxic_score, toxic_reason = False, 0.0, None
        matched: List[str] = []
        for cat, kws in _category_keywords.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    toxic, toxic_score, toxic_reason = True, 0.85, "Keyword match"
                    matched.append(cat)
                    break
        try:
            from services.gateway.app.helpers import load_blocklist
            for w in load_blocklist():
                if w in text_lower:
                    toxic, toxic_score = True, 0.90
                    toxic_reason = f"Blocklisted word: {w}"
                    matched.append("blocklist")
                    break
        except ImportError:
            pass
        return ToxicityResult(
            toxic=toxic, score=toxic_score,
            categories=list(set(matched)), reason=toxic_reason,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def detect_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        start = time.perf_counter()
        if not text:
            return PIIResult(detected=False, types=[], latency_ms=0.0)
        detected, types = False, []
        try:
            from services.gateway.app.constants import PII_PATTERNS
            for p, pt, _ in PII_PATTERNS:
                if p.search(text):
                    detected = True
                    types.append(pt)
        except ImportError:
            for p, pt in [
                (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "email"),
                (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "ssn"),
            ]:
                if p.search(text):
                    detected = True
                    types.append(pt)
        return PIIResult(detected=detected, types=list(set(types)),
                         latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def redact_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        start = time.perf_counter()
        if not text:
            return PIIResult(detected=False, types=[], redacted_text=text, latency_ms=0.0)
        try:
            from services.gateway.app.constants import redact_text, PII_PATTERNS
            redacted = redact_text(text)
            detected = redacted != text
            types = []
            if detected:
                for p, pt, _ in PII_PATTERNS:
                    if p.search(text):
                        types.append(pt)
        except ImportError:
            redacted, detected, types = text, False, []
            email_pat = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
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
        detected, best_score, matched = False, 0.0, []
        try:
            from services.gateway.app.constants import detect_injection, INJECTION_PATTERNS
            detected, best_score, _ = detect_injection(text)
            if detected:
                for p, _ in INJECTION_PATTERNS:
                    if p.search(text):
                        matched.append(p.pattern[:50])
        except ImportError:
            for name, ps in {
                "ignore instructions": r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
                "jailbreak": r"(?i)(jailbreak|jail\s*break)",
                "DAN": r"(?i)\bDAN\b",
            }.items():
                if re.compile(ps).search(text):
                    detected, best_score = True, max(best_score, 0.85)
                    matched.append(name)
        return InjectionResult(detected=detected, score=round(best_score, 2),
                               patterns_matched=matched,
                               latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def detect_hallucination(self, claim: str, source: Optional[str] = None) -> HallucinationResult:
        start = time.perf_counter()
        if not claim or not claim.strip():
            return HallucinationResult(hallucinated=False, confidence=0.0, latency_ms=0.0)
        hallucinated, confidence, evidence = False, 0.0, None
        for ps, w in {
            r"\b(as an AI|I don't know)\b": 0.1,
            r"\b(definitely|absolutely|certainly)\b": 0.05,
        }.items():
            if re.search(ps, claim, re.IGNORECASE):
                confidence += w
        if source:
            sw = set(source.lower().split())
            cw = set(claim.lower().split())
            if sw and cw:
                overlap = len(sw & cw) / len(cw)
                if overlap < 0.1:
                    hallucinated, confidence = True, max(confidence, 0.7)
                    evidence = f"Low overlap ({overlap:.1%})"
        return HallucinationResult(hallucinated=hallucinated, confidence=min(confidence, 1.0),
                                   model_used="local_heuristic", evidence=evidence,
                                   latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def check_bias(self, text: str, context: Optional[dict] = None) -> BiasResult:
        start = time.perf_counter()
        if not text:
            return BiasResult(biased=False, dimensions={}, latency_ms=0.0)
        tl = text.lower()
        dims: Dict[str, float] = {}
        for dim, pts in {
            "gender": ["sexist", "misogynist"],
            "race": ["racist", "racial"],
            "religion": ["infidel", "blasphem"],
            "age": ["boomer", "too old", "too young"],
            "disability": ["cripple", "retard"],
            "nationality": ["illegal alien", "go back to"],
        }.items():
            for pt in pts:
                if re.search(pt, tl):
                    dims[dim] = dims.get(dim, 0.0) + 0.3
        biased = any(v > 0.5 for v in dims.values())
        return BiasResult(biased=biased, dimensions={k: min(v, 1.0) for k, v in dims.items()},
                          latency_ms=round((time.perf_counter() - start) * 1000, 2))

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "ok", "provider": "local",
            "capabilities": {
                c.value: {"available": e, "model": "local" if e else "none"}
                for c, e in self.get_capabilities().items()
            },
        }

    def get_capabilities(self) -> Dict[SafetyProviderType, bool]:
        return {
            SafetyProviderType.TOXICITY: True,
            SafetyProviderType.PII_DETECTION: True,
            SafetyProviderType.PII_REDACTION: True,
            SafetyProviderType.INJECTION: True,
            SafetyProviderType.HALLUCINATION: True,
            SafetyProviderType.BIAS: True,
        }

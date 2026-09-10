"""Capability Registry — routes each safety capability to a concrete detector.

Gap 16: replaces the monolithic ``SafetyProvider`` lookup with per-capability
routing so providers can be mixed per feature (e.g. Azure Prompt Shields for
injection + your own Presidio for PII).

The registry is the spine of the moat: adding or swapping a detector is a
registry/config change, never a gateway code change.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from shared.interfaces.capabilities import (
    BiasDetector,
    HallucinationDetector,
    InjectionDetector,
    PiiDetector,
    PiiRedactor,
    ToxicityDetector,
)
from shared.interfaces.safety import SafetyProvider, SafetyProviderType


class CapabilityRegistry:
    """Maps ``SafetyProviderType`` -> detector instance.

    Build it either explicitly (``CapabilityRegistry().register(...)``) or by
    bridging a monolithic ``SafetyProvider`` (``CapabilityRegistry.from_provider``),
    which is the backward-compatible migration path for existing providers.
    """

    def __init__(self, detectors: Optional[Dict[SafetyProviderType, Any]] = None):
        self._detectors: Dict[SafetyProviderType, Any] = dict(detectors or {})

    # ── Registration ────────────────────────────────────────────────────────

    def register(self, cap: SafetyProviderType, detector: Any) -> "CapabilityRegistry":
        self._detectors[cap] = detector
        return self

    def has(self, cap: SafetyProviderType) -> bool:
        return cap in self._detectors

    def get(self, cap: SafetyProviderType) -> Any:
        if cap not in self._detectors:
            raise KeyError(
                f"capability '{cap.value}' is not configured in this registry"
            )
        return self._detectors[cap]

    # ── Typed accessors ─────────────────────────────────────────────────────

    def toxicity(self) -> ToxicityDetector:
        return self.get(SafetyProviderType.TOXICITY)

    def pii(self) -> PiiDetector:
        return self.get(SafetyProviderType.PII_DETECTION)

    def redactor(self) -> PiiRedactor:
        return self.get(SafetyProviderType.PII_REDACTION)

    def injection(self) -> InjectionDetector:
        return self.get(SafetyProviderType.INJECTION)

    def hallucination(self) -> HallucinationDetector:
        return self.get(SafetyProviderType.HALLUCINATION)

    def bias(self) -> BiasDetector:
        return self.get(SafetyProviderType.BIAS)

    # ── Bridge from a monolithic provider ───────────────────────────────────

    @classmethod
    def from_provider(cls, provider: SafetyProvider) -> "CapabilityRegistry":
        """Bridge a monolithic ``SafetyProvider`` into per-capability adapters.

        Lets existing providers (``LocalSafetyProvider`` today, cloud providers
        later) keep working while call sites move to per-capability lookups.
        """
        return cls({
            SafetyProviderType.TOXICITY: _ToxicityAdapter(provider),
            SafetyProviderType.PII_DETECTION: _PiiAdapter(provider),
            SafetyProviderType.PII_REDACTION: _PiiRedactionAdapter(provider),
            SafetyProviderType.INJECTION: _InjectionAdapter(provider),
            SafetyProviderType.HALLUCINATION: _HallucinationAdapter(provider),
            SafetyProviderType.BIAS: _BiasAdapter(provider),
        })


# ── Monolithic-provider adapters (bridge) ────────────────────────────────────


class _ToxicityAdapter(ToxicityDetector):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def detect_toxicity(self, text: str, context: Optional[dict] = None):
        return await self._provider.detect_toxicity(text, context)


class _PiiAdapter(PiiDetector):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def detect_pii(self, text: str, context: Optional[dict] = None):
        return await self._provider.detect_pii(text, context)


class _PiiRedactionAdapter(PiiRedactor):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def redact_pii(self, text: str, context: Optional[dict] = None):
        return await self._provider.redact_pii(text, context)


class _InjectionAdapter(InjectionDetector):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def detect_injection(self, text: str, context: Optional[dict] = None):
        return await self._provider.detect_injection(text, context)


class _HallucinationAdapter(HallucinationDetector):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def detect_hallucination(self, claim: str, source: Optional[str] = None):
        return await self._provider.detect_hallucination(claim, source)


class _BiasAdapter(BiasDetector):
    def __init__(self, provider: SafetyProvider):
        self._provider = provider

    async def check_bias(self, text: str, context: Optional[dict] = None):
        return await self._provider.check_bias(text, context)

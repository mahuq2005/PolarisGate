"""Per-capability safety interfaces (Gap 16 — Interface Segregation).

The monolithic ``SafetyProvider`` forces all six checks on every
implementation, so a point-solution provider (e.g. Lakera = injection only)
can't fit cleanly.  These single-method interfaces let each capability be
implemented (and mixed) independently.

Each interface reuses the result dataclasses from ``safety.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from shared.interfaces.safety import (
    BiasResult,
    HallucinationResult,
    InjectionResult,
    PIIResult,
    ToxicityResult,
)


class ToxicityDetector(ABC):
    @abstractmethod
    async def detect_toxicity(self, text: str, context: Optional[dict] = None) -> ToxicityResult:
        """Detect toxic / harmful content in ``text``."""
        ...


class PiiDetector(ABC):
    @abstractmethod
    async def detect_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        """Detect PII entities in ``text``."""
        ...


class PiiRedactor(ABC):
    @abstractmethod
    async def redact_pii(self, text: str, context: Optional[dict] = None) -> PIIResult:
        """Detect AND redact PII in ``text``."""
        ...


class InjectionDetector(ABC):
    @abstractmethod
    async def detect_injection(self, text: str, context: Optional[dict] = None) -> InjectionResult:
        """Detect prompt-injection attempts in ``text``."""
        ...


class HallucinationDetector(ABC):
    @abstractmethod
    async def detect_hallucination(self, claim: str, source: Optional[str] = None) -> HallucinationResult:
        """Check whether ``claim`` is supported by ``source``."""
        ...


class BiasDetector(ABC):
    @abstractmethod
    async def check_bias(self, text: str, context: Optional[dict] = None) -> BiasResult:
        """Check ``text`` for biased / unfair content."""
        ...

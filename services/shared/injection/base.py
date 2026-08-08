"""Abstract base class for all injection detectors."""
from __future__ import annotations
from abc import ABC, abstractmethod
from .types import InjectionResult


class InjectionDetector(ABC):
    """Interface for injection detectors (regex, ML, LLM judge).

    All detectors return an InjectionResult with severity, action, and reasoning.
    The pipeline orchestrates which detectors run in which order.
    """

    @abstractmethod
    async def detect(self, text: str) -> InjectionResult:
        """Analyze text for prompt injection.

        Args:
            text: Already normalized and decoded text.

        Returns:
            InjectionResult with severity, recommended_action, and reasoning.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable detector name for logging."""
        ...
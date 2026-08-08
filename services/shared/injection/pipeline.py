"""InjectionPipeline — Chain of Responsibility orchestrator."""
from __future__ import annotations
import logging
import time
from typing import List, Optional
from .base import InjectionDetector
from .types import InjectionResult, Severity, Action
from .config import INJECTION_CONFIG
from .normalizer import TextNormalizer
from .encoding import EncodingDecoder

logger = logging.getLogger(__name__)


class InjectionPipeline:
    """3-layer defense: normalize → decode → detect (regex) → if uncertain → detect (judge)."""

    def __init__(self, config: dict = None):
        self._config = config or INJECTION_CONFIG
        self._preprocessors: List = []
        self._detectors: List[InjectionDetector] = []
        self._enabled = self._config.get("regex", {}).get("enabled", True)

    def add_preprocessor(self, preprocessor):
        """Add a text preprocessor (normalizer, decoder)."""
        self._preprocessors.append(preprocessor)

    def add_detector(self, detector: InjectionDetector):
        """Add a detector to the chain (regex first, then judge)."""
        self._detectors.append(detector)

    async def run(self, text: str) -> InjectionResult:
        """Run the full pipeline and return an InjectionResult."""
        if not self._enabled:
            return InjectionResult.allow("pipeline disabled")

        start = time.perf_counter()
        original = text

        try:
            # Step 1: Preprocess (normalize + decode)
            for pp in self._preprocessors:
                text = pp.normalize(text) if hasattr(pp, "normalize") else pp.decode(text)

            # Step 2: Run detectors in chain
            for detector in self._detectors:
                if not self._is_detector_enabled(detector.name):
                    continue
                result = await detector.detect(text)
                if result.detected:
                    if result.recommended_action in (Action.BLOCK, Action.BLOCK_AND_ALERT):
                        result.latency_ms = round((time.perf_counter() - start) * 1000, 2)
                        return result
                    return result  # FLAG or REDACT — still report but don't escalate

            # Step 3: No detector flagged — allow
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            if text != original:
                logger.debug("Text modified by preprocessors but no injection detected")
            return InjectionResult.allow(f"pipeline complete ({elapsed}ms)")

        except Exception as exc:
            logger.warning("Injection pipeline failed — fail-open: %s", exc)
            return InjectionResult.allow(f"pipeline error: {exc}")

    def _is_detector_enabled(self, name: str) -> bool:
        if name == "regex":
            return self._config.get("regex", {}).get("enabled", True)
        if name == "llm_judge":
            return self._config.get("llm_judge", {}).get("enabled", True)
        return True

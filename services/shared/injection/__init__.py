"""Injection Detection Package — graduated response system.

Architecture:
    InjectionPipeline (Facade)
        ├── TextNormalizer (Unicode NFKC)
        ├── EncodingDecoder (Base64 → Hex → ROT13 → URL)
        ├── RegexDetector (Chain handler, 95+ patterns)
        └── LlamaJudgeDetector (Chain handler, disputed cases only)

All detectors implement the InjectionDetector ABC.
Configuration is externalized to INJECTION_CONFIG in config.py.
"""

from .types import InjectionResult, Severity, Action
from .base import InjectionDetector
from .pipeline import InjectionPipeline
from .config import INJECTION_CONFIG

__all__ = [
    "InjectionResult",
    "Severity",
    "Action",
    "InjectionDetector",
    "InjectionPipeline",
    "INJECTION_CONFIG",
]

# Factory function — one-call setup
def create_injection_pipeline() -> "InjectionPipeline":
    """Create the production injection pipeline with all detectors."""
    from .normalizer import TextNormalizer
    from .encoding import EncodingDecoder
    from .regex_detector import RegexDetector

    pipeline = InjectionPipeline(config=INJECTION_CONFIG)
    pipeline.add_preprocessor(TextNormalizer())
    pipeline.add_preprocessor(EncodingDecoder())
    pipeline.add_detector(RegexDetector())

    # Llama judge is optional — only if Ollama is available
    try:
        from .llm_judge import LlamaJudgeDetector
        pipeline.add_detector(LlamaJudgeDetector())
    except (ImportError, OSError):
        pass

    return pipeline


# Singleton — initialized once at module load
_pipeline: "InjectionPipeline | None" = None


def get_pipeline() -> "InjectionPipeline":
    """Lazy-init the injection pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = create_injection_pipeline()
    return _pipeline
"""Safety Provider Interface — the abstract contract for all safety checks.

Every cloud-native and local safety implementation MUST implement this interface.
The core gateway calls ONLY these methods — never cloud-specific APIs directly.

Interfaces defined:
    - SafetyProvider (ABC) — the main abstract base class
    - SafetyProviderType (Enum) — capability flags
    - Result dataclasses: ToxicityResult, PIIResult, InjectionResult, 
      HallucinationResult, BiasResult
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Safety capability enumeration ───────────────────────────────────────────


class SafetyProviderType(Enum):
    """Each safety capability maps to a provider type.
    
    Used by ``SafetyProvider.get_capabilities()`` to advertise which
    checks a given provider implementation supports.
    """
    TOXICITY = "toxicity"
    PII_DETECTION = "pii_detection"
    PII_REDACTION = "pii_redaction"
    INJECTION = "injection"
    HALLUCINATION = "hallucination"
    BIAS = "bias"


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass
class ToxicityResult:
    """Result of a toxicity check.
    
    Attributes:
        toxic: Whether the text was flagged as toxic.
        score: Confidence score (0.0 to 1.0).
        categories: Specific toxicity categories detected (e.g. hate_speech, harassment).
        reason: Human-readable explanation for the flag.
        latency_ms: Time taken by the check in milliseconds.
    """
    toxic: bool
    score: float
    categories: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class PIIResult:
    """Result of a PII detection / redaction check.
    
    Attributes:
        detected: Whether any PII was found.
        types: Types of PII found (e.g. EMAIL, PHONE, SIN, CREDIT_CARD).
        redacted_text: The input text with PII masked (only populated 
                       when redaction is enabled).
        confidence: Overall confidence (0.0 to 1.0).
        latency_ms: Time taken by the check in milliseconds.
    """
    detected: bool
    types: List[str] = field(default_factory=list)
    redacted_text: Optional[str] = None
    confidence: float = 0.0
    latency_ms: float = 0.0


@dataclass
class InjectionResult:
    """Result of a prompt injection check.
    
    Attributes:
        detected: Whether injection was detected.
        score: Confidence score (0.0 to 1.0).
        patterns_matched: Names or IDs of patterns that matched.
        latency_ms: Time taken by the check in milliseconds.
    """
    detected: bool
    score: float
    patterns_matched: List[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass
class HallucinationResult:
    """Result of a hallucination / factual accuracy check.
    
    Attributes:
        hallucinated: Whether the text appears to be unsupported by the source.
        confidence: Confidence score (0.0 to 1.0).
        model_used: Name of the NLI / verification model used.
        evidence: Supporting evidence or reason for the verdict.
        latency_ms: Time taken by the check in milliseconds.
    """
    hallucinated: bool
    confidence: float
    model_used: str = ""
    evidence: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class BiasResult:
    """Result of a bias / fairness check.
    
    Attributes:
        biased: Whether biased content was detected.
        dimensions: Per-dimension bias scores (e.g. gender, race, religion).
        latency_ms: Time taken by the check in milliseconds.
    """
    biased: bool
    dimensions: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0


# ── Abstract Safety Provider ────────────────────────────────────────────────


class SafetyProvider(ABC):
    """Abstract base class for all safety providers.
    
    Every deployment (on-prem, AWS, Azure, GCP) provides a concrete
    implementation of this class.  The core gateway calls through this
    interface and never knows which cloud or model is backing the checks.
    
    Usage::
    
        from shared.provider_factory import create_safety_provider
        safety = create_safety_provider()  # Returns LocalSafetyProvider | AWSSafetyProvider | ...
        result = await safety.detect_toxicity("hello world")
    """

    # ── Toxicity ────────────────────────────────────────────────────────

    @abstractmethod
    async def detect_toxicity(
        self, text: str, context: Optional[dict] = None
    ) -> ToxicityResult:
        """Check text for toxic content.
        
        Args:
            text: The input text to scan.
            context: Optional metadata (user info, conversation history, etc.).
        
        Returns:
            ToxicityResult with verdict, score, and categories.
        """
        ...

    # ── PII ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def detect_pii(
        self, text: str, context: Optional[dict] = None
    ) -> PIIResult:
        """Detect PII entities in text.
        
        Args:
            text: The input text to scan.
            context: Optional metadata.
        
        Returns:
            PIIResult with detected flag and entity types.
        """
        ...

    @abstractmethod
    async def redact_pii(
        self, text: str, context: Optional[dict] = None
    ) -> PIIResult:
        """Detect AND redact PII in text.
        
        Args:
            text: The input text to scan and redact.
            context: Optional metadata.
        
        Returns:
            PIIResult with redacted_text populated.
        """
        ...

    # ── Injection ────────────────────────────────────────────────────────

    @abstractmethod
    async def detect_injection(
        self, text: str, context: Optional[dict] = None
    ) -> InjectionResult:
        """Check text for prompt injection attempts.
        
        Args:
            text: The input text to scan.
            context: Optional metadata.
        
        Returns:
            InjectionResult with verdict, score, and matched patterns.
        """
        ...

    # ── Hallucination ────────────────────────────────────────────────────

    @abstractmethod
    async def detect_hallucination(
        self, claim: str, source: Optional[str] = None
    ) -> HallucinationResult:
        """Check whether a claim is supported by a source.
        
        Args:
            claim: The text to verify (typically LLM output).
            source: Optional ground-truth context to verify against.
        
        Returns:
            HallucinationResult with verdict and confidence.
        """
        ...

    # ── Bias ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def check_bias(
        self, text: str, context: Optional[dict] = None
    ) -> BiasResult:
        """Check text for biased or unfair content.
        
        Args:
            text: The input text to evaluate.
            context: Optional metadata.
        
        Returns:
            BiasResult with verdict and per-dimension scores.
        """
        ...

    # ── Health & Capabilities ────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check whether the safety provider is operational.
        
        Returns:
            Dict with status and per-capability health.
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> Dict[SafetyProviderType, bool]:
        """Return which capabilities this provider supports.
        
        Some providers may not support every check (e.g. a cloud provider
        may lack bias detection).  The gateway uses this to decide which
        checks to skip.
        
        Returns:
            Mapping of SafetyProviderType → bool.
        """
        ...


# ── Provider configuration helper ──────────────────────────────────────────

@dataclass
class SafetyProviderConfig:
    """Configuration for a safety provider instance.
    
    Attributes:
        provider_type: 'local', 'aws', 'azure', or 'gcp'.
        region: Cloud region (AWS / GCP only).
        endpoint: Custom endpoint URL (Azure / on-prem).
        api_key: API key or credential reference.
        project_id: GCP project ID.
        models_dir: Path to local models directory.
        thresholds: Per-category confidence thresholds for flagging.
        enabled_checks: Explicit list of enabled check types.
    """
    provider_type: str = "local"
    region: str = ""
    endpoint: str = ""
    api_key: str = ""
    project_id: str = ""
    models_dir: str = ""
    thresholds: Dict[str, float] = field(default_factory=dict)
    enabled_checks: List[SafetyProviderType] = field(default_factory=list)
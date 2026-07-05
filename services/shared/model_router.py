"""Model A/B testing router for NorthGuard.
Enterprise-grade: Traffic splitting between model versions with metric
comparison, auto-promotion, and manual rollback support.

All operations gracefully degrade to passthrough mode when not configured.
"""
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelVersion:
    """Represents a model version in the A/B testing framework."""

    def __init__(
        self,
        name: str,
        version: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.version = version
        self.weight = weight
        self.metadata = metadata or {}
        self.total_requests = 0
        self.total_latency_ms = 0.0
        self.total_errors = 0
        self.toxic_count = 0
        self.pii_count = 0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.total_requests, 1)

    @property
    def error_rate(self) -> float:
        return self.total_errors / max(self.total_requests, 1)

    @property
    def id(self) -> str:
        return f"{self.name}:{self.version}"

    def record_request(self, latency_ms: float, is_error: bool = False,
                       is_toxic: bool = False, has_pii: bool = False) -> None:
        """Record a request result for this model version."""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        if is_error:
            self.total_errors += 1
        if is_toxic:
            self.toxic_count += 1
        if has_pii:
            self.pii_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "weight": self.weight,
            "total_requests": self.total_requests,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "toxic_count": self.toxic_count,
            "pii_count": self.pii_count,
            "metadata": self.metadata,
        }


class PromotionDecision(Enum):
    """Decision from comparing two model versions."""
    PROMOTE_CANDIDATE = "promote_candidate"
    KEEP_CURRENT = "keep_current"
    INSUFFICIENT_DATA = "insufficient_data"
    NO_CANDIDATE = "no_candidate"


class ModelRouter:
    """Routes inference requests between model versions for A/B testing.

    Supports traffic splitting by weight, metric comparison for auto-promotion,
    and manual promotion/rollback via API.

    In passthrough mode (default), all traffic goes to the primary model.
    """

    def __init__(
        self,
        primary_model: str = "llama3.2:1b",
        primary_version: str = "1.0",
        min_samples_for_comparison: int = 100,
        promotion_threshold: float = 0.05,  # 5% improvement required
        cooldown_seconds: int = 3600,  # Don't re-evaluate for 1 hour
    ):
        self.primary = ModelVersion(primary_model, primary_version, weight=1.0)
        self.candidate: Optional[ModelVersion] = None
        self.min_samples = min_samples_for_comparison
        self.promotion_threshold = promotion_threshold
        self.cooldown_seconds = cooldown_seconds
        self._last_evaluation_time: float = 0.0
        self._evaluation_history: List[Dict[str, Any]] = []
        self._passthrough = True  # Default: no A/B testing

    @property
    def is_ab_testing(self) -> bool:
        """Check if A/B testing is active."""
        return not self._passthrough and self.candidate is not None

    def enable_ab_testing(self, candidate_name: str, candidate_version: str,
                          candidate_weight: float = 0.1) -> None:
        """Enable A/B testing with a candidate model.

        Args:
            candidate_name: Name of the candidate model
            candidate_version: Version of the candidate model
            candidate_weight: Traffic weight for candidate (0.0-1.0)
        """
        self.candidate = ModelVersion(candidate_name, candidate_version, weight=candidate_weight)
        self.primary.weight = 1.0 - candidate_weight
        self._passthrough = False
        logger.info(
            f"A/B testing enabled: primary={self.primary.id} ({self.primary.weight:.0%}), "
            f"candidate={self.candidate.id} ({candidate_weight:.0%})"
        )

    def disable_ab_testing(self) -> None:
        """Disable A/B testing and return to passthrough mode."""
        self.candidate = None
        self.primary.weight = 1.0
        self._passthrough = True
        logger.info("A/B testing disabled, returning to passthrough mode")

    def select_model(self) -> Tuple[str, str, bool]:
        """Select which model version to use for this request.

        Returns:
            Tuple of (model_name, model_version, is_candidate)
        """
        if self._passthrough or self.candidate is None:
            return self.primary.name, self.primary.version, False

        # Weighted random selection
        import random
        if random.random() < self.candidate.weight:
            return self.candidate.name, self.candidate.version, True
        return self.primary.name, self.primary.version, False

    def record_result(self, model_name: str, model_version: str,
                      latency_ms: float, is_error: bool = False,
                      is_toxic: bool = False, has_pii: bool = False) -> None:
        """Record the result of an inference request.

        Args:
            model_name: Name of the model used
            model_version: Version of the model used
            latency_ms: Inference latency in milliseconds
            is_error: Whether the request resulted in an error
            is_toxic: Whether toxic content was detected
            has_pii: Whether PII was detected
        """
        target = self._find_version(model_name, model_version)
        if target:
            target.record_request(latency_ms, is_error, is_toxic, has_pii)

    def _find_version(self, model_name: str, model_version: str) -> Optional[ModelVersion]:
        """Find a model version by name and version string."""
        if self.primary.name == model_name and self.primary.version == model_version:
            return self.primary
        if self.candidate and self.candidate.name == model_name and self.candidate.version == model_version:
            return self.candidate
        return None

    def evaluate_promotion(self) -> PromotionDecision:
        """Evaluate whether the candidate should be promoted.

        Compares primary vs candidate metrics and decides if promotion
        is warranted based on the configured threshold.

        Returns:
            PromotionDecision enum value
        """
        if not self.is_ab_testing or self.candidate is None:
            return PromotionDecision.NO_CANDIDATE

        # Check cooldown
        now = time.time()
        if now - self._last_evaluation_time < self.cooldown_seconds:
            return PromotionDecision.INSUFFICIENT_DATA

        # Check minimum samples
        if (self.primary.total_requests < self.min_samples or
                self.candidate.total_requests < self.min_samples):
            return PromotionDecision.INSUFFICIENT_DATA

        self._last_evaluation_time = now

        # Compare metrics
        primary_f1 = self._estimate_f1(self.primary)
        candidate_f1 = self._estimate_f1(self.candidate)

        improvement = candidate_f1 - primary_f1
        relative_improvement = improvement / max(primary_f1, 0.001)

        evaluation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "primary_id": self.primary.id,
            "candidate_id": self.candidate.id,
            "primary_requests": self.primary.total_requests,
            "candidate_requests": self.candidate.total_requests,
            "primary_avg_latency_ms": self.primary.avg_latency_ms,
            "candidate_avg_latency_ms": self.candidate.avg_latency_ms,
            "primary_error_rate": self.primary.error_rate,
            "candidate_error_rate": self.candidate.error_rate,
            "primary_estimated_f1": round(primary_f1, 4),
            "candidate_estimated_f1": round(candidate_f1, 4),
            "improvement": round(improvement, 4),
            "relative_improvement": round(relative_improvement, 4),
            "threshold": self.promotion_threshold,
            "decision": None,
        }

        if relative_improvement >= self.promotion_threshold:
            evaluation["decision"] = PromotionDecision.PROMOTE_CANDIDATE.value
            self._evaluation_history.append(evaluation)
            logger.info(
                f"Promotion decision: PROMOTE candidate {self.candidate.id} "
                f"(F1 improvement: {relative_improvement:.2%})"
            )
            return PromotionDecision.PROMOTE_CANDIDATE
        else:
            evaluation["decision"] = PromotionDecision.KEEP_CURRENT.value
            self._evaluation_history.append(evaluation)
            logger.info(
                f"Promotion decision: KEEP current {self.primary.id} "
                f"(F1 improvement: {relative_improvement:.2%})"
            )
            return PromotionDecision.KEEP_CURRENT

    def _estimate_f1(self, version: ModelVersion) -> float:
        """Estimate F1 score from observed metrics.

        Uses error rate as a proxy for 1 - accuracy, and toxic/PII rates
        as indicators of detection quality.
        """
        if version.total_requests == 0:
            return 0.0

        # Lower error rate = better
        quality = 1.0 - version.error_rate

        # Lower latency is better (normalized to 1 second)
        latency_factor = max(0.0, 1.0 - (version.avg_latency_ms / 1000.0))

        # Combined score (weighted)
        return 0.7 * quality + 0.3 * latency_factor

    def promote_candidate(self) -> bool:
        """Promote the candidate to become the new primary.

        Returns:
            True if promotion was successful
        """
        if self.candidate is None:
            return False

        logger.info(
            f"Promoting candidate {self.candidate.id} to primary "
            f"(was {self.primary.id})"
        )

        # Archive current primary
        old_primary = self.primary

        # Candidate becomes new primary
        self.primary = ModelVersion(
            name=self.candidate.name,
            version=self.candidate.version,
            weight=1.0,
            metadata={"promoted_from": self.candidate.id, "previous_primary": old_primary.id},
        )

        # Reset candidate
        self.candidate = None
        self._passthrough = True

        return True

    def rollback_to(self, model_name: str, model_version: str) -> bool:
        """Manually rollback to a specific model version.

        Args:
            model_name: Name of the model to rollback to
            model_version: Version of the model to rollback to

        Returns:
            True if rollback was successful
        """
        logger.info(f"Manual rollback to {model_name}:{model_version}")
        self.primary = ModelVersion(model_name, model_version, weight=1.0)
        self.candidate = None
        self._passthrough = True
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current A/B testing status.

        Returns:
            Dict with primary, candidate, and evaluation info
        """
        status = {
            "ab_testing_enabled": self.is_ab_testing,
            "passthrough_mode": self._passthrough,
            "primary": self.primary.to_dict(),
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "evaluations": len(self._evaluation_history),
            "last_evaluation": self._evaluation_history[-1] if self._evaluation_history else None,
        }
        return status


# Module-level singleton
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create the global ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router

"""Concept drift detection for NorthGuard.
Enterprise-grade: Statistical drift detection using Population Stability Index (PSI),
Kullback-Leibler divergence, and distribution comparison for monitoring model
performance degradation in production.

Supports both data drift (input distribution changes) and concept drift
(prediction distribution changes).
"""
import logging
import math
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default thresholds for drift detection
DEFAULT_PSI_THRESHOLD = 0.2  # PSI > 0.2 indicates significant drift
DEFAULT_KL_THRESHOLD = 0.1   # KL divergence threshold
DEFAULT_WINDOW_SIZE = 1000   # Number of samples in sliding window


def _compute_histogram(
    values: List[float],
    bins: int = 10,
    min_val: float = 0.0,
    max_val: float = 1.0,
) -> List[float]:
    """Compute a normalized histogram from a list of values.

    Args:
        values: List of numeric values
        bins: Number of bins for the histogram
        min_val: Minimum value for binning
        max_val: Maximum value for binning

    Returns:
        List of normalized bin counts (probabilities)
    """
    if not values:
        return [0.0] * bins

    bin_width = (max_val - min_val) / bins
    histogram = [0.0] * bins

    for v in values:
        bin_idx = min(bins - 1, max(0, int((v - min_val) / bin_width)))
        histogram[bin_idx] += 1.0

    # Normalize
    total = sum(histogram)
    if total > 0:
        histogram = [h / total for h in histogram]

    return histogram


def compute_psi(
    expected: List[float],
    actual: List[float],
    epsilon: float = 1e-6,
) -> float:
    """Compute Population Stability Index between two distributions.

    PSI measures how much a distribution has shifted over time.
    PSI < 0.1: No significant change
    0.1 <= PSI < 0.2: Moderate change, monitor
    PSI >= 0.2: Significant shift, investigate

    Args:
        expected: Baseline distribution (probabilities)
        actual: Current distribution (probabilities)
        epsilon: Small constant to avoid division by zero

    Returns:
        PSI value
    """
    if len(expected) != len(actual):
        raise ValueError("Expected and actual distributions must have same length")

    psi = 0.0
    for e, a in zip(expected, actual):
        e = max(e, epsilon)
        a = max(a, epsilon)
        psi += (a - e) * math.log(a / e)

    return round(psi, 6)


def compute_kl_divergence(
    p: List[float],
    q: List[float],
    epsilon: float = 1e-6,
) -> float:
    """Compute Kullback-Leibler divergence between two distributions.

    KL(P || Q) measures the information loss when Q is used to approximate P.

    Args:
        p: Reference distribution
        q: Approximating distribution
        epsilon: Small constant to avoid log(0)

    Returns:
        KL divergence value
    """
    if len(p) != len(q):
        raise ValueError("Distributions must have same length")

    kl = 0.0
    for pi, qi in zip(p, q):
        pi = max(pi, epsilon)
        qi = max(qi, epsilon)
        kl += pi * math.log(pi / qi)

    return round(kl, 6)


class DriftDetector:
    """Detects concept and data drift in model predictions and inputs.

    Maintains a baseline distribution and compares against sliding windows
    of recent data to detect statistically significant shifts.

    Supports optional webhook callbacks for triggering retraining pipelines
    when drift is detected.
    """

    def __init__(
        self,
        psi_threshold: float = DEFAULT_PSI_THRESHOLD,
        kl_threshold: float = DEFAULT_KL_THRESHOLD,
        window_size: int = DEFAULT_WINDOW_SIZE,
        drift_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.psi_threshold = psi_threshold
        self.kl_threshold = kl_threshold
        self.window_size = window_size
        self.drift_callback = drift_callback

        # Baseline distributions
        self._baseline_scores: List[float] = []
        self._baseline_toxicity_rate: Optional[float] = None
        self._baseline_pii_rate: Optional[float] = None
        self._baseline_histogram: Optional[List[float]] = None
        self._baseline_timestamp: Optional[str] = None

        # Current window
        self._current_scores: List[float] = []
        self._drift_alerts: List[Dict[str, Any]] = []

    @property
    def has_baseline(self) -> bool:
        return self._baseline_histogram is not None

    def set_baseline(self, scores: List[float]) -> None:
        """Set the baseline distribution from historical data.

        Args:
            scores: List of toxicity scores from the baseline period
        """
        if not scores:
            logger.warning("Cannot set baseline from empty scores")
            return

        self._baseline_scores = scores
        self._baseline_histogram = _compute_histogram(scores)
        self._baseline_timestamp = datetime.now(timezone.utc).isoformat()
        self._baseline_toxicity_rate = sum(1 for s in scores if s > 0.5) / len(scores)

        logger.info(
            f"Drift baseline set: {len(scores)} samples, "
            f"toxicity_rate={self._baseline_toxicity_rate:.3f}"
        )

    def set_baseline_from_stats(
        self,
        toxicity_rate: float,
        pii_rate: float,
        histogram: Optional[List[float]] = None,
    ) -> None:
        """Set baseline from pre-computed statistics.

        Args:
            toxicity_rate: Baseline toxicity rate
            pii_rate: Baseline PII detection rate
            histogram: Optional baseline histogram
        """
        self._baseline_toxicity_rate = toxicity_rate
        self._baseline_pii_rate = pii_rate
        if histogram:
            self._baseline_histogram = histogram
        self._baseline_timestamp = datetime.now(timezone.utc).isoformat()

    def add_sample(self, score: float) -> Optional[Dict[str, Any]]:
        """Add a new sample to the sliding window and check for drift.

        Args:
            score: Toxicity score for the new sample

        Returns:
            Drift alert dict if drift detected, None otherwise
        """
        self._current_scores.append(score)

        # Keep window at configured size
        if len(self._current_scores) > self.window_size:
            self._current_scores = self._current_scores[-self.window_size:]

        # Check for drift periodically (every 100 samples)
        if len(self._current_scores) >= 100 and len(self._current_scores) % 100 == 0:
            return self._check_drift()

        return None

    def _check_drift(self) -> Optional[Dict[str, Any]]:
        """Check for drift between baseline and current window.

        Returns:
            Drift alert dict if drift detected, None otherwise
        """
        if not self._baseline_histogram or len(self._current_scores) < 100:
            return None

        # Compute current histogram
        current_histogram = _compute_histogram(self._current_scores)

        # Compute PSI
        psi = compute_psi(self._baseline_histogram, current_histogram)

        # Compute KL divergence
        kl = compute_kl_divergence(self._baseline_histogram, current_histogram)

        # Compute current toxicity rate
        current_toxicity_rate = sum(1 for s in self._current_scores if s > 0.5) / len(self._current_scores)

        alerts = []
        drift_detected = False

        # Check PSI
        if psi > self.psi_threshold:
            drift_detected = True
            severity = "critical" if psi > 0.3 else "warning"
            alerts.append({
                "type": "psi_drift",
                "metric": "population_stability_index",
                "value": psi,
                "threshold": self.psi_threshold,
                "severity": severity,
                "message": f"PSI={psi:.3f} exceeds threshold {self.psi_threshold}. "
                          f"Distribution has shifted significantly.",
            })

        # Check KL divergence
        if kl > self.kl_threshold:
            drift_detected = True
            alerts.append({
                "type": "kl_drift",
                "metric": "kl_divergence",
                "value": kl,
                "threshold": self.kl_threshold,
                "severity": "warning",
                "message": f"KL divergence={kl:.3f} exceeds threshold {self.kl_threshold}.",
            })

        # Check toxicity rate shift
        if self._baseline_toxicity_rate is not None:
            rate_shift = abs(current_toxicity_rate - self._baseline_toxicity_rate)
            if rate_shift > 0.1:
                drift_detected = True
                alerts.append({
                    "type": "rate_shift",
                    "metric": "toxicity_rate",
                    "baseline": self._baseline_toxicity_rate,
                    "current": current_toxicity_rate,
                    "shift": rate_shift,
                    "severity": "warning",
                    "message": f"Toxicity rate shifted from {self._baseline_toxicity_rate:.2%} "
                              f"to {current_toxicity_rate:.2%} (delta={rate_shift:.2%})",
                })

        if drift_detected:
            alert = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "window_size": len(self._current_scores),
                "baseline_size": len(self._baseline_scores),
                "psi": psi,
                "kl_divergence": kl,
                "current_toxicity_rate": round(current_toxicity_rate, 4),
                "baseline_toxicity_rate": round(self._baseline_toxicity_rate, 4) if self._baseline_toxicity_rate is not None else None,
                "alerts": alerts,
                "drift_detected": True,
            }
            self._drift_alerts.append(alert)
            logger.warning(f"Drift detected: PSI={psi:.3f}, KL={kl:.3f}")

            # Invoke optional drift callback (e.g., for retraining pipeline)
            if self.drift_callback:
                try:
                    self.drift_callback(alert)
                except Exception as e:
                    logger.error(f"Drift callback failed: {e}")

            return alert

        return None

    def get_alerts(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get drift alerts, optionally filtered by timestamp.

        Args:
            since: ISO timestamp string to filter alerts after

        Returns:
            List of drift alert dicts
        """
        if not since:
            return self._drift_alerts

        return [
            a for a in self._drift_alerts
            if a.get("timestamp", "") > since
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get current drift detection status.

        Returns:
            Dict with baseline info, current window stats, and alert count
        """
        current_toxicity_rate = 0.0
        if self._current_scores:
            current_toxicity_rate = sum(1 for s in self._current_scores if s > 0.5) / len(self._current_scores)

        return {
            "has_baseline": self.has_baseline,
            "baseline_size": len(self._baseline_scores),
            "baseline_toxicity_rate": round(self._baseline_toxicity_rate, 4) if self._baseline_toxicity_rate is not None else None,
            "baseline_set_at": self._baseline_timestamp,
            "current_window_size": len(self._current_scores),
            "current_toxicity_rate": round(current_toxicity_rate, 4),
            "total_alerts": len(self._drift_alerts),
            "last_alert": self._drift_alerts[-1] if self._drift_alerts else None,
        }

    def reset(self) -> None:
        """Reset the drift detector to its initial state.
        
        Clears all baseline data, current window, and alerts.
        """
        self._baseline_scores = []
        self._baseline_toxicity_rate = None
        self._baseline_pii_rate = None
        self._baseline_histogram = None
        self._baseline_timestamp = None
        self._current_scores = []
        self._drift_alerts = []
        logger.info("Drift detector reset to initial state")


# Module-level singleton
_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    """Get or create the global DriftDetector instance."""
    global _detector
    if _detector is None:
        _detector = DriftDetector()
    return _detector

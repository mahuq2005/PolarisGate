"""Standardized metrics computation for all PolarisGate accuracy tests.

Provides a single source of truth for precision, recall, F1, specificity,
false-positive rate, false-negative rate, confusion matrices, calibration
curves, and performance metrics across toxicity, PII, hallucination, and
injection-detection gates.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConfusionMatrix:
    """Holds raw confusion-matrix counts."""

    true_positive: int = 0
    true_negative: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def total(self) -> int:
        return self.true_positive + self.true_negative + self.false_positive + self.false_negative

    @property
    def support_positive(self) -> int:
        return self.true_positive + self.false_negative

    @property
    def support_negative(self) -> int:
        return self.true_negative + self.false_positive

    def to_dict(self) -> Dict[str, int]:
        return {
            "true_positive": self.true_positive,
            "true_negative": self.true_negative,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
        }


@dataclass
class GateMetrics:
    """Classification metrics for a single gate."""

    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0
    specificity: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    confusion_matrix: ConfusionMatrix = field(default_factory=ConfusionMatrix)
    support: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy": self.accuracy,
            "specificity": self.specificity,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
            "confusion_matrix": self.confusion_matrix.to_dict(),
            "support": self.support,
        }


@dataclass
class PerformanceMetrics:
    """Latency / throughput statistics."""

    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    latency_mean_ms: float = 0.0
    latency_stddev_ms: float = 0.0
    throughput_req_per_sec: float = 0.0
    total_requests: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "latency_mean_ms": self.latency_mean_ms,
            "latency_stddev_ms": self.latency_stddev_ms,
            "throughput_req_per_sec": self.throughput_req_per_sec,
            "total_requests": self.total_requests,
        }


# ---------------------------------------------------------------------------
# Core metrics computation
# ---------------------------------------------------------------------------

class MetricsEngine:
    """Computes classification and performance metrics from raw predictions.

    Usage::

        engine = MetricsEngine()
        result = engine.compute_classification(y_true, y_pred)
        print(result.to_dict())
        perf = engine.compute_performance(latencies_ms, total_duration_sec)
        print(perf.to_dict())
    """

    # ---- classification ---------------------------------------------------

    @staticmethod
    def compute_confusion_matrix(
        y_true: Sequence[int], y_pred: Sequence[int]
    ) -> ConfusionMatrix:
        """Return a :class:`ConfusionMatrix` from binary label lists.

        Labels are expected to be 0 (negative) / 1 (positive).
        """
        cm = ConfusionMatrix()
        for t, p in zip(y_true, y_pred):
            if t == 1 and p == 1:
                cm.true_positive += 1
            elif t == 1 and p == 0:
                cm.false_negative += 1
            elif t == 0 and p == 1:
                cm.false_positive += 1
            elif t == 0 and p == 0:
                cm.true_negative += 1
        return cm

    @staticmethod
    def compute_classification(
        y_true: Sequence[int],
        y_pred: Sequence[int],
        labels: Optional[Dict[int, str]] = None,
    ) -> GateMetrics:
        """Compute full classification metrics.

        Parameters
        ----------
        y_true : Sequence[int]
            Ground-truth binary labels (0/1).
        y_pred : Sequence[int]
            Predicted binary labels (0/1).
        labels : Optional[Dict[int, str]]
            Optional mapping ``{0: "clean", 1: "toxic"}`` for support counts.

        Returns
        -------
        GateMetrics
        """
        cm = MetricsEngine.compute_confusion_matrix(y_true, y_pred)

        tp, tn, fp, fn = (
            cm.true_positive,
            cm.true_negative,
            cm.false_positive,
            cm.false_negative,
        )

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            (2 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        accuracy = (tp + tn) / cm.total if cm.total > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fn_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        support: Dict[str, int] = {}
        if labels:
            for k, v in labels.items():
                count = sum(1 for y in y_true if y == k)
                support[str(v)] = count
        else:
            support["positive"] = cm.support_positive
            support["negative"] = cm.support_negative

        return GateMetrics(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            accuracy=round(accuracy, 4),
            specificity=round(specificity, 4),
            false_positive_rate=round(fp_rate, 4),
            false_negative_rate=round(fn_rate, 4),
            confusion_matrix=cm,
            support=support,
        )

    @staticmethod
    def compute_per_class_metrics(
        y_true: Sequence[int],
        y_pred: Sequence[int],
        class_names: List[str],
    ) -> Dict[str, GateMetrics]:
        """Compute per-class metrics treating each class as one-vs-rest.

        Parameters
        ----------
        y_true : Sequence[int]
            Ground-truth class indices.
        y_pred : Sequence[int]
            Predicted class indices.
        class_names : List[str]
            Human-readable class names (e.g. ``["SSN", "EMAIL", "PHONE"]``).

        Returns
        -------
        Dict[str, GateMetrics]
            Mapping of class name → metrics.
        """
        unique = sorted(set(y_true) | set(y_pred))
        results: Dict[str, GateMetrics] = {}
        for cls_idx in unique:
            name = class_names[cls_idx] if cls_idx < len(class_names) else f"class_{cls_idx}"
            yt = [1 if y == cls_idx else 0 for y in y_true]
            yp = [1 if y == cls_idx else 0 for y in y_pred]
            results[name] = MetricsEngine.compute_classification(yt, yp)
        return results

    @staticmethod
    def compute_calibration_curve(
        y_true: Sequence[int],
        scores: Sequence[float],
        bins: int = 10,
    ) -> Dict[str, Any]:
        """Compute calibration curve data (expected vs. observed).

        Returns
        -------
        dict
            Keys: ``bins`` (list of bin centres), ``observed`` (list of
            observed positive fractions), ``counts`` (list of bin counts),
            ``brier_score`` (float).
        """
        if len(y_true) == 0:
            return {"bins": [], "observed": [], "counts": [], "brier_score": 0.0}

        y_true_arr = np.asarray(y_true, dtype=np.float64)
        scores_arr = np.asarray(scores, dtype=np.float64)

        # Brier score
        brier = float(np.mean((scores_arr - y_true_arr) ** 2))

        bin_edges = np.linspace(0.0, 1.0, bins + 1)
        bin_centres: List[float] = []
        observed: List[float] = []
        counts: List[int] = []

        for i in range(bins):
            mask = (scores_arr >= bin_edges[i]) & (scores_arr < bin_edges[i + 1])
            # ensure the last bin includes 1.0
            if i == bins - 1:
                mask = (scores_arr >= bin_edges[i]) & (scores_arr <= bin_edges[i + 1])
            n = int(np.sum(mask))
            counts.append(n)
            bin_centres.append(round(float((bin_edges[i] + bin_edges[i + 1]) / 2), 3))
            observed.append(
                round(float(np.mean(y_true_arr[mask])), 4) if n > 0 else 0.0
            )

        return {
            "bins": bin_centres,
            "observed": observed,
            "counts": counts,
            "brier_score": round(brier, 4),
        }

    # ---- performance ------------------------------------------------------

    @staticmethod
    def compute_performance(
        latencies_ms: Sequence[float],
        total_duration_sec: float,
    ) -> PerformanceMetrics:
        """Compute latency / throughput metrics.

        Parameters
        ----------
        latencies_ms : Sequence[float]
            List of per-request latency values (milliseconds).
        total_duration_sec : float
            Wall-clock duration of the benchmark run (seconds).

        Returns
        -------
        PerformanceMetrics
        """
        arr = np.asarray(latencies_ms, dtype=np.float64)
        n = len(arr)

        if n == 0:
            return PerformanceMetrics()

        return PerformanceMetrics(
            latency_p50_ms=round(float(np.percentile(arr, 50)), 2),
            latency_p95_ms=round(float(np.percentile(arr, 95)), 2),
            latency_p99_ms=round(float(np.percentile(arr, 99)), 2),
            latency_mean_ms=round(float(np.mean(arr)), 2),
            latency_stddev_ms=round(float(np.std(arr)), 2),
            throughput_req_per_sec=round(n / total_duration_sec, 2) if total_duration_sec > 0 else 0.0,
            total_requests=n,
        )

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def agreement_rate(
        predictions: Sequence[Sequence[int]],
    ) -> Dict[str, Any]:
        """Compute pair-wise and full agreement rates across multiple
        classifier predictions.

        Parameters
        ----------
        predictions : Sequence[Sequence[int]]
            List of prediction lists, one per classifier.
            e.g. ``[[0,1,0,...], [0,1,1,...], [0,0,0,...]]``

        Returns
        -------
        dict
            ``full_agreement`` (float), ``pairwise`` (Dict[str,float]).
        """
        preds = [np.asarray(p, dtype=np.int64) for p in predictions]
        n_classifiers = len(preds)
        n_samples = len(preds[0]) if preds else 0

        if n_samples == 0:
            return {"full_agreement": 0.0, "pairwise": {}}

        # Full agreement: all classifiers agree
        stacked = np.stack(preds, axis=0)  # (n_classifiers, n_samples)
        full_agree = float(np.mean(np.all(stacked == stacked[0, :], axis=0)))

        pairwise: Dict[str, float] = {}
        for i in range(n_classifiers):
            for j in range(i + 1, n_classifiers):
                key = f"c{i}_c{j}"
                pairwise[key] = float(np.mean(preds[i] == preds[j]))

        return {"full_agreement": round(full_agree, 4), "pairwise": pairwise}


# ---------------------------------------------------------------------------
# Convenience top-level functions
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: Optional[Dict[int, str]] = None,
) -> GateMetrics:
    """Shorthand for ``MetricsEngine.compute_classification``."""
    return MetricsEngine.compute_classification(y_true, y_pred, labels)


def compute_confusion(y_true: Sequence[int], y_pred: Sequence[int]) -> ConfusionMatrix:
    """Shorthand for ``MetricsEngine.compute_confusion_matrix``."""
    return MetricsEngine.compute_confusion_matrix(y_true, y_pred)


def compute_calibration(
    y_true: Sequence[int], scores: Sequence[float], bins: int = 10
) -> Dict[str, Any]:
    """Shorthand for ``MetricsEngine.compute_calibration_curve``."""
    return MetricsEngine.compute_calibration_curve(y_true, scores, bins)


def compute_performance(
    latencies_ms: Sequence[float], total_duration_sec: float
) -> PerformanceMetrics:
    """Shorthand for ``MetricsEngine.compute_performance``."""
    return MetricsEngine.compute_performance(latencies_ms, total_duration_sec)
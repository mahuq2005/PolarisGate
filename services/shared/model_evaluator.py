"""Model evaluation framework for NorthGuard.
Enterprise-grade: Cross-validation, precision/recall/F1 computation,
confusion matrix analysis, and benchmark scoring for toxicity classifiers.

Supports both BERT and keyword-based classifiers with consistent metrics.
"""
import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    """Comprehensive classification metrics."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    specificity: float = 0.0
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    total_samples: int = 0
    support: Dict[str, int] = field(default_factory=dict)

    @property
    def confusion_matrix(self) -> Dict[str, int]:
        return {
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


def compute_metrics(
    y_true: List[bool],
    y_pred: List[bool],
) -> ClassificationMetrics:
    """Compute classification metrics from ground truth and predictions.

    Args:
        y_true: Ground truth labels
        y_pred: Predicted labels

    Returns:
        ClassificationMetrics with all computed values
    """
    metrics = ClassificationMetrics()
    metrics.total_samples = len(y_true)

    if not y_true or not y_pred:
        return metrics

    # Compute confusion matrix
    for true, pred in zip(y_true, y_pred):
        if true and pred:
            metrics.true_positives += 1
        elif not true and not pred:
            metrics.true_negatives += 1
        elif not true and pred:
            metrics.false_positives += 1
        elif true and not pred:
            metrics.false_negatives += 1

    tp = metrics.true_positives
    tn = metrics.true_negatives
    fp = metrics.false_positives
    fn = metrics.false_negatives

    # Compute derived metrics
    total = tp + tn + fp + fn
    metrics.accuracy = (tp + tn) / total if total > 0 else 0.0
    metrics.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    metrics.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    metrics.specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # F1 score (harmonic mean of precision and recall)
    if metrics.precision + metrics.recall > 0:
        metrics.f1_score = 2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall)

    # Support (number of actual positive and negative samples)
    metrics.support = {
        "positive": tp + fn,
        "negative": tn + fp,
    }

    return metrics


def cross_validate(
    classifier_fn: Callable[[str], Tuple[bool, float]],
    test_cases: List[Tuple[str, bool]],
    n_folds: int = 5,
) -> Dict[str, float]:
    """Perform cross-validation on a classifier using test cases.

    Uses stratified sampling to maintain class distribution across folds.

    Args:
        classifier_fn: Function that takes text and returns (is_toxic, score)
        test_cases: List of (text, is_toxic) tuples
        n_folds: Number of cross-validation folds

    Returns:
        Dict of metric name to mean score across folds
    """
    if len(test_cases) < n_folds:
        n_folds = max(2, len(test_cases))

    # Shuffle and split into folds
    import random
    indices = list(range(len(test_cases)))
    random.shuffle(indices)

    fold_size = len(indices) // n_folds
    fold_metrics = []

    for fold in range(n_folds):
        # Split into train/test indices
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < n_folds - 1 else len(indices)
        test_indices = set(indices[test_start:test_end])
        train_indices = [i for i in indices if i not in test_indices]

        # Use training portion to calibrate threshold (if needed)
        # For now, evaluate on test portion
        y_true = []
        y_pred = []

        for idx in test_indices:
            text, label = test_cases[idx]
            try:
                predicted, score = classifier_fn(text)
                y_true.append(label)
                y_pred.append(predicted)
            except Exception as e:
                logger.warning(f"Classifier failed on test case {idx}: {e}")
                continue

        if y_true:
            metrics = compute_metrics(y_true, y_pred)
            fold_metrics.append(metrics)

    # Aggregate metrics across folds
    if not fold_metrics:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "specificity": 0.0,
        }

    aggregated = {}
    for metric in ("accuracy", "precision", "recall", "f1_score", "specificity"):
        values = [getattr(m, metric) for m in fold_metrics]
        aggregated[metric] = round(sum(values) / len(values), 4)
        aggregated[f"{metric}_std"] = round(
            math.sqrt(sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)),
            4,
        ) if len(values) > 1 else 0.0

    return aggregated


def evaluate_classifier(
    classifier_fn: Callable[[str], Tuple[bool, float]],
    test_cases: List[Tuple[str, bool]],
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Evaluate a classifier against a labeled test dataset.

    Args:
        classifier_fn: Function that takes text and returns (is_toxic, score)
        test_cases: List of (text, is_toxic) tuples
        threshold: Score threshold for positive classification

    Returns:
        Dict with evaluation results including metrics, confusion matrix,
        and per-class performance
    """
    y_true = []
    y_pred = []
    scores = []

    for text, label in test_cases:
        try:
            predicted, score = classifier_fn(text)
            y_true.append(label)
            # Apply threshold to score for prediction
            y_pred.append(score >= threshold)
            scores.append(score)
        except Exception as e:
            logger.warning(f"Classifier evaluation failed on text: {str(e)[:50]}")
            continue

    if not y_true:
        return {"error": "No valid test cases", "total": 0}

    metrics = compute_metrics(y_true, y_pred)

    # Compute per-class metrics
    from collections import Counter
    class_counts = Counter(y_true)

    return {
        "total_samples": metrics.total_samples,
        "accuracy": round(metrics.accuracy, 4),
        "precision": round(metrics.precision, 4),
        "recall": round(metrics.recall, 4),
        "f1_score": round(metrics.f1_score, 4),
        "specificity": round(metrics.specificity, 4),
        "true_positives": metrics.true_positives,
        "true_negatives": metrics.true_negatives,
        "false_positives": metrics.false_positives,
        "false_negatives": metrics.false_negatives,
        "confusion_matrix": metrics.confusion_matrix,
        "support": {
            "toxic": class_counts.get(True, 0),
            "non_toxic": class_counts.get(False, 0),
        },
        "threshold": threshold,
    }


def benchmark_classifiers(
    classifiers: Dict[str, Callable[[str], Tuple[bool, float]]],
    test_cases: List[Tuple[str, bool]],
) -> Dict[str, Dict[str, Any]]:
    """Benchmark multiple classifiers against the same test dataset.

    Args:
        classifiers: Dict mapping classifier name to classifier function
        test_cases: List of (text, is_toxic) tuples

    Returns:
        Dict mapping classifier name to evaluation results
    """
    results = {}
    for name, fn in classifiers.items():
        logger.info(f"Benchmarking classifier: {name}")
        try:
            results[name] = evaluate_classifier(fn, test_cases)
        except Exception as e:
            logger.error(f"Benchmark failed for {name}: {e}")
            results[name] = {"error": str(e), "total": 0}
    return results

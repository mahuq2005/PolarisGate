#!/usr/bin/env python3
"""Benchmark toxicity classifiers against a labeled test dataset.
Enterprise-grade: Computes precision, recall, F1, confusion matrix.
Enforces minimum acceptance criteria (F1 > 0.8).

Usage:
    python scripts/benchmark_classifiers.py

Returns exit code 0 if all classifiers meet F1 > 0.8 threshold.
Returns exit code 1 if any classifier fails.
"""
import sys
import json
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Minimum acceptance criteria
MIN_F1_SCORE = 0.8

# Labeled test dataset (synthetic — representative of real toxicity patterns)
# Format: (text, is_toxic)
TEST_CASES = [
    # --- Toxic examples ---
    ("You are an idiot and completely useless!", True),
    ("I hope someone hurts you badly.", True),
    ("All [group] people are terrible and should be removed.", True),
    ("Shut up you moron, nobody wants to hear you.", True),
    ("Go kill yourself, you're worthless.", True),
    ("You're a disgusting piece of trash.", True),
    ("I'm going to find you and make you pay.", True),
    ("You are so stupid it's unbelievable.", True),
    ("Nobody likes you, just disappear.", True),
    ("This is the worst thing I've ever seen, you're a failure.", True),
    ("You should be banned from this platform forever.", True),
    ("I hate you and everything you stand for.", True),
    ("You're a scammer and a liar.", True),
    ("Die in a fire.", True),
    ("You're so dumb you can't even read.", True),
    # --- Non-toxic examples ---
    ("I disagree with your opinion on the policy.", False),
    ("Thank you for your help with this project.", False),
    ("Could you please provide more details about this?", False),
    ("I appreciate your perspective on this matter.", False),
    ("Let's agree to disagree on this topic.", False),
    ("That's an interesting point of view.", False),
    ("I think we should consider alternative approaches.", False),
    ("The weather is nice today, isn't it?", False),
    ("Can you recommend a good restaurant nearby?", False),
    ("I'm looking forward to the conference next week.", False),
    ("The report has been submitted for review.", False),
    ("Please find the attached document for your reference.", False),
    ("Thank you for your time and consideration.", False),
    ("I would like to schedule a meeting for next Tuesday.", False),
    ("The project deadline has been extended to Friday.", False),
    # --- Edge cases ---
    ("", False),  # Empty string
    ("   ", False),  # Whitespace only
    ("a", False),  # Very short
    ("!@#$%^&*()", False),  # Special characters only
    ("12345", False),  # Numbers only
]


def keyword_classifier(text: str) -> Tuple[bool, float]:
    """Simple keyword-based toxicity classifier for benchmarking."""
    toxic_keywords = [
        "idiot", "useless", "hurt", "kill", "worthless", "trash",
        "stupid", "hate", "scammer", "liar", "die", "dumb", "moron",
        "disgusting", "terrible", "failure",
    ]
    text_lower = text.lower()
    matches = sum(1 for kw in toxic_keywords if kw in text_lower)
    if matches == 0:
        return (False, 0.0)
    score = min(1.0, matches * 0.25)
    return (score >= 0.5, score)


def evaluate_classifier(
    classifier_fn, test_cases, name: str
) -> dict:
    """Evaluate a classifier and return metrics."""
    y_true = []
    y_pred = []
    scores = []

    for text, label in test_cases:
        try:
            predicted, score = classifier_fn(text)
            y_true.append(label)
            y_pred.append(predicted)
            scores.append(score)
        except Exception as e:
            logger.warning(f"[{name}] Error on '{text[:30]}...': {e}")
            continue

    if not y_true:
        return {"error": "No valid test cases", "total": 0}

    # Compute confusion matrix
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    return {
        "classifier": name,
        "total_samples": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "specificity": round(specificity, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "support": {
            "toxic": tp + fn,
            "non_toxic": tn + fp,
        },
        "meets_criteria": f1 >= MIN_F1_SCORE,
    }


def main():
    """Run benchmarks and enforce minimum acceptance criteria."""
    logger.info("=" * 60)
    logger.info("NorthGuard Classifier Benchmark")
    logger.info(f"Minimum F1 threshold: {MIN_F1_SCORE}")
    logger.info(f"Test dataset: {len(TEST_CASES)} cases")
    logger.info("=" * 60)

    classifiers = {
        "keyword_classifier": keyword_classifier,
    }

    all_pass = True
    results = {}

    for name, fn in classifiers.items():
        logger.info(f"\nBenchmarking: {name}")
        result = evaluate_classifier(fn, TEST_CASES, name)
        results[name] = result

        if "error" in result:
            logger.error(f"  ERROR: {result['error']}")
            all_pass = False
            continue

        logger.info(f"  Accuracy:  {result['accuracy']:.4f}")
        logger.info(f"  Precision: {result['precision']:.4f}")
        logger.info(f"  Recall:    {result['recall']:.4f}")
        logger.info(f"  F1 Score:  {result['f1_score']:.4f} {'✅' if result['meets_criteria'] else '❌'}")
        logger.info(f"  Specificity: {result['specificity']:.4f}")
        logger.info(f"  Confusion Matrix: TP={result['confusion_matrix']['true_positives']}, "
                    f"TN={result['confusion_matrix']['true_negatives']}, "
                    f"FP={result['confusion_matrix']['false_positives']}, "
                    f"FN={result['confusion_matrix']['false_negatives']}")

        if not result["meets_criteria"]:
            logger.error(f"  ❌ FAILED: F1={result['f1_score']:.4f} < {MIN_F1_SCORE}")
            all_pass = False
        else:
            logger.info(f"  ✅ PASSED: F1={result['f1_score']:.4f} >= {MIN_F1_SCORE}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    for name, result in results.items():
        if "error" in result:
            logger.info(f"  {name}: ERROR")
        else:
            status = "✅ PASS" if result["meets_criteria"] else "❌ FAIL"
            logger.info(f"  {name}: F1={result['f1_score']:.4f} {status}")

    # Output JSON for CI
    output = {
        "min_f1_threshold": MIN_F1_SCORE,
        "test_cases_count": len(TEST_CASES),
        "results": results,
        "all_pass": all_pass,
    }
    with open("benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"\nResults written to benchmark_results.json")

    if all_pass:
        logger.info("\n✅ All classifiers meet minimum acceptance criteria.")
    else:
        logger.error("\n❌ Some classifiers failed to meet minimum acceptance criteria.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

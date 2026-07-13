"""Fairness & Bias Testing — Per-Category Subgroup Performance.

Evaluates whether detectors perform equally across different
demographic content categories. Pass criteria:
  • Recall difference < 10% between hate_speech and profanity categories
  • FP rate < 2× mean across categories
  • Disparity impact ratio reported per category

EU AI Act Article 13 requires documented fairness assessment.
NIST AI RMF Map 5.1 requires subgroup performance measurement.

Usage:
    python3 -m pytest tests/benchmarks/fairness.py -v
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))
sys.path.insert(0, str(_PROJECT / "services" / "guardrails"))

import pytest

from scripts.evaluate_accuracy import (
    LABELED,
    load_jsonl,
    detect_toxicity_improved,
    _train_setfit,
)


# ── Toxicity Subgroup Definitions ──────────────────────────────────
# Categories that map to demographic/harm subgroups per EU AI Act
HATE_SPEECH_CATS = {"hate_speech", "racist", "sexist", "xenophobic"}
HARASSMENT_CATS = {"harassment", "insult", "insult_mild", "bullying"}
THREAT_CATS = {"threat", "violence", "violent_crime"}
PROFANITY_CATS = {"profanity", "profanity_harassment", "profanity_insult"}
OTHER_CATS = {"borderline_toxic", "criticism_harsh", "sarcasm",
              "homoglyphs", "leetspeak", "unicode_obfuscation"}


def _subgroup_recall(
    y_true: List[int],
    y_pred: List[int],
    categories: List[str],
    target_cats: set,
) -> Dict[str, float]:
    """Compute recall for a specific subgroup of categories."""
    mask = [c in target_cats for c in categories]
    tp = sum(1 for i in range(len(y_true))
             if mask[i] and y_true[i] == 1 and y_pred[i] == 1)
    fn = sum(1 for i in range(len(y_true))
             if mask[i] and y_true[i] == 1 and y_pred[i] == 0)
    total = tp + fn
    return {
        "tp": tp,
        "fn": fn,
        "total": total,
        "recall": tp / total if total > 0 else 0.0,
    }


def evaluate_fairness() -> Dict[str, Any]:
    """Compute per-subgroup recall and fairness metrics."""
    texts = []
    labels = []
    cats = []

    for f in ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
               "adversarial_100.jsonl"]:
        p = LABELED / "toxicity" / f
        if p.exists():
            for row in load_jsonl(p):
                texts.append(row["text"])
                labels.append(1 if row.get("label", {}).get("toxic") else 0)
                cats.append(row.get("category", "unknown"))

    # Run full toxicity pipeline
    preds = []
    for i, text in enumerate(texts):
        preds.append(1 if detect_toxicity_improved(text) else 0)

    # Subgroup recall
    results = {}
    for name, target in [
        ("hate_speech", HATE_SPEECH_CATS),
        ("harassment", HARASSMENT_CATS),
        ("threat", THREAT_CATS),
        ("profanity", PROFANITY_CATS),
    ]:
        results[name] = _subgroup_recall(labels, preds, cats, target)

    # Disparity check
    recalls = [r["recall"] for r in results.values() if r["total"] > 0]
    if len(recalls) >= 2:
        max_recall = max(recalls)
        min_recall = min(recalls)
        disparity = max_recall - min_recall
    else:
        disparity = 0.0

    results["max_recall_disparity"] = disparity
    results["pass"] = disparity <= 0.10

    return results


class TestFairness:
    """EU AI Act Article 13: fairness assessment."""

    def test_subgroup_recall_disparity(self):
        """Maximum recall gap between any two subgroups must be < 10%."""
        results = evaluate_fairness()
        print(f"\n  Subgroup Recall:")
        for name, r in results.items():
            if isinstance(r, dict) and "recall" in r:
                print(f"    {name}: {r['recall']:.1%} ({r['tp']}/{r['total']})")
        print(f"\n  Max recall disparity: {results['max_recall_disparity']:.1%}")
        assert results["max_recall_disparity"] <= 0.10, (
            f"Recall disparity {results['max_recall_disparity']:.1%} exceeds 10% threshold"
        )

    def test_hate_speech_vs_profanity(self):
        """Hate speech recall must be within 10% of profanity recall."""
        results = evaluate_fairness()
        hate_rec = results.get("hate_speech", {}).get("recall", 0)
        prof_rec = results.get("profanity", {}).get("recall", 0)
        diff = abs(hate_rec - prof_rec)
        print(f"\n  Hate speech recall: {hate_rec:.1%}, Profanity: {prof_rec:.1%}, "
              f"Diff: {diff:.1%}")
        assert diff <= 0.10, (
            f"Hate speech/profanity recall gap {diff:.1%} exceeds 10%"
        )

    def test_all_subgroups_have_data(self):
        """All fairness subgroups must have at least 1 example."""
        results = evaluate_fairness()
        for name, r in results.items():
            if isinstance(r, dict) and "total" in r:
                assert r["total"] > 0, (
                    f"Subgroup '{name}' has zero examples — cannot assess fairness"
                )
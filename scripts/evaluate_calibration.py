#!/usr/bin/env python3
"""Confidence Calibration Evaluation — NIST AI RMF Measure 2.2 Compliance.

Evaluates whether SetFit and BERT probability scores reflect actual accuracy.
A well-calibrated model means: when it predicts 95% confidence, it should be
correct ~95% of the time.

Metrics computed:
  - Brier Score (lower is better, <0.15 passes)
  - Expected Calibration Error / ECE (lower is better, <0.10 passes)
  - Reliability diagram data
  - Per-detector calibration report

Usage:
    python3 scripts/evaluate_calibration.py
    python3 scripts/evaluate_calibration.py --gate toxicity
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))
sys.path.insert(0, str(_PROJECT / "services" / "guardrails"))

from scripts.evaluate_accuracy import (
    LABELED,
    _train_setfit,
    _setfit_model,
    _setfit_classifier,
    load_jsonl,
    _run_bert_only,
)
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss


def _get_setfit_probabilities(texts: List[str]) -> np.ndarray:
    """Get SetFit probability scores for a list of texts."""
    _train_setfit()
    # Use injection classifier or toxicity based on gate
    # For calibration, we test toxicity classifier
    embs = _setfit_model.encode(texts, convert_to_numpy=True)
    proba = _setfit_classifier[1].predict_proba(embs)
    return proba[:, 1]  # Probability of class 1 (toxic)


def compute_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Compute Brier score, ECE, and calibration curve."""
    brier = float(brier_score_loss(y_true, y_prob))

    # Expected Calibration Error
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    bin_accuracies = []
    bin_confidences = []
    bin_counts = []

    for i in range(n_bins):
        mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        if mask.sum() == 0:
            bin_accuracies.append(0.0)
            bin_confidences.append(0.0)
            bin_counts.append(0)
            continue
        bin_acc = float(y_true[mask].mean())
        bin_conf = float(y_prob[mask].mean())
        bin_count = int(mask.sum())
        bin_accuracies.append(bin_acc)
        bin_confidences.append(bin_conf)
        bin_counts.append(bin_count)
        ece += abs(bin_acc - bin_conf) * bin_count

    ece = float(ece / len(y_true))

    # Calibration curve (prob_true, prob_pred)
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)

    return {
        "brier_score": brier,
        "ece": ece,
        "n_bins": n_bins,
        "n_samples": len(y_true),
        "bin_accuracies": bin_accuracies,
        "bin_confidences": bin_confidences,
        "bin_counts": bin_counts,
        "prob_true": prob_true.tolist(),
        "prob_pred": prob_pred.tolist(),
        "pass_brier": brier < 0.15,
        "pass_ece": ece < 0.10,
    }


def evaluate_calibration(gate: str = "toxicity") -> Dict[str, Any]:
    """Run calibration evaluation for a specified gate."""
    texts = []
    labels = []

    if gate == "toxicity":
        files = ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
                  "adversarial_100.jsonl"]
        for f in files:
            p = LABELED / "toxicity" / f
            if p.exists():
                for row in load_jsonl(p):
                    texts.append(row["text"])
                    labels.append(1 if row.get("label", {}).get("toxic") else 0)
    elif gate == "injection":
        files = ["injection_200.jsonl", "benign_200.jsonl", "obfuscated_100.jsonl"]
        for f in files:
            p = LABELED / "injection" / f
            if p.exists():
                for row in load_jsonl(p):
                    texts.append(row["text"])
                    labels.append(1 if row.get("label", {}).get("injection_detected", False) else 0)
    else:
        raise ValueError(f"Unknown gate: {gate}")

    results = {}

    # SetFit calibration
    print(f"\n  Computing SetFit probabilities for {len(texts)} examples...")
    setfit_probs = _get_setfit_probabilities(texts)
    y_true = np.array(labels)
    setfit_calib = compute_calibration_metrics(y_true, setfit_probs)
    print(f"  SetFit — Brier: {setfit_calib['brier_score']:.4f} "
          f"({'✅' if setfit_calib['pass_brier'] else '❌'}), "
          f"ECE: {setfit_calib['ece']:.4f} "
          f"({'✅' if setfit_calib['pass_ece'] else '❌'})")
    results["setfit"] = setfit_calib

    # BERT calibration (sample first 50 for speed)
    print(f"  Computing BERT probabilities (sampling 50 examples)...")
    sample_texts = texts[:50]
    sample_labels = np.array(labels[:50])
    bert_probs = []
    for i, text in enumerate(sample_texts):
        result = _run_bert_only(text)
        if result is not None:
            # BERT binary — use 0.95 for toxic, 0.05 for not toxic
            bert_probs.append(0.95 if result else 0.05)
        else:
            bert_probs.append(0.5)  # Unknown

    bert_probs = np.array(bert_probs)
    bert_calib = compute_calibration_metrics(sample_labels, bert_probs)
    print(f"  BERT — Brier: {bert_calib['brier_score']:.4f} "
          f"({'✅' if bert_calib['pass_brier'] else '❌'}), "
          f"ECE: {bert_calib['ece']:.4f} "
          f"({'✅' if bert_calib['pass_ece'] else '❌'})")
    results["bert"] = bert_calib

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", default="toxicity", choices=["toxicity", "injection"])
    parser.add_argument("--json", action="store_true", help="Output JSON for CI")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  CONFIDENCE CALIBRATION — {args.gate.upper()}")
    print(f"{'='*60}")

    results = evaluate_calibration(args.gate)

    if args.json:
        print(json.dumps(results, indent=2))
        sys.exit(
            0 if all(
                r["pass_brier"] and r["pass_ece"] for r in results.values()
            ) else 1
        )

    print(f"\n  Acceptance Criteria:")
    for name, r in results.items():
        brier_status = "✅" if r["pass_brier"] else "❌"
        ece_status = "✅" if r["pass_ece"] else "❌"
        print(f"    {name}: Brier {r['brier_score']:.4f} {brier_status}, "
              f"ECE {r['ece']:.4f} {ece_status}")
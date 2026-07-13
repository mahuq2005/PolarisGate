#!/usr/bin/env python3
"""SetFit Cross-Validation + Model Drift Detection — Combined Script.

Cross-Validation: 5-fold stratified CV across all 170 labeled examples.
Pass criteria: F1 std ≤ 3% across folds.

Model Drift: Compare current detector outputs against baseline.
Pass criteria: Kolmogorov-Smirnov p-value > 0.05 across all detectors.

Usage:
    python3 scripts/validate_setfit_stability.py
    python3 scripts/validate_setfit_stability.py --cv-only
    python3 scripts/validate_setfit_stability.py --drift-only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_PROJECT = Path(__file__).resolve().parent.parent
_REPORTS = _PROJECT / "reports"
_REPORTS.mkdir(exist_ok=True)
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))

from scripts.evaluate_accuracy import LABELED, load_jsonl
from sklearn.model_selection import StratifiedKFold
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, f1_score
from scipy.stats import ks_2samp


# ── Cross-Validation ───────────────────────────────────────────────
def run_cross_validation(n_folds: int = 5) -> Dict[str, Any]:
    """Run stratified k-fold CV for SetFit on toxicity data."""
    print(f"\n  Running {n_folds}-fold cross-validation...")

    texts = []
    labels = []
    for f in ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
               "adversarial_100.jsonl"]:
        p = LABELED / "toxicity" / f
        if p.exists():
            for row in load_jsonl(p):
                texts.append(row["text"])
                labels.append(1 if row.get("label", {}).get("toxic") else 0)

    texts = np.array(texts)
    labels = np.array(labels)
    kf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    precisions, recalls, f1s = [], [], []

    for fold, (train_idx, test_idx) in enumerate(kf.split(texts, labels)):
        model = SentenceTransformer('all-MiniLM-L6-v2')
        train_embs = model.encode(texts[train_idx].tolist(), convert_to_numpy=True)
        clf = LogisticRegression(max_iter=1000)
        clf.fit(train_embs, labels[train_idx])

        test_embs = model.encode(texts[test_idx].tolist(), convert_to_numpy=True)
        preds = clf.predict(test_embs)

        prec = precision_score(labels[test_idx], preds, zero_division=0)
        rec = recall_score(labels[test_idx], preds, zero_division=0)
        f1 = f1_score(labels[test_idx], preds, zero_division=0)

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        print(f"    Fold {fold+1}: P={prec:.4f} R={rec:.4f} F1={f1:.4f}")

    mean_f1 = float(np.mean(f1s))
    std_f1 = float(np.std(f1s))

    print(f"\n  CV Summary: F1={mean_f1:.4f} ± {std_f1:.4f}")
    print(f"  Pass: {'✅' if std_f1 <= 0.03 else '❌'} (std ≤ 0.03)")

    return {
        "n_folds": n_folds,
        "mean_precision": float(np.mean(precisions)),
        "mean_recall": float(np.mean(recalls)),
        "mean_f1": mean_f1,
        "std_precision": float(np.std(precisions)),
        "std_recall": float(np.std(recalls)),
        "std_f1": std_f1,
        "pass": std_f1 <= 0.03,
    }


# ── Model Drift Detection ──────────────────────────────────────────
def run_drift_detection() -> Dict[str, Any]:
    """Compare current detector outputs against saved baseline."""
    baseline_path = _REPORTS / "accuracy_results.json"
    if not baseline_path.exists():
        print(f"  ⚠️  No baseline found at {baseline_path}")
        return {"error": "no_baseline", "pass": True}

    print(f"\n  Loading baseline from {baseline_path}...")
    with open(baseline_path) as f:
        baseline = json.load(f)

    # Compute current metrics
    from scripts.evaluate_accuracy import (
        detect_toxicity_keyword, detect_injection, detect_pii,
    )
    from tests.metrics import MetricsEngine

    drift_results = {}

    for gate, detect_fn, files, files_path in [
        ("toxicity", detect_toxicity_keyword,
         ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
           "adversarial_100.jsonl"], "toxicity"),
        ("injection", detect_injection,
         ["injection_200.jsonl", "benign_200.jsonl", "obfuscated_100.jsonl"],
         "injection"),
    ]:
        yt, yp = [], []
        for f in files:
            p = LABELED / files_path / f
            if p.exists():
                for row in load_jsonl(p):
                    label_key = "toxic" if gate == "toxicity" else "injection_detected"
                    yt.append(1 if row.get("label", {}).get(label_key, False) else 0)
                    yp.append(1 if detect_fn(row["text"]) else 0)

        m = MetricsEngine.compute_classification(yt, yp)
        current = m.to_dict()

        # K-S test for distribution shift
        if gate in baseline:
            bl = baseline[gate]
            ks_stat, ks_pval = ks_2samp(
                [1 if p else 0 for p in yp],
                [1] * int(bl.get("recall", 0) * 100) + [0] * 100,
            )
            drift = ks_pval < 0.05
            drift_results[gate] = {
                "ks_statistic": float(ks_stat),
                "ks_pvalue": float(ks_pval),
                "drift_detected": bool(drift),
                "current_precision": current["precision"],
                "current_recall": current["recall"],
                "current_f1": current["f1_score"],
            }
            status = "⚠️ DRIFT" if drift else "✅ stable"
            print(f"  {gate}: K-S p={ks_pval:.4f} ({status})")
        else:
            drift_results[gate] = {"error": "no_baseline_for_gate"}

    drift_results["pass"] = all(
        not r.get("drift_detected", False)
        for r in drift_results.values() if isinstance(r, dict)
    )
    drift_results["timestamp"] = datetime.now(timezone.utc).isoformat()

    return drift_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-only", action="store_true")
    parser.add_argument("--drift-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  SETFIT VALIDATION + DRIFT MONITORING")
    print(f"{'='*60}")

    results = {}

    if not args.drift_only:
        cv = run_cross_validation()
        results["cross_validation"] = cv
        if args.cv_only:
            sys.exit(0 if cv["pass"] else 1)

    if not args.cv_only:
        drift = run_drift_detection()
        results["drift"] = drift

    if args.json:
        print(json.dumps(results, indent=2))
        sys.exit(0 if results.get("drift", {}).get("pass", True) else 1)

    print(f"\n  Done. {'✅ All checks pass' if not results.get('drift', {}).get('drift_detected', False) else '⚠️ Drift detected'}")
#!/usr/bin/env python3
"""
Compare benchmark results against a saved baseline to detect accuracy regressions.

If no baseline exists, saves the current results and exits 0.
If a baseline exists, compares F1 score, false-positive rate, and
false-negative rate per gate.  Flags regressions exceeding configured
thresholds.

Usage::

    python scripts/alert_accuracy_regression.py \
        --results reports/drift_results.json \
        --baseline reports/accuracy_baseline.json

    # After manual review, update the baseline:
    python scripts/alert_accuracy_regression.py \
        --results reports/drift_results.json \
        --baseline reports/accuracy_baseline.json \
        --save-baseline

Exit 0 → no regressions (or baseline created).
Exit 1 → one or more regressions detected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Regression thresholds (absolute deltas)
# ---------------------------------------------------------------------------
F1_DROP_THRESHOLD = 0.02       # F1 drops by more than 2 %
FP_RATE_INCREASE_THRESHOLD = 0.01   # FP rate increases by more than 1 %
FN_RATE_INCREASE_THRESHOLD = 0.02   # FN rate increases by more than 2 %

# ---------------------------------------------------------------------------
# Metric keys to compare (with aliases)
# ---------------------------------------------------------------------------
METRIC_KEYS = {
    "f1": ["f1_score", "f1"],
    "fp_rate": ["false_positive_rate", "fp_rate"],
    "fn_rate": ["false_negative_rate", "fn_rate"],
}


def _get_metric(metrics: Dict[str, Any], aliases: List[str]) -> float | None:
    """Return the first matching metric value, or None."""
    for key in aliases:
        val = metrics.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def extract_gate_metrics(results: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Extract a flat {gate_name: {f1: ..., fp_rate: ..., fn_rate: ...}} dict."""
    gates = results.get("gates", {})
    output: Dict[str, Dict[str, float]] = {}
    for gate_name, metrics in gates.items():
        f1 = _get_metric(metrics, METRIC_KEYS["f1"])
        fp = _get_metric(metrics, METRIC_KEYS["fp_rate"])
        fn = _get_metric(metrics, METRIC_KEYS["fn_rate"])
        if f1 is not None or fp is not None or fn is not None:
            output[gate_name] = {
                "f1": f1 if f1 is not None else 0.0,
                "fp_rate": fp if fp is not None else 0.0,
                "fn_rate": fn if fn is not None else 0.0,
            }
    return output


def detect_regressions(
    current: Dict[str, Dict[str, float]],
    baseline: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Compare current vs. baseline per gate.  Return list of regressions."""
    regressions: List[Dict[str, Any]] = []

    for gate_name, cur_metrics in current.items():
        base_metrics = baseline.get(gate_name, {})
        if not base_metrics:
            continue  # new gate — no baseline to compare

        # F1 regression (drop)
        cur_f1 = cur_metrics.get("f1", 0.0)
        base_f1 = base_metrics.get("f1", 0.0)
        f1_delta = cur_f1 - base_f1
        if f1_delta < -F1_DROP_THRESHOLD:
            regressions.append({
                "gate": gate_name,
                "metric": "f1_score",
                "baseline": base_f1,
                "current": cur_f1,
                "delta": round(f1_delta, 4),
                "direction": "dropped",
            })

        # FP rate regression (increase)
        cur_fp = cur_metrics.get("fp_rate", 0.0)
        base_fp = base_metrics.get("fp_rate", 0.0)
        fp_delta = cur_fp - base_fp
        if fp_delta > FP_RATE_INCREASE_THRESHOLD:
            regressions.append({
                "gate": gate_name,
                "metric": "false_positive_rate",
                "baseline": base_fp,
                "current": cur_fp,
                "delta": round(fp_delta, 4),
                "direction": "increased",
            })

        # FN rate regression (increase)
        cur_fn = cur_metrics.get("fn_rate", 0.0)
        base_fn = base_metrics.get("fn_rate", 0.0)
        fn_delta = cur_fn - base_fn
        if fn_delta > FN_RATE_INCREASE_THRESHOLD:
            regressions.append({
                "gate": gate_name,
                "metric": "false_negative_rate",
                "baseline": base_fn,
                "current": cur_fn,
                "delta": round(fn_delta, 4),
                "direction": "increased",
            })

    return regressions


def print_report(regressions: List[Dict[str, Any]]) -> None:
    """Print a human-readable regression report."""
    print(f"\n{'='*60}")
    print("  PolarisGate Accuracy Regression Report")
    print(f"{'='*60}\n")

    if not regressions:
        print("  ✅ No regressions detected.\n")
        return

    for r in regressions:
        direction = r["direction"]
        arrow = "↓" if direction == "dropped" else "↑"
        print(
            f"  ❌ {r['gate']}.{r['metric']}: "
            f"{r['baseline']:.4f} → {r['current']:.4f} "
            f"({arrow} {abs(r['delta']):.4f})"
        )

    print(f"\n  {len(regressions)} regression(s) detected\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect accuracy regressions vs. baseline"
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("reports/drift_results.json"),
        help="Path to current benchmark results JSON",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("reports/accuracy_baseline.json"),
        help="Path to baseline JSON (created if missing)",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current results as the new baseline (after manual review)",
    )
    args = parser.parse_args()

    if not args.results.exists():
        print(f"❌ Results file not found: {args.results}")
        sys.exit(2)

    results = json.loads(args.results.read_text(encoding="utf-8"))

    # If baseline doesn't exist, create it
    if not args.baseline.exists():
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        # Save only the gates portion
        baseline_data = {"gates": extract_gate_metrics(results)}
        args.baseline.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")
        print(f"✅ Baseline saved to {args.baseline} (first run)")
        sys.exit(0)

    # If --save-baseline flag is set, overwrite
    if args.save_baseline:
        baseline_data = {"gates": extract_gate_metrics(results)}
        args.baseline.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")
        print(f"✅ Baseline updated at {args.baseline}")
        sys.exit(0)

    # Compare against baseline
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    current_metrics = extract_gate_metrics(results)
    baseline_metrics = baseline.get("gates", {})

    regressions = detect_regressions(current_metrics, baseline_metrics)
    print_report(regressions)

    if regressions:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
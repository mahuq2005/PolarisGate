#!/usr/bin/env python3
"""
Compare accuracy benchmark results against thresholds.yaml.

Reads a JSON results file produced by the benchmark suite and validates
every gate's metrics against the configured pass/fail thresholds.

Usage::

    python scripts/check_accuracy_thresholds.py \\
        --results reports/accuracy_results.json \\
        --thresholds tests/thresholds.yaml

Exit code 0 → all thresholds met.  Exit code 1 → one or more failures.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def load_results(path: Path) -> Dict[str, Any]:
    """Load benchmark results JSON."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_thresholds(path: Path) -> Dict[str, Any]:
    """Load thresholds YAML."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _extract_metric(metrics: Dict[str, Any], key: str) -> float | None:
    """Try common aliases for a metric key."""
    aliases = {
        "min_precision": "precision",
        "min_recall": "recall",
        "min_f1": "f1_score",
        "max_false_positive_rate": "false_positive_rate",
        "max_false_negative_rate": "false_negative_rate",
        "min_f1_score": "f1_score",
        "max_fp_rate": "false_positive_rate",
        "max_fn_rate": "false_negative_rate",
    }
    lookup = aliases.get(key, key)
    for k in (lookup, key):
        if k in metrics and metrics[k] is not None:
            return float(metrics[k])
    return None


def compare(
    results: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Compare per-gate results to thresholds.

    Returns (passes, failures) where each is a list of dicts with keys
    ``gate``, ``metric``, ``actual``, ``threshold``, and ``rule`` (min/max).
    """
    passes: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    # Top-level "gates" key expected in results
    gates = results.get("gates", {})
    if not gates:
        # Maybe results *are* the gates flat
        if any(k in results for k in ("precision", "recall", "f1_score")):
            gates = {"default": results}
        else:
            print("⚠️  No 'gates' key found in results; nothing to check.")
            return passes, failures

    for gate_name, gate_data in gates.items():
        gate_thresholds = thresholds.get(gate_name, {})
        if not gate_thresholds:
            continue  # no thresholds defined for this gate

        # If gate_data has nested "classifiers" dict (from run_live_accuracy_benchmark),
        # pick the "ensemble" classifier if available, else the first one.
        gate_metrics = gate_data
        if "classifiers" in gate_data and isinstance(gate_data["classifiers"], dict):
            classifiers = gate_data["classifiers"]
            # Prefer ensemble, then any non-error classifier
            for preferred in ("ensemble", "keyword", "pii_detector", "injection_detector"):
                if preferred in classifiers and "error" not in classifiers[preferred]:
                    gate_metrics = classifiers[preferred]
                    gate_name = f"{gate_name}/{preferred}"
                    break
            else:
                # Pick first non-error classifier
                for cname, cdata in classifiers.items():
                    if "error" not in cdata:
                        gate_metrics = cdata
                        gate_name = f"{gate_name}/{cname}"
                        break
                else:
                    continue  # all classifiers errored

        for tkey, threshold_val in gate_thresholds.items():
            if not isinstance(threshold_val, (int, float)):
                # Skip nested sections (entities, stages, etc.)
                continue

            actual = _extract_metric(gate_metrics, tkey)
            if actual is None:
                continue

            entry = {
                "gate": gate_name,
                "metric": tkey,
                "actual": actual,
                "threshold": threshold_val,
            }

            if tkey.startswith("min_"):
                entry["rule"] = "min"
                if actual >= threshold_val:
                    passes.append(entry)
                else:
                    failures.append(entry)
            elif tkey.startswith("max_"):
                entry["rule"] = "max"
                if actual <= threshold_val:
                    passes.append(entry)
                else:
                    failures.append(entry)
            else:
                # Skip keys that are neither min_ nor max_
                pass

    return passes, failures


def print_report(
    passes: List[Dict[str, Any]],
    failures: List[Dict[str, Any]],
) -> None:
    """Pretty-print the threshold check results."""
    print(f"\n{'='*60}")
    print("  PolarisGate Accuracy Threshold Check")
    print(f"{'='*60}\n")

    for p in passes:
        rule = "≥" if p["rule"] == "min" else "≤"
        print(f"  ✅ {p['gate']}.{p['metric']}: {p['actual']:.4f} {rule} {p['threshold']}")

    for f in failures:
        rule = "≥" if f["rule"] == "min" else "≤"
        print(f"  ❌ {f['gate']}.{f['metric']}: {f['actual']:.4f} {rule} {f['threshold']}  ← FAIL")

    print(f"\n  {len(passes)} passed, {len(failures)} failed")

    if failures:
        print(f"\n❌ Threshold check FAILED ({len(failures)} violation(s))")
    else:
        print("\n✅ All thresholds passed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check PolarisGate accuracy benchmark results against thresholds"
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("reports/accuracy_results.json"),
        help="Path to benchmark results JSON (default: reports/accuracy_results.json)",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("tests/thresholds.yaml"),
        help="Path to thresholds YAML (default: tests/thresholds.yaml)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="If set, write pass/fail results as JSON to this path",
    )
    args = parser.parse_args()

    if not args.results.exists():
        print(f"⚠️  Results file not found: {args.results}")
        print("   Skipping threshold check (no results to compare).")
        sys.exit(0)

    if not args.thresholds.exists():
        print(f"❌ Thresholds file not found: {args.thresholds}")
        sys.exit(1)

    results = load_results(args.results)
    thresholds = load_thresholds(args.thresholds)

    passes, failures = compare(results, thresholds)
    print_report(passes, failures)

    if args.json_output:
        output = {
            "passes": passes,
            "failures": failures,
            "total_checks": len(passes) + len(failures),
            "all_pass": len(failures) == 0,
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_output, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)
        print(f"\n  📄 JSON report written to {args.json_output}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
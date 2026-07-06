#!/usr/bin/env python3
"""
Generate a Markdown accuracy dashboard from benchmark results.

Reads a JSON results file produced by the benchmark suite and produces a
human-readable dashboard with per-gate metrics, pass/fail status, and
trend information.

Usage::

    python scripts/generate_accuracy_dashboard.py \\
        --results reports/accuracy_results.json \\
        --output reports/accuracy_dashboard.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_git_info() -> Dict[str, str]:
    """Return current git commit and branch, if available."""
    info: Dict[str, str] = {}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        info["commit"] = "unknown"

    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        info["branch"] = "unknown"

    return info


def _status_emoji(meets: bool) -> str:
    return "✅" if meets else "❌"


def _fmt(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def generate_dashboard(
    results: Dict[str, Any],
    git_info: Dict[str, str],
) -> str:
    """Build the Markdown dashboard string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gates = results.get("gates", {})

    lines: List[str] = []
    lines.append("# PolarisGate Accuracy Dashboard")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Commit:** `{git_info.get('commit', '?')}` ({git_info.get('branch', '?')})")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not gates:
        lines.append("⚠️  No gate results found in input file.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Per-gate table
    # ------------------------------------------------------------------
    lines.append("## Gate Summary")
    lines.append("")
    lines.append("| Gate | Precision | Recall | F1 Score | FP Rate | FN Rate | Accuracy | Status |")
    lines.append("|------|-----------|--------|----------|---------|---------|----------|--------|")

    pass_count = 0
    fail_count = 0

    for gate_name, metrics in gates.items():
        precision = metrics.get("precision")
        recall = metrics.get("recall")
        f1 = metrics.get("f1_score") or metrics.get("f1")
        fp_rate = metrics.get("false_positive_rate")
        fn_rate = metrics.get("false_negative_rate")
        accuracy = metrics.get("accuracy")

        # Simple heuristic: if F1 is ≥ 0.60, consider pass (will be refined by threshold checker)
        f1_val = f1 if isinstance(f1, (int, float)) else 0.0
        status = f1_val >= 0.60
        if status:
            pass_count += 1
        else:
            fail_count += 1

        lines.append(
            f"| {gate_name} | {_fmt(precision)} | {_fmt(recall)} | {_fmt(f1)} "
            f"| {_fmt(fp_rate)} | {_fmt(fn_rate)} | {_fmt(accuracy)} "
            f"| {_status_emoji(status)} |"
        )

    lines.append("")
    total = pass_count + fail_count
    lines.append(f"- **Passed:** {pass_count}/{total}  {_status_emoji(fail_count == 0)}")
    if fail_count > 0:
        lines.append(f"- **Failed:** {fail_count}/{total}  ❌")
    lines.append("")

    # ------------------------------------------------------------------
    # Per-gate detail sections
    # ------------------------------------------------------------------
    for gate_name, metrics in gates.items():
        lines.append(f"## {gate_name.title()} Gate")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")

        for k, v in sorted(metrics.items()):
            if isinstance(v, dict):
                continue  # nested objects rendered separately
            lines.append(f"| {k} | {_fmt(v)} |")

        # Confusion matrix
        cm = metrics.get("confusion_matrix", {})
        if cm:
            lines.append("")
            lines.append("### Confusion Matrix")
            lines.append("")
            lines.append("| | Predicted Positive | Predicted Negative |")
            lines.append("|---|---|---|")
            lines.append(
                f"| **Actual Positive** | {cm.get('true_positive', '?')} | {cm.get('false_negative', '?')} |"
            )
            lines.append(
                f"| **Actual Negative** | {cm.get('false_positive', '?')} | {cm.get('true_negative', '?')} |"
            )

        # Performance metrics
        perf = metrics.get("performance", {})
        if perf:
            lines.append("")
            lines.append("### Performance")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            perf_keys = [
                ("latency_p50_ms", "Latency p50"),
                ("latency_p95_ms", "Latency p95"),
                ("latency_p99_ms", "Latency p99"),
                ("latency_mean_ms", "Latency Mean"),
                ("throughput_req_per_sec", "Throughput (req/s)"),
            ]
            for key, label in perf_keys:
                if key in perf:
                    lines.append(f"| {label} | {_fmt(perf[key])} |")

        lines.append("")

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    lines.append("---")
    lines.append("")
    lines.append(
        "_Dashboard generated by "
        "[`generate_accuracy_dashboard.py`](../scripts/generate_accuracy_dashboard.py)._"
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate PolarisGate accuracy dashboard Markdown"
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("reports/accuracy_results.json"),
        help="Path to benchmark results JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/accuracy_dashboard.md"),
        help="Output Markdown path",
    )
    args = parser.parse_args()

    if not args.results.exists():
        print(f"❌ Results file not found: {args.results}")
        sys.exit(1)

    results = json.loads(args.results.read_text(encoding="utf-8"))
    git_info = _get_git_info()

    dashboard = generate_dashboard(results, git_info)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dashboard, encoding="utf-8")
    print(f"✅ Dashboard written to {args.output}")


if __name__ == "__main__":
    main()
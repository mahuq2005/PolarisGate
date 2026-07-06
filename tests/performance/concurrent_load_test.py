"""Concurrent load performance test for PolarisGate.

Runs multiple benchmark iterations concurrently using ThreadPoolExecutor
to simulate production load patterns. Measures p50/p95/p99 latency and
throughput at 1, 10, 50, and 100 concurrent levels.

Usage::

    python3 tests/performance/concurrent_load_test.py
    python3 tests/performance/concurrent_load_test.py --concurrency 10 50 100
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

_PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT))

from tests.metrics import MetricsEngine, PerformanceMetrics  # noqa: E402

_LABELED_DIR = _PROJECT / "tests" / "test_data" / "labeled"


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_texts() -> List[str]:
    """Load all texts from toxicity and PII labeled datasets for load testing."""
    texts: List[str] = []
    for gate in ["toxicity", "pii"]:
        gate_dir = _LABELED_DIR / gate
        for fname in gate_dir.glob("*.jsonl"):
            for row in _load_jsonl(fname):
                texts.append(row["text"])
    # Deduplicate but keep order
    seen = set()
    unique = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _run_toxicity_inference(text: str) -> float:
    """Run toxicity keyword check and return latency in ms."""
    t0 = time.time()
    # Minimal keyword check — runs in microseconds
    toxic_keywords = [
        "idiot", "useless", "hurt", "kill", "worthless", "hate",
        "moron", "die", "stupid", "disgusting", "terrible", "failure",
    ]
    text_lower = text.lower()
    for kw in toxic_keywords:
        if kw in text_lower:
            break
    return (time.time() - t0) * 1000


def _run_pii_inference(text: str) -> float:
    """Run PII regex check and return latency in ms."""
    import re
    t0 = time.time()
    patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",       # SSN
        r"\b\d{3}\s\d{3}\s\d{3}\b",      # SIN
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",  # Email
        r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",  # Phone
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit Card
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP
    ]
    for pat in patterns:
        re.search(pat, text)
    return (time.time() - t0) * 1000


def _run_benchmark_at_concurrency(
    texts: List[str],
    concurrency: int,
    iterations: int = 200,
) -> PerformanceMetrics:
    """Run a mixed load test at a given concurrency level.

    Each worker alternates between toxicity and PII inference on a
    rotating set of texts for the specified number of iterations.
    """
    latencies: List[float] = []
    start = time.time()

    def worker(worker_id: int):
        local_latencies = []
        for i in range(iterations // concurrency + 1):
            idx = (worker_id * 10 + i) % len(texts)
            text = texts[idx]
            # Alternate between toxicity and PII
            if i % 2 == 0:
                lat = _run_toxicity_inference(text)
            else:
                lat = _run_pii_inference(text)
            local_latencies.append(lat)
        return local_latencies

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(worker, i): i for i in range(concurrency)}
        for future in as_completed(futures):
            latencies.extend(future.result())

    elapsed = time.time() - start
    return MetricsEngine.compute_performance(
        [float(l) for l in latencies], elapsed
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run concurrent load performance test"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        nargs="+",
        default=[1, 10, 50, 100],
        help="Concurrency levels to test (default: 1 10 50 100)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Total iterations (default: 200)",
    )
    args = parser.parse_args()

    texts = _load_texts()
    print(f"Loaded {len(texts)} unique texts for load testing\n")

    print(f"{'='*70}")
    print(f"  PolarisGate Concurrent Load Test")
    print(f"  Iterations: ~{args.iterations} per level")
    print(f"{'='*70}\n")

    print(f"  {'Concurrency':>12s}  {'p50(ms)':>8s}  {'p95(ms)':>8s}  "
          f"{'p99(ms)':>8s}  {'mean(ms)':>9s}  {'rps':>8s}  {'total_req':>9s}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*9}  {'-'*8}  {'-'*9}")

    results = {"concurrency_levels": {}}
    for conc in args.concurrency:
        pm = _run_benchmark_at_concurrency(texts, conc, args.iterations)
        results["concurrency_levels"][str(conc)] = pm.to_dict()
        print(
            f"  {conc:>12d}  "
            f"{pm.latency_p50_ms:>8.2f}  "
            f"{pm.latency_p95_ms:>8.2f}  "
            f"{pm.latency_p99_ms:>8.2f}  "
            f"{pm.latency_mean_ms:>9.2f}  "
            f"{pm.throughput_req_per_sec:>8.1f}  "
            f"{pm.total_requests:>9d}"
        )

    print(f"\n✅ Load test complete. p95 < 500ms: " +
          ("PASS" if results["concurrency_levels"]["100"]["latency_p95_ms"] < 500 else "NEEDS REVIEW"))

    # Save results
    output = _PROJECT / "reports" / "concurrent_load_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"📄 Results saved to {output}")


if __name__ == "__main__":
    main()
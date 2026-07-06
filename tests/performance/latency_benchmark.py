"""Performance latency benchmarks for PolarisGate gates.

Validates the PerformanceMetrics dataclass and MetricsEngine.compute_performance()
with synthetic latency data covering p50/p95/p99 percentile correctness,
throughput calculation, edge cases (empty, single-value, zero-duration),
and threshold configuration validation.

All tests run without a live gateway.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.metrics import MetricsEngine, PerformanceMetrics  # noqa: E402

_THRESHOLDS_PATH = _PROJECT_ROOT / "tests" / "thresholds.yaml"


@pytest.fixture(scope="module")
def perf_thresholds() -> Dict[str, Any]:
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("performance", {})


# ------------------------------------------------------------------
# Dataclass tests
# ------------------------------------------------------------------


class TestPerformanceMetricsDataclass:
    """Validate the PerformanceMetrics dataclass."""

    def test_default_values(self):
        pm = PerformanceMetrics()
        assert pm.latency_p50_ms == 0.0
        assert pm.latency_p95_ms == 0.0
        assert pm.latency_p99_ms == 0.0
        assert pm.latency_mean_ms == 0.0
        assert pm.latency_stddev_ms == 0.0
        assert pm.throughput_req_per_sec == 0.0
        assert pm.total_requests == 0

    def test_to_dict_all_keys(self):
        pm = PerformanceMetrics(
            latency_p50_ms=10.0,
            latency_p95_ms=50.0,
            latency_p99_ms=100.0,
            latency_mean_ms=25.0,
            latency_stddev_ms=5.0,
            throughput_req_per_sec=200.0,
            total_requests=1000,
        )
        d = pm.to_dict()
        assert d["latency_p50_ms"] == 10.0
        assert d["latency_p95_ms"] == 50.0
        assert d["latency_p99_ms"] == 100.0
        assert d["latency_mean_ms"] == 25.0
        assert d["latency_stddev_ms"] == 5.0
        assert d["throughput_req_per_sec"] == 200.0
        assert d["total_requests"] == 1000
        assert len(d) == 7

    def test_field_types(self):
        pm = PerformanceMetrics()
        # all fields are floats or ints
        for key, val in pm.to_dict().items():
            assert isinstance(val, (int, float)), f"{key} is {type(val)}"


# ------------------------------------------------------------------
# compute_performance tests
# ------------------------------------------------------------------


class TestComputePerformance:
    """Validate MetricsEngine.compute_performance()."""

    def test_empty_input_returns_defaults(self):
        pm = MetricsEngine.compute_performance([], 10.0)
        assert pm.total_requests == 0
        assert pm.latency_p50_ms == 0.0
        assert pm.throughput_req_per_sec == 0.0

    def test_single_value(self):
        pm = MetricsEngine.compute_performance([42.0], 1.0)
        assert pm.latency_p50_ms == 42.0
        assert pm.latency_p95_ms == 42.0
        assert pm.latency_p99_ms == 42.0
        assert pm.latency_mean_ms == 42.0
        assert pm.latency_stddev_ms == 0.0
        assert pm.throughput_req_per_sec == 1.0
        assert pm.total_requests == 1

    def test_uniform_distribution(self):
        """1..100 ms uniform → p50 ≈ 50.5, p95 ≈ 95.05, p99 ≈ 99.01."""
        latencies = [float(i) for i in range(1, 101)]  # 1..100
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert 49.0 < pm.latency_p50_ms < 52.0
        assert 94.0 < pm.latency_p95_ms < 97.0
        assert 98.0 < pm.latency_p99_ms < 100.0
        assert pm.throughput_req_per_sec == 10.0  # 100 / 10s
        assert pm.total_requests == 100

    def test_two_values(self):
        pm = MetricsEngine.compute_performance([10.0, 20.0], 5.0)
        assert pm.total_requests == 2
        assert pm.latency_mean_ms == 15.0
        assert pm.throughput_req_per_sec == 0.4  # 2/5

    def test_zero_duration_avoids_division_by_zero(self):
        pm = MetricsEngine.compute_performance([10.0], 0.0)
        assert pm.throughput_req_per_sec == 0.0  # no division error

    def test_large_latency(self):
        pm = MetricsEngine.compute_performance([9999.0], 1.0)
        assert pm.latency_p50_ms == 9999.0


class TestPercentileCorrectness:
    """Verify p50/p95/p99 match numpy.percentile."""

    def test_p50_matches_numpy(self):
        arr = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        pm = MetricsEngine.compute_performance(arr, 1.0)
        np_p50 = float(np.percentile(arr, 50))
        assert pm.latency_p50_ms == pytest.approx(np_p50, abs=0.01)

    def test_p95_matches_numpy(self):
        arr = [float(i) for i in range(1, 101)]
        pm = MetricsEngine.compute_performance(arr, 1.0)
        np_p95 = float(np.percentile(arr, 95))
        assert pm.latency_p95_ms == pytest.approx(np_p95, abs=0.1)

    def test_p99_with_outlier(self):
        arr = [1.0] * 99 + [500.0]  # 1 outlier
        pm = MetricsEngine.compute_performance(arr, 1.0)
        assert pm.latency_p50_ms == 1.0  # median still 1
        assert pm.latency_p99_ms == pytest.approx(500.0, abs=10)

    def test_all_same_values(self):
        arr = [25.0] * 50
        pm = MetricsEngine.compute_performance(arr, 1.0)
        assert pm.latency_p50_ms == 25.0
        assert pm.latency_p95_ms == 25.0
        assert pm.latency_p99_ms == 25.0
        assert pm.latency_stddev_ms == 0.0


class TestThroughputCalculation:
    """Throughput RPS correctness."""

    def test_basic(self):
        pm = MetricsEngine.compute_performance([1.0] * 200, 10.0)
        assert pm.throughput_req_per_sec == 20.0

    def test_high_throughput(self):
        pm = MetricsEngine.compute_performance([1.0] * 5000, 5.0)
        assert pm.throughput_req_per_sec == 1000.0

    def test_fractional_duration(self):
        pm = MetricsEngine.compute_performance([1.0] * 100, 0.5)
        assert pm.throughput_req_per_sec == 200.0

    def test_large_request_count(self):
        pm = MetricsEngine.compute_performance([1.0] * 100000, 20.0)
        assert pm.throughput_req_per_sec == 5000.0
        assert pm.total_requests == 100000

    def test_rounding(self):
        """Throughput is rounded to 2 decimal places."""
        pm = MetricsEngine.compute_performance([1.0] * 7, 3.0)
        assert pm.throughput_req_per_sec == 2.33


class TestThresholdConfiguration:
    """Validate performance thresholds in thresholds.yaml."""

    def test_performance_section_exists(self, perf_thresholds):
        assert len(perf_thresholds) > 0, "performance section empty"

    def test_guardrails_latency_thresholds(self, perf_thresholds):
        assert "guardrails_check_latency_p50_ms" in perf_thresholds
        assert "guardrails_check_latency_p95_ms" in perf_thresholds
        assert "guardrails_check_latency_p99_ms" in perf_thresholds
        assert perf_thresholds["guardrails_check_latency_p95_ms"] < 2000

    def test_hallucination_latency_thresholds(self, perf_thresholds):
        assert "hallucination_detect_latency_p50_ms" in perf_thresholds
        assert "hallucination_detect_latency_p95_ms" in perf_thresholds
        assert "hallucination_detect_latency_p99_ms" in perf_thresholds
        # Hallucination cascade is slower, threshold should be higher
        assert perf_thresholds["hallucination_detect_latency_p95_ms"] <= 5000

    def test_throughput_thresholds(self, perf_thresholds):
        assert "min_guardrails_throughput_rps" in perf_thresholds
        assert "min_hallucination_throughput_rps" in perf_thresholds
        assert perf_thresholds["min_guardrails_throughput_rps"] > 0
        assert perf_thresholds["min_hallucination_throughput_rps"] > 0

    def test_batch_and_stream_thresholds(self, perf_thresholds):
        assert "batch_latency_per_item_ms" in perf_thresholds
        assert "stream_chunk_interval_ms" in perf_thresholds

    def test_compare_against_thresholds(self, perf_thresholds):
        """Simulated performance must meet thresholds."""
        # Simulate guardrails check: 1000 requests, avg 100ms, 10s duration
        guardrails_latencies = [float(i) for i in range(50, 150)]  # 50-150ms
        pm = MetricsEngine.compute_performance(guardrails_latencies, 10.0)

        assert pm.latency_p50_ms <= perf_thresholds.get("guardrails_check_latency_p50_ms", 1000)
        assert pm.latency_p95_ms <= perf_thresholds.get("guardrails_check_latency_p95_ms", 1000)
        assert pm.latency_p99_ms <= perf_thresholds.get("guardrails_check_latency_p99_ms", 5000)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
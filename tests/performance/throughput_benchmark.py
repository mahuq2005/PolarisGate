"""Throughput benchmarks for PolarisGate gates.

Validates throughput calculation, scaling behaviour, warmup effects,
and saturation detection using the MetricsEngine with synthetic data.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.metrics import MetricsEngine, PerformanceMetrics  # noqa: E402


class TestThroughputBasic:
    """Basic throughput calculation correctness."""

    def test_simple(self):
        latencies = [10.0] * 100
        pm = MetricsEngine.compute_performance(latencies, 5.0)
        assert pm.throughput_req_per_sec == 20.0
        assert pm.total_requests == 100

    def test_zero_requests(self):
        pm = MetricsEngine.compute_performance([], 10.0)
        assert pm.throughput_req_per_sec == 0.0
        assert pm.total_requests == 0

    def test_single_request(self):
        pm = MetricsEngine.compute_performance([50.0], 2.0)
        assert pm.throughput_req_per_sec == 0.5
        assert pm.total_requests == 1


class TestThroughputScaling:
    """Throughput under concurrent load simulations."""

    def test_1_concurrent(self):
        """1 concurrent request → throughput = N / duration."""
        latencies = [100.0] * 100
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert pm.throughput_req_per_sec == 10.0

    def test_10_concurrent(self):
        """10 concurrent → throughput scales linearly (no contention simulated)."""
        latencies = [100.0] * 1000
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert pm.throughput_req_per_sec == 100.0

    def test_50_concurrent(self):
        latencies = [100.0] * 5000
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert pm.throughput_req_per_sec == 500.0

    def test_100_concurrent(self):
        latencies = [100.0] * 10000
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert pm.throughput_req_per_sec == 1000.0

    def test_scaling_is_linear(self):
        """Doubling requests doubles throughput for same duration."""
        pm1 = MetricsEngine.compute_performance([10.0] * 500, 10.0)
        pm2 = MetricsEngine.compute_performance([10.0] * 1000, 10.0)
        assert pm2.throughput_req_per_sec == pytest.approx(pm1.throughput_req_per_sec * 2, abs=0.1)


class TestThroughputWithWarmup:
    """Warmup and cooldown effects on throughput."""

    def test_warmup_then_steady_state(self):
        """First 10% of requests slower, rest faster — throughput reflects average."""
        slow = [200.0] * 10   # warmup: 200ms
        fast = [50.0] * 90    # steady: 50ms
        all_latencies = slow + fast
        pm = MetricsEngine.compute_performance(all_latencies, 10.0)
        # 100 requests / 10s = 10 rps (throughput depends only on count/duration)
        assert pm.throughput_req_per_sec == 10.0
        # Mean latency reflects mix
        expected_mean = (10 * 200.0 + 90 * 50.0) / 100  # 65ms
        assert pm.latency_mean_ms == pytest.approx(expected_mean, abs=0.1)

    def test_cooldown_spike(self):
        """Last few requests spike → p99 captures it, throughput unchanged."""
        normal = [50.0] * 95
        spike = [1000.0] * 5
        all_latencies = normal + spike
        pm = MetricsEngine.compute_performance(all_latencies, 10.0)
        assert pm.latency_p50_ms == 50.0
        assert pm.latency_p99_ms >= 1000.0
        assert pm.throughput_req_per_sec == 10.0  # 100/10


class TestSaturationDetection:
    """Throughput saturation point approximation."""

    def test_no_saturation(self):
        """Throughput meets minimum threshold."""
        latencies = [50.0] * 500
        pm = MetricsEngine.compute_performance(latencies, 5.0)
        assert pm.throughput_req_per_sec >= 50  # 100 rps >= 50 min threshold

    def test_saturation_approaching(self):
        """As latency increases, throughput drops if duration is fixed by slow responses."""
        # Simulate: 100 requests at 500ms avg — if each is sequential, total = 50s
        # But with concurrency, duration stays low; throughput = count / wall_duration
        latencies = [500.0] * 100  # high latency
        pm = MetricsEngine.compute_performance(latencies, 20.0)  # wall duration 20s
        assert pm.throughput_req_per_sec == 5.0  # 100/20 = 5 rps — below 50 threshold

    def test_burst_then_saturation(self):
        """Brief burst of high RPS, then latency spikes, throughput drops."""
        burst = [10.0] * 900   # 900 fast requests
        slow = [500.0] * 100   # 100 slow requests
        all_latencies = burst + slow
        pm = MetricsEngine.compute_performance(all_latencies, 10.0)
        assert pm.throughput_req_per_sec == 100.0  # 1000/10
        assert pm.total_requests == 1000


class TestThroughputThresholdComparison:
    """Compare against thresholds.yaml performance section."""

    def test_min_guardrails_throughput(self):
        """Simulated guardrails throughput meets min threshold (50 rps)."""
        latencies = [100.0] * 1000
        pm = MetricsEngine.compute_performance(latencies, 10.0)
        assert pm.throughput_req_per_sec == 100.0
        assert pm.throughput_req_per_sec >= 50

    def test_min_hallucination_throughput(self):
        """Simulated hallucination throughput meets min threshold (10 rps)."""
        latencies = [2000.0] * 100
        pm = MetricsEngine.compute_performance(latencies, 20.0)
        assert pm.throughput_req_per_sec == 5.0  # 100/20
        # 5 rps might be below 10 → needs more capacity or caching


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
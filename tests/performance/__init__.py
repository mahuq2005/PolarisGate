"""PolarisGate performance benchmark test suite.

Measures latency (p50/p95/p99), throughput (requests/sec), and
resource utilisation for every gate and endpoint under load.
"""

from tests.metrics import PerformanceMetrics, compute_performance  # noqa: F401
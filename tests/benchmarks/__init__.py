"""PolarisGate accuracy benchmark test suite.

Tests in this package run against live services and measure
precision, recall, F1, false-positive rate, false-negative rate,
and calibration for every AI/ML gate in the PolarisGate platform.

Imports are guarded so that individual benchmark files can be run
independently without requiring every test dependency at once.
"""

from tests.metrics import MetricsEngine, compute_metrics  # noqa: F401
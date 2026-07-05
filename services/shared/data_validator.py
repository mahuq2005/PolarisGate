"""Data validation and quality monitoring for NorthGuard traces.
Enterprise-grade: Schema validation, data quality checks, null rate tracking,
and drift baseline computation for incoming trace data.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class DataQualityReport:
    """Report of data quality metrics for a batch of traces."""

    def __init__(self):
        self.total_records: int = 0
        self.null_fields: Dict[str, int] = {}
        self.out_of_range_fields: Dict[str, int] = {}
        self.type_mismatches: Dict[str, int] = {}
        self.validation_errors: List[Dict[str, Any]] = []
        self.timestamp: str = datetime.now(timezone.utc).isoformat()

    @property
    def quality_score(self) -> float:
        """Compute an overall quality score from 0.0 to 1.0."""
        if self.total_records == 0:
            return 1.0
        total_issues = (
            sum(self.null_fields.values())
            + sum(self.out_of_range_fields.values())
            + sum(self.type_mismatches.values())
            + len(self.validation_errors)
        )
        return max(0.0, 1.0 - (total_issues / max(self.total_records, 1)))

    def merge(self, other: "DataQualityReport") -> "DataQualityReport":
        """Merge another report into this one."""
        merged = DataQualityReport()
        merged.total_records = self.total_records + other.total_records
        for d in (self.null_fields, other.null_fields):
            for k, v in d.items():
                merged.null_fields[k] = merged.null_fields.get(k, 0) + v
        for d in (self.out_of_range_fields, other.out_of_range_fields):
            for k, v in d.items():
                merged.out_of_range_fields[k] = merged.out_of_range_fields.get(k, 0) + v
        for d in (self.type_mismatches, other.type_mismatches):
            for k, v in d.items():
                merged.type_mismatches[k] = merged.type_mismatches.get(k, 0) + v
        merged.validation_errors = self.validation_errors + other.validation_errors
        return merged


class TraceValidator:
    """Validates trace data against schema and quality rules.

    Supports configurable field constraints, null-rate thresholds,
    and out-of-range detection.
    """

    FIELD_CONSTRAINTS = {
        "prompt": {"max_length": 10000, "min_length": 1},
        "completion": {"max_length": 10000},
        "model_id": {"max_length": 255, "min_length": 1, "pattern": r"^[a-zA-Z0-9\-_]+$"},
        "user_id": {"max_length": 255},
    }

    NULL_THRESHOLD = 0.95  # Warn if >95% of a field is null

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    def validate_trace(self, trace: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a single trace dict. Returns (is_valid, error_message)."""
        errors = []

        # Check required fields
        for field in ("prompt", "completion", "model_id"):
            if field not in trace or trace[field] is None:
                errors.append(f"Missing required field: {field}")
                continue
            if not isinstance(trace[field], str):
                errors.append(f"Field {field} must be a string")
                continue

        if errors:
            return False, "; ".join(errors)

        # Check field constraints
        for field, constraints in self.FIELD_CONSTRAINTS.items():
            value = trace.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                errors.append(f"Field {field} must be a string")
                continue
            max_len = constraints.get("max_length")
            if max_len and len(value) > max_len:
                errors.append(f"Field {field} exceeds max length {max_len}")
            min_len = constraints.get("min_length")
            if min_len and len(value) < min_len:
                errors.append(f"Field {field} below min length {min_len}")
            pattern = constraints.get("pattern")
            if pattern:
                import re
                if not re.match(pattern, value):
                    errors.append(f"Field {field} does not match pattern {pattern}")

        # Validate tags if present
        tags = trace.get("tags", {})
        if tags is not None and not isinstance(tags, dict):
            errors.append("tags must be a dict")
        elif isinstance(tags, dict):
            for k, v in tags.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    errors.append(f"tags entries must be strings: {k}={v}")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def assess_quality(self, traces: List[Dict[str, Any]]) -> DataQualityReport:
        """Assess data quality across a batch of traces."""
        report = DataQualityReport()
        report.total_records = len(traces)

        fields_to_check = ["prompt", "completion", "model_id", "user_id", "tags"]

        for trace in traces:
            # Check nulls
            for field in fields_to_check:
                if field not in trace or trace[field] is None:
                    report.null_fields[field] = report.null_fields.get(field, 0) + 1

            # Check type mismatches
            if "prompt" in trace and trace["prompt"] is not None and not isinstance(trace["prompt"], str):
                report.type_mismatches["prompt"] = report.type_mismatches.get("prompt", 0) + 1
            if "completion" in trace and trace["completion"] is not None and not isinstance(trace["completion"], str):
                report.type_mismatches["completion"] = report.type_mismatches.get("completion", 0) + 1
            if "model_id" in trace and trace["model_id"] is not None and not isinstance(trace["model_id"], str):
                report.type_mismatches["model_id"] = report.type_mismatches.get("model_id", 0) + 1

            # Check out-of-range (length violations)
            if isinstance(trace.get("prompt"), str) and len(trace["prompt"]) > self.FIELD_CONSTRAINTS["prompt"]["max_length"]:
                report.out_of_range_fields["prompt"] = report.out_of_range_fields.get("prompt", 0) + 1
            if isinstance(trace.get("completion"), str) and len(trace["completion"]) > self.FIELD_CONSTRAINTS["completion"]["max_length"]:
                report.out_of_range_fields["completion"] = report.out_of_range_fields.get("completion", 0) + 1

            # Run full validation
            is_valid, error = self.validate_trace(trace)
            if not is_valid:
                report.validation_errors.append({
                    "trace_id": trace.get("id", "unknown"),
                    "error": error,
                })

        # Log warnings for high null rates
        for field, count in report.null_fields.items():
            rate = count / max(report.total_records, 1)
            if rate > self.NULL_THRESHOLD:
                logger.warning(f"High null rate for field '{field}': {rate:.1%}")

        return report


class SchemaDriftDetector:
    """Detects schema drift by comparing field distributions over time.

    Stores baseline statistics and compares against sliding windows
    to detect changes in data distribution.
    """

    def __init__(self, baseline: Optional[Dict[str, Any]] = None):
        self.baseline = baseline or {}

    def compute_statistics(self, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute summary statistics for a set of traces."""
        stats = {
            "total": len(traces),
            "fields": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not traces:
            return stats

        fields = ["prompt", "completion", "model_id", "user_id"]
        for field in fields:
            values = [t.get(field) for t in traces if t.get(field) is not None]
            if not values:
                continue
            field_stats = {
                "present": len(values),
                "null_count": len(traces) - len(values),
                "null_rate": round((len(traces) - len(values)) / len(traces), 4),
                "avg_length": round(sum(len(v) for v in values) / len(values), 2),
            }
            # Unique values for categorical fields
            if field in ("model_id", "user_id"):
                unique = set(values)
                field_stats["unique_values"] = len(unique)
                field_stats["cardinality"] = round(len(unique) / len(values), 4)

            stats["fields"][field] = field_stats

        return stats

    def detect_drift(self, current: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect drift between baseline and current statistics.

        Returns a list of drift alerts, each containing the field name,
        metric that drifted, and severity.
        """
        alerts = []
        if not self.baseline or not current:
            return alerts

        for field, current_stats in current.get("fields", {}).items():
            baseline_stats = self.baseline.get("fields", {}).get(field)
            if not baseline_stats:
                continue

            # Check null rate drift
            current_null = current_stats.get("null_rate", 0)
            baseline_null = baseline_stats.get("null_rate", 0)
            if baseline_null > 0 and abs(current_null - baseline_null) / baseline_null > 0.5:
                alerts.append({
                    "field": field,
                    "metric": "null_rate",
                    "baseline": baseline_null,
                    "current": current_null,
                    "severity": "warning",
                    "message": f"Null rate for '{field}' changed from {baseline_null:.2%} to {current_null:.2%}",
                })

            # Check average length drift
            current_len = current_stats.get("avg_length", 0)
            baseline_len = baseline_stats.get("avg_length", 0)
            if baseline_len > 0 and abs(current_len - baseline_len) / baseline_len > 0.3:
                alerts.append({
                    "field": field,
                    "metric": "avg_length",
                    "baseline": baseline_len,
                    "current": current_len,
                    "severity": "info",
                    "message": f"Average length for '{field}' changed from {baseline_len:.1f} to {current_len:.1f}",
                })

        return alerts

    def update_baseline(self, stats: Dict[str, Any]) -> None:
        """Update the baseline with new statistics (rolling window)."""
        if not self.baseline:
            self.baseline = stats
        else:
            # Exponential moving average for smooth baseline updates
            alpha = 0.3
            for field, current_stats in stats.get("fields", {}).items():
                if field in self.baseline.get("fields", {}):
                    baseline_stats = self.baseline["fields"][field]
                    for metric in ("null_rate", "avg_length"):
                        if metric in current_stats and metric in baseline_stats:
                            baseline_stats[metric] = (
                                alpha * current_stats[metric]
                                + (1 - alpha) * baseline_stats[metric]
                            )
                else:
                    if "fields" not in self.baseline:
                        self.baseline["fields"] = {}
                    self.baseline["fields"][field] = current_stats
            self.baseline["total"] = stats.get("total", 0)

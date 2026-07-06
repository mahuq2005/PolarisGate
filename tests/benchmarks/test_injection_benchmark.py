"""Prompt injection detection accuracy benchmark for PolarisGate.

Validates injection detection data quality, benign vs. injection
classification metrics, obfuscated injection structure, category coverage,
and threshold configuration — without requiring a live gateway.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.metrics import MetricsEngine, GateMetrics  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_LABELED_DIR = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "injection"
_THRESHOLDS_PATH = _PROJECT_ROOT / "tests" / "thresholds.yaml"


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


@pytest.fixture(scope="module")
def inj_data() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "injection": _load_jsonl(_LABELED_DIR / "injection_200.jsonl"),
        "benign": _load_jsonl(_LABELED_DIR / "benign_200.jsonl"),
        "obfuscated": _load_jsonl(_LABELED_DIR / "obfuscated_100.jsonl"),
    }


@pytest.fixture(scope="module")
def inj_thresholds() -> Dict[str, Any]:
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("injection", {})


class TestInjectionAccuracy:
    """Accuracy benchmarks for PolarisGate prompt injection detection."""

    def test_labeled_data_loaded(self, inj_data):
        assert len(inj_data["injection"]) == 20
        assert len(inj_data["benign"]) == 25
        assert len(inj_data["obfuscated"]) == 10

    def test_label_structure(self, inj_data):
        for key, rows in inj_data.items():
            for row in rows:
                assert "id" in row, f"{key}: missing id"
                assert "text" in row, f"{key}: missing text"
                assert "label" in row, f"{key}: missing label"
                assert isinstance(row["label"]["injection_detected"], bool), f"{key}: not bool"

    def test_injection_all_detected(self, inj_data):
        for row in inj_data["injection"]:
            assert row["label"]["injection_detected"] is True, f"{row['id']}: not True"

    def test_benign_all_clean(self, inj_data):
        for row in inj_data["benign"]:
            assert row["label"]["injection_detected"] is False, f"{row['id']}: not False"

    def test_perfect_classifier_metrics(self, inj_data, inj_thresholds):
        all_rows = inj_data["injection"] + inj_data["benign"]
        y_true = [1 if r["label"]["injection_detected"] else 0 for r in all_rows]
        y_pred = list(y_true)

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["false_positive_rate"] == 0.0
        assert d["false_negative_rate"] == 0.0

        assert d["precision"] >= inj_thresholds.get("min_precision", 0.0)
        assert d["recall"] >= inj_thresholds.get("min_recall", 0.0)
        assert d["f1_score"] >= inj_thresholds.get("min_f1", 0.0)
        assert d["false_positive_rate"] <= inj_thresholds.get("max_false_positive_rate", 1.0)
        assert d["false_negative_rate"] <= inj_thresholds.get("max_false_negative_rate", 1.0)

    def test_false_positive_rate_scenario(self, inj_data):
        """All benign flagged as injection → FP rate = 1.0."""
        y_true = [0] * len(inj_data["benign"])
        y_pred = [1] * len(inj_data["benign"])
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_positive_rate == 1.0
        assert metrics.confusion_matrix.false_positive == len(inj_data["benign"])

    def test_false_negative_rate_scenario(self, inj_data):
        """All injections missed → FN rate = 1.0."""
        y_true = [1] * len(inj_data["injection"])
        y_pred = [0] * len(inj_data["injection"])
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_negative_rate == 1.0
        assert metrics.confusion_matrix.false_negative == len(inj_data["injection"])

    def test_obfuscated_injection_structure(self, inj_data):
        """All 10 obfuscated examples have type field and injection_detected=True."""
        obf = inj_data["obfuscated"]
        assert len(obf) == 10
        for row in obf:
            assert "type" in row, f"{row['id']}: missing type"
            assert row["label"]["injection_detected"] is True, f"{row['id']}: not True"

    def test_injection_categories(self, inj_data):
        """Injection examples have category field with distinct values."""
        cats = {r.get("category", "") for r in inj_data["injection"] if "category" in r}
        assert len(cats) >= 5, f"Expected >=5 categories, got {len(cats)}"

    def test_threshold_configuration(self, inj_thresholds):
        """Injection thresholds have all required keys."""
        required = ["min_precision", "min_recall", "min_f1", "max_false_positive_rate", "max_false_negative_rate"]
        for key in required:
            assert key in inj_thresholds, f"Missing threshold: {key}"
            val = inj_thresholds[key]
            assert 0.0 <= val <= 1.0, f"{key}={val} not in [0,1]"

    def test_benign_borderline_cases(self, inj_data):
        """Borderline benign cases (researcher questions) are labeled False."""
        borderline_ids = {"inj_ben_021", "inj_ben_022", "inj_ben_023", "inj_ben_024", "inj_ben_025"}
        found = 0
        for row in inj_data["benign"]:
            if row["id"] in borderline_ids:
                assert row["label"]["injection_detected"] is False, f"{row['id']}: borderline mislabeled"
                found += 1
        assert found == 5, f"Expected 5 borderline benign, found {found}"

    def test_obfuscated_types_distinct(self, inj_data):
        """All 10 obfuscated examples have distinct types."""
        types = [r["type"] for r in inj_data["obfuscated"]]
        assert len(types) == len(set(types)), f"Duplicate types in obfuscated: {types}"

    def test_confusion_matrix_invariants(self, inj_data):
        rows = inj_data["injection"] + inj_data["benign"]
        y_true = [1 if r["label"]["injection_detected"] else 0 for r in rows]
        y_pred = list(y_true)
        cm = MetricsEngine.compute_confusion_matrix(y_true, y_pred)
        assert cm.total == len(rows)
        assert cm.true_positive == len(inj_data["injection"])
        assert cm.true_negative == len(inj_data["benign"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
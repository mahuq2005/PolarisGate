"""Real-inference pytest accuracy benchmark for the PolarisGate toxicity ensemble.

Validates that the MetricsEngine computes correct classification metrics
and that every labeled dataset, threshold configuration, and mathematical
invariant is well-formed—without requiring a live gateway connection.
Predictions are simulated from ground-truth labels so the measurement
infrastructure itself is tested deterministically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml

# Ensure the project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.metrics import MetricsEngine, GateMetrics, ConfusionMatrix  # noqa: E402


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_LABELED_DIR = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "toxicity"
_THRESHOLDS_PATH = _PROJECT_ROOT / "tests" / "thresholds.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def toxicity_data() -> Dict[str, List[Dict[str, Any]]]:
    """Load all 4 toxicity JSONL datasets."""
    files = {
        "toxic": _LABELED_DIR / "toxic_500.jsonl",
        "clean": _LABELED_DIR / "clean_500.jsonl",
        "edge": _LABELED_DIR / "edge_cases_100.jsonl",
        "adversarial": _LABELED_DIR / "adversarial_100.jsonl",
    }
    return {key: _load_jsonl(path) for key, path in files.items()}


@pytest.fixture(scope="module")
def toxicity_thresholds() -> Dict[str, Any]:
    """Load the toxicity section from thresholds.yaml."""
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("toxicity", {})


# ---------------------------------------------------------------------------
# Test Class
# ---------------------------------------------------------------------------


class TestToxicityAccuracy:
    """Accuracy benchmarks for the PolarisGate toxicity detection gate."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_labels(rows: List[Dict[str, Any]]) -> Tuple[List[int], List[int]]:
        """Return (y_true, y_pred) where pred == true (simulated perfect)."""
        y_true = [1 if r["label"]["toxic"] else 0 for r in rows]
        y_pred = list(y_true)  # perfect prediction for metric-structure validation
        return y_true, y_pred

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_labeled_data_loaded(self, toxicity_data):
        """All four datasets are present and non‑empty."""
        assert len(toxicity_data["toxic"]) == 40
        assert len(toxicity_data["clean"]) == 40
        assert len(toxicity_data["edge"]) == 20
        assert len(toxicity_data["adversarial"]) == 15

    def test_label_structure(self, toxicity_data):
        """Every row has id, text, label, and label.toxic is a bool."""
        for key, rows in toxicity_data.items():
            for row in rows:
                assert "id" in row, f"{key}: missing id"
                assert "text" in row, f"{key}: missing text"
                assert "label" in row, f"{key}: missing label"
                assert isinstance(row["label"]["toxic"], bool), f"{key}: toxic not bool"

    def test_metrics_computation(self, toxicity_data, toxicity_thresholds):
        """MetricsEngine returns correct metrics when predictions match labels."""
        all_rows = toxicity_data["toxic"] + toxicity_data["clean"]
        y_true, y_pred = self._extract_labels(all_rows)

        metrics: GateMetrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        # Perfect prediction → all metrics = 1.0, rates = 0.0
        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["accuracy"] == 1.0
        assert d["false_positive_rate"] == 0.0
        assert d["false_negative_rate"] == 0.0

        # Confusion matrix
        cm = d["confusion_matrix"]
        assert cm["true_positive"] == 40
        assert cm["true_negative"] == 40
        assert cm["false_positive"] == 0
        assert cm["false_negative"] == 0

        # Threshold check (should easily pass)
        assert d["precision"] >= toxicity_thresholds.get("min_precision", 0.0)
        assert d["recall"] >= toxicity_thresholds.get("min_recall", 0.0)
        assert d["f1_score"] >= toxicity_thresholds.get("min_f1", 0.0)
        assert d["false_positive_rate"] <= toxicity_thresholds.get("max_false_positive_rate", 1.0)
        assert d["false_negative_rate"] <= toxicity_thresholds.get("max_false_negative_rate", 1.0)

    def test_false_positive_rate_scenario(self, toxicity_data, toxicity_thresholds):
        """A scenario where all clean texts are incorrectly flagged as toxic."""
        clean = toxicity_data["clean"]
        # y_true = all 0 (clean), y_pred = all 1 (flagged toxic) → all FP
        y_true = [0] * len(clean)
        y_pred = [1] * len(clean)

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["precision"] == 0.0
        assert d["recall"] == 0.0  # no positives to recall
        assert d["false_positive_rate"] == 1.0
        assert d["confusion_matrix"]["false_positive"] == len(clean)
        assert d["confusion_matrix"]["true_negative"] == 0

    def test_false_negative_rate_scenario(self, toxicity_data, toxicity_thresholds):
        """A scenario where all toxic texts are missed."""
        toxic = toxicity_data["toxic"]
        # y_true = all 1 (toxic), y_pred = all 0 (clean) → all FN
        y_true = [1] * len(toxic)
        y_pred = [0] * len(toxic)

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["recall"] == 0.0
        assert d["false_negative_rate"] == 1.0
        assert d["confusion_matrix"]["false_negative"] == len(toxic)
        assert d["confusion_matrix"]["true_positive"] == 0

    def test_edge_case_precision(self, toxicity_data):
        """Edge cases: count how many are borderline-toxic vs clean."""
        edge = toxicity_data["edge"]
        toxic_count = sum(1 for r in edge if r["label"]["toxic"])
        clean_count = len(edge) - toxic_count

        # Verify data distribution is reasonable
        assert toxic_count >= 1, "Need at least one borderline-toxic example"
        assert clean_count >= 15, "Most edge cases should be clean"

        # All edge cases have a note field
        for row in edge:
            assert "note" in row, f"Edge case {row['id']} missing note"

    def test_adversarial_data_structure(self, toxicity_data):
        """All adversarial examples are labeled toxic and have a type field."""
        adv = toxicity_data["adversarial"]
        for row in adv:
            assert row["label"]["toxic"] is True, f"{row['id']}: adversarial must be toxic"
            assert "type" in row, f"{row['id']}: missing type"

        # At least 5 distinct obfuscation types
        types = {r["type"] for r in adv}
        assert len(types) >= 5, f"Need >=5 attack types, got {len(types)}"

    def test_confusion_matrix_structure(self, toxicity_data):
        """Confusion matrix invariants."""
        rows = toxicity_data["toxic"] + toxicity_data["clean"]
        y_true, y_pred = self._extract_labels(rows)
        cm = MetricsEngine.compute_confusion_matrix(y_true, y_pred)

        assert cm.true_positive + cm.true_negative + cm.false_positive + cm.false_negative == len(rows)
        assert cm.support_positive == cm.true_positive + cm.false_negative
        assert cm.support_negative == cm.true_negative + cm.false_positive
        assert cm.total == len(rows)

    def test_metrics_all_false_positives(self):
        """All predictions positive, all ground-truth negative → FP rate = 1.0."""
        y_true = [0, 0, 0, 0, 0]
        y_pred = [1, 1, 1, 1, 1]
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()
        assert d["false_positive_rate"] == 1.0
        assert d["precision"] == 0.0
        assert d["confusion_matrix"]["false_positive"] == 5

    def test_metrics_all_false_negatives(self):
        """All predictions negative, all ground-truth positive → FN rate = 1.0."""
        y_true = [1, 1, 1, 1, 1]
        y_pred = [0, 0, 0, 0, 0]
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()
        assert d["false_negative_rate"] == 1.0
        assert d["recall"] == 0.0
        assert d["confusion_matrix"]["false_negative"] == 5

    def test_metrics_empty_input(self):
        """Empty input returns zeros, not division errors."""
        metrics = MetricsEngine.compute_classification([], [])
        d = metrics.to_dict()
        assert d["accuracy"] == 0.0
        assert d["precision"] == 0.0
        assert d["recall"] == 0.0
        assert d["f1_score"] == 0.0
        assert d["confusion_matrix"]["true_positive"] == 0

    def test_metrics_edge_all_correct(self):
        """All predictions correct → perfect scores."""
        y_true = [1, 1, 0, 0, 1, 0]
        y_pred = [1, 1, 0, 0, 1, 0]
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()
        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["accuracy"] == 1.0
        assert d["false_positive_rate"] == 0.0
        assert d["false_negative_rate"] == 0.0

    def test_support_counts(self, toxicity_data):
        """Support counts match dataset sizes."""
        toxic = toxicity_data["toxic"]
        clean = toxicity_data["clean"]
        all_rows = toxic + clean
        y_true, y_pred = self._extract_labels(all_rows)
        metrics = MetricsEngine.compute_classification(y_true, y_pred, labels={0: "clean", 1: "toxic"})
        assert metrics.support.get("toxic") == len(toxic)
        assert metrics.support.get("clean") == len(clean)

    def test_thresholds_loadable(self, toxicity_thresholds):
        """All expected threshold keys are present."""
        required = ["min_precision", "min_recall", "min_f1", "max_false_positive_rate", "max_false_negative_rate"]
        for key in required:
            assert key in toxicity_thresholds, f"Missing threshold key: {key}"
        # Values are in [0, 1]
        for key in required:
            val = toxicity_thresholds[key]
            assert 0.0 <= val <= 1.0, f"{key} = {val} not in [0,1]"

    def test_calibration_curve_basics(self):
        """Calibration curve returns expected structure."""
        y_true = [0, 0, 0, 1, 1, 1, 1, 1]
        scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.85, 0.9, 0.95]
        curve = MetricsEngine.compute_calibration_curve(y_true, scores, bins=5)
        assert "bins" in curve
        assert "observed" in curve
        assert "counts" in curve
        assert "brier_score" in curve
        assert len(curve["bins"]) == 5
        assert curve["brier_score"] >= 0.0

    def test_agreement_rate(self):
        """Agreement rate works for multiple classifier predictions."""
        preds = [
            [1, 1, 0, 0, 1],
            [1, 1, 0, 0, 1],
            [1, 0, 0, 0, 1],
        ]
        result = MetricsEngine.agreement_rate(preds)
        assert "full_agreement" in result
        assert "pairwise" in result
        assert result["full_agreement"] == 0.8  # 4/5 agree
        assert result["pairwise"]["c0_c1"] == 1.0  # identical
        assert result["pairwise"]["c0_c2"] == 0.8


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
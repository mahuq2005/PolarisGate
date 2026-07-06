"""Hallucination detection accuracy benchmark for PolarisGate.

Validates hallucination detection data quality, cascade stage metrics,
and the MetricsEngine on factual vs. hallucinated classification scenarios.
All tests run without a live gateway.
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

_LABELED_DIR = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "hallucination"
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
def hal_data() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "factual": _load_jsonl(_LABELED_DIR / "factual_500.jsonl"),
        "hallucinated": _load_jsonl(_LABELED_DIR / "hallucinated_500.jsonl"),
        "ambiguous": _load_jsonl(_LABELED_DIR / "ambiguous_100.jsonl"),
        "entity": _load_jsonl(_LABELED_DIR / "entity_level_100.jsonl"),
    }


@pytest.fixture(scope="module")
def hal_thresholds() -> Dict[str, Any]:
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("hallucination", {})


class TestHallucinationAccuracy:
    """Accuracy benchmarks for PolarisGate hallucination detection cascade."""

    def test_labeled_data_integrity(self, hal_data):
        """Factual all hallucinated=False, hallucinated all True."""
        assert len(hal_data["factual"]) == 30
        assert len(hal_data["hallucinated"]) == 30
        assert len(hal_data["ambiguous"]) == 10
        assert len(hal_data["entity"]) == 10

        for row in hal_data["factual"]:
            assert row["label"]["hallucinated"] is False, f"{row['id']}: factual labeled True"

        for row in hal_data["hallucinated"]:
            assert row["label"]["hallucinated"] is True, f"{row['id']}: hallucinated labeled False"

    def test_perfect_classifier_metrics(self, hal_data, hal_thresholds):
        """Perfect prediction on factual+hallucinated yields FP=0, FN=0."""
        all_rows = hal_data["factual"] + hal_data["hallucinated"]
        y_true = [1 if r["label"]["hallucinated"] else 0 for r in all_rows]
        y_pred = list(y_true)

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["false_positive_rate"] == 0.0
        assert d["false_negative_rate"] == 0.0

        assert d["precision"] >= hal_thresholds.get("min_precision", 0.0)
        assert d["recall"] >= hal_thresholds.get("min_recall", 0.0)
        assert d["f1_score"] >= hal_thresholds.get("min_f1", 0.0)
        assert d["false_positive_rate"] <= hal_thresholds.get("max_false_positive_rate", 1.0)
        assert d["false_negative_rate"] <= hal_thresholds.get("max_false_negative_rate", 1.0)

    def test_false_positive_rate_scenario(self, hal_data):
        """All factual flagged as hallucinated → FP rate = 1.0."""
        y_true = [0] * len(hal_data["factual"])
        y_pred = [1] * len(hal_data["factual"])
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_positive_rate == 1.0
        assert metrics.confusion_matrix.false_positive == len(hal_data["factual"])

    def test_false_negative_rate_scenario(self, hal_data):
        """All hallucinated missed → FN rate = 1.0."""
        y_true = [1] * len(hal_data["hallucinated"])
        y_pred = [0] * len(hal_data["hallucinated"])
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_negative_rate == 1.0
        assert metrics.confusion_matrix.false_negative == len(hal_data["hallucinated"])

    def test_ambiguous_data_structure(self, hal_data):
        """Ambiguous all labeled hallucinated=False with note field."""
        amb = hal_data["ambiguous"]
        for row in amb:
            assert row["label"]["hallucinated"] is False, f"{row['id']}: ambiguous labeled True"
            assert "note" in row, f"{row['id']}: ambiguous missing note"

    def test_entity_level_data_structure(self, hal_data):
        """Entity-level has both True and False labels with note field."""
        ent = hal_data["entity"]
        labels = [r["label"]["hallucinated"] for r in ent]
        assert True in labels, "Entity data missing hallucinated=True examples"
        assert False in labels, "Entity data missing factual examples"
        for row in ent:
            assert "note" in row, f"{row['id']}: entity missing note"

    def test_cascade_stage_thresholds(self, hal_thresholds):
        """Hallucination thresholds define 4 cascade stages with min_recall values."""
        stages = hal_thresholds.get("stages", {})
        assert len(stages) >= 4, f"Expected >=4 stages, got {len(stages)}"

        expected = ["stage_1_prefilter", "stage_2_nli_ensemble", "stage_3_self_debate", "stage_4_dual_debate"]
        for stage in expected:
            assert stage in stages, f"Missing stage: {stage}"
            assert "min_recall" in stages[stage], f"{stage}: missing min_recall"
            val = stages[stage]["min_recall"]
            assert 0.0 <= val <= 1.0, f"{stage}.min_recall={val} not in [0,1]"

        # Stages should have increasing min_recall (cumulative)
        recalls = [stages[s]["min_recall"] for s in expected]
        for i in range(1, len(recalls)):
            assert recalls[i] >= recalls[i - 1], (
                f"Stage {i+1} recall ({recalls[i]}) < stage {i} ({recalls[i-1]})"
            )

    def test_debate_consistency_threshold(self, hal_thresholds):
        """min_debate_consistency threshold exists and is in [0, 1]."""
        assert "min_debate_consistency" in hal_thresholds, "Missing min_debate_consistency"
        val = hal_thresholds["min_debate_consistency"]
        assert 0.0 <= val <= 1.0, f"min_debate_consistency={val} not in [0,1]"

    def test_metrics_on_all_hallucination_true(self):
        """All positives: recall=1.0, FN=0."""
        y_true = [1, 1, 1, 1]
        y_pred = [1, 1, 1, 1]
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.recall == 1.0
        assert metrics.false_negative_rate == 0.0
        assert metrics.confusion_matrix.false_negative == 0

    def test_metrics_on_all_hallucination_false(self):
        """All negatives: FP=0, false_positive_rate=0."""
        y_true = [0, 0, 0, 0]
        y_pred = [0, 0, 0, 0]
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_positive_rate == 0.0
        assert metrics.confusion_matrix.false_positive == 0
        assert metrics.specificity == 1.0

    def test_mixed_scenario_partial_errors(self):
        """2 TP, 1 FP, 1 FN → correct metric computation."""
        y_true = [1, 1, 0, 0]
        y_pred = [1, 0, 0, 1]  # one FN, one FP
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["precision"] == 0.5  # 1 TP / (1 TP + 1 FP)
        assert d["recall"] == 0.5     # 1 TP / (2 positives)
        assert d["accuracy"] == 0.5   # 2/4 correct
        assert d["false_positive_rate"] == 0.5  # 1 FP / 2 negatives
        assert d["false_negative_rate"] == 0.5  # 1 FN / 2 positives
        cm = d["confusion_matrix"]
        assert cm["true_positive"] == 1
        assert cm["true_negative"] == 1
        assert cm["false_positive"] == 1
        assert cm["false_negative"] == 1

    def test_factual_data_source_field(self, hal_data):
        """Factual examples have source field for domain tracking."""
        sources = {r.get("source") for r in hal_data["factual"] if "source" in r}
        assert len(sources) >= 5, f"Need >=5 source domains, got {len(sources)}"

    def test_hallucinated_data_category_field(self, hal_data):
        """Hallucinated examples have category field for error type."""
        categories = {r.get("category") for r in hal_data["hallucinated"] if "category" in r}
        assert len(categories) >= 5, f"Need >=5 error categories, got {len(categories)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
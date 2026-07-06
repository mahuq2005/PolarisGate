"""PII detection accuracy benchmark for PolarisGate.

Validates PII detection data quality, per-entity metrics computation,
and threshold configuration correctness.  All tests run without a live
gateway by simulating predictions from labeled data.
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
_LABELED_DIR = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "pii"
_THRESHOLDS_PATH = _PROJECT_ROOT / "tests" / "thresholds.yaml"

# Known PII entity types
_ENTITY_TYPES = ["SSN", "SIN", "EMAIL", "PHONE", "CREDIT_CARD", "IP_ADDRESS", "HEALTH_CARD"]


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pii_data() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "positive": _load_jsonl(_LABELED_DIR / "pii_positive_500.jsonl"),
        "negative": _load_jsonl(_LABELED_DIR / "pii_negative_500.jsonl"),
        "contextual": _load_jsonl(_LABELED_DIR / "contextual_100.jsonl"),
        "fragmented": _load_jsonl(_LABELED_DIR / "fragmented_100.jsonl"),
    }


@pytest.fixture(scope="module")
def pii_thresholds() -> Dict[str, Any]:
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("pii", {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPIIAccuracy:
    """Accuracy benchmarks for PolarisGate PII detection gate."""

    # ------------------------------------------------------------------
    # data-integrity checks
    # ------------------------------------------------------------------

    def test_data_loaded(self, pii_data):
        assert len(pii_data["positive"]) == 30
        assert len(pii_data["negative"]) == 30
        assert len(pii_data["contextual"]) == 10
        assert len(pii_data["fragmented"]) == 10

    def test_label_structure(self, pii_data):
        for key, rows in pii_data.items():
            for row in rows:
                assert "id" in row, f"{key}: missing id"
                assert "text" in row, f"{key}: missing text"
                assert "label" in row, f"{key}: missing label"
                lbl = row["label"]
                assert isinstance(lbl["pii_detected"], bool), f"{key}: pii_detected not bool"

    def test_positive_all_have_pii(self, pii_data):
        for row in pii_data["positive"]:
            assert row["label"]["pii_detected"] is True, f"{row['id']}: positive has pii_detected=False"
            assert "pii_types" in row["label"], f"{row['id']}: missing pii_types"
            assert len(row["label"]["pii_types"]) >= 1, f"{row['id']}: empty pii_types"

    def test_negative_all_clean(self, pii_data):
        for row in pii_data["negative"]:
            assert row["label"]["pii_detected"] is False, f"{row['id']}: negative has pii_detected=True"
            types = row["label"].get("pii_types", [])
            assert types == [], f"{row['id']}: negative has non-empty pii_types={types}"

    # ------------------------------------------------------------------
    # metrics tests
    # ------------------------------------------------------------------

    def test_precision_recall_perfect(self, pii_data, pii_thresholds):
        """Perfect classifier on positive+negative corpus."""
        pos = pii_data["positive"]
        neg = pii_data["negative"]
        all_rows = pos + neg
        y_true = [1 if r["label"]["pii_detected"] else 0 for r in all_rows]
        y_pred = list(y_true)  # perfect prediction

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        d = metrics.to_dict()

        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["false_positive_rate"] == 0.0
        assert d["false_negative_rate"] == 0.0

        # Threshold compliance
        assert d["precision"] >= pii_thresholds.get("min_precision", 0.0)
        assert d["recall"] >= pii_thresholds.get("min_recall", 0.0)
        assert d["f1_score"] >= pii_thresholds.get("min_f1", 0.0)
        assert d["false_positive_rate"] <= pii_thresholds.get("max_false_positive_rate", 1.0)
        assert d["false_negative_rate"] <= pii_thresholds.get("max_false_negative_rate", 1.0)

    def test_false_positive_rate_scenario(self, pii_data):
        """All negatives flagged as PII → FP rate = 1.0."""
        neg = pii_data["negative"]
        y_true = [0] * len(neg)
        y_pred = [1] * len(neg)
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_positive_rate == 1.0
        assert metrics.confusion_matrix.false_positive == len(neg)

    def test_false_negative_rate_scenario(self, pii_data):
        """All positives missed → FN rate = 1.0."""
        pos = pii_data["positive"]
        y_true = [1] * len(pos)
        y_pred = [0] * len(pos)
        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.false_negative_rate == 1.0
        assert metrics.confusion_matrix.false_negative == len(pos)

    # ------------------------------------------------------------------
    # per-entity coverage
    # ------------------------------------------------------------------

    def test_per_entity_data_coverage(self, pii_data):
        """Each entity type appears in at least 3 positive examples."""
        entity_counts: Dict[str, int] = {et: 0 for et in _ENTITY_TYPES}
        for row in pii_data["positive"]:
            for et in row["label"]["pii_types"]:
                if et in entity_counts:
                    entity_counts[et] += 1

        for et, count in entity_counts.items():
            assert count >= 3, f"{et}: only {count} examples, need >= 3"

    def test_per_entity_metrics_computation(self, pii_data):
        """Per-class metrics via MetricsEngine."""
        rows = pii_data["positive"] + pii_data["negative"]
        # Build y_true with class indices: 0=no_PII, 1=SSN, 2=SIN, ...
        type_to_idx = {et: i + 1 for i, et in enumerate(_ENTITY_TYPES)}
        type_to_idx["NONE"] = 0

        y_true: List[int] = []
        y_pred: List[int] = []
        for row in rows:
            types = row["label"].get("pii_types", [])
            if not types:
                y_true.append(0)
                y_pred.append(0)
            else:
                idx = type_to_idx.get(types[0], 0)
                y_true.append(idx)
                y_pred.append(idx)

        class_names = ["NONE"] + _ENTITY_TYPES
        results = MetricsEngine.compute_per_class_metrics(y_true, y_pred, class_names)

        # Each entity type that exists in data should have perfect metrics
        for et in _ENTITY_TYPES:
            if et in results:
                assert results[et].precision in (0.0, 1.0), f"{et}: precision not 0/1"
                assert results[et].recall in (0.0, 1.0), f"{et}: recall not 0/1"

    def test_multi_entity_examples(self, pii_data):
        """Examples with multiple PII types are well-formed."""
        multi = [r for r in pii_data["positive"] if len(r["label"]["pii_types"]) >= 2]
        assert len(multi) >= 5, f"Need >=5 multi-type examples, got {len(multi)}"
        for row in multi:
            types = row["label"]["pii_types"]
            assert len(types) == len(set(types)), f"{row['id']}: duplicate types"
            for t in types:
                assert t in _ENTITY_TYPES, f"{row['id']}: unknown type {t}"

    # ------------------------------------------------------------------
    # contextual data
    # ------------------------------------------------------------------

    def test_contextual_data_structure(self, pii_data):
        """Contextual examples have context field and pii_detected=True."""
        ctx = pii_data["contextual"]
        assert len(ctx) == 10
        for row in ctx:
            assert "context" in row, f"{row['id']}: missing context"
            assert row["context"] in ("medical", "financial", "general"), f"{row['id']}: bad context"
            assert row["label"]["pii_detected"] is True, f"{row['id']}: contextual not pii_detected"

        # Both medical and financial contexts are represented
        contexts = {r["context"] for r in ctx}
        assert "medical" in contexts
        assert "financial" in contexts

    # ------------------------------------------------------------------
    # fragmented data
    # ------------------------------------------------------------------

    def test_fragmented_data_structure(self, pii_data):
        """Fragmented examples have note field and pii_detected=True."""
        frag = pii_data["fragmented"]
        assert len(frag) == 10
        for row in frag:
            assert "note" in row, f"{row['id']}: missing note"
            assert row["label"]["pii_detected"] is True, f"{row['id']}: fragmented not detected"
            assert len(row["label"].get("pii_types", [])) >= 1, f"{row['id']}: no pii_types"

    # ------------------------------------------------------------------
    # threshold validation
    # ------------------------------------------------------------------

    def test_threshold_configuration(self, pii_thresholds):
        """PII thresholds have all required keys including per-entity."""
        required = ["min_precision", "min_recall", "min_f1", "max_false_positive_rate", "max_false_negative_rate"]
        for key in required:
            assert key in pii_thresholds, f"Missing threshold: {key}"

        # Per-entity thresholds
        entities = pii_thresholds.get("entities", {})
        assert len(entities) > 0, "No per-entity thresholds"
        for et in _ENTITY_TYPES:
            if et not in entities:
                continue  # some entities optional
            e_cfg = entities[et]
            assert "min_precision" in e_cfg, f"entities.{et}: missing min_precision"
            assert "min_recall" in e_cfg, f"entities.{et}: missing min_recall"
            assert 0.0 <= e_cfg["min_precision"] <= 1.0
            assert 0.0 <= e_cfg["min_recall"] <= 1.0

    def test_confusion_matrix_invariants(self, pii_data):
        """Confusion matrix totals match input sizes."""
        rows = pii_data["positive"] + pii_data["negative"]
        y_true = [1 if r["label"]["pii_detected"] else 0 for r in rows]
        y_pred = list(y_true)

        cm = MetricsEngine.compute_confusion_matrix(y_true, y_pred)
        assert cm.total == len(rows)
        assert cm.true_positive + cm.false_negative == len(pii_data["positive"])
        assert cm.true_negative + cm.false_positive == len(pii_data["negative"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
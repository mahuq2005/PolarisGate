"""Adversarial robustness tests for PolarisGate.

Validates that adversarial datasets are well-constructed with diverse
attack vectors (leetspeak, homoglyphs, zero-width, whitespace, separators,
concatenation, obfuscated injection), and verifies that the detection rate
computation via MetricsEngine works correctly against thresholds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.metrics import MetricsEngine, GateMetrics  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_TOXICITY_ADV = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "toxicity" / "adversarial_100.jsonl"
_INJECTION_OBF = _PROJECT_ROOT / "tests" / "test_data" / "labeled" / "injection" / "obfuscated_100.jsonl"
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
def tox_adv() -> List[Dict[str, Any]]:
    return _load_jsonl(_TOXICITY_ADV)


@pytest.fixture(scope="module")
def inj_obf() -> List[Dict[str, Any]]:
    return _load_jsonl(_INJECTION_OBF)


@pytest.fixture(scope="module")
def adv_thresholds() -> Dict[str, Any]:
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("adversarial", {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdversarialRobustness:
    """Validate adversarial test data coverage and detection-rate computation."""

    def test_adversarial_data_coverage(self, tox_adv):
        """At least 8 distinct attack vectors in toxicity adversarial data."""
        types = {r.get("type", "") for r in tox_adv}
        expected = {"leetspeak", "homoglyphs", "zero_width", "whitespace", "mixed_unicode", "zalgo_text", "separator", "concat"}
        missing = expected - types
        assert len(missing) == 0, f"Missing attack vectors: {missing}"
        assert len(types) >= 8, f"Expected >=8 attack vectors, got {len(types)}"

    def test_attack_vector_labels(self, tox_adv, inj_obf):
        """All adversarial examples are labeled positive."""
        for row in tox_adv:
            assert row["label"]["toxic"] is True, f"{row['id']}: toxic not True"
        for row in inj_obf:
            assert row["label"]["injection_detected"] is True, f"{row['id']}: injection not True"

    def test_adversarial_detection_rate_computation(self, tox_adv, adv_thresholds):
        """Simulate >70% detection rate, verify it meets thresholds.yaml."""
        # Simulate: ceil(15 * 0.7) = 11 of 15 = 0.7333 which exceeds 0.70
        import math
        y_true = [1] * len(tox_adv)
        detected = math.ceil(len(tox_adv) * 0.7)  # 11 of 15
        missed = len(tox_adv) - detected
        y_pred = [1] * detected + [0] * missed

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.recall == pytest.approx(0.7, abs=0.1)

        min_detection = adv_thresholds.get("min_toxicity_detection_rate", 0.0)
        assert metrics.recall >= min_detection, (
            f"Recall {metrics.recall} < min_threshold {min_detection}"
        )

    def test_zero_width_characters_present(self, tox_adv):
        """Adversarial data contains zero-width space (U+200B)."""
        zero_width = [r for r in tox_adv if r.get("type") == "zero_width"]
        assert len(zero_width) >= 2, f"Expected >=2 zero_width examples, got {len(zero_width)}"
        for row in zero_width:
            assert "\u200B" in row["text"], f"{row['id']}: missing U+200B"

    def test_homoglyphs_present(self, tox_adv):
        """Homoglyph examples contain Unicode math symbols."""
        homoglyphs = [r for r in tox_adv if r.get("type") == "homoglyphs"]
        assert len(homoglyphs) >= 2
        for row in homoglyphs:
            # At least one character outside ASCII range
            has_non_ascii = any(ord(c) > 127 for c in row["text"])
            assert has_non_ascii, f"{row['id']}: no non-ASCII chars"

    def test_leetspeak_patterns(self, tox_adv):
        """Leetspeak examples contain digit-for-letter substitutions."""
        leet = [r for r in tox_adv if r.get("type") == "leetspeak"]
        assert len(leet) >= 3
        for row in leet:
            has_digit = any(c.isdigit() for c in row["text"])
            assert has_digit, f"{row['id']}: no digits in leetspeak"

    def test_obfuscated_injection_data(self, inj_obf):
        """Injection obfuscated dataset has 10 examples with distinct types."""
        assert len(inj_obf) == 10
        types = {r.get("type", "") for r in inj_obf}
        assert len(types) == 10, f"Expected 10 distinct types, got {len(types)}"

    def test_concatenation_no_space(self, tox_adv):
        """CamelCase/concat examples exist."""
        concat = [r for r in tox_adv if r.get("type") == "concat"]
        assert len(concat) >= 2
        for row in concat:
            # Text has uppercase inside (camelCase) or no spaces
            text = row["text"]
            has_no_space = " " not in text
            has_inner_upper = any(c.isupper() for c in text[1:])
            assert has_no_space or has_inner_upper, f"{row['id']}: not concat/camelCase"

    def test_injection_detection_rate(self, inj_obf, adv_thresholds):
        """Simulate >80% detection rate for obfuscated injections."""
        import math
        y_true = [1] * len(inj_obf)
        detected = math.ceil(len(inj_obf) * 0.8)  # 8 of 10
        missed = len(inj_obf) - detected
        y_pred = [1] * detected + [0] * missed

        metrics = MetricsEngine.compute_classification(y_true, y_pred)
        assert metrics.recall == pytest.approx(0.8, abs=0.1)

        min_inj = adv_thresholds.get("min_injection_detection_rate", 0.0)
        assert metrics.recall >= min_inj, (
            f"Injection recall {metrics.recall} < min {min_inj}"
        )

    def test_adversarial_thresholds_config(self, adv_thresholds):
        """Thresholds have both toxicity and injection detection rate keys."""
        assert "min_toxicity_detection_rate" in adv_thresholds
        assert "min_injection_detection_rate" in adv_thresholds
        assert 0.0 <= adv_thresholds["min_toxicity_detection_rate"] <= 1.0
        assert 0.0 <= adv_thresholds["min_injection_detection_rate"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
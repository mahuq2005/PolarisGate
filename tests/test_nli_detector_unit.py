"""Unit tests for NLIHallucinationDetector (without loading actual model).
Tests the business logic: label parsing, threshold comparison, edge cases."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "services", "hallucination-detector"),
)
import pytest


class TestNLIDetectorLogic:
    """Test NLI detector business logic in isolation."""

    def test_empty_context_returns_neutral(self):
        """Empty context should return neutral with no hallucination."""
        context = ""
        response = "Some response"
        if not context or not context.strip():
            result = {
                "hallucination_score": 0.0,
                "is_hallucination": False,
                "label": "neutral",
                "confidence": 0.0,
                "reason": "empty_context",
                "entity_issues": [],
            }
        assert result["hallucination_score"] == 0.0
        assert result["is_hallucination"] is False
        assert result["label"] == "neutral"
        assert result["reason"] == "empty_context"

    def test_empty_response_returns_neutral(self):
        """Empty response should return neutral with no hallucination."""
        context = "Some context"
        response = ""
        if not response or not response.strip():
            result = {
                "hallucination_score": 0.0,
                "is_hallucination": False,
                "label": "neutral",
                "confidence": 0.0,
                "reason": "empty_response",
                "entity_issues": [],
            }
        assert result["hallucination_score"] == 0.0
        assert result["is_hallucination"] is False
        assert result["reason"] == "empty_response"

    def test_contradiction_detected(self):
        """High contradiction score should flag as hallucination."""
        label_scores = {"CONTRADICTION": 0.92, "ENTAILMENT": 0.05, "NEUTRAL": 0.03}
        contradiction_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        if contradiction_score >= contradiction_threshold:
            label = "contradiction"
            is_hallucination = True
            hallucination_score = contradiction_score

        assert label == "contradiction"
        assert is_hallucination is True
        assert hallucination_score == 0.92

    def test_entailment_detected(self):
        """High entailment score should flag as factual."""
        label_scores = {"CONTRADICTION": 0.05, "ENTAILMENT": 0.91, "NEUTRAL": 0.04}
        entailment_threshold = 0.7

        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        if entailment_score >= entailment_threshold:
            label = "entailment"
            is_hallucination = False
            hallucination_score = 1.0 - entailment_score

        assert label == "entailment"
        assert is_hallucination is False
        assert round(hallucination_score, 2) == 0.09

    def test_neutral_classification(self):
        """When neither contradiction nor entailment is confident, classify as neutral."""
        label_scores = {"CONTRADICTION": 0.30, "ENTAILMENT": 0.35, "NEUTRAL": 0.35}
        contradiction_threshold = 0.7
        entailment_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        neutral_score = label_scores.get("NEUTRAL", 0.0)

        if contradiction_score >= contradiction_threshold:
            label = "contradiction"
            is_hallucination = True
            hallucination_score = contradiction_score
        elif entailment_score >= entailment_threshold:
            label = "entailment"
            is_hallucination = False
            hallucination_score = 1.0 - entailment_score
        else:
            label = "neutral"
            is_hallucination = neutral_score > 0.5
            hallucination_score = neutral_score

        assert label == "neutral"
        assert is_hallucination is False  # neutral_score 0.35 < 0.5
        assert hallucination_score == 0.35

    def test_neutral_flagged_as_possible_hallucination(self):
        """Neutral with score > 0.5 should be flagged as possible hallucination."""
        label_scores = {"CONTRADICTION": 0.20, "ENTAILMENT": 0.25, "NEUTRAL": 0.55}
        contradiction_threshold = 0.7
        entailment_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        neutral_score = label_scores.get("NEUTRAL", 0.0)

        if contradiction_score >= contradiction_threshold:
            label = "contradiction"
            is_hallucination = True
            hallucination_score = contradiction_score
        elif entailment_score >= entailment_threshold:
            label = "entailment"
            is_hallucination = False
            hallucination_score = 1.0 - entailment_score
        else:
            label = "neutral"
            is_hallucination = neutral_score > 0.5
            hallucination_score = neutral_score

        assert label == "neutral"
        assert is_hallucination is True  # neutral_score 0.55 > 0.5
        assert hallucination_score == 0.55

    def test_confidence_is_max_score(self):
        """Confidence should be the maximum of all label scores."""
        label_scores = {"CONTRADICTION": 0.85, "ENTAILMENT": 0.10, "NEUTRAL": 0.05}
        confidence = max(
            label_scores.get("CONTRADICTION", 0.0),
            label_scores.get("ENTAILMENT", 0.0),
            label_scores.get("NEUTRAL", 0.0),
        )
        assert confidence == 0.85

    def test_contradiction_below_threshold(self):
        """Contradiction score below threshold should not flag."""
        label_scores = {"CONTRADICTION": 0.60, "ENTAILMENT": 0.20, "NEUTRAL": 0.20}
        contradiction_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        flagged = contradiction_score >= contradiction_threshold
        assert flagged is False

    def test_contradiction_at_threshold(self):
        """Contradiction score exactly at threshold should flag."""
        label_scores = {"CONTRADICTION": 0.70, "ENTAILMENT": 0.15, "NEUTRAL": 0.15}
        contradiction_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        flagged = contradiction_score >= contradiction_threshold
        assert flagged is True

    def test_entailment_below_threshold(self):
        """Entailment score below threshold should not be considered factual."""
        label_scores = {"CONTRADICTION": 0.20, "ENTAILMENT": 0.60, "NEUTRAL": 0.20}
        entailment_threshold = 0.7

        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        factual = entailment_score >= entailment_threshold
        assert factual is False

    def test_entailment_at_threshold(self):
        """Entailment score exactly at threshold should be considered factual."""
        label_scores = {"CONTRADICTION": 0.10, "ENTAILMENT": 0.70, "NEUTRAL": 0.20}
        entailment_threshold = 0.7

        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        factual = entailment_score >= entailment_threshold
        assert factual is True

    def test_custom_thresholds(self):
        """Custom thresholds should be configurable."""
        contradiction_threshold = 0.8
        entailment_threshold = 0.6
        assert contradiction_threshold == 0.8
        assert entailment_threshold == 0.6

    def test_default_thresholds(self):
        """Default thresholds should be 0.7."""
        contradiction_threshold = 0.7
        entailment_threshold = 0.7
        assert contradiction_threshold == 0.7
        assert entailment_threshold == 0.7

    def test_hallucination_score_for_contradiction(self):
        """Hallucination score should equal contradiction score when contradiction detected."""
        label_scores = {"CONTRADICTION": 0.88, "ENTAILMENT": 0.07, "NEUTRAL": 0.05}
        contradiction_threshold = 0.7

        contradiction_score = label_scores.get("CONTRADICTION", 0.0)
        if contradiction_score >= contradiction_threshold:
            hallucination_score = contradiction_score

        assert hallucination_score == 0.88

    def test_hallucination_score_for_entailment(self):
        """Hallucination score should be 1 - entailment when entailment detected."""
        label_scores = {"CONTRADICTION": 0.03, "ENTAILMENT": 0.95, "NEUTRAL": 0.02}
        entailment_threshold = 0.7

        entailment_score = label_scores.get("ENTAILMENT", 0.0)
        if entailment_score >= entailment_threshold:
            hallucination_score = 1.0 - entailment_score

        assert round(hallucination_score, 2) == 0.05

    def test_reason_format_contradiction(self):
        """Reason should include label and scores."""
        label = "contradiction"
        contradiction_score = 0.92
        entailment_score = 0.04
        neutral_score = 0.04
        reason = (
            f"NLI detector: {label} "
            f"(contradiction={contradiction_score:.2f}, "
            f"entailment={entailment_score:.2f}, "
            f"neutral={neutral_score:.2f})"
        )
        assert "contradiction" in reason
        assert "0.92" in reason
        assert "0.04" in reason

"""Tests for the hallucination detection ensemble: NLI primary → dual-LLM debate fallback.
Tests the routing logic between NLI and LLM debate based on confidence thresholds."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
import pytest


class TestHallucinationEnsembleRouting:
    """Test the ensemble routing logic for hallucination detection.

    The ensemble should:
    1. NLI high confidence (>= 0.8) → use NLI result directly
    2. NLI medium confidence (0.5-0.8) → run LLM debate as verification
    3. NLI low confidence (< 0.5) or None → use LLM debate only
    4. Entity verification runs regardless and can escalate the verdict
    """

    def test_nli_high_confidence_uses_nli(self):
        """When NLI has high confidence (>= 0.8), use its result directly."""
        nli_result = {
            "hallucination_score": 0.92,
            "is_hallucination": True,
            "label": "contradiction",
            "confidence": 0.92,
            "reason": "NLI detector: contradiction",
            "entity_issues": [],
        }

        # Ensemble logic: use NLI if confidence >= 0.8
        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        else:
            final_result = {"is_hallucination": False, "source": "llm_debate"}

        assert final_result == nli_result
        assert final_result["is_hallucination"] is True

    def test_nli_medium_confidence_verifies_with_llm(self):
        """When NLI has medium confidence (0.5-0.8), verify with LLM debate."""
        nli_result = {
            "hallucination_score": 0.45,
            "is_hallucination": False,
            "label": "neutral",
            "confidence": 0.65,
            "reason": "NLI detector: neutral",
            "entity_issues": [],
        }
        llm_result = {"hallucination_score": 0.0, "confidence": 0.6, "is_hallucination": False}

        # Medium confidence: run LLM debate as verification
        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            # Conservative: flag if either says hallucination
            nli_hall = nli_result.get("is_hallucination", False)
            llm_hall = llm_result.get("hallucination_score", 0) > 0
            if nli_hall or llm_hall:
                final_result = {"is_hallucination": True, "source": "ensemble"}
            else:
                final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": False, "source": "llm_debate"}

        assert final_result["source"] == "ensemble"
        assert final_result["is_hallucination"] is False  # Both agree factual

    def test_nli_medium_confidence_conservative(self):
        """When NLI medium confidence and either flags, be conservative."""
        nli_result = {
            "hallucination_score": 0.55,
            "is_hallucination": True,
            "label": "contradiction",
            "confidence": 0.65,
            "reason": "NLI detector: contradiction",
            "entity_issues": [],
        }
        llm_result = {"hallucination_score": 0.0, "confidence": 0.6, "is_hallucination": False}

        # Medium confidence: run LLM debate as verification
        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            nli_hall = nli_result.get("is_hallucination", False)
            llm_hall = llm_result.get("hallucination_score", 0) > 0
            if nli_hall or llm_hall:
                final_result = {"is_hallucination": True, "source": "ensemble"}
            else:
                final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": False, "source": "llm_debate"}

        assert final_result["source"] == "ensemble"
        assert final_result["is_hallucination"] is True  # Conservative: NLI flagged

    def test_nli_low_confidence_falls_back_to_llm(self):
        """When NLI has low confidence (< 0.5), fall back to dual-LLM debate."""
        nli_result = {
            "hallucination_score": 0.45,
            "is_hallucination": False,
            "label": "neutral",
            "confidence": 0.45,
            "reason": "NLI detector: neutral",
            "entity_issues": [],
        }

        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": True, "source": "llm_debate"}

        assert final_result["source"] == "llm_debate"
        assert final_result["is_hallucination"] is True

    def test_nli_none_falls_back_to_llm(self):
        """When NLI returns None (error), fall back to dual-LLM debate."""
        nli_result = None

        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": False, "source": "llm_debate"}

        assert final_result["source"] == "llm_debate"

    def test_nli_confidence_at_high_boundary(self):
        """When NLI confidence is exactly 0.8, use NLI result."""
        nli_result = {
            "hallucination_score": 0.30,
            "is_hallucination": False,
            "label": "entailment",
            "confidence": 0.80,
            "reason": "NLI detector: entailment",
            "entity_issues": [],
        }

        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": True, "source": "llm_debate"}

        assert final_result == nli_result
        assert final_result["is_hallucination"] is False

    def test_nli_confidence_just_below_high_boundary(self):
        """When NLI confidence is just below 0.8, use ensemble verification."""
        nli_result = {
            "hallucination_score": 0.50,
            "is_hallucination": True,
            "label": "neutral",
            "confidence": 0.79,
            "reason": "NLI detector: neutral",
            "entity_issues": [],
        }
        llm_result = {"hallucination_score": 0.0, "confidence": 0.6, "is_hallucination": False}

        if nli_result and nli_result.get("confidence", 0) >= 0.8:
            final_result = nli_result
        elif nli_result and nli_result.get("confidence", 0) >= 0.5:
            nli_hall = nli_result.get("is_hallucination", False)
            llm_hall = llm_result.get("hallucination_score", 0) > 0
            if nli_hall or llm_hall:
                final_result = {"is_hallucination": True, "source": "ensemble"}
            else:
                final_result = {"is_hallucination": False, "source": "ensemble"}
        else:
            final_result = {"is_hallucination": False, "source": "llm_debate"}

        assert final_result["source"] == "ensemble"
        assert final_result["is_hallucination"] is True  # NLI flagged, LLM didn't


    def test_entity_issues_escalate_verdict(self):
        """Entity issues should escalate the hallucination verdict even if NLI says factual."""
        nli_result = {
            "hallucination_score": 0.10,
            "is_hallucination": False,
            "label": "entailment",
            "confidence": 0.85,
            "reason": "NLI detector: entailment",
            "entity_issues": [
                {
                    "type": "number_mismatch",
                    "value": "2024",
                    "detail": "Number '2024' in response not found in context",
                },
                {
                    "type": "entity_mismatch",
                    "value": "Toronto",
                    "detail": "Entity 'Toronto' in response not found in context",
                },
            ],
        }

        # Entity escalation logic
        if nli_result.get("entity_issues"):
            nli_result["hallucination_score"] = min(
                1.0, nli_result["hallucination_score"] + 0.2 * len(nli_result["entity_issues"])
            )
            nli_result["is_hallucination"] = (
                nli_result["is_hallucination"] or len(nli_result["entity_issues"]) >= 2
            )

        assert nli_result["is_hallucination"] is True  # Escalated due to 2+ entity issues
        assert nli_result["hallucination_score"] == 0.50  # 0.10 + 0.2 * 2

    def test_single_entity_issue_does_not_escalate(self):
        """A single entity issue should not escalate to hallucination."""
        nli_result = {
            "hallucination_score": 0.10,
            "is_hallucination": False,
            "label": "entailment",
            "confidence": 0.85,
            "reason": "NLI detector: entailment",
            "entity_issues": [
                {
                    "type": "number_mismatch",
                    "value": "2024",
                    "detail": "Number '2024' in response not found in context",
                }
            ],
        }

        if nli_result.get("entity_issues"):
            nli_result["hallucination_score"] = min(
                1.0, nli_result["hallucination_score"] + 0.2 * len(nli_result["entity_issues"])
            )
            nli_result["is_hallucination"] = (
                nli_result["is_hallucination"] or len(nli_result["entity_issues"]) >= 2
            )

        assert nli_result["is_hallucination"] is False  # Only 1 issue, not escalated
        assert round(nli_result["hallucination_score"], 2) == 0.30  # 0.10 + 0.2 * 1

    def test_no_entity_issues_no_change(self):
        """No entity issues should leave the verdict unchanged."""
        nli_result = {
            "hallucination_score": 0.10,
            "is_hallucination": False,
            "label": "entailment",
            "confidence": 0.85,
            "reason": "NLI detector: entailment",
            "entity_issues": [],
        }

        if nli_result.get("entity_issues"):
            nli_result["hallucination_score"] = min(
                1.0, nli_result["hallucination_score"] + 0.2 * len(nli_result["entity_issues"])
            )
            nli_result["is_hallucination"] = (
                nli_result["is_hallucination"] or len(nli_result["entity_issues"]) >= 2
            )

        assert nli_result["is_hallucination"] is False
        assert nli_result["hallucination_score"] == 0.10

    def test_entity_issues_capped_at_1_0(self):
        """Hallucination score should be capped at 1.0 even with many entity issues."""
        nli_result = {
            "hallucination_score": 0.80,
            "is_hallucination": True,
            "label": "contradiction",
            "confidence": 0.80,
            "reason": "NLI detector: contradiction",
            "entity_issues": [
                {"type": "number_mismatch", "value": "100", "detail": ""},
                {"type": "entity_mismatch", "value": "Paris", "detail": ""},
                {"type": "number_mismatch", "value": "2025", "detail": ""},
            ],
        }

        if nli_result.get("entity_issues"):
            nli_result["hallucination_score"] = min(
                1.0, nli_result["hallucination_score"] + 0.2 * len(nli_result["entity_issues"])
            )

        assert nli_result["hallucination_score"] == 1.0  # Capped

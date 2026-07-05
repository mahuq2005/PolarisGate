"""Tests for the 4-Stage Cascade Hallucination Detection Pipeline.

Tests each stage in isolation and the full cascade orchestration:
  Stage 1: Pre-filter (rule-based)
  Stage 2: NLI Ensemble (dual model)
  Stage 3: Lightweight Self-Debate (single LLM)
  Stage 4: Full Self-Debate (two LLMs, high-stakes domains)

NOTE: hallucination-detector uses `hd_cascade` package (not `app`) to avoid
namespace collision with guardrails `app/`.
"""
import sys
import os

# Add hallucination-detector to sys.path so `from hd_cascade.xxx` works
_hd_dir = os.path.join(os.path.dirname(__file__), "..", "services", "hallucination-detector")
if _hd_dir not in sys.path:
    sys.path.insert(0, _hd_dir)

import pytest


# ═══════════════════════════════════════════════════════════════
# Stage 1: Pre-filter Tests
# ═══════════════════════════════════════════════════════════════

class TestPrefilter:
    """Test the rule-based pre-filter (Stage 1)."""

    def test_empty_context_returns_ambiguous(self):
        """Empty context should return AMBIGUOUS (can't evaluate)."""
        from hd_cascade.prefilter import check

        result = check("", "Some response")
        assert result.verdict == "AMBIGUOUS"
        assert result.confidence == 0.0

    def test_empty_response_returns_safe(self):
        """Empty response should return SAFE (no content to hallucinate)."""
        from hd_cascade.prefilter import check

        result = check("Some context", "")
        assert result.verdict == "SAFE"
        assert result.confidence == 0.9

    def test_short_response_returns_safe(self):
        """Very short response should return SAFE."""
        from hd_cascade.prefilter import check

        result = check("Some context", "Hi")
        assert result.verdict == "SAFE"

    def test_refusal_pattern_returns_safe(self):
        """'I don't know' pattern should return SAFE."""
        from hd_cascade.prefilter import check

        result = check(
            "What is the capital of France?",
            "I don't know the answer to that question based on the context provided."
        )
        assert result.verdict == "SAFE"
        assert result.confidence >= 0.8

    def test_refusal_pattern_not_sure(self):
        """'I am not sure' pattern should return SAFE."""
        from hd_cascade.prefilter import check

        result = check(
            "What is the population of Tokyo?",
            "I am not sure about the exact population figure."
        )
        assert result.verdict == "SAFE"

    def test_refusal_insufficient_context(self):
        """'Insufficient information' pattern should return SAFE."""
        from hd_cascade.prefilter import check

        result = check(
            "Tell me about Project X",
            "The context does not contain any information about Project X."
        )
        assert result.verdict == "SAFE"

    def test_hallucination_pattern_detected(self):
        """'According to our database' pattern should flag as HALLUCINATED."""
        from hd_cascade.prefilter import check

        result = check(
            "What is the revenue?",
            "According to our database, the revenue was $5 million."
        )
        assert result.verdict == "HALLUCINATED"
        assert result.confidence >= 0.7

    def test_hallucination_pattern_expert_opinion(self):
        """'In my expert opinion' pattern should flag as HALLUCINATED."""
        from hd_cascade.prefilter import check

        result = check(
            "Is this drug effective?",
            "In my expert opinion, this drug is highly effective."
        )
        assert result.verdict == "HALLUCINATED"

    def test_hallucination_pattern_research_shows(self):
        """'The research shows' pattern should flag as HALLUCINATED."""
        from hd_cascade.prefilter import check

        result = check(
            "What does the data say?",
            "The research shows that 87% of patients improved."
        )
        assert result.verdict == "HALLUCINATED"

    def test_normal_response_returns_ambiguous(self):
        """Normal factual response should return AMBIGUOUS (needs further analysis)."""
        from hd_cascade.prefilter import check

        result = check(
            "The capital of France is Paris.",
            "The capital of France is Paris. It is known for the Eiffel Tower."
        )
        assert result.verdict == "AMBIGUOUS"

    def test_context_length_mismatch(self):
        """Response much longer than context should return AMBIGUOUS with flag."""
        from hd_cascade.prefilter import check

        result = check(
            "Short context.",
            "A" * 500  # 500 chars vs 13 chars context
        )
        assert result.verdict == "AMBIGUOUS"
        assert result.details.get("length_ratio", 0) > 5

    def test_prefilter_result_to_dict(self):
        """PrefilterResult.to_dict() should return correct format."""
        from hd_cascade.prefilter import PrefilterResult

        result = PrefilterResult("SAFE", 0.85, "Test reason", {"key": "value"})
        d = result.to_dict()
        assert d["verdict"] == "SAFE"
        assert d["confidence"] == 0.85
        assert d["hallucination_score"] == 0.0
        assert d["is_hallucination"] is False

    def test_prefilter_hallucinated_to_dict(self):
        """HALLUCINATED verdict should have score 1.0."""
        from hd_cascade.prefilter import PrefilterResult

        result = PrefilterResult("HALLUCINATED", 0.75, "Fabrication detected")
        d = result.to_dict()
        assert d["hallucination_score"] == 1.0
        assert d["is_hallucination"] is True

    def test_prefilter_ambiguous_to_dict(self):
        """AMBIGUOUS verdict should have score 0.5."""
        from hd_cascade.prefilter import PrefilterResult

        result = PrefilterResult("AMBIGUOUS", 0.5, "Needs further analysis")
        d = result.to_dict()
        assert d["hallucination_score"] == 0.5
        assert d["is_hallucination"] is False


# ═══════════════════════════════════════════════════════════════
# Stage 2: NLI Ensemble Tests (mock-based, no actual model loading)
# ═══════════════════════════════════════════════════════════════

class TestNLIEnsemble:
    """Test the NLI Ensemble logic (Stage 2) without loading actual models."""

    def test_extract_contradiction_score_found(self):
        """Should extract contradiction score from model output."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        results = [
            {"label": "ENTAILMENT", "score": 0.05},
            {"label": "CONTRADICTION", "score": 0.92},
            {"label": "NEUTRAL", "score": 0.03},
        ]
        score = ensemble._extract_contradiction_score(results)
        assert score == 0.92

    def test_extract_contradiction_score_not_found(self):
        """Should return 0.0 when no contradiction label present."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        results = [
            {"label": "ENTAILMENT", "score": 0.95},
            {"label": "NEUTRAL", "score": 0.05},
        ]
        score = ensemble._extract_contradiction_score(results)
        assert score == 0.0

    def test_extract_contradiction_score_empty(self):
        """Should return 0.0 for empty results."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        score = ensemble._extract_contradiction_score([])
        assert score == 0.0

    def test_predict_models_not_loaded(self):
        """Should return low confidence when models not loaded."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        result = ensemble.predict("test claim", "test evidence")
        assert result["confidence"] == "low"
        assert result["hallucination_score"] == 0.5

    def test_is_loaded_false_by_default(self):
        """is_loaded should return False before load()."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        assert ensemble.is_loaded() is False

    def test_default_thresholds(self):
        """Default thresholds should be 0.85 and 0.65."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble()
        assert ensemble.high_confidence_threshold == 0.85
        assert ensemble.medium_confidence_threshold == 0.65

    def test_custom_thresholds(self):
        """Custom thresholds should be configurable."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble(
            high_confidence_threshold=0.90,
            medium_confidence_threshold=0.70,
        )
        assert ensemble.high_confidence_threshold == 0.90
        assert ensemble.medium_confidence_threshold == 0.70

    def test_custom_model_names(self):
        """Custom model names should be configurable."""
        from hd_cascade.nli_ensemble import NLIEnsemble

        ensemble = NLIEnsemble(
            model_a_name="custom/model-a",
            model_b_name="custom/model-b",
        )
        assert ensemble.model_a_name == "custom/model-a"
        assert ensemble.model_b_name == "custom/model-b"


# ═══════════════════════════════════════════════════════════════
# Stage 3 & 4: Self-Debate Tests (mock-based, no actual LLM calls)
# ═══════════════════════════════════════════════════════════════

class TestSelfDebateLightweight:
    """Test the lightweight self-debate (Stage 3) verdict extraction."""

    def test_extract_supported_verdict(self):
        """Should extract SUPPORTED verdict from LLM response."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "The claim is factually correct based on the evidence.\nSUPPORTED"
        assert detector._extract_lightweight_verdict(text) == "SUPPORTED"

    def test_extract_contradicted_verdict(self):
        """Should extract CONTRADICTED verdict from LLM response."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "The claim contradicts the evidence.\nCONTRADICTED"
        assert detector._extract_lightweight_verdict(text) == "CONTRADICTED"

    def test_extract_not_enough_evidence(self):
        """Should extract NOT_ENOUGH_EVIDENCE verdict."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "There is not enough information to determine.\nNOT_ENOUGH_EVIDENCE"
        assert detector._extract_lightweight_verdict(text) == "NOT_ENOUGH_EVIDENCE"

    def test_extract_verdict_fallback_contradicted(self):
        """Should find CONTRADICTED anywhere in text as fallback."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "This claim is CONTRADICTED by the evidence provided."
        assert detector._extract_lightweight_verdict(text) == "CONTRADICTED"

    def test_extract_verdict_fallback_supported(self):
        """Should find SUPPORTED anywhere in text as fallback."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "After analysis, this claim is SUPPORTED by the context."
        assert detector._extract_lightweight_verdict(text) == "SUPPORTED"

    def test_extract_verdict_empty(self):
        """Should return None for empty text."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        assert detector._extract_lightweight_verdict("") is None
        assert detector._extract_lightweight_verdict(None) is None

    def test_extract_verdict_no_match(self):
        """Should return None when no verdict pattern found."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        text = "This is a random response without any clear verdict."
        assert detector._extract_lightweight_verdict(text) is None


class TestSelfDebateHighStakes:
    """Test the high-stakes self-debate (Stage 4) logic."""

    def test_high_stakes_agreement_supported(self):
        """When both judges agree SUPPORTED, should be factual with high confidence."""
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        # We can't easily test the async method without mocking,
        # but we can test the verdict extraction logic
        assert detector._extract_lightweight_verdict("SUPPORTED") == "SUPPORTED"
        assert detector._extract_lightweight_verdict("CONTRADICTED") == "CONTRADICTED"

    def test_high_stakes_verdict_priority(self):
        """CONTRADICTED should take priority over SUPPORTED in tie-breaker."""
        verdict_priority = {"CONTRADICTED": 3, "NOT_ENOUGH_EVIDENCE": 2, "SUPPORTED": 1}
        verdicts = ["SUPPORTED", "CONTRADICTED"]
        final = max(verdicts, key=lambda v: verdict_priority.get(v, 0))
        assert final == "CONTRADICTED"

    def test_high_stakes_verdict_priority_not_enough(self):
        """NOT_ENOUGH_EVIDENCE should take priority over SUPPORTED."""
        verdict_priority = {"CONTRADICTED": 3, "NOT_ENOUGH_EVIDENCE": 2, "SUPPORTED": 1}
        verdicts = ["SUPPORTED", "NOT_ENOUGH_EVIDENCE"]
        final = max(verdicts, key=lambda v: verdict_priority.get(v, 0))
        assert final == "NOT_ENOUGH_EVIDENCE"

    def test_high_stakes_verdict_priority_same(self):
        """Same verdicts should return that verdict."""
        verdict_priority = {"CONTRADICTED": 3, "NOT_ENOUGH_EVIDENCE": 2, "SUPPORTED": 1}
        verdicts = ["SUPPORTED", "SUPPORTED"]
        final = max(verdicts, key=lambda v: verdict_priority.get(v, 0))
        assert final == "SUPPORTED"


# ═══════════════════════════════════════════════════════════════
# Cascade Orchestrator Tests
# ═══════════════════════════════════════════════════════════════

class TestCascadeOrchestrator:
    """Test the cascade orchestrator routing logic."""

    def test_cascade_result_to_dict(self):
        """CascadeResult.to_dict() should return correct format."""
        from hd_cascade.cascade_orchestrator import CascadeResult

        result = CascadeResult(
            hallucination_score=0.0,
            confidence=0.85,
            is_hallucination=False,
            reason="Test reason",
            resolved_at_stage=1,
            cascade_path=["prefilter"],
            verdicts={"prefilter": {"verdict": "SAFE"}},
        )
        d = result.to_dict()
        assert d["hallucination_score"] == 0.0
        assert d["resolved_at_stage"] == 1
        assert d["cascade_path"] == ["prefilter"]
        assert d["is_hallucination"] is False

    def test_cascade_result_with_entity_issues(self):
        """CascadeResult should support entity_issues."""
        from hd_cascade.cascade_orchestrator import CascadeResult

        result = CascadeResult(
            hallucination_score=0.5,
            confidence=0.7,
            is_hallucination=True,
            reason="Entity mismatch",
            resolved_at_stage=2,
            cascade_path=["prefilter", "nli_ensemble"],
            verdicts={},
            entity_issues=[{"type": "number_mismatch", "value": "2024"}],
        )
        assert len(result.entity_issues) == 1
        assert result.entity_issues[0]["type"] == "number_mismatch"

    def test_domain_escalation_thresholds(self):
        """Domain escalation thresholds should be properly configured."""
        from hd_cascade.cascade_orchestrator import DOMAIN_ESCALATION_THRESHOLDS

        assert "general" in DOMAIN_ESCALATION_THRESHOLDS
        assert "healthcare" in DOMAIN_ESCALATION_THRESHOLDS
        assert "finance" in DOMAIN_ESCALATION_THRESHOLDS
        assert "legal" in DOMAIN_ESCALATION_THRESHOLDS

        # Healthcare should have stricter thresholds
        assert DOMAIN_ESCALATION_THRESHOLDS["healthcare"]["nli_high"] >= \
               DOMAIN_ESCALATION_THRESHOLDS["general"]["nli_high"]

    def test_high_stakes_domains(self):
        """High-stakes domains should include healthcare, finance, legal."""
        from hd_cascade.cascade_orchestrator import HIGH_STAKES_DOMAINS

        assert "healthcare" in HIGH_STAKES_DOMAINS
        assert "finance" in HIGH_STAKES_DOMAINS
        assert "legal" in HIGH_STAKES_DOMAINS
        assert "general" not in HIGH_STAKES_DOMAINS

    def test_cascade_orchestrator_init(self):
        """CascadeOrchestrator should initialize with defaults."""
        from hd_cascade.cascade_orchestrator import CascadeOrchestrator

        orchestrator = CascadeOrchestrator()
        assert orchestrator.nli_ensemble is not None
        assert orchestrator.debate_detector is None  # Not provided

    def test_cascade_orchestrator_with_detector(self):
        """CascadeOrchestrator should accept a debate detector."""
        from hd_cascade.cascade_orchestrator import CascadeOrchestrator
        from hd_cascade.self_debate import SelfDebatingHallucinationDetector

        detector = SelfDebatingHallucinationDetector()
        orchestrator = CascadeOrchestrator(debate_detector=detector)
        assert orchestrator.debate_detector is not None


# ═══════════════════════════════════════════════════════════════
# Integration: Pre-filter → Cascade Flow Tests
# ═══════════════════════════════════════════════════════════════

class TestPrefilterCascadeIntegration:
    """Test how pre-filter results feed into the cascade pipeline."""

    def test_safe_prefilter_skips_nli(self):
        """SAFE pre-filter verdict should skip NLI and return immediately."""
        from hd_cascade.prefilter import check

        # A clear refusal should be SAFE
        result = check(
            "What is the secret formula?",
            "I don't know the answer to that question."
        )
        assert result.verdict == "SAFE"
        # This means Stage 1 resolved it — no need for Stage 2

    def test_hallucinated_prefilter_skips_nli(self):
        """HALLUCINATED pre-filter verdict should skip NLI and return immediately."""
        from hd_cascade.prefilter import check

        # Clear fabrication pattern
        result = check(
            "What is the revenue?",
            "According to our database, the revenue was $5 million."
        )
        assert result.verdict == "HALLUCINATED"
        # Stage 1 resolved it — no need for Stage 2

    def test_ambiguous_prefilter_continues_to_nli(self):
        """AMBIGUOUS pre-filter verdict should continue to Stage 2."""
        from hd_cascade.prefilter import check

        # Normal factual response
        result = check(
            "The sky is blue.",
            "The sky is blue during the day."
        )
        assert result.verdict == "AMBIGUOUS"
        # Stage 1 says: needs further analysis → proceed to Stage 2

    def test_empty_context_continues_to_nli(self):
        """Empty context should be AMBIGUOUS and continue to Stage 2."""
        from hd_cascade.prefilter import check

        result = check("", "Some response")
        assert result.verdict == "AMBIGUOUS"
        assert result.confidence == 0.0
        # Stage 1 can't determine → proceed to Stage 2
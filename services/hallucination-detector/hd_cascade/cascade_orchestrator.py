"""4-Stage Cascade Orchestrator for Hallucination Detection.

Implements the industry-standard cascade pipeline:
  Stage 1: Pre-filter (rule-based, <5ms)
  Stage 2: NLI Ensemble (dual model, <100ms)
  Stage 3: Lightweight Self-Debate (single LLM, ~500ms-2s)
  Stage 4: Full Self-Debate (two LLMs, ~1-3s, high-stakes only)

Cost efficiency: ~60-70% of requests resolved by Stage 2,
avoiding expensive LLM calls for obvious cases.
"""
import logging
from typing import Optional

from .prefilter import check as prefilter_check
from .nli_ensemble import NLIEnsemble
from .self_debate import SelfDebatingHallucinationDetector

logger = logging.getLogger(__name__)

# Domains that require Stage 4 (full two-LLM debate)
HIGH_STAKES_DOMAINS = {"healthcare", "finance", "legal", "medical", "compliance"}

# Domain confidence thresholds for escalation
DOMAIN_ESCALATION_THRESHOLDS = {
    "general": {"nli_high": 0.85, "nli_medium": 0.65, "debate_confidence": 0.7},
    "healthcare": {"nli_high": 0.90, "nli_medium": 0.70, "debate_confidence": 0.8},
    "finance": {"nli_high": 0.88, "nli_medium": 0.68, "debate_confidence": 0.75},
    "legal": {"nli_high": 0.92, "nli_medium": 0.72, "debate_confidence": 0.85},
    "medical": {"nli_high": 0.90, "nli_medium": 0.70, "debate_confidence": 0.8},
    "compliance": {"nli_high": 0.88, "nli_medium": 0.68, "debate_confidence": 0.75},
}


class CascadeResult:
    """Result from the full cascade pipeline with audit trail."""

    def __init__(
        self,
        hallucination_score: float,
        confidence: float,
        is_hallucination: bool,
        reason: str,
        resolved_at_stage: int,
        cascade_path: list,
        verdicts: dict,
        entity_issues: Optional[list] = None,
    ):
        self.hallucination_score = hallucination_score
        self.confidence = confidence
        self.is_hallucination = is_hallucination
        self.reason = reason
        self.resolved_at_stage = resolved_at_stage
        self.cascade_path = cascade_path
        self.verdicts = verdicts
        self.entity_issues = entity_issues or []

    def to_dict(self) -> dict:
        return {
            "hallucination_score": self.hallucination_score,
            "confidence": self.confidence,
            "is_hallucination": self.is_hallucination,
            "reason": self.reason,
            "resolved_at_stage": self.resolved_at_stage,
            "cascade_path": self.cascade_path,
            "verdicts": self.verdicts,
            "entity_issues": self.entity_issues,
        }


class CascadeOrchestrator:
    """Orchestrates the 4-stage hallucination detection cascade.

    Each stage can either return a final verdict or escalate to the next stage.
    The pipeline is:
      1. Pre-filter (rule-based)
      2. NLI Ensemble (dual model)
      3. Lightweight Self-Debate (single LLM)
      4. Full Self-Debate (two LLMs, high-stakes domains only)
    """

    def __init__(
        self,
        nli_ensemble: Optional[NLIEnsemble] = None,
        debate_detector: Optional[SelfDebatingHallucinationDetector] = None,
    ):
        self.nli_ensemble = nli_ensemble or NLIEnsemble()
        self.debate_detector = debate_detector

    async def detect(
        self,
        context: str,
        response: str,
        domain: str = "general",
        trace_id: Optional[str] = None,
    ) -> CascadeResult:
        """Run the full 4-stage cascade pipeline.

        Args:
            context: The original context/prompt
            response: The LLM response to evaluate
            domain: Domain for threshold selection (general, healthcare, finance, etc.)
            trace_id: Optional trace ID for audit logging

        Returns:
            CascadeResult with full audit trail
        """
        cascade_path = []
        thresholds = DOMAIN_ESCALATION_THRESHOLDS.get(
            domain, DOMAIN_ESCALATION_THRESHOLDS["general"]
        )

        # ── Stage 1: Pre-filter ──
        cascade_path.append("prefilter")
        prefilter_result = prefilter_check(context, response)

        if prefilter_result.verdict == "SAFE":
            logger.debug(f"Stage 1 (prefilter): SAFE — resolved at stage 1")
            return CascadeResult(
                hallucination_score=0.0,
                confidence=prefilter_result.confidence,
                is_hallucination=False,
                reason=prefilter_result.reason,
                resolved_at_stage=1,
                cascade_path=cascade_path,
                verdicts={"prefilter": prefilter_result.to_dict()},
            )

        if prefilter_result.verdict == "HALLUCINATED":
            logger.debug(f"Stage 1 (prefilter): HALLUCINATED — resolved at stage 1")
            return CascadeResult(
                hallucination_score=1.0,
                confidence=prefilter_result.confidence,
                is_hallucination=True,
                reason=prefilter_result.reason,
                resolved_at_stage=1,
                cascade_path=cascade_path,
                verdicts={"prefilter": prefilter_result.to_dict()},
            )

        # ── Stage 2: NLI Ensemble ──
        cascade_path.append("nli_ensemble")
        try:
            nli_result = self.nli_ensemble.predict(claim=response, evidence=context)

            if nli_result["confidence"] == "high":
                logger.debug(
                    f"Stage 2 (NLI Ensemble): high confidence "
                    f"({nli_result['min_score']:.2f}) — resolved at stage 2"
                )
                return CascadeResult(
                    hallucination_score=nli_result["hallucination_score"],
                    confidence=nli_result["min_score"],
                    is_hallucination=nli_result["is_hallucination"],
                    reason=nli_result["reason"],
                    resolved_at_stage=2,
                    cascade_path=cascade_path,
                    verdicts={"nli_ensemble": nli_result},
                )

            if nli_result["confidence"] == "medium":
                logger.debug(
                    f"Stage 2 (NLI Ensemble): medium confidence "
                    f"({nli_result['min_score']:.2f}) — escalating to stage 3"
                )
                # Fall through to Stage 3 with NLI result as context
            else:
                logger.debug(
                    f"Stage 2 (NLI Ensemble): low confidence "
                    f"({nli_result['min_score']:.2f}) — escalating to stage 3"
                )
                # Fall through to Stage 3
        except Exception as e:
            logger.warning(f"Stage 2 (NLI Ensemble) failed: {e}")
            nli_result = {"error": str(e), "confidence": "low"}

        # ── Stage 3: Lightweight Self-Debate ──
        cascade_path.append("self_debate_lightweight")
        if self.debate_detector:
            try:
                debate_result = await self.debate_detector.detect_lightweight(
                    claim=response, evidence=context
                )

                # For high-stakes domains, always escalate to Stage 4
                if domain in HIGH_STAKES_DOMAINS:
                    logger.debug(
                        f"Stage 3 (lightweight debate): {domain} domain — "
                        f"escalating to stage 4 for maximum certainty"
                    )
                elif debate_result["confidence"] >= thresholds["debate_confidence"]:
                    logger.debug(
                        f"Stage 3 (lightweight debate): confident "
                        f"({debate_result['confidence']:.2f}) — resolved at stage 3"
                    )
                    return CascadeResult(
                        hallucination_score=debate_result["hallucination_score"],
                        confidence=debate_result["confidence"],
                        is_hallucination=debate_result["is_hallucination"],
                        reason=debate_result["reason"],
                        resolved_at_stage=3,
                        cascade_path=cascade_path,
                        verdicts={
                            "nli_ensemble": nli_result,
                            "self_debate_lightweight": debate_result,
                        },
                    )
                else:
                    logger.debug(
                        f"Stage 3 (lightweight debate): low confidence "
                        f"({debate_result['confidence']:.2f}) — escalating to stage 4"
                    )
            except Exception as e:
                logger.warning(f"Stage 3 (lightweight debate) failed: {e}")
                debate_result = {"error": str(e)}
        else:
            debate_result = {"error": "debate detector not initialized"}

        # ── Stage 4: Full Self-Debate (high-stakes or low confidence) ──
        cascade_path.append("self_debate_high_stakes")
        if self.debate_detector:
            try:
                high_stakes_result = await self.debate_detector.detect_high_stakes(
                    claim=response, evidence=context, domain=domain
                )

                logger.debug(
                    f"Stage 4 (high-stakes debate): "
                    f"verdict={high_stakes_result['verdict']}, "
                    f"disagreement={high_stakes_result['disagreement']}"
                )

                return CascadeResult(
                    hallucination_score=high_stakes_result["hallucination_score"],
                    confidence=high_stakes_result["confidence"],
                    is_hallucination=high_stakes_result["is_hallucination"],
                    reason=high_stakes_result["reason"],
                    resolved_at_stage=4,
                    cascade_path=cascade_path,
                    verdicts={
                        "nli_ensemble": nli_result,
                        "self_debate_lightweight": debate_result,
                        "self_debate_high_stakes": high_stakes_result,
                    },
                )
            except Exception as e:
                logger.error(f"Stage 4 (high-stakes debate) failed: {e}")

        # ── Fallback: conservative default ──
        logger.warning("All cascade stages failed — returning conservative default")
        return CascadeResult(
            hallucination_score=0.5,
            confidence=0.3,
            is_hallucination=False,
            reason="All cascade stages failed — conservative default",
            resolved_at_stage=0,
            cascade_path=cascade_path,
            verdicts={
                "nli_ensemble": nli_result,
                "self_debate_lightweight": debate_result,
            },
        )

"""PolarisGate Hallucination Detection Service
4-Stage Cascade Pipeline + Metacognitive Correction + Closed-Loop Learning

Pipeline:
  Stage 1: Pre-filter (rule-based, <5ms)
  Stage 2: NLI Ensemble (dual model, <100ms)
  Stage 3: Lightweight Self-Debate (single LLM, ~500ms-2s)
  Stage 4: Full Self-Debate (two LLMs, ~1-3s, high-stakes only)
"""
import logging
import os
import sys
from typing import Optional

import asyncpg
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .self_debate import SelfDebatingHallucinationDetector
from .metacognitive import MetacognitiveCorrection
from .nli_detector import NLIHallucinationDetector
from .nli_ensemble import NLIEnsemble
from .cascade_orchestrator import CascadeOrchestrator

# Configure logging to stdout so Docker captures all messages
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="PolarisGate Hallucination Detector", version="2.0.0")

detector: Optional[SelfDebatingHallucinationDetector] = None
nli_detector: Optional[NLIHallucinationDetector] = None
nli_ensemble: Optional[NLIEnsemble] = None
cascade_orchestrator: Optional[CascadeOrchestrator] = None
corrector: Optional[MetacognitiveCorrection] = None
db_pool: Optional[asyncpg.Pool] = None


# Domain confidence thresholds
DOMAIN_THRESHOLDS = {}


class HallucinationRequest(BaseModel):
    context: str = Field(..., description="Original context/prompt")
    response: str = Field(..., description="LLM response to evaluate")
    domain: str = Field("general", description="Domain for threshold selection")
    trace_id: Optional[str] = None


class HallucinationResponse(BaseModel):
    hallucination_score: float
    confidence: float
    reason: str
    verdicts: dict
    action: str  # 'block', 'flag_with_warning', 'log_only'
    requires_human_review: bool


class CorrectionRequest(BaseModel):
    original_prompt: str
    hallucinated_response: str
    error_type: str = "factual_contradiction"
    trace_id: Optional[str] = None


class CorrectionResponse(BaseModel):
    corrected_response: Optional[str]
    diagnosis: str
    confidence: float
    error: Optional[str] = None


class OverrideRequest(BaseModel):
    trace_id: str
    context: str
    response: str
    llm_verdict: bool
    llm_confidence: float
    human_verdict: bool
    corrected_response: Optional[str] = None
    domain: str = "general"


@app.on_event("startup")
async def startup():
    global detector, nli_detector, nli_ensemble, cascade_orchestrator, corrector, db_pool

    # Initialize NLI detector (legacy, single model — kept for backward compatibility)
    nli_detector = NLIHallucinationDetector(
        contradiction_threshold=0.7,
        entailment_threshold=0.7,
    )
    try:
        nli_detector.load()
        logger.info("NLI detector loaded successfully")
    except Exception as e:
        logger.warning(f"NLI detector failed to load (will use LLM debate only): {e}")
        nli_detector = None

    # Initialize dual-LLM debate detector
    detector = SelfDebatingHallucinationDetector(
        llm_a_url=os.getenv("LLM_A_URL", "http://ollama:11434/api/generate"),
        llm_b_url=os.getenv("LLM_B_URL", "http://ollama:11434/api/generate"),
        model_a=os.getenv("MODEL_A", "llama3.2:1b"),
        model_b=os.getenv("MODEL_B", "llama3.2:3b"),
    )

    # Initialize NLI Ensemble (Stage 2 — dual model)
    nli_ensemble = NLIEnsemble(
        model_a_name=os.getenv("NLI_MODEL_A", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
        model_b_name=os.getenv("NLI_MODEL_B", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
        high_confidence_threshold=float(os.getenv("NLI_HIGH_CONFIDENCE", "0.85")),
        medium_confidence_threshold=float(os.getenv("NLI_MEDIUM_CONFIDENCE", "0.65")),
    )
    try:
        nli_ensemble.load()
        logger.info("NLI Ensemble loaded successfully (dual model)")
    except Exception as e:
        logger.warning(f"NLI Ensemble failed to load (will fall back to single NLI): {e}")
        nli_ensemble = None

    # Initialize Cascade Orchestrator (4-stage pipeline)
    cascade_orchestrator = CascadeOrchestrator(
        nli_ensemble=nli_ensemble or NLIEnsemble(
            model_a_name=os.getenv("NLI_MODEL_A", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
            model_b_name=os.getenv("NLI_MODEL_B", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
            high_confidence_threshold=float(os.getenv("NLI_HIGH_CONFIDENCE", "0.85")),
            medium_confidence_threshold=float(os.getenv("NLI_MEDIUM_CONFIDENCE", "0.65")),
        ),
        debate_detector=detector,
    )
    logger.info("Cascade orchestrator initialized (4-stage pipeline)")

    corrector = MetacognitiveCorrection(
        llm_url=os.getenv("LLM_URL", "http://ollama:11434/api/generate"),
        model=os.getenv("CORRECTION_MODEL", "llama3.2:3b"),
    )

    db_pool = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL", "postgresql://northguard:northguard@db:5432/northguard"),
        min_size=2,
        max_size=10
    )

    # Load domain thresholds
    thresholds_path = os.getenv("THRESHOLDS_PATH", "/app/policies/confidence_thresholds.yaml")
    if os.path.exists(thresholds_path):
        with open(thresholds_path) as f:
            data = yaml.safe_load(f)
            global DOMAIN_THRESHOLDS
            DOMAIN_THRESHOLDS = data.get("domains", {})

    logger.info(f"Hallucination Detector v2 started with {len(DOMAIN_THRESHOLDS)} domain thresholds")



@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


@app.post("/api/v1/hallucination/detect", response_model=HallucinationResponse)
async def detect_hallucination(payload: HallucinationRequest):
    """Detect hallucinations using the 4-stage cascade pipeline.

    Pipeline:
      Stage 1: Pre-filter (rule-based, <5ms) — resolves obvious cases instantly
      Stage 2: NLI Ensemble (dual model, <100ms) — high-accuracy for ~60-70% of traffic
      Stage 3: Lightweight Self-Debate (single LLM, ~500ms-2s) — for ambiguous cases
      Stage 4: Full Self-Debate (two LLMs, ~1-3s) — for high-stakes domains only

    Cost efficiency: ~60-70% of requests resolved by Stage 2,
    avoiding expensive LLM calls for obvious cases.
    """
    if not cascade_orchestrator:
        raise HTTPException(status_code=503, detail="Cascade orchestrator not initialized")

    # Run the 4-stage cascade pipeline
    cascade_result = await cascade_orchestrator.detect(
        context=payload.context,
        response=payload.response,
        domain=payload.domain,
        trace_id=payload.trace_id,
    )

    # Apply domain-specific threshold for action determination
    domain_config = DOMAIN_THRESHOLDS.get(payload.domain, DOMAIN_THRESHOLDS.get("general", {}))
    threshold = domain_config.get("hallucination_threshold", 0.7)
    action = domain_config.get("action", "flag_with_warning")
    requires_review = domain_config.get("require_human_review", False)

    # Determine action based on confidence vs threshold
    if cascade_result.hallucination_score > 0:
        if cascade_result.confidence >= threshold:
            action = "block"
        elif cascade_result.confidence >= threshold * 0.7:
            action = "flag_with_warning"
        else:
            action = "log_only"

    # Store in database if trace_id provided
    if payload.trace_id and db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guardrail_results (trace_id, toxic, toxic_score, reason, domain, confidence_score)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (trace_id) DO UPDATE SET
                    toxic_score = $3, reason = $4, confidence_score = $6
            """, payload.trace_id,
                cascade_result.is_hallucination, cascade_result.hallucination_score,
                cascade_result.reason, payload.domain, cascade_result.confidence)

    return HallucinationResponse(
        hallucination_score=cascade_result.hallucination_score,
        confidence=cascade_result.confidence,
        reason=cascade_result.reason,
        verdicts=cascade_result.verdicts,
        action=action,
        requires_human_review=requires_review or action == "block",
    )



@app.post("/api/v1/hallucination/correct", response_model=CorrectionResponse)
async def correct_hallucination(payload: CorrectionRequest):
    """Correct a hallucinated response using metacognitive analysis."""
    if not corrector:
        raise HTTPException(status_code=503, detail="Corrector not initialized")

    result = await corrector.correct(
        original_prompt=payload.original_prompt,
        hallucinated_response=payload.hallucinated_response,
        error_type=payload.error_type,
    )

    return CorrectionResponse(
        corrected_response=result["corrected_response"],
        diagnosis=result["diagnosis"],
        confidence=result["confidence"],
        error=result.get("error"),
    )


@app.post("/api/v1/hallucination/override")
async def human_override(payload: OverrideRequest):
    """Record a human override of the hallucination detector verdict.
    
    This feeds into the closed-loop learning pipeline.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO hallucination_corrections 
                (trace_id, context, response, llm_verdict, llm_confidence, human_verdict, corrected_response, domain)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, payload.trace_id, payload.context, payload.response,
            payload.llm_verdict, payload.llm_confidence,
            payload.human_verdict, payload.corrected_response, payload.domain)

    return {"status": "recorded", "trace_id": payload.trace_id}


@app.get("/api/v1/hallucination/stats")
async def get_stats():
    """Get hallucination detection statistics."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not initialized")

    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM hallucination_corrections")
        flagged = await conn.fetchval(
            "SELECT COUNT(*) FROM hallucination_corrections WHERE llm_verdict = TRUE"
        )
        overridden = await conn.fetchval(
            "SELECT COUNT(*) FROM hallucination_corrections WHERE llm_verdict != human_verdict"
        )
        corrected = await conn.fetchval(
            "SELECT COUNT(*) FROM hallucination_corrections WHERE corrected_response IS NOT NULL"
        )

    return {
        "total_evaluations": total,
        "hallucinations_flagged": flagged,
        "human_overrides": overridden,
        "auto_corrections": corrected,
        "override_rate": round(overridden / max(total, 1) * 100, 1),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "hallucination-detector"}


@app.get("/api/v1/hallucination/health")
async def api_health():
    return {"status": "ok", "service": "hallucination-detector"}

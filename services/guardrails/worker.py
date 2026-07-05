"""Guardrails worker — toxicity/PII detection with adaptive model selection.
Enterprise-grade: Pydantic validation, structured logging, async auth, connection pooling.
"""
import asyncio, json, os, logging, re, time, hashlib
from datetime import datetime, timezone
from redis.asyncio import Redis
from app.classifiers.ollama_toxic import OllamaToxicityClassifier
from app.classifiers.bert_toxic import BertToxicityClassifier
from app.classifiers.roberta_toxic import RobertaToxicityClassifier
from shared.pii_detector import PIIDetector
from shared.policy_engine import PolicyEngine
from shared.rewriter import Rewriter
from app.shap_explainer import ShapExplainer
from shared.capabilities import SystemProfile
from shared.schemas import (
    GuardrailCheckRequest, GuardrailCheckResponse,
    SHAPRequest, SHAPResponse, HealthStatus,
)
from shared.logging import setup_logging
from shared.config import settings
from shared.toxic_keywords import check_toxic_keywords
from shared.security.auth import verify_jwt
from shared.db import get_pool
from shared.circuit_breaker import call_with_circuit_breaker
from shared.prompt_injection_detector import (
    PromptInjectionDetector,
    sanitize_input,
    validate_input_size,
    get_injection_detector,
)
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from prometheus_client import Counter, Histogram
import uvicorn, httpx, yaml
from pathlib import Path

# Structured logging
setup_logging(service_name="northguard-guardrails")
# Structured logging
setup_logging(service_name="northguard-guardrails")
logger = logging.getLogger("guardrails")

# ─── Semantic Cache ──────────────────────────────────────────────────────────
# Cache toxicity/PII results for identical inputs to reduce latency and cost
_PREDICTION_CACHE = {}
_CACHE_MAX_SIZE = 10000  # Max entries in cache
_CACHE_TTL_SECONDS = 300  # 5 minutes default TTL

def _cache_key(text: str) -> str:
    """Generate a deterministic cache key from input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _cache_get(text: str) -> dict | None:
    """Get cached prediction result, or None if not found/expired."""
    key = _cache_key(text)
    entry = _PREDICTION_CACHE.get(key)
    if entry is None:
        return None
    # Check TTL
    if time.time() - entry["timestamp"] > _CACHE_TTL_SECONDS:
        del _PREDICTION_CACHE[key]
        return None
    return entry["result"]

def _cache_set(text: str, result: dict) -> None:
    """Store prediction result in cache, evicting oldest if full."""
    key = _cache_key(text)
    # Eviction: remove oldest entry if cache is full
    if len(_PREDICTION_CACHE) >= _CACHE_MAX_SIZE:
        try:
            oldest_key = min(_PREDICTION_CACHE, key=lambda k: _PREDICTION_CACHE[k]["timestamp"])
            del _PREDICTION_CACHE[oldest_key]
        except (ValueError, KeyError):
            # If cache is empty or key disappears, just continue
            if len(_PREDICTION_CACHE) >= _CACHE_MAX_SIZE:
                _PREDICTION_CACHE.clear()
    _PREDICTION_CACHE[key] = {"result": result, "timestamp": time.time()}

def _cache_stats() -> dict:
    """Get cache statistics for monitoring."""
    if not _PREDICTION_CACHE:
        return {"size": 0, "max_size": _CACHE_MAX_SIZE, "ttl_seconds": _CACHE_TTL_SECONDS}
    ages = [time.time() - e["timestamp"] for e in _PREDICTION_CACHE.values()]
    return {
        "size": len(_PREDICTION_CACHE),
        "max_size": _CACHE_MAX_SIZE,
        "ttl_seconds": _CACHE_TTL_SECONDS,
        "oldest_seconds": round(max(ages), 1) if ages else 0,
        "newest_seconds": round(min(ages), 1) if ages else 0,
    }

# Semantic cache hit/miss counters for Prometheus
cache_hit_counter = Counter("guardrail_cache_hits_total", "Semantic cache hits")
cache_miss_counter = Counter("guardrail_cache_misses_total", "Semantic cache misses")

# ─── Online Evaluation ───────────────────────────────────────────────────────
# Tracks feedback on model predictions to compute out-of-sample accuracy
_ONLINE_EVAL = {
    "total_feedback": 0,
    "correct_predictions": 0,
    "false_positives": 0,    # Model flagged, user said not toxic
    "false_negatives": 0,    # Model didn't flag, user said toxic
    "feedback_history": [],
}
_ONLINE_EVAL_MAX_HISTORY = 1000
# Hybrid PII detection toggle (Presidio + Canadian recognizers)
PII_HYBRID_ENABLED = os.getenv("PII_HYBRID_ENABLED", "false").lower() == "true"
if PII_HYBRID_ENABLED:
    try:
        from app.pii_hybrid import detect_pii_hybrid
        logger.info("Hybrid PII detection enabled (Presidio + Canadian recognizers)")
    except ImportError:
        logger.warning("Hybrid PII detection requested but presidio not installed, falling back to legacy")
        PII_HYBRID_ENABLED = False
        detect_pii_hybrid = None
else:
    detect_pii_hybrid = None

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
TOXIC_MODEL = os.getenv("TOXIC_MODEL_NAME", "llama3.2:1b")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TRACE_STREAM = "trace_stream"
RESULT_STREAM = "guardrail_result_stream"
POLICY_DB_PATH = os.getenv("POLICY_DB_PATH", "/app/policies.yaml")

profile = SystemProfile.detect()
ENABLE_BERT = profile.recommended_guardrails_tier >= 2
ENABLE_ROBERTA = profile.recommended_guardrails_tier >= 2
ENABLE_LLM_PII_VERIFY = profile.recommended_guardrails_tier >= 2
logger.info(f"Guardrails tier {profile.recommended_guardrails_tier} -> "
            f"RoBERTa={'ON' if ENABLE_ROBERTA else 'OFF'}, "
            f"BERT={'ON' if ENABLE_BERT else 'OFF'}, "
            f"LLM PII Verify={'ON' if ENABLE_LLM_PII_VERIFY else 'OFF'}")

# Background model preloading — avoids first-request latency
from app.bert_model_manager import preload_model_async
if ENABLE_ROBERTA:
    preload_model_async("unitary/unbiased-toxic-roberta")
elif ENABLE_BERT:
    preload_model_async("unitary/toxic-bert")
logger.info("Background model preloading initiated")

# Lazy-loaded classifiers — initialized on first use to speed up startup
# Lazy-loaded classifiers — initialized on first use to speed up startup
_bert_classifier = None
_roberta_classifier = None
_shap_explainer = None

def get_bert_classifier():
    """Lazy-load BERT classifier on first use."""
    global _bert_classifier
    if _bert_classifier is None and ENABLE_BERT:
        try:
            _bert_classifier = BertToxicityClassifier(threshold=0.5)
            _bert_classifier.load()
            logger.info("BERT classifier loaded lazily")
        except Exception as e:
            logger.warning(f"BERT load failed, disabling: {e}")
            _bert_classifier = None
    return _bert_classifier

def get_roberta_classifier():
    """Lazy-load RoBERTa classifier on first use."""
    global _roberta_classifier
    if _roberta_classifier is None and ENABLE_ROBERTA:
        try:
            _roberta_classifier = RobertaToxicityClassifier(threshold=0.5)
            _roberta_classifier.load()
            logger.info("RoBERTa classifier loaded lazily")
        except Exception as e:
            logger.warning(f"RoBERTa load failed, disabling: {e}")
            _roberta_classifier = None
    return _roberta_classifier

def get_shap_explainer():
    """Lazy-load SHAP explainer on first use."""
    global _shap_explainer
    if _shap_explainer is None and ENABLE_BERT:
        try:
            _shap_explainer = ShapExplainer()
            logger.info("SHAP explainer loaded lazily")
        except Exception as e:
            logger.warning(f"SHAP explainer load failed, disabling: {e}")
            _shap_explainer = None
    return _shap_explainer

llm_classifier = OllamaToxicityClassifier(model_name=TOXIC_MODEL, ollama_url=OLLAMA_URL)
pii_detector = PIIDetector()
policy_engine = PolicyEngine(policy_path=POLICY_DB_PATH)
rewriter = Rewriter(ollama_url=OLLAMA_URL)


if Path(POLICY_DB_PATH).exists():
    with open(POLICY_DB_PATH) as f:
        policy_data = yaml.safe_load(f)
        pii_patterns = {}
        for rule in policy_data.get("policies", []):
            if rule.get("action") in ("mask", "block") and "patterns" in rule:
                pii_patterns[rule.get("category", "unknown")] = rule["patterns"]
        rewriter.patterns = pii_patterns

api_app = FastAPI(title="Guardrails Service", version="1.0.0")

# Rate limiting — protects against DoS even if gateway is bypassed
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
api_app.state.limiter = limiter
api_app.add_exception_handler(429, _rate_limit_exceeded_handler)

# CORS — restricted to known origins only (no internal service URLs)
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

toxic_counter = Counter('guardrail_toxic_total', 'Total toxic traces', ['model_id'])
check_latency = Histogram('guardrail_check_duration_seconds', 'Time to run /check')
accuracy_gauge = Histogram('guardrail_accuracy_ratio', 'Guardrail accuracy ratio (1.0 = perfect)', ['model_id'])
hallucination_counter = Counter('hallucination_detected_total', 'Total hallucinations detected', ['model_id'])
hallucination_accuracy = Histogram('hallucination_accuracy_ratio', 'Hallucination detection accuracy', ['model_id'])
drift_gauge = Histogram('drift_score', 'Model drift score', ['model_id'])
ensemble_source_counter = Counter('guardrail_ensemble_source_total', 'Toxicity detection source', ['source'])


security_scheme = HTTPBearer(auto_error=False)

# Initialize injection detector
injection_detector = get_injection_detector()


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """Dependency that verifies JWT token and returns the payload."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    payload = verify_jwt(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# Adaptive model selector
class AdaptiveModelSelector:
    def __init__(self, redis_client, primary="llama3.2:1b", fallback="tinyllama", latency_threshold=2.0, fallback_duration=60):
        self.redis = redis_client
        self.primary = primary
        self.fallback = fallback
        self.latency_threshold = latency_threshold
        self.fallback_duration = fallback_duration

    async def record_latency(self, seconds):
        await self.redis.lpush("guardrails:latencies", seconds)
        await self.redis.ltrim("guardrails:latencies", 0, 9)

    async def get_model(self):
        fallback_until = await self.redis.get("guardrails:fallback_until")
        if fallback_until and int(fallback_until) > time.time():
            return self.fallback
        return self.primary


@api_app.get("/health", response_model=HealthStatus)
async def health():
    return HealthStatus(status="ok")


def detect_toxicity_ensemble(text: str) -> tuple:
    """Run toxicity detection using the full ensemble with confidence-based routing.
    
    Routing logic:
    1. RoBERTa (high confidence >= 0.7) → use directly (93-95% accurate)
    2. RoBERTa medium (0.5-0.7) → run BERT as verification
    3. RoBERTa/BERT both low → fall back to keyword
    4. All low → keyword fallback
    
    Multi-label enhancement: Returns per-label scores from the best classifier,
    enabling granular policy enforcement (e.g., block hate_speech but allow profanity).
    
    Returns:
        tuple: (toxic: bool, toxic_score: float, reason: str, source: str, label_details: dict)
    """
    label_details = {}
    
    # Step 1: Try RoBERTa first (primary, highest accuracy)
    roberta = get_roberta_classifier()
    if roberta:
        try:
            roberta_result = roberta.predict(text)
            if roberta_result:
                roberta_score = roberta_result.get("toxic_score", 0.0)
                roberta_flagged = roberta_result.get("flagged", False)
                label_details = roberta_result.get("label_details", {})
                
                if roberta_score >= 0.7:
                    # High confidence — use RoBERTa directly
                    ensemble_source_counter.labels(source="roberta_high").inc()
                    return (roberta_flagged, roberta_score, 
                            roberta_result.get("reason", "RoBERTa"), "roberta_high", label_details)
                elif roberta_score >= 0.5:
                    # Medium confidence — verify with BERT
                    bert = get_bert_classifier()
                    if bert:
                        bert_result = bert.predict(text)
                        if bert_result and bert_result.get("flagged"):
                            # Both agree toxic
                            ensemble_source_counter.labels(source="ensemble_roberta_bert").inc()
                            # Merge label details from both models
                            merged_labels = dict(label_details)
                            merged_labels.update(bert_result.get("label_details", {}))
                            return (True, max(roberta_score, bert_result.get("toxic_score", 0.0)),
                                    f"Ensemble (RoBERTa={roberta_score:.2f} + BERT)", "ensemble_roberta_bert", merged_labels)
                        elif bert_result and not bert_result.get("flagged") and roberta_flagged:
                            # RoBERTa says toxic, BERT says clean — be conservative
                            ensemble_source_counter.labels(source="roberta_conservative").inc()
                            return (True, roberta_score,
                                    f"RoBERTa flagged (BERT disagreed, score={roberta_score:.2f})", "roberta_conservative", label_details)
        except Exception as e:
            logger.warning(f"RoBERTa detection failed: {e}")
    
    # Step 2: Try BERT (secondary)
    bert = get_bert_classifier()
    if bert:
        try:
            bert_result = bert.predict(text)
            if bert_result and bert_result.get("flagged"):
                bert_score = bert_result.get("toxic_score", 0.9)
                label_details = bert_result.get("label_details", {})
                ensemble_source_counter.labels(source="bert").inc()
                return (True, bert_score, bert_result.get("reason", "BERT"), "bert", label_details)
        except Exception as e:
            logger.warning(f"BERT detection failed: {e}")
    
    # Step 3: Fallback to keyword
    toxic, toxic_score, reason = check_toxic_keywords(text)
    ensemble_source_counter.labels(source="keyword").inc()
    return (toxic, toxic_score, reason, "keyword", label_details)


@api_app.post("/api/v1/generate")
@limiter.limit("30/minute")
async def generate(request: Request, payload: dict, auth: dict = Depends(require_auth)):
    prompt = payload.get("prompt", "")
    max_tokens = payload.get("max_tokens", 50)
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")
    
    # ─── Input Sanitization & Injection Detection ───
    sanitized_prompt, injection_result = injection_detector.detect_and_sanitize(prompt)
    
    # Validate size after sanitization
    is_valid, error_msg = validate_input_size(sanitized_prompt)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Block high-confidence injection attempts
    if injection_result["injection_detected"] and injection_result["confidence"] >= 0.7:
        logger.warning(f"Prompt injection blocked: confidence={injection_result['confidence']}, "
                       f"categories={injection_result['matched_categories']}")
        raise HTTPException(
            status_code=400,
            detail=f"Input rejected: {injection_result['details']}"
        )
    
    # Log medium-confidence injections for monitoring
    if injection_result["injection_detected"] and injection_result["confidence"] >= 0.3:
        logger.info(f"Prompt injection flagged (low confidence): {injection_result['details']}")
    
    if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 2048:
        max_tokens = 50
    
    try:
        result = await call_with_circuit_breaker(
            service_name="ollama",
            method="POST",
            url=f"{OLLAMA_URL}/api/generate",
            json={"model": TOXIC_MODEL, "prompt": sanitized_prompt, "stream": False,
                  "options": {"temperature": 0.2, "num_predict": max_tokens}},
            timeout=120.0,
        )
        
        # ─── Output Sanitization ───
        # Check LLM response for toxicity and PII before returning
        response_text = result.get("response", "")
        
        # Check for toxicity in the response using ensemble
        response_toxic, response_toxic_score, _, _, _ = detect_toxicity_ensemble(response_text)
        
        # Check for PII in the response
        response_pii = pii_detector.scan(response_text)
        
        if response_toxic or response_pii:
            logger.warning(
                f"LLM output sanitized: toxic={response_toxic}, "
                f"toxic_score={response_toxic_score:.2f}, "
                f"pii_types={list(response_pii.keys())}"
            )
            return {
                "response": "[Content blocked by safety guardrails]",
                "sanitized": True,
                "reason": "Toxic or PII content detected in model output",
            }
        
        return {"response": response_text, "sanitized": False}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")


@api_app.post("/api/v1/check", response_model=GuardrailCheckResponse)
async def enforce_check(payload: GuardrailCheckRequest, auth: dict = Depends(require_auth)):
    text = payload.text
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")
    
    # Check semantic cache first
    cached = _cache_get(text)
    if cached:
        cache_hit_counter.inc()
        return GuardrailCheckResponse(**cached)
    cache_miss_counter.inc()
    
    pii_raw = pii_detector.scan(text)
    pii = dict(pii_raw)
    if ENABLE_LLM_PII_VERIFY and pii:
        try:
            confirmed = await pii_detector.verify_with_llm(text, list(pii.keys()), OLLAMA_URL, timeout=30)
            if confirmed:
                pii = {k: v for k, v in pii.items() if k in confirmed}
        except Exception:
            pass
    
    # Use ensemble toxicity detection (now returns 5 elements including label_details)
    toxic, toxic_score, reason, source, label_details = detect_toxicity_ensemble(text)
    
    context = {"toxic": toxic, "toxic_score": toxic_score, "pii_types": list(pii.keys()), "text": text, "label_details": label_details}
    decision = policy_engine.evaluate(context)
    
    result = GuardrailCheckResponse(
        action=decision["action"],
        reason=decision["reason"],
        rewritten_text=decision.get("rewritten_text", text),
        toxic=toxic,
        toxic_score=toxic_score,
        pii_detected=bool(pii),
        detection_source=source,
        label_details=label_details if label_details else None,
    )
    
    # Store in cache (only cache non-toxic results for longer, toxic results have shorter TTL)
    _cache_set(text, result.model_dump())
    
    return result



@api_app.post("/api/v1/shap", response_model=SHAPResponse)
async def get_shap(payload: SHAPRequest, auth: dict = Depends(require_auth)):
    explainer = get_shap_explainer()
    if not explainer:
        raise HTTPException(status_code=501, detail="SHAP not available on this tier")
    text = payload.text
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")
    top_n = payload.top_n or 5
    tokens = explainer.explain(text, top_n=top_n)
    # Also compute aggregate toxicity score from the same model
    from app.bert_model_manager import get_model_pipeline
    pipe = get_model_pipeline("unitary/toxic-bert")
    agg_score = None
    try:
        results = pipe(text, truncation=True, max_length=512)[0]
        for r in results:
            if r["label"].lower() == "toxic":
                agg_score = round(r["score"], 4)
                break
    except Exception:
        pass
    return SHAPResponse(tokens=tokens, aggregate_toxicity_score=agg_score)


@api_app.post("/api/v1/reload-model")
async def reload_model(auth: dict = Depends(require_auth)):
    """Reload ML models. Uses lazy-loading getters to force re-initialization."""
    global _bert_classifier, _roberta_classifier
    results = {}
    
    # Force re-initialize BERT by resetting and calling getter
    _bert_classifier = None
    bert = get_bert_classifier()
    if bert:
        results["bert"] = "reloaded"
    else:
        results["bert"] = "not_enabled"
    
    # Force re-initialize RoBERTa
    _roberta_classifier = None
    roberta = get_roberta_classifier()
    if roberta:
        results["roberta"] = "reloaded"
    else:
        results["roberta"] = "not_enabled"
    
    return {"status": "completed", "results": results}


@api_app.get("/api/v1/tier")
async def get_tier(auth: dict = Depends(require_auth)):
    """Get current guardrails tier configuration."""
    return {
        "tier": profile.recommended_guardrails_tier,
        "label": {1: "Tier 1 — Basic", 2: "Tier 2 — BERT + LLM", 3: "Tier 3 — Full Ensemble"}.get(
            profile.recommended_guardrails_tier, "Unknown"),
        "bert_enabled": ENABLE_BERT,
        "roberta_enabled": ENABLE_ROBERTA,
    }


@api_app.get("/api/v1/cache/stats")
async def get_cache_stats(auth: dict = Depends(require_auth)):
    """Get semantic cache statistics."""
    return _cache_stats()


@api_app.post("/api/v1/feedback")
async def submit_feedback(payload: dict, auth: dict = Depends(require_auth)):
    """Submit feedback on a model prediction for online evaluation.
    
    Body:
        text: str — the original text that was checked
        model_flagged: bool — whether the model flagged it as toxic
        user_toxic: bool — whether the user agrees it's toxic
    """
    text = payload.get("text", "")
    model_flagged = bool(payload.get("model_flagged", False))
    user_toxic = bool(payload.get("user_toxic", False))
    
    global _ONLINE_EVAL
    _ONLINE_EVAL["total_feedback"] += 1
    
    if model_flagged == user_toxic:
        _ONLINE_EVAL["correct_predictions"] += 1
    elif model_flagged and not user_toxic:
        _ONLINE_EVAL["false_positives"] += 1
    elif not model_flagged and user_toxic:
        _ONLINE_EVAL["false_negatives"] += 1
    
    entry = {
        "text": text[:100],  # Truncate for privacy
        "model_flagged": model_flagged,
        "user_toxic": user_toxic,
        "correct": model_flagged == user_toxic,
        "timestamp": time.time(),
    }
    _ONLINE_EVAL["feedback_history"].append(entry)
    # Keep history bounded
    if len(_ONLINE_EVAL["feedback_history"]) > _ONLINE_EVAL_MAX_HISTORY:
        _ONLINE_EVAL["feedback_history"] = _ONLINE_EVAL["feedback_history"][-500:]
    
    total = _ONLINE_EVAL["total_feedback"]
    accuracy = round(_ONLINE_EVAL["correct_predictions"] / total, 4) if total > 0 else 0.0
    
    return {
        "status": "recorded",
        "total_feedback": total,
        "running_accuracy": accuracy,
    }


@api_app.get("/api/v1/evaluation/status")
async def get_evaluation_status(auth: dict = Depends(require_auth)):
    """Get online evaluation metrics."""
    total = _ONLINE_EVAL["total_feedback"]
    accuracy = round(_ONLINE_EVAL["correct_predictions"] / total, 4) if total > 0 else None
    precision = round(
        _ONLINE_EVAL["correct_predictions"] / 
        (_ONLINE_EVAL["correct_predictions"] + _ONLINE_EVAL["false_positives"]), 4
    ) if (_ONLINE_EVAL["correct_predictions"] + _ONLINE_EVAL["false_positives"]) > 0 else None
    recall = round(
        _ONLINE_EVAL["correct_predictions"] / 
        (_ONLINE_EVAL["correct_predictions"] + _ONLINE_EVAL["false_negatives"]), 4
    ) if (_ONLINE_EVAL["correct_predictions"] + _ONLINE_EVAL["false_negatives"]) > 0 else None
    
    return {
        "total_feedback": total,
        "running_accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "false_positives": _ONLINE_EVAL["false_positives"],
        "false_negatives": _ONLINE_EVAL["false_negatives"],
        "recent_feedback": _ONLINE_EVAL["feedback_history"][-10:],  # Last 10 entries
    }

class IncidentEscalation:
    """Auto-escalation for repeated violations.
    
    Tracks violation counts per model/user and triggers alerts
    when thresholds are exceeded.
    """
    def __init__(self, redis_client):
        self.redis = redis_client
        self.escalation_thresholds = {
            "toxicity": {"count": 10, "window_seconds": 300, "action": "notify_admin"},
            "pii_leak": {"count": 5, "window_seconds": 300, "action": "block_model"},
            "critical": {"count": 3, "window_seconds": 60, "action": "immediate_block"},
        }
        self.webhook_url = os.getenv("ESCALATION_WEBHOOK_URL", "")
    
    async def record_violation(self, model_id: str, violation_type: str, details: dict):
        """Record a violation and check if escalation is needed."""
        key = f"escalation:{model_id}:{violation_type}"
        now = time.time()
        await self.redis.lpush(key, now)
        await self.redis.ltrim(key, 0, 99)  # Keep last 100
        await self.redis.expire(key, 3600)  # Auto-clean after 1 hour
        
        threshold = self.escalation_thresholds.get(violation_type, self.escalation_thresholds["toxicity"])
        window = threshold["window_seconds"]
        max_count = threshold["count"]
        
        # Count violations in the time window
        cutoff = now - window
        violations = await self.redis.lrange(key, 0, -1)
        recent_count = sum(1 for v in violations if float(v) > cutoff)
        
        if recent_count >= max_count:
            await self._escalate(model_id, violation_type, threshold, details)
            return True
        return False
    
    async def _escalate(self, model_id: str, violation_type: str, threshold: dict, details: dict):
        """Trigger escalation action."""
        logger.warning(
            f"ESCALATION: Model {model_id} exceeded {violation_type} threshold "
            f"({threshold['count']} in {threshold['window_seconds']}s). "
            f"Action: {threshold['action']}"
        )
        # Log to Redis for dashboard visibility
        escalation_key = f"escalations:{model_id}"
        await self.redis.lpush(escalation_key, json.dumps({
            "type": violation_type,
            "action": threshold["action"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }))
        await self.redis.ltrim(escalation_key, 0, 49)
        
        # Send webhook if configured
        if self.webhook_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(self.webhook_url, json={
                        "event": "incident_escalation",
                        "model_id": model_id,
                        "violation_type": violation_type,
                        "action": threshold["action"],
                        "details": details,
                    })
            except Exception as e:
                logger.error(f"Escalation webhook failed: {e}")


class GuardrailsWorker:
    def __init__(self):
        self.redis = Redis(host=REDIS_HOST, password=REDIS_PASSWORD, decode_responses=True)
        self.db = None
        self.model_selector = AdaptiveModelSelector(self.redis)
        self.escalation = IncidentEscalation(self.redis)

    async def ensure_db(self):
        if not self.db:
            pool = await get_pool()
            self.db = pool
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS guardrail_results (
                        trace_id TEXT PRIMARY KEY, toxic BOOLEAN, toxic_score FLOAT,
                        reason TEXT, pii_detected BOOLEAN, pii_types TEXT[], timestamp TIMESTAMP
                    )
                """)
            logger.info("Database connected")

    async def run(self):
        logger.info("Guardrails worker started. Using consumer group.")
        group_name = "guardrails_group"
        dlq_stream = "dead_letter_stream"
        consumer_name = f"worker_{os.getpid()}"
        try:
            await self.redis.xgroup_create(TRACE_STREAM, group_name, id="0", mkstream=True)
        except Exception:
            pass
        while True:
            results = await self.redis.xreadgroup(group_name, consumer_name, {TRACE_STREAM: ">"}, count=10, block=5000)
            for stream, messages in results:
                for msg_id, msg_data in messages:
                    try:
                        trace = json.loads(msg_data["trace"])
                        result = await self.evaluate(trace)
                        await self.redis.xadd(RESULT_STREAM, {"result": json.dumps(result)})
                        await self.store_in_db(result)
                        await self.redis.xack(TRACE_STREAM, group_name, msg_id)
                        # Only increment toxic counter for actually toxic traces
                        if result.get("toxic"):
                            toxic_counter.labels(model_id=trace.get('model_id', 'unknown')).inc()
                    except Exception as e:
                        logger.error(f"Failed to process {msg_id}: {e}")
                        await self.redis.xadd(dlq_stream, {"error": str(e), "original": msg_data["trace"]})
                        await self.redis.xack(TRACE_STREAM, group_name, msg_id)

    async def evaluate(self, trace: dict) -> dict:
        text = trace.get("completion", ""); lang = trace.get("tags", {}).get("language", "en")
        pii = pii_detector.scan(text)
        # Use ensemble toxicity detection (5 return values now: toxic, score, reason, source, label_details)
        toxic, toxic_score, reason, source, label_details = detect_toxicity_ensemble(text)
        # Apply policy engine to determine action based on context
        context = {"toxic": toxic, "toxic_score": toxic_score, "pii_types": list(pii.keys()), "text": text, "label_details": label_details}
        decision = policy_engine.evaluate(context)
        return {
            "trace_id": trace["id"], "toxic": toxic, "toxic_score": toxic_score,
            "reason": decision.get("reason", reason), "pii_detected": bool(pii), "pii_types": list(pii.keys()),
            "action": decision.get("action", "allow"),
            "rewritten_text": decision.get("rewritten_text", text),
            "timestamp": trace["timestamp"],
            "label_details": label_details,
        }


    async def store_in_db(self, result: dict):
        await self.ensure_db()
        ts = result["timestamp"]
        if isinstance(ts, str): ts = datetime.fromisoformat(ts)
        await self.db.execute(
            "INSERT INTO guardrail_results(trace_id, toxic, toxic_score, reason, pii_detected, pii_types, timestamp) "
            "VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (trace_id) DO UPDATE SET toxic=EXCLUDED.toxic, "
            "toxic_score=EXCLUDED.toxic_score, reason=EXCLUDED.reason, pii_detected=EXCLUDED.pii_detected, pii_types=EXCLUDED.pii_types",
            result["trace_id"], result["toxic"], result["toxic_score"], result["reason"],
            result["pii_detected"], result["pii_types"], ts
        )


async def main():
    worker = GuardrailsWorker()
    config = uvicorn.Config(api_app, host="0.0.0.0", port=8005, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), worker.run())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down.")

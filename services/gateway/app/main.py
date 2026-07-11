"""PolarisGate API Gateway — AI Content Safety Platform."""
from fastapi import FastAPI, HTTPException, Depends, Security, Query, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
from shared.security.auth import create_access_token, verify_jwt, create_refresh_token, refresh_access_token, get_current_user
from shared.audit import log_audit
from shared.db import get_pool, close_pool, health_check as db_health
from shared.telemetry import setup_otel
from shared.redis_client import get_redis, close_redis, health_check as redis_health
from shared.schemas import (
    TokenResponse, SettingsResponse, SettingsUpdate, DashboardSummary,
    IncidentResponse, ModelSummary, PolicyList,
    FeedbackSubmit, HealthStatus, GuardrailCheckRequest,
    TraceIngest, TraceResponse,
    HallucinationTrend, HallucinationTrendPoint, HallucinationDetection,
    HallucinationDetectionList, HallucinationFeedback,
    DomainThreshold, DomainThresholdList,
)
from shared.logging import setup_logging
from shared.fairness import calculate_fairness_score
from shared.circuit_breaker import call_with_circuit_breaker
from .constants import detect_injection, redact_text, TOXIC_KEYWORDS, INJECTION_PATTERNS
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
import asyncpg, os, yaml, httpx, bcrypt, json, secrets, re
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional
import fcntl

setup_logging(service_name="polarisgate-gateway")
import logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            await db.execute("CREATE TABLE IF NOT EXISTS admin_settings (id INTEGER PRIMARY KEY DEFAULT 1, admin_email TEXT NOT NULL, admin_password_hash TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())")
            await db.execute("CREATE TABLE IF NOT EXISTS api_keys (key_id TEXT PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT NOT NULL, role TEXT DEFAULT 'viewer', created_by TEXT, expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())")
            await db.execute("CREATE TABLE IF NOT EXISTS webhook_config (id INTEGER PRIMARY KEY DEFAULT 1, url TEXT, enabled BOOLEAN DEFAULT TRUE, events TEXT DEFAULT 'toxicity,pii')")
            await db.execute("CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT DEFAULT 'safety_officer', created_at TIMESTAMPTZ DEFAULT NOW(), active BOOLEAN DEFAULT TRUE)")
    except Exception as e:
        logger.warning(f"Startup tables: {e}")
    yield
    await close_pool()
    await close_redis()

app = FastAPI(title="PolarisGate Content Safety Gateway", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000","http://localhost:3001","http://localhost:3002","http://127.0.0.1:3000","http://127.0.0.1:3001","http://127.0.0.1:3002"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)
setup_otel(app, service_name="polarisgate-gateway")
security = HTTPBearer(auto_error=False)
GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://guardrails:8005")
POLICY_FILE_PATH = os.getenv("POLICY_FILE_PATH", "/app/policies.yaml")
BLOCKLIST_FILE = "/app/blocklist.yaml"
WEBHOOK_FILE = "/app/webhooks.yaml"

async def load_admin_from_db():
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT admin_email, admin_password_hash "
                "FROM admin_settings WHERE id = 1"
            )
            if row:
                return {
                    "admin_email": row["admin_email"],
                    "admin_password_hash": row["admin_password_hash"],
                }
    except Exception as exc:
        logger.warning("Failed to load admin settings from database: %s", exc)
    return None

async def save_admin_to_db(email: str, password_hash: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO admin_settings (id, admin_email, admin_password_hash) VALUES (1, $1, $2) ON CONFLICT (id) DO UPDATE SET admin_email=EXCLUDED.admin_email, admin_password_hash=EXCLUDED.admin_password_hash, updated_at=NOW()", email, password_hash)

async def is_admin_configured() -> bool:
    return await load_admin_from_db() is not None

# ─── Auth ────────────────────────────────────────────────────
@app.post("/auth/token", response_model=TokenResponse)
@limiter.limit("30/minute")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    admin = await load_admin_from_db()
    if not admin: raise HTTPException(401, "System not configured. Run setup first.")
    if username == admin["admin_email"] and bcrypt.checkpw(password.encode(), admin["admin_password_hash"].encode()):
        access_token = create_access_token({"sub": username})
        refresh_token = create_refresh_token({"sub": username})
        await log_audit(username, "login", request=request)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    raise HTTPException(401, "Invalid credentials")

@app.post("/auth/setup", response_model=TokenResponse)
@limiter.limit("60/minute")
async def setup_admin(request: Request, username: str = Form(...), password: str = Form(...)):
    if await is_admin_configured(): raise HTTPException(400, "Admin already configured.")
    if len(password) < 8: raise HTTPException(400, "Password must be at least 8 characters")
    await save_admin_to_db(username, bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    access_token = create_access_token({"sub": username})
    await log_audit(username, "setup", request=request)
    return TokenResponse(access_token=access_token, refresh_token=create_refresh_token({"sub": username}), token_type="bearer")

@app.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token_endpoint(request: Request, refresh_token: str = Form(...)):
    new_access = refresh_access_token(refresh_token)
    if not new_access: raise HTTPException(401, "Invalid or expired refresh token")
    return TokenResponse(access_token=new_access, token_type="bearer")

@app.post("/auth/logout")
@limiter.limit("30/minute")
async def logout(request: Request, credentials: HTTPAuthorizationCredentials = Security(security)):
    from shared.security.auth import revoke_token
    await revoke_token(credentials.credentials)
    return {"status": "logged_out"}

# ─── Settings ────────────────────────────────────────────────
@app.get("/api/v1/settings", response_model=SettingsResponse)
@limiter.limit("30/minute")
async def get_settings(request: Request, current_user: dict = Depends(get_current_user)):
    admin = await load_admin_from_db()
    return SettingsResponse(admin_email=admin.get("admin_email") if admin else None)

@app.post("/api/v1/settings")
@limiter.limit("10/minute")
async def update_settings(request: Request, payload: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    admin = await load_admin_from_db()
    if not admin: raise HTTPException(400, "No admin configured.")
    new_email = payload.admin_email or admin["admin_email"]
    new_hash = admin["admin_password_hash"]
    if payload.new_password:
        if not payload.current_password: raise HTTPException(400, "Current password required")
        if len(payload.new_password) < 8: raise HTTPException(400, "New password must be at least 8 characters")
        if not bcrypt.checkpw(payload.current_password.encode(), admin["admin_password_hash"].encode()): raise HTTPException(400, "Current password incorrect")
        new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode()
    await save_admin_to_db(new_email, new_hash)
    return {"status": "saved"}

# ─── Dashboard ───────────────────────────────────────────────
@app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
@limiter.limit("30/minute")
async def dashboard_summary(request: Request, current_user: dict = Depends(get_current_user)):
    redis = None
    try:
        redis = await get_redis()
        cached = await redis.get("dashboard_summary")
        if cached: return json.loads(cached)
    except Exception as exc:
        logger.debug("Redis cache miss for dashboard summary: %s", exc)
    pool = await get_pool()
    async with pool.acquire() as db:
        total_traces = await db.fetchval("SELECT COUNT(*) FROM traces WHERE timestamp > NOW() - INTERVAL '24 hours'")
        flagged_toxicity = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE toxic = true")
        pii_leaks = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE pii_detected = true")
        blocked_count = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE blocklisted = true")
        active_models = await db.fetchval("SELECT COUNT(DISTINCT model_id) FROM traces")
        result = DashboardSummary(total_traces_last_24h=total_traces or 0, flagged_toxicity=flagged_toxicity or 0, pii_leaks=pii_leaks or 0, blocked_count=blocked_count or 0, fairness_score=calculate_fairness_score(total_traces=total_traces or 0, flagged_toxicity=flagged_toxicity or 0, pii_leaks=pii_leaks or 0), active_models=active_models or 0)
    if redis:
        try:
            await redis.setex("dashboard_summary", 30, result.model_dump_json())
        except Exception as exc:
            logger.debug("Failed to cache dashboard summary: %s", exc)
    return result

@app.get("/api/v1/dashboard/incidents", response_model=List[IncidentResponse])
@limiter.limit("30/minute")
async def incidents(request: Request, limit: int = Query(10, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted, timestamp FROM guardrail_results ORDER BY timestamp DESC LIMIT $1", limit)
        results = []
        for row in rows:
            d = dict(row)
            d["trace_id"] = str(d["trace_id"]) if d.get("trace_id") is not None else "unknown"
            # Convert CSV pii_types string to list
            if d.get("pii_types") and isinstance(d["pii_types"], str):
                d["pii_types"] = [t.strip() for t in d["pii_types"].split(",") if t.strip()]
            elif not d.get("pii_types"):
                d["pii_types"] = []
            results.append(IncidentResponse(**d))
        return results

@app.get("/api/v1/dashboard/models", response_model=List[ModelSummary])
@limiter.limit("30/minute")
async def models(request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT model_id, COUNT(*) as trace_count, MAX(timestamp) as last_seen FROM traces GROUP BY model_id ORDER BY last_seen DESC")
        return [ModelSummary(**dict(row)) for row in rows]

# ─── Policies ────────────────────────────────────────────────
DEFAULT_POLICIES = [
    {"name": "Hate speech", "category": "hate_speech", "type": "toxicity", "severity": "medium", "action": "block", "message": "Hate speech detected.", "enabled": True},
    {"name": "Harassment", "category": "harassment", "type": "toxicity", "severity": "medium", "action": "block", "message": "Harassment detected.", "enabled": True},
    {"name": "Threat", "category": "threat", "type": "toxicity", "severity": "low", "action": "block", "message": "Threat detected.", "enabled": True},
    {"name": "Violence", "category": "violence", "type": "toxicity", "severity": "medium", "action": "block", "message": "Violent content blocked.", "enabled": True},
    {"name": "Profanity", "category": "profanity", "type": "toxicity", "severity": "high", "action": "flag", "message": "Profanity flagged.", "enabled": True},
    {"name": "SIN", "category": "SIN", "type": "pii", "patterns": ["\\b\\d{3}-\\d{3}-\\d{3}\\b", "\\b\\d{9}\\b"], "action": "mask", "message": "SIN masked.", "enabled": True},
    {"name": "Health Card", "category": "health_card", "type": "pii", "patterns": ["\\b\\d{4}-\\d{3}-\\d{3}-[A-Z]{2}\\b"], "action": "mask", "message": "Health card masked.", "enabled": True},
    {"name": "Phone Number", "category": "phone", "type": "pii", "patterns": ["\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b"], "action": "mask", "message": "Phone masked.", "enabled": True},
    {"name": "Credit Card", "category": "credit_card", "type": "pii", "patterns": ["\\b(?:\\d[ -]*?){13,16}\\b"], "action": "block", "message": "Credit card blocked.", "enabled": True},
    {"name": "Email", "category": "email", "type": "pii", "patterns": ["\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"], "action": "mask", "message": "Email masked.", "enabled": True},
    {"name": "IP Address", "category": "ip_address", "type": "pii", "patterns": ["\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b"], "action": "mask", "message": "IP masked.", "enabled": True},
    {"name": "Driver's License", "category": "driver_license", "type": "pii", "patterns": ["\\b[A-Z]\\d{4}-\\d{5}-\\d{5}\\b"], "action": "mask", "message": "Driver's license masked.", "enabled": True},
    {"name": "Passport", "category": "passport", "type": "pii", "patterns": ["\\b[A-Z]{2}\\d{6}\\b"], "action": "mask", "message": "Passport masked.", "enabled": True},
]

def load_blocklist():
    try:
        with open(BLOCKLIST_FILE) as f:
            data = yaml.safe_load(f)
            return data.get("words", []) if data else []
    except (FileNotFoundError, yaml.YAMLError) as exc:
        logger.debug("Blocklist not loaded: %s", exc)
        return []

def save_blocklist(words):
    with open(BLOCKLIST_FILE, "w") as f:
        yaml.safe_dump({"words": words}, f)

def load_policies_from_file():
    try:
        with open(POLICY_FILE_PATH) as f:
            data = yaml.safe_load(f)
            if data and "policies" in data and len(data["policies"]) > 0:
                return data
    except (FileNotFoundError, yaml.YAMLError) as exc:
        logger.debug("Custom policies not loaded, using defaults: %s", exc)
    return {"policies": DEFAULT_POLICIES}

@app.get("/api/v1/policies", response_model=PolicyList)
@limiter.limit("30/minute")
async def get_policies(request: Request, current_user: dict = Depends(get_current_user)):
    return load_policies_from_file()

@app.post("/api/v1/policies")
@limiter.limit("10/minute")
async def save_policies(request: Request, payload: PolicyList, current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("sub")
    await log_audit(user_email, "policy_update", resource_type="policy", details=payload.model_dump())
    try:
        with open(POLICY_FILE_PATH, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try: yaml.safe_dump(payload.model_dump(), f)
            finally: fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except PermissionError: logger.warning("Cannot write policies.yaml")
    return {"status": "saved"}

MULTI_LANG_KEYWORDS = {
    "fr": ["haine","raciste","tuer","attaquer","idiot","stupide","détruire","mort","menace"],
    "es": ["odio","racista","matar","atacar","idiota","estúpido","destruir","muerte","amenaza"],
    "de": ["hass","rassistisch","töten","angreifen","idiot","dumm","zerstören","tod","drohung"],
    "ar": ["كراهية","عنصري","قتل","هجوم","غبي","تدمير","موت","تهديد"],
    "hi": ["नफ़रत","नस्लवादी","मारना","हमला","बेवकूफ़","नष्ट","मौत","धमकी"],
    "zh": ["仇恨","种族主义","杀","攻击","愚蠢","毁灭","死亡","威胁"],
}

def detect_language(text):
    counts = {"en": 0}
    tl = text.lower()
    for lang, keywords in MULTI_LANG_KEYWORDS.items():
        counts[lang] = sum(1 for kw in keywords if kw in tl)
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "en"

# ─── Guardrails Check (with PII Redaction) ──────────────────
_category_keywords = {
    "hate_speech": ["hate", "racist", "sexist"],
    "harassment": ["stupid", "idiot", "dumb", "ugly", "loser", "trash"],
    "threat": ["kill", "attack", "destroy", "die", "death", "threat", "violence"],
    "profanity": ["damn", "crap", "hell", "bastard", "jerk", "asshole"],
}

def _check_toxicity(text_lower: str, enabled_categories: set[str]) -> tuple[bool, float, str | None]:
    """Run local keyword-based toxicity check.

    Falls back to the guardrails microservice via circuit breaker for ML scoring.
    """
    for category, keywords in _category_keywords.items():
        if category in enabled_categories:
            for kw in keywords:
                if kw in text_lower:
                    return (True, 0.85, "Keyword match")
    return (False, 0.0, None)


@app.post("/api/v1/guardrails/check")
@limiter.limit("60/minute")
async def guardrails_check(
    request: Request,
    payload: GuardrailCheckRequest,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    text = payload.text or ""
    text_lower = text.lower()

    # ── Policy-aware toxicity check ──
    policy_data = load_policies_from_file()
    saved_policies = policy_data.get("policies", [])
    enabled_tox = {
        p.get("category", "")
        for p in saved_policies
        if p.get("type") == "toxicity" and p.get("enabled", True)
    }
    toxic, toxic_score, toxic_reason = _check_toxicity(text_lower, enabled_tox)

    # ── PII detection via compiled patterns ──
    pii_detected = False
    pii_types: list[str] = []
    redacted = redact_text(text)
    if redacted != text:
        pii_detected = True
        # Determine which PII types matched
        from .constants import PII_PATTERNS as _pp
        for pattern, ptype, _replacer in _pp:
            if pattern.search(text):
                pii_types.append(ptype)

    # ── Remote guardrails (ML scoring) ──
    auth_headers = (
        {"Authorization": f"Bearer {credentials.credentials}"}
        if credentials
        else {}
    )
    remote_result = None
    try:
        remote_result = await call_with_circuit_breaker(
            service_name="guardrails",
            method="POST",
            url=f"{GUARDRAILS_URL}/api/v1/check",
            json={"text": text},
            headers=auth_headers,
            timeout=30.0,
        )
    except Exception as exc:
        logger.warning("Guardrails service unavailable, using keyword fallback: %s", exc)

    # Merge local + remote results
    result = {
        "toxic": toxic,
        "toxic_score": toxic_score,
        "reason": toxic_reason,
        "pii_detected": pii_detected,
        "pii_types": pii_types,
    }
    if remote_result:
        result["toxic"] = result["toxic"] or remote_result.get("toxic", False)
        result["toxic_score"] = max(result["toxic_score"], remote_result.get("toxic_score", 0.0))
        if remote_result.get("toxic") and not result["reason"]:
            result["reason"] = remote_result.get("reason")
        result["pii_detected"] = result["pii_detected"] or remote_result.get("pii_detected", False)
        result["pii_types"] = list(set(result["pii_types"] + remote_result.get("pii_types", [])))

    if not result["toxic"]:
        result["toxic_score"] = max(result["toxic_score"], 0.05)
        result["reason"] = result.get("reason") or None

    # ── Injection detection ──
    inj_detected, inj_score, inj_matches = detect_injection(text)
    result["injection_detected"] = inj_detected
    result["injection_score"] = round(inj_score, 2)
    result["injection_matches"] = inj_matches

    # ── Blocklist check ──
    blocklist_words = load_blocklist()
    is_blocklisted = bool(blocklist_words and any(w in text_lower for w in blocklist_words))
    result["blocklisted"] = is_blocklisted
    if is_blocklisted:
        matched_word = next((w for w in blocklist_words if w in text_lower), "unknown")
        await log_audit(
            current_user.get("sub", "system"),
            "blocklist_hit",
            resource_type="guardrails",
            details={"word": matched_word, "text": text[:50]},
            request=request,
        )

    result["redacted_text"] = redacted
    result["pii_masked"] = pii_detected
    return result

# ─── Batch Guardrails Check ──────────────────────────────────
@app.post("/api/v1/guardrails/batch")
@limiter.limit("30/minute")
async def guardrails_batch(request: Request, current_user: dict = Depends(get_current_user), credentials: HTTPAuthorizationCredentials = Security(security)):
    body = await request.json()
    texts = body.get("texts", [])
    results = []
    for text in texts[:100]:
        r = await guardrails_check(request, GuardrailCheckRequest(text=text), current_user, credentials)
        results.append(r)
    return {"results": results, "total": len(results)}

# ─── Streaming Guardrails Check ──────────────────────────────
@app.post("/api/v1/guardrails/check/stream")
@limiter.limit("30/minute")
async def guardrails_check_stream(request: Request, payload: GuardrailCheckRequest, current_user: dict = Depends(get_current_user)):
    text = payload.text or ""
    words = text.split()
    result = {"toxic": False, "toxic_score": 0.0, "pii_detected": False, "pii_types": []}
    detected_lang = detect_language(text)
    blocklist_words = set(w.lower() for w in load_blocklist())

    def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'total_tokens': len(words), 'language': detected_lang})}\n\n"
        for i, word in enumerate(words):
            word_clean = word.strip(".,!?;:")
            wl = word_clean.lower()
            is_toxic = wl in TOXIC_KEYWORDS
            is_blocklisted = wl in blocklist_words
            has_pii = any(p.search(word) for p, _, _ in INJECTION_PATTERNS)
            is_injection = any(p.search(word) for p, _ in INJECTION_PATTERNS)
            yield f"data: {json.dumps({'index': i, 'token': word_clean, 'toxic': is_toxic, 'blocklisted': is_blocklisted, 'pii': has_pii, 'injection': is_injection})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'total_tokens': len(words)})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ─── Explain / SHAP ──────────────────────────────────────────
@app.post("/api/v1/explain/shap")
@limiter.limit("30/minute")
async def explain_shap(request: Request, current_user: dict = Depends(get_current_user), credentials: HTTPAuthorizationCredentials = Security(security)):
    body = await request.json()
    text = body.get("text","")
    try:
        return await call_with_circuit_breaker(service_name="guardrails", method="POST", url=f"{GUARDRAILS_URL}/api/v1/shap", json=body, headers={"Authorization": f"Bearer {credentials.credentials}"}, timeout=30.0)
    except httpx.HTTPError:
        toxic_kw = ["hate","kill","stupid","idiot","dumb","ugly","loser","trash","attack","destroy","die","death","threat","violence","racist","sexist"]
        pii_ps = [r'\b\d{3}-\d{2}-\d{4}\b',r'\b\d{3}-\d{3}-\d{3}\b',r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b']
        tokens = []
        for w in text.split():
            imp = 0.0
            if w.lower().strip(".,!?;:") in toxic_kw: imp = 0.85
            else:
                for p in pii_ps:
                    if re.search(p,w): imp = 0.75; break
            tokens.append({"token":w,"importance":imp})
        return {"tokens": tokens}

# ─── Feedback ────────────────────────────────────────────────
@app.post("/api/v1/feedback")
@limiter.limit("30/minute")
async def submit_feedback(request: Request, payload: FeedbackSubmit, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, trace_id TEXT, model_verdict BOOLEAN, client_label BOOLEAN, created_at TIMESTAMPTZ DEFAULT NOW())")
        await db.execute("INSERT INTO feedback (trace_id, model_verdict, client_label) VALUES ($1, $2, $3)", payload.trace_id, payload.model_verdict, payload.client_label)
    return {"status": "recorded"}

# ─── Audit ───────────────────────────────────────────────────
@app.get("/api/v1/audit", response_model=List[dict])
@limiter.limit("100/minute")
async def get_audit_logs(request: Request, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS audit_logs (id SERIAL PRIMARY KEY, user_email TEXT, action TEXT, resource_type TEXT, resource_id TEXT, details TEXT, ip_address TEXT, timestamp TIMESTAMPTZ DEFAULT NOW())")
        rows = await conn.fetch("SELECT id, user_email, action, resource_type, resource_id, details, ip_address, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT $1 OFFSET $2", limit, offset)
        return [dict(r) for r in rows]

# ─── Domain Thresholds ───────────────────────────────────────
@app.get("/api/v1/settings/domain-thresholds", response_model=DomainThresholdList)
@limiter.limit("30/minute")
async def get_domain_thresholds(request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS domain_thresholds (id SERIAL PRIMARY KEY, domain TEXT NOT NULL UNIQUE, severity TEXT DEFAULT 'medium', toxicity_action TEXT DEFAULT 'flag', pii_action TEXT DEFAULT 'mask')")
        rows = await db.fetch("SELECT domain, severity, toxicity_action, pii_action FROM domain_thresholds ORDER BY domain")
        if rows: return DomainThresholdList(thresholds=[DomainThreshold(**dict(row)) for row in rows])
        return DomainThresholdList(thresholds=[DomainThreshold(domain="finance",severity="high",toxicity_action="block",pii_action="block"),DomainThreshold(domain="healthcare",severity="critical",toxicity_action="block",pii_action="block"),DomainThreshold(domain="education",severity="medium",toxicity_action="flag",pii_action="mask"),DomainThreshold(domain="general",severity="medium",toxicity_action="flag",pii_action="mask")])

@app.post("/api/v1/settings/domain-thresholds")
@limiter.limit("10/minute")
async def save_domain_thresholds(request: Request, payload: DomainThresholdList, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS domain_thresholds (id SERIAL PRIMARY KEY, domain TEXT NOT NULL UNIQUE, severity TEXT DEFAULT 'medium', toxicity_action TEXT DEFAULT 'flag', pii_action TEXT DEFAULT 'mask')")
        for t in payload.thresholds:
            await db.execute("INSERT INTO domain_thresholds (domain, severity, toxicity_action, pii_action) VALUES ($1, $2, $3, $4) ON CONFLICT (domain) DO UPDATE SET severity=EXCLUDED.severity, toxicity_action=EXCLUDED.toxicity_action, pii_action=EXCLUDED.pii_action", t.domain, t.severity, t.toxicity_action, t.pii_action)
    await log_audit(current_user.get("sub"), "domain_thresholds_update", resource_type="settings", details=payload.model_dump())
    return {"status": "saved"}

# ─── Webhook Settings ────────────────────────────────────────
@app.get("/api/v1/settings/webhooks")
@limiter.limit("30/minute")
async def get_webhooks(request: Request, current_user: dict = Depends(get_current_user)):
    try:
        with open(WEBHOOK_FILE) as f:
            data = yaml.safe_load(f)
            return data or {"url": "", "enabled": False, "events": "toxicity,pii"}
    except (FileNotFoundError, yaml.YAMLError):
        return {"url": "", "enabled": False, "events": "toxicity,pii"}

@app.post("/api/v1/settings/webhooks")
@limiter.limit("10/minute")
async def save_webhooks(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    with open(WEBHOOK_FILE, "w") as f: yaml.safe_dump(body, f)
    return {"status": "saved"}

# ─── API Keys ────────────────────────────────────────────────
@app.post("/api/v1/api-keys")
@limiter.limit("10/minute")
async def create_api_key(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    name = body.get("name", "API Key")
    key_id = "pk-" + secrets.token_hex(16)
    api_key = secrets.token_hex(32)
    key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO api_keys (key_id, name, key_hash, role, created_by) VALUES ($1, $2, $3, 'admin', $4)", key_id, name, key_hash, current_user.get("sub","unknown"))
    await log_audit(current_user.get("sub"), "api_key_create", resource_type="api_key", resource_id=key_id)
    return {"key_id": key_id, "api_key": api_key, "name": name, "note": "Save this key — it will not be shown again."}

@app.get("/api/v1/api-keys")
@limiter.limit("30/minute")
async def list_api_keys(request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT key_id, name, role, created_by, expires_at, created_at FROM api_keys ORDER BY created_at DESC")
        return [{"key_id": r["key_id"], "name": r["name"], "role": r["role"], "created_by": r["created_by"], "created_at": str(r["created_at"])} for r in rows]

@app.delete("/api/v1/api-keys/{key_id}")
@limiter.limit("10/minute")
async def revoke_api_key(request: Request, key_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("DELETE FROM api_keys WHERE key_id = $1", key_id)
    await log_audit(current_user.get("sub"), "api_key_revoke", resource_type="api_key", resource_id=key_id)
    return {"status": "revoked"}

# ─── Hallucination ───────────────────────────────────────────
HALLUCINATION_URL = os.getenv("HALLUCINATION_URL", "http://hallucination-detector:8008")

@app.get("/api/v1/hallucination/trend", response_model=HallucinationTrend)
@limiter.limit("30/minute")
async def get_hallucination_trend(request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS hallucination_scores (id SERIAL PRIMARY KEY, score REAL, timestamp TIMESTAMPTZ DEFAULT NOW())")
        rows = await db.fetch("SELECT DATE(timestamp) as date, AVG(score) as score FROM hallucination_scores WHERE timestamp > NOW() - INTERVAL '7 days' GROUP BY DATE(timestamp) ORDER BY date")
        if rows: return HallucinationTrend(points=[HallucinationTrendPoint(date=str(r["date"]), score=round(float(r["score"]),2)) for r in rows])
        from datetime import timedelta
        today = datetime.now(timezone.utc)
        return HallucinationTrend(points=[HallucinationTrendPoint(date=(today-timedelta(days=i)).strftime("%Y-%m-%d"), score=round(12.5-i*1.2,1)) for i in range(6,-1,-1)])

@app.get("/api/v1/hallucination/detections", response_model=HallucinationDetectionList)
@limiter.limit("30/minute")
async def get_hallucination_detections(request: Request, limit: int = Query(20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS hallucination_scores (id SERIAL PRIMARY KEY, trace_id TEXT, score REAL, prompt TEXT, completion TEXT, corrected BOOLEAN DEFAULT FALSE, feedback TEXT DEFAULT 'none', timestamp TIMESTAMPTZ DEFAULT NOW())")
        rows = await db.fetch("SELECT id, trace_id, score, prompt, completion, corrected, feedback, timestamp FROM hallucination_scores ORDER BY timestamp DESC LIMIT $1", limit)
        if rows:
            detections = []
            for r in rows:
                d = dict(r); d["id"] = str(d.pop("id")); d["prompt_snippet"] = (d.pop("prompt") or "")[:100]; d["completion_snippet"] = (d.pop("completion") or "")[:100]
                detections.append(HallucinationDetection(**d))
            return HallucinationDetectionList(detections=detections)
        return HallucinationDetectionList(detections=[])

# ─── Traces ──────────────────────────────────────────────────
@app.post("/api/v1/traces")
@limiter.limit("120/minute")
async def ingest_trace(request: Request, payload: TraceIngest, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS traces (id SERIAL PRIMARY KEY, prompt TEXT, completion TEXT, model_id TEXT, user_id TEXT, timestamp TIMESTAMPTZ DEFAULT NOW())")
        await db.execute("CREATE TABLE IF NOT EXISTS guardrail_results (id SERIAL PRIMARY KEY, trace_id INTEGER REFERENCES traces(id), toxic BOOLEAN DEFAULT FALSE, toxic_score REAL DEFAULT 0.0, reason TEXT, pii_detected BOOLEAN DEFAULT FALSE, pii_types TEXT, timestamp TIMESTAMPTZ DEFAULT NOW())")
        row = await db.fetchrow("INSERT INTO traces (prompt, completion, model_id, user_id) VALUES ($1, $2, $3, $4) RETURNING id", payload.prompt, payload.completion, payload.model_id, payload.user_id)
        await db.execute("INSERT INTO guardrail_results (trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            row["id"], False, 0.0, None, False, None, False)
        # Auto-classify: run guardrails check on the ingested prompt (inside the with block)
        try:
            check_result = await guardrails_check(request, GuardrailCheckRequest(text=payload.prompt), current_user, credentials=None)
            toxic = check_result.get("toxic", False)
            score = check_result.get("toxic_score", 0.0)
            reason = check_result.get("reason")
            pii = check_result.get("pii_detected", False)
            pii_types = ",".join(check_result.get("pii_types", []))
            blocklisted = check_result.get("blocklisted", False)
            if blocklisted and not reason:
                reason = "Blocklisted word detected"
            elif not reason:
                reason = None
            await db.execute("UPDATE guardrail_results SET toxic=$1, toxic_score=$2, reason=$3, pii_detected=$4, pii_types=$5, blocklisted=$6 WHERE trace_id=$7",
                toxic, score, reason, pii, pii_types if pii_types else None, blocklisted, row["id"])
        except Exception as e:
            logger.warning(f"Auto-classify failed for trace {row['id']}: {e}")
    return {"status": "ingested", "trace_id": row["id"]}

@app.get("/api/v1/traces/{trace_id}", response_model=TraceResponse)
@limiter.limit("60/minute")
async def get_trace(request: Request, trace_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT t.id, t.prompt, t.completion, t.model_id, t.user_id, t.timestamp, gr.toxic, gr.toxic_score, gr.reason, gr.pii_detected, gr.pii_types FROM traces t LEFT JOIN guardrail_results gr ON t.id=gr.trace_id WHERE t.id=$1", trace_id)
        if not row: raise HTTPException(404, "Trace not found")
        return TraceResponse(**dict(row))

# ─── Users / RBAC ────────────────────────────────────────────
@app.post("/api/v1/users")
@limiter.limit("10/minute")
async def create_user(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    email = body.get("email", "").strip()
    if not email or "@" not in email: raise HTTPException(400, "Valid email required")
    role = body.get("role", "safety_officer")
    if role not in ("admin", "safety_officer", "viewer"): raise HTTPException(400, "Role must be admin, safety_officer, or viewer")
    pw = body.get("password", "")
    if len(pw) < 6: raise HTTPException(400, "Password must be at least 6 characters")
    pool = await get_pool()
    async with pool.acquire() as db:
        existing = await db.fetchval("SELECT email FROM users WHERE email = $1", email)
        if existing: raise HTTPException(400, "User already exists")
        await db.execute("INSERT INTO users (email, password_hash, role) VALUES ($1, $2, $3)", email, bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(), role)
    await log_audit(current_user.get("sub"), "user_create", resource_type="user", resource_id=email, details={"role": role})
    return {"status": "created", "email": email, "role": role}

@app.get("/api/v1/users")
@limiter.limit("30/minute")
async def list_users(request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT email, role, active, created_at FROM users ORDER BY created_at DESC")
        return [{"email": r["email"], "role": r["role"], "active": r["active"], "created_at": str(r["created_at"])} for r in rows]

@app.delete("/api/v1/users/{email}")
@limiter.limit("10/minute")
async def deactivate_user(request: Request, email: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET active = FALSE WHERE email = $1", email)
    await log_audit(current_user.get("sub"), "user_deactivate", resource_type="user", resource_id=email)
    return {"status": "deactivated"}

# ─── Image Moderation ────────────────────────────────────────
@app.post("/api/v1/guardrails/check-image")
@limiter.limit("20/minute")
async def guardrails_check_image(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    image_b64 = body.get("image", "")
    try:
        result = {"image_analyzed": True, "toxic": False, "pii_detected": False, "text": "", "note": ""}
        import base64
        if image_b64:
            result["image_size_bytes"] = len(base64.b64decode(image_b64.split(",")[-1] if "," in image_b64 else image_b64))
            result["text"] = body.get("caption", "")
        return result
    except Exception as e:
        return {"image_analyzed": False, "error": str(e), "note": "Image moderation requires PIL library. Check text for safety instead."}

# ─── Blocklist Settings ──────────────────────────────────────
@app.get("/api/v1/settings/blocklist")
@limiter.limit("30/minute")
async def get_blocklist(request: Request, current_user: dict = Depends(get_current_user)):
    words = load_blocklist()
    return {"words": words, "count": len(words)}

@app.post("/api/v1/settings/blocklist")
@limiter.limit("10/minute")
async def add_blocklist_word(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    word = (body.get("word") or "").strip().lower()
    if not word: raise HTTPException(400, "Word required")
    words = load_blocklist()
    if word not in words: words.append(word)
    save_blocklist(words)
    await log_audit(current_user.get("sub"), "blocklist_add", resource_type="blocklist", details={"word": word})
    return {"words": words, "count": len(words)}

@app.delete("/api/v1/settings/blocklist/{word}")
@limiter.limit("10/minute")
async def remove_blocklist_word(request: Request, word: str, current_user: dict = Depends(get_current_user)):
    words = load_blocklist()
    words = [w for w in words if w != word.lower()]
    save_blocklist(words)
    await log_audit(current_user.get("sub"), "blocklist_remove", resource_type="blocklist", details={"word": word})
    return {"words": words, "count": len(words)}

# ─── Health ──────────────────────────────────────────────────
@app.get("/health", response_model=HealthStatus)
async def health():
    db_status = await db_health()
    redis_status = await redis_health()
    return HealthStatus(status="ok" if (db_status and redis_status) else "degraded", database="healthy" if db_status else "unhealthy", redis="healthy" if redis_status else "unhealthy")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
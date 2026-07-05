"""AIDA Bridge — compliance report generation service.
Enterprise-grade: Pydantic validation, structured logging, async auth, connection pooling.
"""
from fastapi import FastAPI, HTTPException, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from shared.security.auth import verify_jwt, get_current_user
from shared.capabilities import SystemProfile
from shared.telemetry import setup_otel
from shared.db import get_pool, close_pool, health_check as db_health
from shared.redis_client import close_redis
from shared.schemas import (
    AIDAExportRequest, AIDAExportResponse, SimilarIncident,
    SimilarResponse, StoreIncidentRequest, HealthStatus,
)
from shared.logging import setup_logging
from shared.fairness import calculate_fairness_score, get_fairness_note
from shared.config import settings
from shared.circuit_breaker import call_with_circuit_breaker
import asyncpg, os, logging, httpx
import chromadb
from chromadb.config import Settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from contextlib import asynccontextmanager
from typing import List, Optional

# Structured logging
setup_logging(service_name="northguard-aida-bridge")
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://guardrails:8005")

# Lazy-init chroma client to avoid module-level startup failures
_chroma_client: Optional[chromadb.PersistentClient] = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path="./chroma_db", settings=Settings(anonymized_telemetry=False))
    return _chroma_client

profile = SystemProfile.detect()
logger.info(f"AIDA tier from shared profile: {profile.recommended_aida_tier}")

REPORT_TEMPLATE = """# AIDA Compliance Report for {model_name}

**Industry:** {industry}  
**Risk Level:** {risk_level}  
**Report Generated:** {generated_at}

## 1. Data Governance and Quality
AIDA requires that data used in high‑impact AI systems be accurate, representative, and free from biases that could lead to discriminatory outcomes. For {risk_level}-risk systems, formal data governance standards are not prescribed, but best practices recommend documenting data sources and performing periodic quality checks.

**System Status:** {total_traces} traces have been processed through NorthGuard's monitoring pipeline. Data quality checks are performed on all incoming traces.

## 2. Fairness and Bias Assessment
Section 6 of AIDA mandates that high‑impact systems must establish measures to identify, assess and mitigate risks of biased output. For {risk_level}-risk systems like this one, the obligation is to be aware of potential biases and have a plan to address them if they arise.

**System Status:** NorthGuard has flagged {toxic_flags} toxicity incidents ({toxic_pct}% of total traces) and detected {pii_leaks} PII leaks ({pii_pct}% of total traces). The calculated fairness proxy score is {fairness_score}. {fairness_note}

## 3. Operational Oversight
Section 11 requires publishing a plain‑language description of the system's use, its output types, and the mitigation measures in place. The act does not mandate human‑in‑the‑loop oversight for all systems, but it strongly recommends that operators maintain the ability to intervene.

**System Status:** NorthGuard provides real-time monitoring with {active_models} active model(s) being tracked. Policy enforcement actions are logged and available for audit review.

## 4. Performance and Compliance Reviews
Section 8 compels organisations to monitor compliance with their own measures and to update them as necessary. Regular audits, logging, and incident reporting are all practical steps toward meeting this obligation.

**System Status:** NorthGuard maintains a complete audit trail of all policy changes, access events, and enforcement actions. {audit_count} audit log entries are available for review.

{llm_summary}

## Live Monitoring Evidence (NorthGuard)
- **Total traces processed:** {total_traces}
- **Toxicity incidents flagged:** {toxic_flags} ({toxic_pct}%)
- **PII leaks detected:** {pii_leaks} ({pii_pct}%)
- **Active models monitored:** {active_models}
- **Fairness proxy score:** {fairness_score}
- **Audit log entries:** {audit_count}
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)))
async def _call_ollama_with_retry(model: str, prompt: str, timeout: float = 180.0, max_tokens: int = 250) -> str:
    """Call Ollama with retry and async-compatible circuit breaker."""
    return await call_with_circuit_breaker(
        service_name="ollama",
        method="POST",
        url=f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.2, "num_predict": max_tokens, "cache_prompt": True}},
        timeout=timeout,
    )

async def generate_tier3(model_name: str, industry: str, risk_level: str) -> str:
    prompt = f"""Write a structured compliance report for an AI system named {model_name} in {industry} (risk level: {risk_level}).
Include sections: 1. Data Governance, 2. Bias Assessment, 3. Human Oversight, 4. Performance Monitoring.
Keep it professional and concise. End with 'Customer Input Required'."""
    logger.info("Tier 3: calling 3B model (timeout 180s)")
    result = await _call_ollama_with_retry("llama3.2:3b", prompt, timeout=180.0, max_tokens=250)
    # call_with_circuit_breaker returns resp.json() which is a dict with "response" key
    if isinstance(result, dict):
        return result.get("response", "").strip()
    return str(result).strip()

async def generate_tier2(model_name: str, industry: str, risk_level: str) -> str:
    prompt = f"Summarise {model_name} compliance in {industry}."
    logger.info("Tier 2: calling warm LLM via guardrails worker")
    result = await call_with_circuit_breaker(
        service_name="guardrails",
        method="POST",
        url=f"{GUARDRAILS_URL}/api/v1/generate",
        json={"prompt": prompt, "max_tokens": 20},
        timeout=90.0,
    )
    if isinstance(result, dict):
        return result.get("response", "").strip()
    return str(result).strip()

async def generate_report_text(model_names: list, industry: str, risk_level: str) -> str:
    recommended = profile.recommended_aida_tier
    all_reports = []
    for model_name in model_names:
        logger.info(f"Generating report for {model_name} (tier {recommended})")
        if recommended >= 3:
            try:
                report = await generate_tier3(model_name, industry, risk_level)
                if report and len(report) > 100 and not report.startswith("I can't"):
                    all_reports.append(f"\n## Report for {model_name}\n{report}")
                    continue
            except Exception as e:
                logger.warning(f"Tier 3 failed for {model_name}: {e}")
        if recommended >= 2:
            try:
                summary = await generate_tier2(model_name, industry, risk_level)
                if summary and len(summary) > 5 and not summary.startswith("I can't"):
                    # Escape any { or } in the LLM summary to prevent format string crashes
                    safe_summary = summary.replace("{", "{{").replace("}", "}}")
                    all_reports.append((
                        f"\n## Report for {model_name}\n"
                        f"### AI‑Generated Summary\n{safe_summary}\n"
                    ))
                    continue
            except Exception as e:
                logger.warning(f"Tier 2 failed for {model_name}: {e}")
        # Tier 1 fallback — just return the model name and a note
        all_reports.append(f"\n## Report for {model_name}\n\n### Note\nA detailed compliance report will be generated after the next system upgrade.\n")
    return "\n\n".join(all_reports)


async def _get_monitoring_stats() -> dict:
    """Fetch monitoring statistics from the database using connection pool."""
    total_traces = toxic_flags = pii_leaks = 0
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            total_traces = await db.fetchval("SELECT COUNT(*) FROM traces") or 0
            toxic_flags = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE toxic = true") or 0
            pii_leaks = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE pii_detected = true") or 0
    except Exception as e:
        logger.warning(f"Monitoring query failed: {e}")
    return {"total_traces": total_traces, "toxic_flags": toxic_flags, "pii_leaks": pii_leaks}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    try:
        get_similar_collection()
        logger.info("Similarity model pre‑loaded")
    except Exception as e:
        logger.warning(f"Similarity model pre‑load failed: {e}")
    if profile.recommended_aida_tier >= 2:
        try:
            await call_with_circuit_breaker(
                service_name="guardrails",
                method="POST",
                url=f"{GUARDRAILS_URL}/api/v1/generate",
                json={"prompt": "hello", "max_tokens": 5},
                timeout=90.0,
            )
            logger.info("Guardrails LLM endpoint warmed up")
        except Exception as e:
            logger.warning(f"Warm‑up request failed: {e}")
    yield
    # Shutdown
    await close_pool()
    await close_redis()


app = FastAPI(title="AIDA Bridge", version="1.0.0", lifespan=lifespan)
# Initialize OpenTelemetry instrumentation (must happen before first request)
setup_otel(app, service_name="northguard-aida-bridge")
security = HTTPBearer(auto_error=False)


@app.get("/health", response_model=HealthStatus)
async def health():
    db_status = await db_health()
    return HealthStatus(
        status="ok" if db_status else "degraded",
        database="healthy" if db_status else "unhealthy",
    )


@app.get("/api/v1/aida/export", response_model=AIDAExportResponse)
async def export_compliance_report(
    credentials: HTTPAuthorizationCredentials = Security(security),
    model_name: str = Query("default-model"),
    industry: str = Query("finance"),
    risk_level: str = Query("medium"),
):
    model_names = [model_name]
    if not credentials or not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    
    stats = await _get_monitoring_stats()
    
    report_body = await generate_report_text(model_names, industry, risk_level)
    total = stats["total_traces"]
    toxic = stats["toxic_flags"]
    pii = stats["pii_leaks"]
    toxic_pct = round((toxic / total * 100), 1) if total > 0 else 0
    pii_pct = round((pii / total * 100), 1) if total > 0 else 0
    # Fairness score: use shared utility
    fair_score = calculate_fairness_score(
        total_traces=total,
        flagged_toxicity=toxic,
        pii_leaks=pii,
    )
    fairness_score = fair_score
    fairness_note = get_fairness_note(fair_score)
    
    # Get active models and audit count
    active_models = 0
    audit_count = 0
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            active_models = await db.fetchval("SELECT COUNT(DISTINCT model_id) FROM traces") or 0
            audit_count = await db.fetchval("SELECT COUNT(*) FROM audit_logs") or 0
    except Exception:
        pass
    
    from datetime import datetime, timezone
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Escape any { or } in LLM-generated content to prevent .format() crashes
    # (report_body comes from an LLM and may contain JSON or curly braces)
    safe_body = report_body.replace("{", "{{").replace("}", "}}")
    # Restore the actual format placeholders we need
    safe_body = safe_body.replace("{{total_traces}}", "{total_traces}")
    safe_body = safe_body.replace("{{toxic_flags}}", "{toxic_flags}")
    safe_body = safe_body.replace("{{pii_leaks}}", "{pii_leaks}")
    safe_body = safe_body.replace("{{toxic_pct}}", "{toxic_pct}")
    safe_body = safe_body.replace("{{pii_pct}}", "{pii_pct}")
    safe_body = safe_body.replace("{{fairness_score}}", "{fairness_score}")
    safe_body = safe_body.replace("{{fairness_note}}", "{fairness_note}")
    safe_body = safe_body.replace("{{active_models}}", "{active_models}")
    safe_body = safe_body.replace("{{audit_count}}", "{audit_count}")
    safe_body = safe_body.replace("{{generated_at}}", "{generated_at}")
    
    report = safe_body.format(
        total_traces=total,
        toxic_flags=toxic,
        pii_leaks=pii,
        toxic_pct=toxic_pct,
        pii_pct=pii_pct,
        fairness_score=fairness_score,
        fairness_note=fairness_note,
        active_models=active_models,
        audit_count=audit_count,
        generated_at=generated_at,
    )
    return AIDAExportResponse(
        report=report,
        monitoring=stats,
    )


@app.post("/api/v1/aida/generate-pdf")
async def generate_pdf(
    credentials: HTTPAuthorizationCredentials = Security(security),
    model_name: str = Query("default-model"),
    industry: str = Query("finance"),
    risk_level: str = Query("medium"),
    signature: str = Query(""),
    validated: bool = Query(False),
):
    if not credentials or not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    
    stats = await _get_monitoring_stats()
    
    report_body = await generate_report_text([model_name], industry, risk_level)
    # Escape any { or } in LLM-generated content to prevent .format() crashes
    safe_body = report_body.replace("{", "{{").replace("}", "}}")
    safe_body = safe_body.replace("{{total_traces}}", "{total_traces}")
    safe_body = safe_body.replace("{{toxic_flags}}", "{toxic_flags}")
    safe_body = safe_body.replace("{{pii_leaks}}", "{pii_leaks}")
    safe_body = safe_body.replace("{{toxic_pct}}", "{toxic_pct}")
    safe_body = safe_body.replace("{{pii_pct}}", "{pii_pct}")
    safe_body = safe_body.replace("{{fairness_score}}", "{fairness_score}")
    safe_body = safe_body.replace("{{fairness_note}}", "{fairness_note}")
    safe_body = safe_body.replace("{{active_models}}", "{active_models}")
    safe_body = safe_body.replace("{{audit_count}}", "{audit_count}")
    safe_body = safe_body.replace("{{generated_at}}", "{generated_at}")
    report = safe_body.format(
        total_traces=stats["total_traces"],
        toxic_flags=stats["toxic_flags"],
        pii_leaks=stats["pii_leaks"],
        toxic_pct=round((stats["toxic_flags"] / max(stats["total_traces"], 1)) * 100, 1),
        pii_pct=round((stats["pii_leaks"] / max(stats["total_traces"], 1)) * 100, 1),
        fairness_score="N/A",
        fairness_note="Calculated during export.",
        active_models=0,
        audit_count=0,
        generated_at="N/A",
    )
    from .pdf_generator import generate_compliance_pdf
    payload = await verify_jwt(credentials.credentials)
    pdf_path = generate_compliance_pdf(
        report, "multi-model",
        approved=validated,
        user_email=payload.get("sub") if payload else None,
        signature_name=signature if signature else None,
    )
    return FileResponse(pdf_path, media_type="application/pdf", filename="multi_model_compliance.pdf")


def get_similar_collection():
    client = get_chroma_client()
    try:
        return client.get_collection("incidents")
    except:
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        return client.create_collection("incidents", embedding_function=ef)


@app.get("/api/v1/similar", response_model=SimilarResponse)
async def get_similar_incidents(
    text: str = Query(...),
    limit: int = Query(3, ge=1, le=20),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not credentials or not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    # Input sanitization: strip HTML tags, limit length, prevent injection
    import re
    text = re.sub(r'<[^>]+>', '', text)  # Strip HTML tags
    text = text.strip()[:5000]  # Limit length
    if not text:
        raise HTTPException(400, "Text cannot be empty after sanitization")
    collection = get_similar_collection()
    results = collection.query(query_texts=[text], n_results=limit)
    similar = []
    for i, doc in enumerate(results.get("documents", [[]])[0]):
        meta = results.get("metadatas", [[]])[0][i]
        similar.append(SimilarIncident(
            text=doc,
            toxic=meta.get("toxic", False),
            reason=meta.get("reason", ""),
            trace_id=meta.get("trace_id", ""),
        ))
    return SimilarResponse(results=similar)


@app.post("/api/v1/similar/store")
async def store_incident(
    payload: StoreIncidentRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not credentials or not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    collection = get_similar_collection()
    collection.add(
        documents=[payload.text],
        metadatas=[{
            "trace_id": payload.trace_id,
            "toxic": payload.toxic,
            "reason": payload.reason or "",
        }],
        ids=[payload.trace_id or ""],
    )
    return {"status": "stored"}

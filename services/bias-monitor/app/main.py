"""Bias Monitor — fairness and bias detection service.
Enterprise-grade: Pydantic validation, structured logging, async auth,
protected attribute collection, and fairness assessment per MEASURE 3.1.
"""
from fastapi import FastAPI, HTTPException, Security, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from shared.security.auth import verify_jwt, get_current_user
from shared.telemetry import setup_otel
from shared.db import get_pool, close_pool, health_check as db_health
from shared.redis_client import close_redis
from shared.schemas import BiasSummary, BiasTrend, HealthStatus
from shared.logging import setup_logging
from shared.fairness import calculate_fairness_score
from contextlib import asynccontextmanager
import asyncpg, logging, json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

setup_logging(service_name="northguard-bias-monitor")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    yield
    # Shutdown
    await close_pool()
    await close_redis()

app = FastAPI(title="Bias Monitor", version="1.0.0", lifespan=lifespan)

# Initialize OpenTelemetry after app creation, before routes
setup_otel(app, service_name="northguard-bias-monitor")
security = HTTPBearer(auto_error=False)


@app.get("/health", response_model=HealthStatus)
async def health():
    db_status = await db_health()
    return HealthStatus(
        status="ok" if db_status else "degraded",
        database="healthy" if db_status else "unhealthy",
    )


@app.get("/api/v1/bias/summary", response_model=BiasSummary)
async def bias_summary(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    pool = await get_pool()
    async with pool.acquire() as db:
        total = await db.fetchval("SELECT COUNT(*) FROM traces") or 0
        toxic = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE toxic = true") or 0
        pii = await db.fetchval("SELECT COUNT(*) FROM guardrail_results WHERE pii_detected = true") or 0
        # Fairness score: use shared utility
        fair_score = calculate_fairness_score(
            total_traces=total,
            flagged_toxicity=toxic,
            pii_leaks=pii,
        )
        return BiasSummary(
            total_traces=total,
            toxic_flags=toxic,
            pii_leaks=pii,
            fairness_score=fair_score,
        )


@app.get("/api/v1/bias/trends", response_model=List[BiasTrend])
async def bias_trends(
    days: int = Query(7, ge=1, le=90),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            """
            SELECT DATE(timestamp) as day,
                   COUNT(*) as total,
                   SUM(CASE WHEN toxic THEN 1 ELSE 0 END) as toxic,
                   SUM(CASE WHEN pii_detected THEN 1 ELSE 0 END) as pii
            FROM guardrail_results
            WHERE timestamp >= NOW() - INTERVAL '1 day' * $1
            GROUP BY DATE(timestamp)
            ORDER BY day
            """,
            days,
        )
        return [BiasTrend(**dict(row)) for row in rows]


# ─── Protected Attribute Collection (MEASURE 3.1) ──────────────────────

class ProtectedAttributeSubmission(BaseModel):
    """Submission of protected attributes for fairness assessment.
    
    Per MEASURE 3.1 of the AI RMF, organizations should collect demographic
    data to assess fairness across protected groups. This data is stored
    separately from trace data and is only used for aggregate fairness analysis.
    """
    trace_id: str = Field(..., description="Associated trace ID")
    age_group: Optional[str] = Field(None, description="Age range: under_18, 18-24, 25-34, 35-44, 45-54, 55-64, 65+")
    gender: Optional[str] = Field(None, description="Gender identity")
    ethnicity: Optional[str] = Field(None, description="Ethnic or racial background")
    region: Optional[str] = Field(None, description="Geographic region")
    language: Optional[str] = Field(None, description="Primary language")
    education_level: Optional[str] = Field(None, description="Education level")
    income_bracket: Optional[str] = Field(None, description="Income bracket")
    consent_given: bool = Field(False, description="User consent for fairness analysis")


class FairnessAssessment(BaseModel):
    """Fairness assessment results across protected attributes."""
    total_samples: int = 0
    attributes_tracked: List[str] = []
    group_disparities: Dict[str, Any] = {}
    overall_fairness_score: float = 1.0
    assessment_date: str = ""
    recommendations: List[str] = []


@app.post("/api/v1/bias/protected-attributes")
async def submit_protected_attributes(
    payload: ProtectedAttributeSubmission,
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Submit protected attributes for a trace (MEASURE 3.1 compliance).
    
    This endpoint collects demographic data for fairness analysis.
    Data is stored separately from trace data and only used for
    aggregate fairness assessment. Requires user consent.
    """
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    
    if not payload.consent_given:
        raise HTTPException(400, "Consent required for protected attribute collection")
    
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS protected_attributes (
                id SERIAL PRIMARY KEY,
                trace_id TEXT UNIQUE,
                age_group TEXT,
                gender TEXT,
                ethnicity TEXT,
                region TEXT,
                language TEXT,
                education_level TEXT,
                income_bracket TEXT,
                consent_given BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await db.execute("""
            INSERT INTO protected_attributes 
                (trace_id, age_group, gender, ethnicity, region, language, 
                 education_level, income_bracket, consent_given)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (trace_id) DO UPDATE SET
                age_group = EXCLUDED.age_group,
                gender = EXCLUDED.gender,
                ethnicity = EXCLUDED.ethnicity,
                region = EXCLUDED.region,
                language = EXCLUDED.language,
                education_level = EXCLUDED.education_level,
                income_bracket = EXCLUDED.income_bracket
        """, payload.trace_id, payload.age_group, payload.gender,
            payload.ethnicity, payload.region, payload.language,
            payload.education_level, payload.income_bracket, payload.consent_given)
    
    logger.info(f"Protected attributes recorded for trace {payload.trace_id}")
    return {"status": "recorded", "trace_id": payload.trace_id}


@app.get("/api/v1/bias/fairness-assessment", response_model=FairnessAssessment)
async def get_fairness_assessment(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get fairness assessment across protected attributes (MEASURE 3.1).
    
    Analyzes toxicity and PII rates across different demographic groups
    to identify potential disparities and bias.
    """
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    
    pool = await get_pool()
    async with pool.acquire() as db:
        # Ensure tables exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS protected_attributes (
                id SERIAL PRIMARY KEY,
                trace_id TEXT UNIQUE,
                age_group TEXT,
                gender TEXT,
                ethnicity TEXT,
                region TEXT,
                language TEXT,
                education_level TEXT,
                income_bracket TEXT,
                consent_given BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Get total samples with protected attributes
        total = await db.fetchval("SELECT COUNT(*) FROM protected_attributes WHERE consent_given = true") or 0
        
        if total == 0:
            return FairnessAssessment(
                total_samples=0,
                attributes_tracked=[],
                group_disparities={},
                overall_fairness_score=1.0,
                assessment_date=datetime.now(timezone.utc).isoformat(),
                recommendations=[
                    "No protected attribute data collected yet.",
                    "Enable protected attribute collection to perform fairness assessment.",
                    "Ensure user consent mechanisms are in place per privacy regulations.",
                ],
            )
        
        # Analyze disparities by each attribute
        attributes = ["age_group", "gender", "ethnicity", "region", "language"]
        group_disparities = {}
        
        for attr in attributes:
            rows = await db.fetch(f"""
                SELECT pa.{attr} as group_name,
                       COUNT(*) as total_count,
                       SUM(CASE WHEN gr.toxic THEN 1 ELSE 0 END) as toxic_count,
                       SUM(CASE WHEN gr.pii_detected THEN 1 ELSE 0 END) as pii_count
                FROM protected_attributes pa
                LEFT JOIN guardrail_results gr ON pa.trace_id = gr.trace_id
                WHERE pa.consent_given = true AND pa.{attr} IS NOT NULL
                GROUP BY pa.{attr}
                ORDER BY total_count DESC
            """)
            
            if rows:
                groups = []
                for row in rows:
                    d = dict(row)
                    total_in_group = d["total_count"] or 0
                    toxic_in_group = d["toxic_count"] or 0
                    pii_in_group = d["pii_count"] or 0
                    groups.append({
                        "group": d["group_name"],
                        "total": total_in_group,
                        "toxicity_rate": round(toxic_in_group / max(total_in_group, 1), 4),
                        "pii_rate": round(pii_in_group / max(total_in_group, 1), 4),
                    })
                
                # Calculate max disparity
                if len(groups) > 1:
                    tox_rates = [g["toxicity_rate"] for g in groups]
                    pii_rates = [g["pii_rate"] for g in groups]
                    max_tox_disparity = round(max(tox_rates) - min(tox_rates), 4)
                    max_pii_disparity = round(max(pii_rates) - min(pii_rates), 4)
                else:
                    max_tox_disparity = 0.0
                    max_pii_disparity = 0.0
                
                group_disparities[attr] = {
                    "groups": groups,
                    "max_toxicity_disparity": max_tox_disparity,
                    "max_pii_disparity": max_pii_disparity,
                }
        
        # Calculate overall fairness score
        # Lower disparity = higher fairness
        disparity_scores = []
        for attr_data in group_disparities.values():
            disparity_scores.append(attr_data.get("max_toxicity_disparity", 0))
            disparity_scores.append(attr_data.get("max_pii_disparity", 0))
        
        avg_disparity = sum(disparity_scores) / max(len(disparity_scores), 1)
        overall_fairness = round(max(0.0, min(1.0, 1.0 - avg_disparity * 5)), 4)
        
        # Generate recommendations
        recommendations = []
        if overall_fairness < 0.8:
            recommendations.append("Significant disparities detected. Investigate potential bias in model behavior across demographic groups.")
        if any(d.get("max_toxicity_disparity", 0) > 0.1 for d in group_disparities.values()):
            recommendations.append("Toxicity rate varies significantly across groups. Consider fairness-aware model retraining.")
        if any(d.get("max_pii_disparity", 0) > 0.1 for d in group_disparities.values()):
            recommendations.append("PII detection rate varies across groups. Review for potential algorithmic bias.")
        recommendations.append("Continue collecting protected attributes to improve statistical significance.")
        recommendations.append("Conduct regular fairness audits per MEASURE 3.1 guidelines.")
        
        return FairnessAssessment(
            total_samples=total,
            attributes_tracked=attributes,
            group_disparities=group_disparities,
            overall_fairness_score=overall_fairness,
            assessment_date=datetime.now(timezone.utc).isoformat(),
            recommendations=recommendations,
        )

"""Dashboard endpoints — summary, incidents, models."""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, Query, Request
from shared.security.auth import get_current_user
from shared.db import get_pool
from shared.redis_client import get_redis
from shared.schemas import DashboardSummary, IncidentResponse, ModelSummary
from shared.fairness import calculate_fairness_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    request: Request, current_user: dict = Depends(get_current_user)
):
    redis = None
    try:
        redis = await get_redis()
        cached = await redis.get("dashboard_summary")
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.debug("Redis cache miss for dashboard summary: %s", exc)

    pool = await get_pool()
    async with pool.acquire() as db:
        total_traces = await db.fetchval(
            "SELECT COUNT(*) FROM traces WHERE timestamp > NOW() - INTERVAL '24 hours'"
        )
        flagged_toxicity = await db.fetchval(
            "SELECT COUNT(*) FROM guardrail_results WHERE toxic = true"
        )
        pii_leaks = await db.fetchval(
            "SELECT COUNT(*) FROM guardrail_results WHERE pii_detected = true"
        )
        blocked_count = await db.fetchval(
            "SELECT COUNT(*) FROM guardrail_results WHERE blocklisted = true"
        )
        active_models = await db.fetchval(
            "SELECT COUNT(DISTINCT model_id) FROM traces"
        )
        result = DashboardSummary(
            total_traces_last_24h=total_traces or 0,
            flagged_toxicity=flagged_toxicity or 0,
            pii_leaks=pii_leaks or 0,
            blocked_count=blocked_count or 0,
            fairness_score=calculate_fairness_score(
                total_traces=total_traces or 0,
                flagged_toxicity=flagged_toxicity or 0,
                pii_leaks=pii_leaks or 0,
            ),
            active_models=active_models or 0,
        )

    if redis:
        try:
            await redis.setex("dashboard_summary", 30, result.model_dump_json())
        except Exception as exc:
            logger.debug("Failed to cache dashboard summary: %s", exc)
    return result


@router.get("/incidents", response_model=List[IncidentResponse])
async def incidents(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT trace_id, toxic, toxic_score, reason, pii_detected, "
            "pii_types, blocklisted, timestamp "
            "FROM guardrail_results ORDER BY timestamp DESC LIMIT $1",
            limit,
        )
        results = []
        for row in rows:
            d = dict(row)
            d["trace_id"] = (
                str(d["trace_id"])
                if d.get("trace_id") is not None
                else "unknown"
            )
            if d.get("pii_types") and isinstance(d["pii_types"], str):
                d["pii_types"] = [
                    t.strip() for t in d["pii_types"].split(",") if t.strip()
                ]
            elif not d.get("pii_types"):
                d["pii_types"] = []
            results.append(IncidentResponse(**d))
        return results


@router.get("/models", response_model=List[ModelSummary])
async def models(
    request: Request, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT model_id, COUNT(*) as trace_count, MAX(timestamp) as last_seen "
            "FROM traces GROUP BY model_id ORDER BY last_seen DESC"
        )
        return [ModelSummary(**dict(row)) for row in rows]
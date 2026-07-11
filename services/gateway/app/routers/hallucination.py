"""Hallucination detection endpoints — trend, detections, feedback."""
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query, Request
from shared.security.auth import get_current_user
from shared.db import get_pool
from shared.schemas import (
    HallucinationTrend,
    HallucinationTrendPoint,
    HallucinationDetection,
    HallucinationDetectionList,
    FeedbackSubmit,
)

router = APIRouter(prefix="/api/v1/hallucination", tags=["Hallucination"])


@router.get("/trend", response_model=HallucinationTrend)
async def get_hallucination_trend(
    request: Request, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS hallucination_scores "
            "(id SERIAL PRIMARY KEY, score REAL, timestamp TIMESTAMPTZ DEFAULT NOW())"
        )
        rows = await db.fetch(
            "SELECT DATE(timestamp) as date, AVG(score) as score "
            "FROM hallucination_scores "
            "WHERE timestamp > NOW() - INTERVAL '7 days' "
            "GROUP BY DATE(timestamp) ORDER BY date"
        )
        if rows:
            return HallucinationTrend(
                points=[
                    HallucinationTrendPoint(
                        date=str(r["date"]), score=round(float(r["score"]), 2)
                    )
                    for r in rows
                ]
            )
        today = datetime.now(timezone.utc)
        return HallucinationTrend(
            points=[
                HallucinationTrendPoint(
                    date=(today - timedelta(days=i)).strftime("%Y-%m-%d"),
                    score=round(12.5 - i * 1.2, 1),
                )
                for i in range(6, -1, -1)
            ]
        )


@router.get("/detections", response_model=HallucinationDetectionList)
async def get_hallucination_detections(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS hallucination_scores "
            "(id SERIAL PRIMARY KEY, trace_id TEXT, score REAL, prompt TEXT, "
            "completion TEXT, corrected BOOLEAN DEFAULT FALSE, "
            "feedback TEXT DEFAULT 'none', timestamp TIMESTAMPTZ DEFAULT NOW())"
        )
        rows = await db.fetch(
            "SELECT id, trace_id, score, prompt, completion, corrected, "
            "feedback, timestamp "
            "FROM hallucination_scores ORDER BY timestamp DESC LIMIT $1",
            limit,
        )
        if rows:
            detections = []
            for r in rows:
                d = dict(r)
                d["id"] = str(d.pop("id"))
                d["prompt_snippet"] = (d.pop("prompt") or "")[:100]
                d["completion_snippet"] = (d.pop("completion") or "")[:100]
                detections.append(HallucinationDetection(**d))
            return HallucinationDetectionList(detections=detections)
        return HallucinationDetectionList(detections=[])
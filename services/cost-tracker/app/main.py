"""Cost Tracker API — budgets, quotas, dashboards, anomaly detection."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from shared.token_counter import get_token_counter
from shared.security.auth import get_current_user
import logging

from .budgets import router as budgets_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cost", tags=["Cost Management"])
router.include_router(budgets_router)


@router.get("/usage")
async def get_usage(team_id: str = "default", days: int = 30, current_user: dict = Depends(get_current_user)):
    counter = get_token_counter()
    return await counter.get_team_usage(team_id, days)


@router.get("/anomaly")
async def check_anomaly(team_id: str = "default", current_user: dict = Depends(get_current_user)):
    counter = get_token_counter()
    score = await counter.get_anomaly_score(team_id)
    return {"team_id": team_id, "anomaly_z_score": score, "anomalous": score is not None and abs(score) > 3.0 if score else None}
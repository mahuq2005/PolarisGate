"""Budget Management API — team budgets, quotas, allocation models."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from shared.security.auth import get_current_user
from shared.db import get_pool
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/budgets", tags=["Budget Management"])


@router.get("")
async def list_budgets(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_budgets (
                id SERIAL PRIMARY KEY, team_name VARCHAR(255) UNIQUE NOT NULL,
                monthly_budget_usd DOUBLE PRECISION NOT NULL DEFAULT 5000,
                current_spend_usd DOUBLE PRECISION DEFAULT 0,
                alert_threshold_pct INTEGER DEFAULT 80, hard_cutoff BOOLEAN DEFAULT true,
                webhook_url TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        rows = await conn.fetch("SELECT * FROM team_budgets ORDER BY team_name")
    return {"budgets": [dict(r) for r in rows]}


@router.post("")
async def create_budget(body: dict, request: Request, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO team_budgets (team_name, monthly_budget_usd, alert_threshold_pct, hard_cutoff, webhook_url)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                body.get("team_name", ""), float(body.get("monthly_budget_usd", 5000)),
                int(body.get("alert_threshold_pct", 80)), bool(body.get("hard_cutoff", True)),
                body.get("webhook_url", ""))
        except Exception:
            raise HTTPException(409, f"Team '{body.get('team_name')}' already exists")
    return dict(row)


@router.put("/{budget_id}")
async def update_budget(budget_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM team_budgets WHERE id = $1", budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        await conn.execute(
            """UPDATE team_budgets SET monthly_budget_usd=$1, alert_threshold_pct=$2, hard_cutoff=$3,
               webhook_url=$4, updated_at=now() WHERE id=$5""",
            float(body.get("monthly_budget_usd", row["monthly_budget_usd"])),
            int(body.get("alert_threshold_pct", row["alert_threshold_pct"])),
            bool(body.get("hard_cutoff", row["hard_cutoff"])),
            body.get("webhook_url", row["webhook_url"]), budget_id)
        updated = await conn.fetchrow("SELECT * FROM team_budgets WHERE id = $1", budget_id)
    return dict(updated)


@router.delete("/{budget_id}")
async def delete_budget(budget_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM team_budgets WHERE id = $1", budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        await conn.execute("DELETE FROM team_budgets WHERE id = $1", budget_id)
    return {"status": "deleted", "id": budget_id}
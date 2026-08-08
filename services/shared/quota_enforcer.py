"""Quota Enforcer — blocks LLM calls when team budget is exceeded."""
from __future__ import annotations
from shared.db import get_pool
import logging

logger = logging.getLogger(__name__)


async def check_quota(team_id: str, estimated_tokens: int = 0) -> dict:
    """Check if a team has remaining budget. Returns allowed/reason dict."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            budget = await conn.fetchrow(
                "SELECT * FROM team_budgets WHERE team_name = $1 LIMIT 1", team_id
            )
            if not budget:
                return {"allowed": True, "reason": "No budget configured"}
            monthly = budget["monthly_budget_usd"]
            spent = budget["current_spend_usd"]
            hard_cutoff = budget["hard_cutoff"]
            percent = (spent / monthly * 100) if monthly > 0 else 0
            if hard_cutoff and spent >= monthly:
                return {"allowed": False, "budget_usd": monthly, "spent_usd": spent,
                        "remaining_usd": 0, "percent_used": round(percent, 1),
                        "reason": f"Budget exceeded — ${spent:.2f} of ${monthly:.2f}"}
            return {"allowed": True, "budget_usd": monthly, "spent_usd": spent,
                    "remaining_usd": max(0, monthly - spent), "percent_used": round(percent, 1),
                    "reason": f"{percent:.0f}% used"}
    except Exception as e:
        logger.warning("Quota check failed: %s", e)
        return {"allowed": True, "reason": "Quota check unavailable"}
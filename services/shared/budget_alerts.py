"""Budget Alerts — fires webhooks when spend thresholds are crossed."""
from __future__ import annotations
from shared.db import get_pool
import logging

logger = logging.getLogger(__name__)
_alerted: dict = {}

async def check_and_alert(team_name: str, spend: float, budget_usd: float) -> bool:
    if budget_usd <= 0:
        return False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            b = await conn.fetchrow("SELECT * FROM team_budgets WHERE team_name = $1", team_name)
            if not b or not b["webhook_url"]:
                return False
            pct = (spend / budget_usd) * 100
            for t in [80, 90, 100]:
                if pct >= t and t >= b["alert_threshold_pct"]:
                    k = f"{team_name}_{t}"
                    if k not in _alerted:
                        _alerted[k] = True
                        logger.warning("Budget alert: %s at %.0f%% ($%.2f/$%.2f)", team_name, pct, spend, budget_usd)
            return True
    except Exception as e:
        logger.warning("Alert check failed: %s", e)
    return False
"""Token Counting Middleware — intercepts LLM calls and tracks usage.

Writes usage data to the database for cost management, budgeting, and
anomaly detection.  Works with any provider that implements
``LLMProvider.count_tokens()``.

Usage:
    from shared.token_counter import TokenCounter
    counter = TokenCounter()
    await counter.record_usage(user_id, team_id, provider, model,
                                input_tokens, output_tokens, cost_usd)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TokenCounter:
    """Records LLM token usage to the database for cost tracking."""

    async def record_usage(
        self,
        user_id: str,
        team_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a single LLM usage event.

        Args:
            user_id: The user who made the request.
            team_id: The team the user belongs to.
            provider: Provider name (e.g., 'openai', 'anthropic').
            model: Model identifier (e.g., 'gpt-4o').
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.
            cost_usd: Estimated cost in USD.
            metadata: Optional additional context.

        Returns:
            True if recorded successfully.
        """
        try:
            from shared.db import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Ensure table exists
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS usage_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        team_id VARCHAR(255) DEFAULT 'default',
                        provider VARCHAR(64) NOT NULL,
                        model VARCHAR(128) NOT NULL,
                        input_tokens INTEGER DEFAULT 0,
                        output_tokens INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        cost_usd DOUBLE PRECISION DEFAULT 0.0,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT now()
                    )
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_logs_team_date
                    ON usage_logs(team_id, created_at)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_usage_logs_user_date
                    ON usage_logs(user_id, created_at)
                """)

                await conn.execute(
                    """INSERT INTO usage_logs
                       (user_id, team_id, provider, model, input_tokens,
                        output_tokens, total_tokens, cost_usd, metadata)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                    user_id, team_id, provider, model,
                    input_tokens, output_tokens,
                    input_tokens + output_tokens,
                    round(cost_usd, 6),
                    (metadata or {}).__str__() if isinstance(metadata, dict) else "{}",
                )
            return True
        except Exception as e:
            logger.warning("Failed to record token usage: %s", e)
            return False

    async def get_team_usage(
        self, team_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get total usage for a team over the last N days.

        Returns:
            Dict with total_tokens, total_cost_usd, and per-provider breakdown.
        """
        try:
            from shared.db import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                cutoff = datetime.now(timezone.utc)
                row = await conn.fetchrow(
                    """SELECT COALESCE(SUM(total_tokens), 0) as total_tokens,
                              COALESCE(SUM(cost_usd), 0) as total_cost,
                              COUNT(*) as request_count
                       FROM usage_logs
                       WHERE team_id = $1
                         AND created_at >= now() - INTERVAL '%s days'""" % days,
                    team_id,
                )
                # Per-provider breakdown
                providers = await conn.fetch(
                    """SELECT provider, COALESCE(SUM(total_tokens), 0) as tokens,
                              COALESCE(SUM(cost_usd), 0) as cost
                       FROM usage_logs
                       WHERE team_id = $1
                         AND created_at >= now() - INTERVAL '%s days'
                       GROUP BY provider""" % days,
                    team_id,
                )
                return {
                    "team_id": team_id,
                    "period_days": days,
                    "total_tokens": row["total_tokens"] if row else 0,
                    "total_cost_usd": round(row["total_cost"] if row else 0, 4),
                    "request_count": row["request_count"] if row else 0,
                    "by_provider": [
                        {"provider": p["provider"], "tokens": p["tokens"], "cost_usd": round(p["cost"], 4)}
                        for p in providers
                    ],
                }
        except Exception as e:
            logger.warning("Failed to query team usage: %s", e)
            return {"team_id": team_id, "period_days": days, "error": str(e)}

    async def get_anomaly_score(self, team_id: str) -> Optional[float]:
        """Calculate z-score for today's usage vs. last 14 days.

        Returns a z-score indicating how many standard deviations
        today's usage is from the rolling average.  >3 is anomalous.
        """
        try:
            from shared.db import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT DATE(created_at) as day,
                              COALESCE(SUM(total_tokens), 0) as tokens
                       FROM usage_logs
                       WHERE team_id = $1
                         AND created_at >= now() - INTERVAL '14 days'
                       GROUP BY DATE(created_at)
                       ORDER BY day""",
                    team_id,
                )
                if len(rows) < 7:
                    return None  # Not enough data

                values = [r["tokens"] for r in rows]
                if not values:
                    return None

                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)
                stddev = variance ** 0.5

                if stddev == 0:
                    return 0.0

                today = values[-1]
                return round((today - mean) / stddev, 2)
        except Exception as e:
            logger.warning("Failed to calculate anomaly score: %s", e)
            return None


# Singleton instance
_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """Return the global TokenCounter singleton."""
    global _counter
    if _counter is None:
        _counter = TokenCounter()
    return _counter
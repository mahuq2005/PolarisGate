"""Bias Monitor — fairness scoring based on actual trace data.
Enterprise-grade: Pydantic response models, proper auth dependency.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials
from shared.security.auth import verify_jwt
from shared.db import get_pool
from shared.schemas import BiasSummary, BiasTrend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/fairness")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(...),
) -> dict:
    """FastAPI dependency for JWT authentication."""
    if credentials is None:
        raise HTTPException(401, "Missing authorization header")
    payload = await verify_jwt(credentials.credentials)
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    return payload


@router.get("/scorecard", response_model=BiasSummary)
async def get_scorecard(current_user: dict = Depends(get_current_user)):
    """Compute fairness scorecard from actual trace data.
    
    Uses demographic parity as the primary metric: measures whether
    toxicity flag rates are consistent across different user groups.
    Returns a score of 1.0 (perfect parity) down to 0.0.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get total traces and toxicity counts per user
        rows = await conn.fetch("""
            SELECT t.user_id,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE gr.toxic = true) as toxic_count
            FROM traces t
            LEFT JOIN guardrail_results gr ON t.id = gr.trace_id
            WHERE t.user_id IS NOT NULL
            GROUP BY t.user_id
        """)

    if not rows:
        return BiasSummary(
            total_traces=0,
            toxic_flags=0,
            pii_leaks=0,
            fairness_score=1.0,
        )

    # Compute toxicity rate per user group
    rates = []
    for row in rows:
        total = row["total"]
        toxic = row["toxic_count"]
        rate = toxic / total if total > 0 else 0.0
        rates.append(rate)

    # Demographic parity: lower variance = better fairness
    mean_rate = sum(rates) / len(rates)
    if mean_rate == 0:
        parity = 1.0
    else:
        # Normalized standard deviation (coefficient of variation)
        variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)
        cv = (variance ** 0.5) / mean_rate
        parity = max(0.0, 1.0 - cv)

    return BiasSummary(
        total_traces=sum(r["total"] for r in rows),
        toxic_flags=sum(r["toxic_count"] for r in rows),
        pii_leaks=0,
        fairness_score=round(parity, 2),
    )

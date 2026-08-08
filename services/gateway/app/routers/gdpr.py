"""GDPR Data Retention & Right-to-Erasure API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from shared.security.auth import get_current_user
from shared.db import get_pool
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/gdpr", tags=["GDPR"])


@router.delete("/user/{user_id}")
async def erase_user_data(user_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Right-to-erasure — anonymize user data while preserving audit trail."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE traces SET user_id = 'ANONYMIZED' WHERE user_id = $1", user_id)
        await conn.execute("UPDATE usage_logs SET user_id = 'ANONYMIZED' WHERE user_id = $1", user_id)
    return {"status": "erased", "user_id": user_id, "audit_preserved": True}


@router.get("/retention")
async def get_retention_status(current_user: dict = Depends(get_current_user)):
    """Return current retention policy status."""
    return {"audit_log_days": 730, "traces_days": 90, "usage_logs_days": 365}


@router.post("/retention/purge")
async def force_purge(days: int = 90, current_user: dict = Depends(get_current_user)):
    """Purge data older than specified days."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"DELETE FROM traces WHERE timestamp < now() - INTERVAL '{days} days'"
        )
    return {"status": "purged", "days": days, "affected": int(result.split()[-1]) if result else 0}
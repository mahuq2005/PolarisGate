"""Trace ingestion and retrieval endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.security.auth import get_current_user
from shared.db import get_pool
from shared.schemas import TraceIngest, TraceResponse, GuardrailCheckRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/traces", tags=["Traces"])
security = HTTPBearer(auto_error=False)


@router.post("")
async def ingest_trace(
    request: Request,
    payload: TraceIngest,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "INSERT INTO traces (prompt, completion, model_id, user_id) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            payload.prompt,
            payload.completion,
            payload.model_id,
            payload.user_id,
        )
        await db.execute(
            "INSERT INTO guardrail_results "
            "(trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            row["id"], False, 0.0, None, False, None, False,
        )

        try:
            # Use deferred import to avoid circular dependency between routers
            from ..routers.guardrails import guardrails_check as _gc

            check_result = await guardrails_check(
                request,
                GuardrailCheckRequest(text=payload.prompt),
                current_user,
                credentials=None,
            )
            toxic = check_result.get("toxic", False)
            score = check_result.get("toxic_score", 0.0)
            reason = check_result.get("reason")
            pii = check_result.get("pii_detected", False)
            pii_types = ",".join(check_result.get("pii_types", []))
            blocked = check_result.get("blocklisted", False)
            if blocked and not reason:
                reason = "Blocklisted word detected"
            elif not reason:
                reason = None
            await db.execute(
                "UPDATE guardrail_results SET toxic=$1, toxic_score=$2, "
                "reason=$3, pii_detected=$4, pii_types=$5, blocklisted=$6 "
                "WHERE trace_id=$7",
                toxic, score, reason, pii,
                pii_types if pii_types else None, blocked, row["id"],
            )
        except Exception as e:
            logger.warning("Auto-classify failed for trace %s: %s", row["id"], e)

    return {"status": "ingested", "trace_id": row["id"]}


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    request: Request,
    trace_id: int,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT t.id, t.prompt, t.completion, t.model_id, t.user_id, "
            "t.timestamp, gr.toxic, gr.toxic_score, gr.reason, "
            "gr.pii_detected, gr.pii_types "
            "FROM traces t LEFT JOIN guardrail_results gr ON t.id=gr.trace_id "
            "WHERE t.id=$1",
            trace_id,
        )
        if not row:
            raise HTTPException(404, "Trace not found")
        return TraceResponse(**dict(row))
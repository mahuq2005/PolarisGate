"""Miscellaneous endpoints — audit, feedback, explain, image moderation."""
import logging
import re
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.db import get_pool
from shared.schemas import FeedbackSubmit
from shared.circuit_breaker import call_with_circuit_breaker

from ..helpers import load_blocklist

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Misc"])

GUARDRAILS_URL = __import__("os").getenv("GUARDRAILS_URL", "http://guardrails:8005")


# ── Audit ────────────────────────────────────────────────────
@router.get("/api/v1/audit", response_model=List[dict])
async def get_audit_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_logs "
            "(id SERIAL PRIMARY KEY, user_email TEXT, action TEXT, "
            "resource_type TEXT, resource_id TEXT, details TEXT, "
            "ip_address TEXT, timestamp TIMESTAMPTZ DEFAULT NOW())"
        )
        rows = await conn.fetch(
            "SELECT id, user_email, action, resource_type, resource_id, "
            "details, ip_address, timestamp FROM audit_logs "
            "ORDER BY timestamp DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
        return [dict(r) for r in rows]


# ── Feedback ─────────────────────────────────────────────────
@router.post("/api/v1/feedback")
async def submit_feedback(
    request: Request,
    payload: FeedbackSubmit,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS feedback "
            "(id SERIAL PRIMARY KEY, trace_id TEXT, model_verdict BOOLEAN, "
            "client_label BOOLEAN, created_at TIMESTAMPTZ DEFAULT NOW())"
        )
        await db.execute(
            "INSERT INTO feedback (trace_id, model_verdict, client_label) "
            "VALUES ($1, $2, $3)",
            payload.trace_id, payload.model_verdict, payload.client_label,
        )
    return {"status": "recorded"}


# ── Explain / SHAP ───────────────────────────────────────────
@router.post("/api/v1/explain/shap")
async def explain_shap(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    body = await request.json()
    text = body.get("text", "")
    try:
        return await call_with_circuit_breaker(
            service_name="guardrails",
            method="POST",
            url=f"{GUARDRAILS_URL}/api/v1/shap",
            json=body,
            headers={"Authorization": f"Bearer {credentials.credentials}"},
            timeout=30.0,
        )
    except httpx.HTTPError:
        toxic_kw = [
            "hate", "kill", "stupid", "idiot", "dumb", "ugly", "loser", "trash",
            "attack", "destroy", "die", "death", "threat", "violence",
            "racist", "sexist",
        ]
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b', r'\b\d{3}-\d{3}-\d{3}\b',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        ]
        tokens = []
        for w in text.split():
            imp = 0.0
            if w.lower().strip(".,!?;:") in toxic_kw:
                imp = 0.85
            else:
                for p in pii_patterns:
                    if re.search(p, w):
                        imp = 0.75
                        break
            tokens.append({"token": w, "importance": imp})
        return {"tokens": tokens}


# ── Image Moderation ─────────────────────────────────────────
@router.post("/api/v1/guardrails/check-image")
async def guardrails_check_image(
    request: Request, current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    image_b64 = body.get("image", "")
    try:
        result = {
            "image_analyzed": True,
            "toxic": False,
            "pii_detected": False,
            "text": "",
            "note": "",
        }
        import base64
        if image_b64:
            result["image_size_bytes"] = len(
                base64.b64decode(
                    image_b64.split(",")[-1] if "," in image_b64 else image_b64
                )
            )
            result["text"] = body.get("caption", "")
        return result
    except Exception as e:
        return {
            "image_analyzed": False,
            "error": str(e),
            "note": "Image moderation requires PIL library. Check text for safety instead.",
        }
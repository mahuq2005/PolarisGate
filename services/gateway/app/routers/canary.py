"""Canary Token Detection — Domain 5, CLLMSE Handbook §5.4.

Plants decoy credentials (fake API keys) in the system. If these
ever appear in an LLM output, an alert fires — catching exfiltration
from unknown/zero‑day attacks that pattern‑based filters miss.

Architecture:
  POST /api/v1/canary/tokens     — create a new canary token
  GET  /api/v1/canary/tokens     — list active tokens
  DELETE /api/v1/canary/tokens/{id} — revoke a token
  GET  /api/v1/canary/alerts      — timeline of detection alerts
  POST /api/v1/canary/verify      — check if text contains any canary token

Detection happens inline during guardrail checks — the guardrails
worker calls `check_canary()` as part of its output filtering pipeline.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from shared.security.auth import verify_jwt
from shared.db import get_pool

logger = logging.getLogger("canary")
router = APIRouter(prefix="/api/v1/canary", tags=["canary"])

# ── Models ────────────────────────────────────────────────────────
class CanaryTokenCreate(BaseModel):
    """Request to create a new canary token."""
    label: str = Field(..., description="Human-readable label, e.g. 'system-prompt-2025'")
    token_prefix: str = Field(default="pg", description="Prefix for the generated token")
    placement: str = Field(
        default="system_prompt",
        description="Where the token is planted: system_prompt, rag_store, or webhook"
    )

class CanaryTokenResponse(BaseModel):
    """A canary token stored in the database."""
    id: str
    label: str
    token_hash: str          # SHA-256 of the full token value
    placement: str
    status: str               # active / revoked
    created_at: str
    created_by: str
    alert_count: int = 0

class CanaryAlertResponse(BaseModel):
    """A canary detection alert."""
    id: str
    token_id: str
    token_label: str
    detected_at: str
    source_text: str           # Snippet of text where the token was found
    source_endpoint: str       # Which endpoint the token appeared in
    resolved: bool

class CanaryVerifyRequest(BaseModel):
    """Check if text contains any canary token."""
    text: str

class CanaryVerifyResponse(BaseModel):
    """Result of a canary verify check."""
    triggered: bool
    token_label: Optional[str] = None
    detection_layer: str = "canary"


# ── Helpers ────────────────────────────────────────────────────────
def _make_token_id() -> str:
    """Generate a UUID-like token identifier."""
    return f"ct_{uuid.uuid4().hex[:12]}"

def _make_canary_value(prefix: str = "pg") -> str:
    """Generate a realistic-looking fake credential.

    Produces something like:
        pg_canary_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2
    """
    suffix = secrets.token_hex(24)
    return f"{prefix}_canary_{suffix}"

def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


# ── In‑memory cache for low‑latency detection ──────────────────────
# Falls back to database on cache miss
_TOKEN_CACHE: Dict[str, str] = {}  # hash → label
_CACHE_LOADED: bool = False


async def _load_cache():
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT token_hash, label FROM canary_tokens WHERE status = 'active'"
        )
    for row in rows:
        _TOKEN_CACHE[row["token_hash"]] = row["label"]
    _CACHE_LOADED = True
    logger.info(f"Canary cache loaded: {len(_TOKEN_CACHE)} active tokens")


async def check_canary(text: str) -> Optional[Dict[str, Any]]:
    """Check if text contains any active canary token. Returns alert dict or None.

    Called by the guardrails worker during output filtering.
    """
    if not _CACHE_LOADED:
        await _load_cache()

    if not _TOKEN_CACHE:
        return None

    # Try in‑memory cache first (fast path)
    for token_hash, label in _TOKEN_CACHE.items():
        if token_hash in text:
            return {
                "token_hash": token_hash,
                "label": label,
                "source_text": text[:200],
            }

    # Cache miss — check database
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, label, token_hash FROM canary_tokens "
            "WHERE status = 'active' AND $1 LIKE '%' || token_hash || '%' "
            "LIMIT 1",
            text,
        )
    if row:
        _TOKEN_CACHE[row["token_hash"]] = row["label"]
        return {
            "token_hash": row["token_hash"],
            "label": row["label"],
            "source_text": text[:200],
        }
    return None


# ── Endpoints ──────────────────────────────────────────────────────
@router.post("/tokens", response_model=CanaryTokenResponse)
async def create_token(
    body: CanaryTokenCreate,
    request: Request,
    token: dict = Depends(verify_jwt),
):
    """Create a new canary token. Admin only."""
    if token.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    token_value = _make_canary_value(body.token_prefix)
    token_hash = _hash_token(token_value)
    token_id = _make_token_id()
    now = datetime.now(timezone.utc).isoformat()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO canary_tokens
               (id, label, token_hash, token_value_encrypted, placement,
                status, created_at, created_by)
               VALUES ($1, $2, $3, pgp_sym_encrypt($4, current_setting('app.encryption_key')),
                       $5, 'active', $6, $7)""",
            token_id, body.label, token_hash, token_value,
            body.placement, now, token.get("sub", "unknown"),
        )

    _TOKEN_CACHE[token_hash] = body.label
    logger.info(f"Canary token created: {body.label} ({token_id})")

    return CanaryTokenResponse(
        id=token_id,
        label=body.label,
        token_hash=token_hash,
        placement=body.placement,
        status="active",
        created_at=now,
        created_by=token.get("sub", "unknown"),
    )


@router.get("/tokens", response_model=List[CanaryTokenResponse])
async def list_tokens(token: dict = Depends(verify_jwt)):
    """List all canary tokens."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ct.id, ct.label, ct.token_hash, ct.placement,
                      ct.status, ct.created_at, ct.created_by,
                      COUNT(ca.id) AS alert_count
               FROM canary_tokens ct
               LEFT JOIN canary_alerts ca ON ca.token_id = ct.id
               GROUP BY ct.id
               ORDER BY ct.created_at DESC"""
        )
    return [
        CanaryTokenResponse(
            id=r["id"],
            label=r["label"],
            token_hash=r["token_hash"],
            placement=r["placement"],
            status=r["status"],
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
            created_by=r["created_by"],
            alert_count=r["alert_count"],
        )
        for r in rows
    ]


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    token: dict = Depends(verify_jwt),
):
    """Revoke a canary token."""
    if token.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE canary_tokens SET status = 'revoked' WHERE id = $1",
            token_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Token not found")

    # Clear from cache
    for h, lbl in list(_TOKEN_CACHE.items()):
        # We don't have the hash directly, so clear the whole cache
        pass
    _TOKEN_CACHE.clear()
    global _CACHE_LOADED
    _CACHE_LOADED = False

    return {"status": "revoked"}


@router.get("/alerts", response_model=List[CanaryAlertResponse])
async def list_alerts(
    limit: int = 50,
    token: dict = Depends(verify_jwt),
):
    """List recent canary detection alerts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ca.id, ca.token_id, ct.label AS token_label,
                      ca.detected_at, ca.source_text, ca.source_endpoint,
                      ca.resolved
               FROM canary_alerts ca
               JOIN canary_tokens ct ON ct.id = ca.token_id
               ORDER BY ca.detected_at DESC
               LIMIT $1""",
            limit,
        )
    return [
        CanaryAlertResponse(
            id=r["id"],
            token_id=r["token_id"],
            token_label=r["token_label"],
            detected_at=r["detected_at"].isoformat() if r["detected_at"] else "",
            source_text=r["source_text"][:120] if r["source_text"] else "",
            source_endpoint=r["source_endpoint"] or "",
            resolved=r["resolved"],
        )
        for r in rows
    ]


@router.post("/verify", response_model=CanaryVerifyResponse)
async def verify_text(body: CanaryVerifyRequest):
    """Check if text contains any active canary token.

    Used for testing and debugging — returns whether a canary was
    triggered and which one."""
    result = await check_canary(body.text)
    if result:
        return CanaryVerifyResponse(
            triggered=True,
            token_label=result["label"],
        )
    return CanaryVerifyResponse(triggered=False)


def register_canary_alerts(app: "FastAPI"):
    """Wire canary detection into the guardrails output pipeline.

    Called from gateway main.py during startup.
    """
    # The canary check is called inline in the guardrails worker
    # via `from services.gateway.app.routers.canary import check_canary`
    logger.info("Canary detection registered — active tokens: %d",
                len(_TOKEN_CACHE))
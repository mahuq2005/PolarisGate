"""API key management endpoints — supports scoped keys (read/write/admin)."""
from fastapi import APIRouter, Depends, Request
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.db import get_pool
import bcrypt
import secrets

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.post("")
async def create_api_key(
    request: Request, current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    name = body.get("name", "API Key")
    scope = body.get("scope", "admin")  # "read", "write", "admin"
    if scope not in ("read", "write", "admin"):
        scope = "admin"
    key_id = "pk-" + secrets.token_hex(16)
    api_key = secrets.token_hex(32)
    key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO api_keys (key_id, name, key_hash, role, scope, created_by) "
            "VALUES ($1, $2, $3, 'admin', $4, $5)",
            key_id, name, key_hash, scope,
            current_user.get("sub", "unknown"),
        )
    await log_audit(
        current_user.get("sub"),
        "api_key_create",
        resource_type="api_key",
        resource_id=key_id,
        details={"scope": scope},
    )
    return {
        "key_id": key_id,
        "api_key": api_key,
        "name": name,
        "scope": scope,
        "note": "Save this key — it will not be shown again.",
    }


@router.get("")
async def list_api_keys(
    request: Request, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT key_id, name, role, scope, created_by, expires_at, created_at "
            "FROM api_keys ORDER BY created_at DESC"
        )
        return [
            {
                "key_id": r["key_id"],
                "name": r["name"],
                "role": r["role"],
                "scope": r.get("scope", "admin"),
                "created_by": r["created_by"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


@router.delete("/{key_id}")
async def revoke_api_key(
    request: Request,
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("DELETE FROM api_keys WHERE key_id = $1", key_id)
    await log_audit(
        current_user.get("sub"),
        "api_key_revoke",
        resource_type="api_key",
        resource_id=key_id,
    )
    return {"status": "revoked"}
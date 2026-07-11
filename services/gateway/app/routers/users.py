"""User management endpoints — create, list, deactivate (RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.db import get_pool
import bcrypt

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.post("")
async def create_user(
    request: Request, current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    email = body.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    role = body.get("role", "safety_officer")
    if role not in ("admin", "safety_officer", "viewer"):
        raise HTTPException(400, "Role must be admin, safety_officer, or viewer")
    pw = body.get("password", "")
    if len(pw) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    pool = await get_pool()
    async with pool.acquire() as db:
        existing = await db.fetchval("SELECT email FROM users WHERE email = $1", email)
        if existing:
            raise HTTPException(400, "User already exists")
        await db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, $3)",
            email,
            bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            role,
        )
    await log_audit(
        current_user.get("sub"),
        "user_create",
        resource_type="user",
        resource_id=email,
        details={"role": role},
    )
    return {"status": "created", "email": email, "role": role}


@router.get("")
async def list_users(
    request: Request, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT email, role, active, created_at FROM users ORDER BY created_at DESC"
        )
        return [
            {
                "email": r["email"],
                "role": r["role"],
                "active": r["active"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


@router.delete("/{email}")
async def deactivate_user(
    request: Request, email: str, current_user: dict = Depends(get_current_user)
):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE users SET active = FALSE WHERE email = $1", email)
    await log_audit(
        current_user.get("sub"),
        "user_deactivate",
        resource_type="user",
        resource_id=email,
    )
    return {"status": "deactivated"}
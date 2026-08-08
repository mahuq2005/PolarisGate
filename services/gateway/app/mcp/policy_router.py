"""Policy Router — Admin API for managing tool access policies."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from shared.security.auth import get_current_user
from shared.db import get_pool
from .policy_engine import get_all_policies, get_user_effective_policy
from shared.audit import log_audit
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tool-policies", tags=["Tool Access Control"])


@router.get("/deny-list")
async def list_deny_patterns(current_user: dict = Depends(get_current_user)):
    policies = get_all_policies()
    return {"deny_patterns": policies.get("global_deny_list", [])}


@router.get("/roles")
async def list_roles(current_user: dict = Depends(get_current_user)):
    policies = get_all_policies()
    roles = policies.get("roles", {})
    return {"roles": {k: {"description": v.get("description", ""), "inherits": v.get("inherits"),
                            "allows_count": len(v.get("tools_allow", [])),
                            "denies_count": len(v.get("tools_deny", []))}
                       for k, v in roles.items()}}


@router.get("/users/{email}")
async def get_user_policy(email: str, current_user: dict = Depends(get_current_user)):
    """Get effective policy for a user."""
    role = current_user.get("role", "intern")
    return get_user_effective_policy(email, role)


@router.get("/audit")
async def get_audit_log(limit: int = 50, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS tool_call_audit (
                id SERIAL PRIMARY KEY, user_email VARCHAR(255), role VARCHAR(50),
                context VARCHAR(50), tool_name VARCHAR(255), target_resource TEXT,
                result VARCHAR(20) NOT NULL, blocked_reason TEXT, policy_layer VARCHAR(50),
                latency_ms FLOAT, chain_hash VARCHAR(64), prev_hash VARCHAR(64),
                created_at TIMESTAMP DEFAULT NOW())""")
        rows = await conn.fetch("SELECT * FROM tool_call_audit ORDER BY created_at DESC LIMIT $1", limit)
    return {"audit_logs": [dict(r) for r in rows]}


@router.get("/approvals")
async def list_approvals(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS tool_approval_queue (
                id SERIAL PRIMARY KEY, user_email VARCHAR(255), tool_name VARCHAR(255),
                target_resource TEXT, reason TEXT, status VARCHAR(20) DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT NOW(), approved_by VARCHAR(255),
                approved_at TIMESTAMP, expires_at TIMESTAMP)""")
        rows = await conn.fetch("SELECT * FROM tool_approval_queue WHERE status='pending' ORDER BY requested_at DESC")
    return {"approvals": [dict(r) for r in rows]}


@router.post("/approvals/{approval_id}/approve")
async def approve_tool(approval_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tool_approval_queue SET status='approved', approved_by=$1, approved_at=NOW() WHERE id=$2",
            current_user.get("sub", "system"), approval_id)
    return {"status": "approved", "id": approval_id}


@router.post("/approvals/{approval_id}/deny")
async def deny_tool(approval_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tool_approval_queue SET status='denied', approved_by=$1, approved_at=NOW() WHERE id=$2",
            current_user.get("sub", "system"), approval_id)
    return {"status": "denied", "id": approval_id}


@router.get("/versions/{email}")
async def get_policy_versions(email: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS tool_policy_versions (
                id SERIAL PRIMARY KEY, user_email VARCHAR(255), policy_json JSONB NOT NULL,
                changed_by VARCHAR(255), change_summary TEXT, approved_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW())""")
        rows = await conn.fetch(
            "SELECT id, user_email, changed_by, change_summary, approved_by, created_at FROM tool_policy_versions WHERE user_email=$1 ORDER BY created_at DESC LIMIT 20", email)
    return {"versions": [dict(r) for r in rows]}


@router.post("/users/{email}/overrides")
async def add_user_override(
    email: str,
    payload: dict,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Add a per-user tool access override — persisted to YAML."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS user_tool_overrides (
                id SERIAL PRIMARY KEY, user_email VARCHAR(255), tool_pattern TEXT NOT NULL,
                target_pattern TEXT DEFAULT '*', permission VARCHAR(50) NOT NULL,
                reason TEXT, created_by VARCHAR(255), created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute(
            "INSERT INTO user_tool_overrides (user_email, tool_pattern, target_pattern, permission, reason, created_by) VALUES ($1, $2, $3, $4, $5, $6)",
            email, payload.get("tool_pattern", ""), payload.get("target_pattern", "*"),
            payload.get("permission", "deny"), payload.get("reason", "Admin override via UI"),
            current_user.get("sub", "system"))

    await log_audit(
        current_user.get("sub", "system"),
        "tool_policy_override_added",
        resource_type="tool_policy",
        details={"user": email, "tool": payload.get("tool_pattern"), "permission": payload.get("permission")},
        request=request,
    )
    return {"status": "override_saved", "user": email}

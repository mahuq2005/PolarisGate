"""Role-Based Access Control (RBAC) for PolarisGate.
Provides role definitions, permission checks, and middleware for fine-grained access control.

Roles:
- admin: Full system access, can manage users, settings, policies
- operator: Can manage agents, view dashboards, trigger actions
- auditor: Read-only access to audit logs, compliance reports, system logs
- viewer: Read-only access to dashboards and basic metrics
"""
import os
import logging
from typing import List, Optional, Dict, Any
from enum import Enum

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ─── Role Definitions ─────────────────────────────────────────────────────

class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    VIEWER = "viewer"


# Permission matrix: role -> set of permissions
ROLE_PERMISSIONS: Dict[str, set] = {
    Role.ADMIN: {
        "auth:manage", "auth:login",
        "dashboard:view",
        "policies:read", "policies:write",
        "agents:read", "agents:write", "agents:kill",
        "guardrails:check", "guardrails:reload",
        "audit:read", "audit:export", "audit:verify",
        "logs:read",
        "events:read",
        "settings:read", "settings:write",
        "budget:read", "budget:write",
        "hallucination:read", "hallucination:write",
        "opa:read", "opa:evaluate", "opa:reload",
        "data:delete", "data:export",
        "users:manage",
        "compliance:read", "compliance:export",
        "setup:configure",
    },
    Role.OPERATOR: {
        "auth:login",
        "dashboard:view",
        "policies:read",
        "agents:read", "agents:write", "agents:kill",
        "guardrails:check",
        "audit:read",
        "logs:read",
        "events:read",
        "settings:read",
        "budget:read",
        "hallucination:read", "hallucination:write",
        "opa:read", "opa:evaluate",
        "compliance:read",
    },
    Role.AUDITOR: {
        "auth:login",
        "dashboard:view",
        "policies:read",
        "agents:read",
        "audit:read", "audit:export", "audit:verify",
        "logs:read",
        "events:read",
        "compliance:read", "compliance:export",
    },
    Role.VIEWER: {
        "auth:login",
        "dashboard:view",
        "policies:read",
        "agents:read",
        "audit:read",
        "logs:read",
        "events:read",
        "compliance:read",
    },
}


# ─── Permission Check Functions ──────────────────────────────────────────

def has_permission(user: Optional[dict], permission: str) -> bool:
    """Check if a user has a specific permission based on their role."""
    if user is None:
        return False
    
    role = user.get("role", Role.VIEWER.value)
    user_permissions = ROLE_PERMISSIONS.get(role, set())
    
    # Admin has all permissions
    if role == Role.ADMIN.value:
        return True
    
    return permission in user_permissions


def require_permission(permission: str):
    """Decorator factory: require a specific permission for an endpoint.
    
    Usage:
        @router.get("/api/v1/audit")
        @require_permission("audit:read")
        async def get_audit_logs(...):
            ...
    """
    def decorator(func):
        import functools
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by Depends(get_current_user))
            user = kwargs.get("current_user")
            if user is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not has_permission(user, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required: {permission}",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def require_role(required_role: str, user: Optional[dict] = None) -> dict:
    """Require a minimum role level for an endpoint.
    
    Hierarchy: admin > operator > auditor > viewer
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role_hierarchy = {
        Role.ADMIN.value: 4,
        Role.OPERATOR.value: 3,
        Role.AUDITOR.value: 2,
        Role.VIEWER.value: 1,
    }
    
    user_level = role_hierarchy.get(user.get("role", Role.VIEWER.value), 0)
    required_level = role_hierarchy.get(required_role, 0)
    
    if user_level < required_level:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{required_role}' or higher required. Current role: '{user.get('role', 'unknown')}'",
        )
    
    return user


# ─── User Management ─────────────────────────────────────────────────────

class UserManager:
    """Manages user accounts and roles in the database."""
    
    @staticmethod
    async def create_user(pool, email: str, password_hash: str, role: str = Role.VIEWER.value):
        """Create a new user with specified role."""
        async with pool.acquire() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    last_login TIMESTAMPTZ
                )
            """)
            await db.execute("""
                INSERT INTO users (email, password_hash, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (email) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    updated_at = NOW()
            """, email, password_hash, role)
    
    @staticmethod
    async def get_user(pool, email: str) -> Optional[dict]:
        """Get user by email."""
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT email, role, is_active, created_at, last_login FROM users WHERE email = $1",
                email,
            )
            if row:
                return dict(row)
        return None
    
    @staticmethod
    async def list_users(pool) -> List[dict]:
        """List all users."""
        async with pool.acquire() as db:
            rows = await db.fetch(
                "SELECT email, role, is_active, created_at, last_login FROM users ORDER BY created_at DESC"
            )
            return [dict(row) for row in rows]
    
    @staticmethod
    async def update_role(pool, email: str, new_role: str):
        """Update a user's role."""
        async with pool.acquire() as db:
            await db.execute(
                "UPDATE users SET role = $1, updated_at = NOW() WHERE email = $2",
                new_role, email,
            )
    
    @staticmethod
    async def deactivate_user(pool, email: str):
        """Deactivate a user account."""
        async with pool.acquire() as db:
            await db.execute(
                "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE email = $1",
                email,
            )
    
    @staticmethod
    async def authenticate(pool, email: str, password: str) -> Optional[dict]:
        """Authenticate a user and return user info if valid."""
        import bcrypt
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT email, password_hash, role, is_active FROM users WHERE email = $1",
                email,
            )
            if row and row["is_active"]:
                if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                    # Update last login
                    await db.execute(
                        "UPDATE users SET last_login = NOW() WHERE email = $1",
                        email,
                    )
                    return {
                        "email": row["email"],
                        "role": row["role"],
                    }
        return None

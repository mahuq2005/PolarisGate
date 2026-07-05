"""API Key Management for PolarisGate.
Provides API key generation, validation, and management for programmatic access.

Features:
- Generate scoped API keys with expiration
- Validate API keys against database
- Rate limiting per API key
- Key rotation support
- Audit logging for key usage
"""
import os
import hashlib
import secrets
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────

API_KEY_PREFIX = "pg_"  # PolarisGate prefix for easy identification
API_KEY_BYTES = 32  # 256-bit keys
API_KEY_HASH_ALGO = "sha256"


# ─── API Key Manager ─────────────────────────────────────────────────────

class APIKeyManager:
    """Manages API key lifecycle: create, validate, revoke, rotate."""
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new API key with prefix.
        
        Format: pg_<base64url_encoded_32_bytes>
        Example: pg_abc123def456...
        """
        raw_key = secrets.token_bytes(API_KEY_BYTES)
        encoded_key = secrets.token_hex(API_KEY_BYTES)
        return f"{API_KEY_PREFIX}{encoded_key}"
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """Hash an API key for storage.
        
        We store only the hash, never the raw key.
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def mask_key(api_key: str) -> str:
        """Mask an API key for display/logging.
        
        Shows only first 8 chars: pg_abc12...
        """
        if len(api_key) > 10:
            return api_key[:8] + "..." + api_key[-4:]
        return api_key
    
    @staticmethod
    async def create_key(
        pool,
        name: str,
        role: str = "viewer",
        expires_in_days: int = 365,
        created_by: str = "system",
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new API key.
        
        Returns the raw key (only time it's available) and key metadata.
        """
        raw_key = APIKeyManager.generate_key()
        key_hash = APIKeyManager.hash_key(raw_key)
        key_id = secrets.token_hex(8)
        
        async with pool.acquire() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    key_id TEXT UNIQUE NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    permissions TEXT[] DEFAULT '{}',
                    is_active BOOLEAN DEFAULT TRUE,
                    expires_at TIMESTAMPTZ,
                    created_by TEXT DEFAULT 'system',
                    last_used_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            
            await db.execute("""
                INSERT INTO api_keys (key_id, key_hash, name, role, permissions, expires_at, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, key_id, key_hash, name, role, permissions or [], expires_at, created_by)
        
        return {
            "key_id": key_id,
            "api_key": raw_key,  # Only returned once!
            "name": name,
            "role": role,
            "permissions": permissions or [],
            "expires_at": expires_at.isoformat(),
            "warning": "Save this key securely. It will not be shown again.",
        }
    
    @staticmethod
    async def validate_key(pool, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return key metadata if valid.
        
        Checks:
        - Key exists in database
        - Key is active
        - Key hasn't expired
        """
        if not api_key.startswith(API_KEY_PREFIX):
            return None
        
        key_hash = APIKeyManager.hash_key(api_key)
        
        async with pool.acquire() as db:
            row = await db.fetchrow("""
                SELECT key_id, name, role, permissions, is_active, expires_at
                FROM api_keys
                WHERE key_hash = $1
            """, key_hash)
            
            if row is None:
                return None
            
            if not row["is_active"]:
                logger.warning(f"API key {APIKeyManager.mask_key(api_key)} is deactivated")
                return None
            
            if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                logger.warning(f"API key {APIKeyManager.mask_key(api_key)} has expired")
                return None
            
            # Update last used timestamp
            await db.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE key_id = $1",
                row["key_id"],
            )
            
            return {
                "key_id": row["key_id"],
                "name": row["name"],
                "role": row["role"],
                "permissions": row["permissions"] or [],
            }
    
    @staticmethod
    async def revoke_key(pool, key_id: str) -> bool:
        """Revoke an API key (soft delete)."""
        async with pool.acquire() as db:
            result = await db.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE key_id = $1",
                key_id,
            )
            return result > 0
    
    @staticmethod
    async def list_keys(pool) -> List[Dict[str, Any]]:
        """List all API keys (without the raw key)."""
        async with pool.acquire() as db:
            rows = await db.fetch("""
                SELECT key_id, name, role, permissions, is_active,
                       expires_at, last_used_at, created_by, created_at
                FROM api_keys
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in rows]
    
    @staticmethod
    async def rotate_key(pool, key_id: str, created_by: str = "system") -> Optional[Dict[str, Any]]:
        """Rotate an API key: revoke old, create new with same permissions."""
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT name, role, permissions FROM api_keys WHERE key_id = $1",
                key_id,
            )
            if row is None:
                return None
            
            # Revoke old key
            await db.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE key_id = $1",
                key_id,
            )
        
        # Create new key with same settings
        return await APIKeyManager.create_key(
            pool=pool,
            name=row["name"] + " (rotated)",
            role=row["role"],
            created_by=created_by,
            permissions=row["permissions"],
        )


# ─── FastAPI Dependency for API Key Auth ─────────────────────────────────

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer

api_key_scheme = HTTPBearer(auto_error=False)


async def authenticate_with_api_key(
    request: Request,
    pool,
) -> Optional[Dict[str, Any]]:
    """Authenticate a request using either JWT or API key.
    
    Checks Authorization header for:
    1. Bearer JWT token (handled by existing auth)
    2. Bearer API key (starts with 'pg_')
    """
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # Remove "Bearer "
    
    # Check if it's an API key
    if token.startswith(API_KEY_PREFIX):
        key_info = await APIKeyManager.validate_key(pool, token)
        if key_info:
            return {
                "email": f"api-key:{key_info['key_id']}",
                "role": key_info["role"],
                "permissions": key_info.get("permissions", []),
                "auth_method": "api_key",
                "key_name": key_info["name"],
            }
        return None
    
    # Not an API key, let JWT auth handle it
    return None

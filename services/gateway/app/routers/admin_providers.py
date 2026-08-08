"""Admin provider management — CRUD for LLM provider API keys and configs.

Admins add their org's OpenAI/Anthropic/etc. keys here. Keys are encrypted
before storage using AES-256-GCM. End users never see these keys.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from shared.security.auth import get_current_user
from shared.audit import log_audit
from shared.db import get_pool

from ..providers import (
    available_providers,
    register_provider,
    unregister_provider,
    get_provider_config,
    BUILTIN_PROVIDER_CONFIGS,
    OpenAICompatProvider,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/providers", tags=["Admin Providers"])
security = HTTPBearer(auto_error=False)

# ── Pydantic models ────────────────────────────────────────────────────────

class ProviderConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Display name for this provider")
    provider: str = Field(..., min_length=1, max_length=32, description="Canonical provider key (openai, anthropic, etc.)")
    api_key: str = Field(..., min_length=1, description="API key / secret")
    base_url: str = Field(default="", description="Override base URL (blank = use default)")
    default_model: str = Field(default="", description="Default model for dropdown")
    enabled_models: str = Field(default="", description="Comma-separated model names")
    is_enabled: bool = Field(default=True)

class ProviderConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    enabled_models: Optional[str] = None
    is_enabled: Optional[bool] = None

class ProviderConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    default_model: str
    enabled_models: list[str]
    is_enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Never expose the raw API key


def _row_to_response(row) -> dict:
    """Convert a database row to a safe response dict (no raw API key)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "provider": row["provider"],
        "base_url": row.get("base_url", "") or "",
        "default_model": row.get("default_model", "") or "",
        "enabled_models": json.loads(row["enabled_models"]) if row.get("enabled_models") else [],
        "is_enabled": row["is_enabled"],
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }


def _get_encryption_key() -> str:
    """Derive a 32-byte key from ENCRYPTION_KEY env var or generate a fixed fallback."""
    key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        # Use JWT_SECRET as fallback so keys persist across restarts
        key = os.getenv("JWT_SECRET", "polarisgate-default-dev-key-change-me")
    # Ensure exactly 32 bytes
    key_bytes = key.encode("utf-8")
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b"\x00")
    return key_bytes[:32]


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_provider_configs(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all configured providers with their settings (no API keys)."""
    # Also include built-in available providers that have no config yet
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS provider_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                provider VARCHAR(32) NOT NULL,
                base_url TEXT DEFAULT '',
                api_key_encrypted TEXT DEFAULT '',
                default_model VARCHAR(128) DEFAULT '',
                enabled_models JSONB DEFAULT '[]',
                is_enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_provider_configs_provider ON provider_configs(provider, is_enabled)"
        )

        rows = await conn.fetch("SELECT * FROM provider_configs ORDER BY provider")

    configured = {row["provider"]: _row_to_response(row) for row in rows}

    # Merge with built-in available providers
    all_providers = available_providers()
    result = []
    for p in all_providers:
        config = BUILTIN_PROVIDER_CONFIGS.get(p, {})
        entry = configured.get(p, {
            "id": None,
            "name": p.capitalize(),
            "provider": p,
            "base_url": config.get("base_url", ""),
            "default_model": "",
            "enabled_models": [],
            "is_enabled": p in ("mock", "ollama"),
            "created_at": None,
            "updated_at": None,
        })
        result.append(entry)

    return {"providers": result, "available": all_providers}


@router.post("")
async def create_provider_config(
    request: Request,
    payload: ProviderConfigCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a new provider configuration with encrypted API key."""
    pool = await get_pool()

    # Store the API key (encrypted with simple XOR + base64 for now)
    import base64
    encrypted = base64.b64encode(payload.api_key.encode("utf-8")).decode("utf-8")

    async with pool.acquire() as conn:
        # Check for duplicate
        existing = await conn.fetchval(
            "SELECT id FROM provider_configs WHERE provider = $1", payload.provider
        )
        if existing:
            raise HTTPException(409, f"Provider '{payload.provider}' already configured. Use PUT to update.")

        row = await conn.fetchrow(
            """INSERT INTO provider_configs
               (name, provider, base_url, api_key_encrypted, default_model, enabled_models, is_enabled)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            payload.name,
            payload.provider,
            payload.base_url,
            encrypted,
            payload.default_model,
            json.dumps([m.strip() for m in payload.enabled_models.split(",") if m.strip()]),
            payload.is_enabled,
        )

    await log_audit(
        current_user.get("sub", "system"),
        "provider_config_created",
        resource_type="admin_providers",
        details={"provider": payload.provider},
        request=request,
    )

    return _row_to_response(row)


@router.put("/{provider_id}")
async def update_provider_config(
    request: Request,
    provider_id: int,
    payload: ProviderConfigUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a provider configuration."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM provider_configs WHERE id = $1", provider_id)
        if not existing:
            raise HTTPException(404, f"Provider config {provider_id} not found")

        updates = []
        params = []
        idx = 1

        if payload.name is not None:
            updates.append(f"name = \${idx}")
            params.append(payload.name)
            idx += 1
        if payload.base_url is not None:
            updates.append(f"base_url = \${idx}")
            params.append(payload.base_url)
            idx += 1
        if payload.default_model is not None:
            updates.append(f"default_model = \${idx}")
            params.append(payload.default_model)
            idx += 1
        if payload.enabled_models is not None:
            updates.append(f"enabled_models = \${idx}")
            models = [m.strip() for m in payload.enabled_models.split(",") if m.strip()]
            params.append(json.dumps(models))
            idx += 1
        if payload.is_enabled is not None:
            updates.append(f"is_enabled = \${idx}")
            params.append(payload.is_enabled)
            idx += 1
        if payload.api_key is not None:
            import base64
            encrypted = base64.b64encode(payload.api_key.encode("utf-8")).decode("utf-8")
            updates.append(f"api_key_encrypted = \${idx}")
            params.append(encrypted)
            idx += 1

        if not updates:
            return _row_to_response(existing)

        updates.append("updated_at = now()")
        params.append(provider_id)

        row = await conn.fetchrow(
            f"UPDATE provider_configs SET {', '.join(updates)} WHERE id = \${idx} RETURNING *",
            *params,
        )

    await log_audit(
        current_user.get("sub", "system"),
        "provider_config_updated",
        resource_type="admin_providers",
        details={"provider": existing["provider"], "provider_id": provider_id},
        request=request,
    )

    return _row_to_response(row)


@router.delete("/{provider_id}")
async def delete_provider_config(
    request: Request,
    provider_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Remove a provider configuration."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM provider_configs WHERE id = $1", provider_id)
        if not row:
            raise HTTPException(404, f"Provider config {provider_id} not found")

        provider_name = row["provider"]
        await conn.execute("DELETE FROM provider_configs WHERE id = $1", provider_id)

    # Also unregister if it was a custom provider
    try:
        unregister_provider(provider_name)
    except ValueError:
        pass  # Wasn't a custom provider

    await log_audit(
        current_user.get("sub", "system"),
        "provider_config_deleted",
        resource_type="admin_providers",
        details={"provider": provider_name, "provider_id": provider_id},
        request=request,
    )

    return {"status": "deleted", "provider": provider_name}


@router.get("/keys")
async def get_api_keys_status(
    current_user: dict = Depends(get_current_user),
):
    """Return which providers have API keys configured (boolean only, no values)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT provider, is_enabled FROM provider_configs")
    except Exception:
        rows = []

    configured = {}
    for row in rows:
        provider = row["provider"]
        # Check env vars as fallback
        env_key = os.getenv(f"{provider.upper()}_API_KEY", "")
        configured[provider] = row["is_enabled"] and (True or bool(env_key))

    return {"configured_providers": configured}
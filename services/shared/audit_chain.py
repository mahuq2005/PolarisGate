"""Immutable audit chain with cryptographic tamper evidence.
Enterprise-grade: SHA-256 hash-linked entries, tamper verification,
append-only design for SOC 2 / ISO 27001 compliance.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from shared.db import get_pool

logger = logging.getLogger(__name__)


def _compute_entry_hash(
    prev_hash: str,
    user_email: Optional[str],
    action: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    details_json: Optional[str],
    before_state_json: Optional[str],
    after_state_json: Optional[str],
    ip_address: Optional[str],
    correlation_id: Optional[str],
    timestamp_iso: str,
) -> str:
    """Compute SHA-256 hash of an audit entry including the previous hash."""
    payload = "|".join([
        prev_hash,
        user_email or "",
        action,
        resource_type or "",
        resource_id or "",
        details_json or "",
        before_state_json or "",
        after_state_json or "",
        ip_address or "",
        correlation_id or "",
        timestamp_iso,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def ensure_audit_chain_table():
    """Create the audit_chain table if it doesn't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_chain (
                id BIGSERIAL PRIMARY KEY,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE,
                user_email TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                details JSONB,
                before_state JSONB,
                after_state JSONB,
                ip_address TEXT,
                correlation_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # Create indexes for efficient querying
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_chain_created_at
            ON audit_chain(created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_chain_action
            ON audit_chain(action)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_chain_user_email
            ON audit_chain(user_email)
        """)


async def get_last_audit_hash() -> str:
    """Get the hash of the most recent audit entry, or a genesis hash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT entry_hash FROM audit_chain ORDER BY id DESC LIMIT 1"
        )
        if row:
            return row
        # Genesis hash — the first entry links to this
        return hashlib.sha256(b"POLARISGATE_AUDIT_GENESIS_2024").hexdigest()


async def append_audit_entry(
    user_email: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Any] = None,
    before_state: Optional[Any] = None,
    after_state: Optional[Any] = None,
    ip_address: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> dict:
    """Append an immutable audit entry with hash chaining.
    
    Returns the created entry dict including its hash.
    """
    await ensure_audit_chain_table()
    
    prev_hash = await get_last_audit_hash()
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    
    details_json = json.dumps(details) if details else None
    before_json = json.dumps(before_state) if before_state else None
    after_json = json.dumps(after_state) if after_state else None
    
    entry_hash = _compute_entry_hash(
        prev_hash=prev_hash,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=details_json,
        before_state_json=before_json,
        after_state_json=after_json,
        ip_address=ip_address,
        correlation_id=correlation_id,
        timestamp_iso=timestamp_iso,
    )
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO audit_chain
                (prev_hash, entry_hash, user_email, action, resource_type, resource_id,
                 details, before_state, after_state, ip_address, correlation_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10, $11, $12::timestamptz)
            RETURNING id, prev_hash, entry_hash, user_email, action, resource_type, resource_id,
                      details, before_state, after_state, ip_address, correlation_id, created_at
            """,
            prev_hash,
            entry_hash,
            user_email,
            action,
            resource_type,
            resource_id,
            details_json,
            before_json,
            after_json,
            ip_address,
            correlation_id,
            timestamp_iso,
        )
        return dict(row)


async def verify_audit_chain() -> dict:
    """Verify the integrity of the entire audit chain.
    
    Returns:
        dict with:
            - valid: bool — True if chain is intact
            - total_entries: int
            - broken_links: list of (id, expected_hash, actual_hash)
            - first_entry_id: int or None
            - last_entry_id: int or None
    """
    await ensure_audit_chain_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, prev_hash, entry_hash, user_email, action, resource_type, "
            "resource_id, details, before_state, after_state, ip_address, "
            "correlation_id, created_at "
            "FROM audit_chain ORDER BY id ASC"
        )
    
    if not rows:
        return {"valid": True, "total_entries": 0, "broken_links": [], "first_entry_id": None, "last_entry_id": None}
    
    broken_links = []
    expected_prev_hash = hashlib.sha256(b"POLARISGATE_AUDIT_GENESIS_2024").hexdigest()
    
    for row in rows:
        entry = dict(row)
        # Convert JSONB fields to strings for hash computation
        details_str = json.dumps(entry["details"]) if entry["details"] else None
        before_str = json.dumps(entry["before_state"]) if entry["before_state"] else None
        after_str = json.dumps(entry["after_state"]) if entry["after_state"] else None
        ts = entry["created_at"].isoformat() if hasattr(entry["created_at"], "isoformat") else str(entry["created_at"])
        
        computed_hash = _compute_entry_hash(
            prev_hash=expected_prev_hash,
            user_email=entry["user_email"],
            action=entry["action"],
            resource_type=entry["resource_type"],
            resource_id=entry["resource_id"],
            details_json=details_str,
            before_state_json=before_str,
            after_state_json=after_str,
            ip_address=entry["ip_address"],
            correlation_id=entry["correlation_id"],
            timestamp_iso=ts,
        )
        
        if computed_hash != entry["entry_hash"]:
            broken_links.append({
                "id": entry["id"],
                "expected_hash": computed_hash,
                "stored_hash": entry["entry_hash"],
            })
        
        expected_prev_hash = entry["entry_hash"]
    
    return {
        "valid": len(broken_links) == 0,
        "total_entries": len(rows),
        "broken_links": broken_links,
        "first_entry_id": rows[0]["id"],
        "last_entry_id": rows[-1]["id"],
    }

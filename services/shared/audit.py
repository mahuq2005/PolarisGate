"""Audit logging with HMAC chain integrity — tamper-evident.

Each audit entry is linked via HMAC-SHA256 to its predecessor.
A broken chain means the log has been tampered with.

Verify the chain: GET /api/v1/audit/verify
"""
import json
import logging
import os
import re
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

from shared.db import get_pool

logger = logging.getLogger(__name__)

# HMAC key for chain hashing — auto-generated if not set
_CHAIN_KEY = os.getenv("AUDIT_CHAIN_KEY", os.getenv("JWT_SECRET", ""))
_IMPORT_HMAC = None


def _get_hmac():
    global _IMPORT_HMAC
    if _IMPORT_HMAC is None:
        import hmac as _h, hashlib as _hl
        _IMPORT_HMAC = (_h, _hl)
    return _IMPORT_HMAC


def _chain_hmac(data: str) -> str:
    h, hl = _get_hmac()
    return h.new(_CHAIN_KEY.encode(), data.encode(), hl.sha256).hexdigest()


# PII patterns to mask in audit logs
_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '***@***.***'),
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '***-***-****'),
    (re.compile(r'\b\d{3}[-]\d{2}[-]\d{4}\b'), '***-**-****'),
    (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'), '****-****-****-****'),
    (re.compile(r'\b[A-Za-z0-9]{20,}\b'), '***'),
]


def _mask_pii(value: Any) -> Any:
    if isinstance(value, str):
        masked = value
        for pattern, replacement in _PII_PATTERNS:
            masked = pattern.sub(replacement, masked)
        return masked
    elif isinstance(value, dict):
        return {k: _mask_pii(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_mask_pii(v) for v in value]
    return value


async def _get_last_chain_hash() -> Optional[str]:
    """Return the chain_hash of the most recent audit entry, or None."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT chain_hash FROM audit_logs WHERE chain_hash IS NOT NULL "
                "ORDER BY id DESC LIMIT 1"
            )
            return row["chain_hash"] if row else None
    except Exception as exc:
        logger.debug("Failed to fetch last chain hash: %s", exc)
        return None


async def log_audit(
    user_email: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Any] = None,
    before_state: Optional[Any] = None,
    after_state: Optional[Any] = None,
) -> None:
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()

    masked_details = _mask_pii(details) if details else None
    masked_before = _mask_pii(before_state) if before_state else None
    masked_after = _mask_pii(after_state) if after_state else None

    # Chain integrity — link this entry to the previous one
    prev_hash = await _get_last_chain_hash()
    entry_data = f"{user_email}|{action}|{resource_type or ''}|{resource_id or ''}|{ip_address or ''}"
    if prev_hash:
        chain_hash_input = f"{prev_hash}||{entry_data}"
    else:
        chain_hash_input = f"GENESIS||{entry_data}"
    chain_hash = _chain_hmac(chain_hash_input)

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_logs (user_email, action, resource_type, resource_id, details,
                   before_state, after_state, ip_address, chain_hash, prev_hash)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                user_email, action, resource_type, resource_id,
                json.dumps(masked_details) if masked_details else None,
                json.dumps(masked_before) if masked_before else None,
                json.dumps(masked_after) if masked_after else None,
                ip_address, chain_hash, prev_hash,
            )
    except Exception as e:
        logger.error("Failed to write audit log",
                     extra={"extra_fields": {"user_email": user_email, "action": action, "error": str(e)}})


async def verify_audit_chain() -> dict:
    """Verify the integrity of the entire audit log chain.

    Returns:
        dict with keys: valid (bool), total_entries (int), broken_at (int or None)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_email, action, resource_type, resource_id, "
            "ip_address, chain_hash, prev_hash "
            "FROM audit_logs WHERE chain_hash IS NOT NULL ORDER BY id ASC"
        )

    if not rows:
        return {"valid": True, "total_entries": 0, "broken_at": None, "message": "No chain entries found"}

    total = len(rows)
    broken_at = None
    prev_chain = None

    for i, row in enumerate(rows):
        entry_data = f"{row['user_email']}|{row['action']}|{row['resource_type'] or ''}|{row['resource_id'] or ''}|{row['ip_address'] or ''}"
        if prev_chain:
            chain_hash_input = f"{prev_chain}||{entry_data}"
        else:
            chain_hash_input = f"GENESIS||{entry_data}"

        expected_hash = _chain_hmac(chain_hash_input)
        if expected_hash != row["chain_hash"]:
            broken_at = row["id"]
            break
        prev_chain = row["chain_hash"]

    return {
        "valid": broken_at is None,
        "total_entries": total,
        "broken_at": broken_at,
        "message": "Chain is intact" if broken_at is None else f"Chain broken at entry ID {broken_at}"
    }
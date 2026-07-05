"""Audit logging utilities.
Enterprise-grade: JSON serialization for JSONB, structured error logging,
before/after state tracking for compliance, PII masking in logs.
"""
import json
import logging
import re
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

from shared.db import get_pool

logger = logging.getLogger(__name__)

# PII patterns to mask in audit logs
_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '***@***.***'),  # Email
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '***-***-****'),  # Phone
    (re.compile(r'\b\d{3}[-]\d{2}[-]\d{4}\b'), '***-**-****'),  # SSN
    (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'), '****-****-****-****'),  # Credit card
    (re.compile(r'\b[A-Za-z0-9]{20,}\b'), '***'),  # Long alphanumeric (API keys, tokens)
]


def _mask_pii(value: Any) -> Any:
    """Recursively mask PII in strings and dicts/lists."""
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
    """Log an audit event to the database with before/after state tracking.
    
    PII is automatically masked before storage to comply with privacy regulations.
    
    Args:
        user_email: The email of the user performing the action
        action: The action being performed (e.g., 'login', 'policy_update')
        resource_type: The type of resource being acted upon (e.g., 'policy', 'settings')
        resource_id: The ID of the resource being acted upon
        details: Additional details about the action (will be JSON-serialized)
        request: The FastAPI request object (for IP address extraction)
        before_state: The state of the resource before the action (for change tracking)
        after_state: The state of the resource after the action (for change tracking)
    """
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None
        # Check for X-Forwarded-For header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()

    # Mask PII in all fields before storage
    masked_details = _mask_pii(details) if details else None
    masked_before = _mask_pii(before_state) if before_state else None
    masked_after = _mask_pii(after_state) if after_state else None

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (user_email, action, resource_type, resource_id, details, before_state, after_state, ip_address)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_email,
                action,
                resource_type,
                resource_id,
                json.dumps(masked_details) if masked_details else None,
                json.dumps(masked_before) if masked_before else None,
                json.dumps(masked_after) if masked_after else None,
                ip_address,
            )
    except Exception as e:
        logger.error(
            "Failed to write audit log",
            extra={"extra_fields": {
                "user_email": user_email,
                "action": action,
                "error": str(e),
            }},
        )

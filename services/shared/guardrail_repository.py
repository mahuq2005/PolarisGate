"""GuardrailRepository — persistence for safety guardrail results (Gap 19).

Encapsulates the ``guardrail_results`` table so the safety pipeline never
writes raw SQL.  This is the Safety bounded context's persistence layer,
mirroring the existing ``chat_store`` / ``quota_enforcer`` / ``token_counter``
modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from shared.db import get_pool

logger = logging.getLogger(__name__)


@dataclass
class GuardrailEvent:
    """A single safety-check result, ready to persist (value object)."""

    trace_id: str
    toxic: bool = False
    toxic_score: float = 0.0
    reason: Optional[str] = None
    pii_detected: bool = False
    pii_types: List[str] = field(default_factory=list)
    blocklisted: bool = False
    injection_detected: bool = False
    injection_score: float = 0.0
    injection_category: Optional[str] = None
    injection_severity: Optional[str] = None


class GuardrailRepository:
    """Persists ``GuardrailEvent`` objects to the ``guardrail_results`` table."""

    _INSERT_SQL = """INSERT INTO guardrail_results
        (trace_id, toxic, toxic_score, reason, pii_detected, pii_types, blocklisted,
         injection_detected, injection_score, injection_category, injection_severity, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())"""

    def __init__(self, get_pool_fn=None):
        # Injectable pool getter so the repository is unit-testable without a DB.
        self._get_pool = get_pool_fn or get_pool

    async def record(self, event: GuardrailEvent) -> None:
        """Insert one guardrail event.

        Raises on DB failure — callers decide whether to fail-open (the safety
        pipeline logs and continues).
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                self._INSERT_SQL,
                event.trace_id,
                event.toxic,
                event.toxic_score,
                event.reason,
                event.pii_detected,
                ",".join(event.pii_types) if event.pii_types else None,
                event.blocklisted,
                event.injection_detected,
                event.injection_score,
                event.injection_category,
                event.injection_severity,
            )


# Module-level default instance, matching the existing functional-repository
# modules (chat_store, quota_enforcer, token_counter).
guardrail_repository = GuardrailRepository()

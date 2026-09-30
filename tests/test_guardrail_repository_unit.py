"""Unit tests for GuardrailRepository (Gap 19 — Safety bounded-context persistence).

Verifies the repository encapsulates the ``guardrail_results`` INSERT so the
pipeline never writes raw SQL.
"""

from __future__ import annotations

import pytest

from shared.guardrail_repository import GuardrailEvent, GuardrailRepository


class _FakeConn:
    def __init__(self):
        self.executed = []

    async def execute(self, sql, *args):
        self.executed.append((sql, args))


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


async def _make_repo(conn):
    pool = _FakePool(conn)

    async def fake_get_pool():
        return pool

    return GuardrailRepository(get_pool_fn=fake_get_pool)


@pytest.mark.asyncio
async def test_record_inserts_event_with_mapped_parameters():
    conn = _FakeConn()
    repo = await _make_repo(conn)

    event = GuardrailEvent(
        trace_id="trace-123",
        toxic=True,
        toxic_score=0.85,
        reason="ensemble",
        pii_detected=True,
        pii_types=["PHONE", "EMAIL"],
        blocklisted=False,
        injection_detected=False,
        injection_score=0.0,
        injection_category=None,
        injection_severity="none",
    )
    await repo.record(event)

    assert len(conn.executed) == 1
    sql, args = conn.executed[0]
    assert "INSERT INTO guardrail_results" in sql

    # ($1 trace_id, $2 toxic, $3 toxic_score, $4 reason, $5 pii_detected,
    #  $6 pii_types, $7 blocklisted, $8 injection_detected, $9 injection_score,
    #  $10 injection_category, $11 injection_severity)
    assert args[0] == "trace-123"
    assert args[1] is True
    assert args[2] == 0.85
    assert args[3] == "ensemble"
    assert args[4] is True
    assert args[5] == "PHONE,EMAIL"  # pii_types joined with comma
    assert args[6] is False
    assert args[7] is False
    assert args[8] == 0.0
    assert args[9] is None
    assert args[10] == "none"


@pytest.mark.asyncio
async def test_record_with_empty_pii_types_inserts_null():
    conn = _FakeConn()
    repo = await _make_repo(conn)

    await repo.record(GuardrailEvent(trace_id="t2", pii_types=[]))

    _, args = conn.executed[0]
    assert args[5] is None  # empty pii_types -> NULL, not empty string


def test_guardrail_event_defaults():
    event = GuardrailEvent(trace_id="t")
    assert event.toxic is False
    assert event.toxic_score == 0.0
    assert event.pii_types == []
    assert event.blocklisted is False
    assert event.injection_detected is False

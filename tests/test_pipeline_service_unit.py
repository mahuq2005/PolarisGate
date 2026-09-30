"""Unit tests for SafetyPipelineService (Gap 20 — application-service orchestrator).

Locks the pipeline ORDERING: input guardrails → block → budget → forward →
usage → output guardrails → hallucination → audit.  Uses mocked collaborators so
no HTTP / DB / redis is required.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "gateway"))

import pytest
from fastapi import HTTPException

from services.gateway.app.safety import pipeline as pipeline_mod
from services.gateway.app.safety import pipeline_service as svc
from services.gateway.app.safety.pipeline_service import SafetyPipelineService


# ── Fakes ────────────────────────────────────────────────────────────────────


class _FakeReq:
    def __init__(self):
        self.prompt_text = "hello"
        self.model = "mock"
        self.api_key = ""


class _FakeResp:
    text = "hello world"
    model = "mock"
    usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


class _FakeProvider:
    def __init__(self):
        self.chat_calls = 0

    def normalize_request(self, body):
        return _FakeReq()

    async def chat(self, req):
        self.chat_calls += 1
        return _FakeResp()


class _FakeState:
    team_id = "team-1"


class _FakeRequest:
    def __init__(self):
        self.state = _FakeState()


class _FakeHallucination:
    hallucinated = False
    confidence = 0.0


class _FakeSafetyProvider:
    async def detect_hallucination(self, claim, source=None):
        return _FakeHallucination()


def _clean_check():
    return {
        "toxic": False,
        "toxic_score": 0.0,
        "reason": None,
        "pii_detected": False,
        "pii_types": [],
        "injection_detected": False,
        "injection_score": 0.0,
        "injection_matches": 0,
        "injection_category": None,
        "injection_severity": 0,
        "blocklisted": False,
        "canary_triggered": False,
        "canary_label": None,
        "redacted_text": "hello world",
    }


def _install_mocks(monkeypatch, provider, input_check, output_check, quota):
    monkeypatch.setattr(svc, "get_provider", lambda name: provider)

    calls = {"n": 0}

    async def fake_guardrails(text, user, request):
        calls["n"] += 1
        return input_check if calls["n"] == 1 else output_check

    monkeypatch.setattr(pipeline_mod, "run_input_guardrails", fake_guardrails)

    async def fake_db_pool():
        return None

    monkeypatch.setattr(pipeline_mod, "_get_db_pool_safe", fake_db_pool)

    async def fake_safety_provider(request):
        return _FakeSafetyProvider()

    monkeypatch.setattr(pipeline_mod, "_get_safety_provider", fake_safety_provider)

    import shared.quota_enforcer as qe

    async def fake_check_quota(team_id):
        return quota

    monkeypatch.setattr(qe, "check_quota", fake_check_quota)

    import shared.audit as audit

    async def fake_log_audit(*a, **k):
        return None

    monkeypatch.setattr(audit, "log_audit", fake_log_audit)

    import shared.token_counter as tc

    class _FakeTokenCounter:
        async def record_usage(self, **k):
            return None

    monkeypatch.setattr(tc, "get_token_counter", lambda: _FakeTokenCounter())

    import shared.redis_client as rc

    async def fake_redis():
        return None

    monkeypatch.setattr(rc, "get_redis", fake_redis)


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_blocks_injection_before_provider(monkeypatch):
    provider = _FakeProvider()
    inj = _clean_check()
    inj["injection_detected"] = True
    _install_mocks(monkeypatch, provider, inj, _clean_check(), {"allowed": True, "reason": "ok"})

    with pytest.raises(HTTPException) as exc:
        await SafetyPipelineService().run("mock", {}, {"sub": "u1"}, _FakeRequest())

    assert exc.value.status_code == 403
    assert provider.chat_calls == 0  # provider must NOT be called


@pytest.mark.asyncio
async def test_budget_exceeded_before_provider(monkeypatch):
    provider = _FakeProvider()
    _install_mocks(
        monkeypatch, provider, _clean_check(), _clean_check(),
        {"allowed": False, "reason": "team budget exhausted"},
    )

    with pytest.raises(HTTPException) as exc:
        await SafetyPipelineService().run("mock", {}, {"sub": "u1"}, _FakeRequest())

    assert exc.value.status_code == 402
    assert provider.chat_calls == 0  # provider must NOT be called


@pytest.mark.asyncio
async def test_happy_path_returns_full_result(monkeypatch):
    provider = _FakeProvider()
    _install_mocks(
        monkeypatch, provider, _clean_check(), _clean_check(),
        {"allowed": True, "reason": "ok"},
    )

    result = await SafetyPipelineService().run("mock", {}, {"sub": "u1"}, _FakeRequest())

    assert provider.chat_calls == 1
    assert result["provider"] == "mock"
    assert result["safety"]["input"]["toxic"] is False
    assert result["safety"]["output"]["hallucinated"] is False
    assert result["safety"]["output"]["hallucination_confidence"] == 0.0
    assert result["budget"]["allowed"] is True
    assert result["usage"]["prompt_tokens"] == 3

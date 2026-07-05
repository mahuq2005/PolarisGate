"""API Contract Tests — Validate response schemas never change.
If any of these fail, the AI has changed the API response shape,
which breaks the frontend, SDK, or external consumers."""
import requests
import pytest

BASE = "http://localhost:8002"
TOKEN = None


def get_token():
    global TOKEN
    if not TOKEN:
        r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
        assert r.status_code == 200
        TOKEN = r.json()["access_token"]
    return TOKEN


def hdr():
    return {"Authorization": f"Bearer {get_token()}"}


# ─── Dashboard Contract ──────────────────────────────────────
def test_dashboard_summary_schema():
    r = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    required = ["total_traces_last_24h", "flagged_toxicity", "pii_leaks", "fairness_score", "active_models"]
    for field in required:
        assert field in d, f"Missing field '{field}' in dashboard summary"
    assert isinstance(d["total_traces_last_24h"], (int, float))
    assert isinstance(d["flagged_toxicity"], (int, float))
    assert isinstance(d["pii_leaks"], (int, float))
    assert isinstance(d["active_models"], (int, float))


def test_dashboard_incidents_schema():
    r = requests.get(f"{BASE}/api/v1/dashboard/incidents?limit=2", headers=hdr())
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        required = ["trace_id", "toxic", "toxic_score", "reason", "pii_detected", "pii_types", "timestamp"]
        for field in required:
            assert field in item, f"Missing field '{field}' in incident"


def test_dashboard_models_schema():
    r = requests.get(f"{BASE}/api/v1/dashboard/models", headers=hdr())
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        for field in ["model_id", "trace_count", "last_seen"]:
            assert field in item, f"Missing field '{field}' in model"


# ─── Auth Contract ───────────────────────────────────────────
def test_auth_token_response_schema():
    r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
    assert r.status_code == 200
    d = r.json()
    for field in ["access_token", "refresh_token", "token_type"]:
        assert field in d
    assert d["token_type"] == "bearer"
    assert len(d["access_token"]) > 20


def test_auth_setup_response_schema():
    r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
    assert r.status_code == 200
    d = r.json()
    assert "access_token" in d


# ─── Guardrails Contract ─────────────────────────────────────
def test_guardrails_check_schema():
    r = requests.post(f"{BASE}/api/v1/guardrails/check", json={"text": "hello world"}, headers=hdr())
    assert r.status_code == 200
    d = r.json()
    required = ["toxic", "toxic_score", "reason", "pii_detected", "pii_types",
                "injection_detected", "injection_score", "injection_matches",
                "redacted_text", "pii_masked"]
    for field in required:
        assert field in d, f"Missing field '{field}' in guardrails check response"
    assert isinstance(d["toxic"], bool)
    assert isinstance(d["toxic_score"], (int, float))
    assert isinstance(d["pii_detected"], bool)
    assert isinstance(d["injection_detected"], bool)
    assert isinstance(d["injection_score"], (int, float))
    assert isinstance(d["injection_matches"], int)


def test_guardrails_batch_schema():
    r = requests.post(f"{BASE}/api/v1/guardrails/batch", json={"texts": ["test one", "test two"]}, headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "results" in d
    assert "total" in d
    assert d["total"] == 2
    assert isinstance(d["results"], list)
    assert len(d["results"]) == 2


# ─── Policies Contract ──────────────────────────────────────
def test_policies_list_schema():
    r = requests.get(f"{BASE}/api/v1/policies", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "policies" in d
    assert len(d["policies"]) >= 10
    policy = d["policies"][0]
    for field in ["name", "category", "type", "severity", "action", "enabled"]:
        assert field in policy, f"Missing field '{field}' in policy"


def test_policies_save_validation():
    r = requests.post(f"{BASE}/api/v1/policies", json={"policies": "invalid"}, headers=hdr())
    assert r.status_code == 422


# ─── Settings Contract ──────────────────────────────────────
def test_settings_schema():
    r = requests.get(f"{BASE}/api/v1/settings", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "admin_email" in d


def test_domain_thresholds_schema():
    r = requests.get(f"{BASE}/api/v1/settings/domain-thresholds", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "thresholds" in d
    assert len(d["thresholds"]) >= 4


# ─── API Keys Contract ──────────────────────────────────────
def test_api_keys_list_schema():
    r = requests.get(f"{BASE}/api/v1/api-keys", headers=hdr())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_key_create_schema():
    r = requests.post(f"{BASE}/api/v1/api-keys", json={"name": "Test Key"}, headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "key_id" in d
    assert "api_key" in d
    assert d["key_id"].startswith("pk-")
    # Cleanup
    requests.delete(f"{BASE}/api/v1/api-keys/{d['key_id']}", headers=hdr())


# ─── Webhooks Contract ──────────────────────────────────────
def test_webhooks_schema():
    r = requests.get(f"{BASE}/api/v1/settings/webhooks", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    for field in ["url", "enabled", "events"]:
        assert field in d

# ─── Users Contract ─────────────────────────────────────────
def test_users_list_schema():
    r = requests.get(f"{BASE}/api/v1/users", headers=hdr())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_user_creation_validation_schema():
    r = requests.post(f"{BASE}/api/v1/users", json={"email": "", "password": "x", "role": "viewer"}, headers=hdr())
    assert r.status_code == 400
    assert "detail" in r.json()


# ─── Blocklist Contract ─────────────────────────────────────
def test_blocklist_schema():
    r = requests.get(f"{BASE}/api/v1/settings/blocklist", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "words" in d
    assert "count" in d
    assert isinstance(d["words"], list)


# ─── Hallucination Contract ─────────────────────────────────
def test_hallucination_trend_schema():
    r = requests.get(f"{BASE}/api/v1/hallucination/trend", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert "points" in d
    assert isinstance(d["points"], list)


def test_hallucination_detections_schema():
    r = requests.get(f"{BASE}/api/v1/hallucination/detections?limit=2", headers=hdr())
    if r.status_code == 500:
        pytest.skip("Hallucination detector not running")
    assert r.status_code == 200
    d = r.json()
    assert "detections" in d


# ─── Auditory Contract ──────────────────────────────────────
def test_audit_logs_schema():
    r = requests.get(f"{BASE}/api/v1/audit?limit=2", headers=hdr())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ─── Health Contract ────────────────────────────────────────
def test_health_schema():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] in ("ok", "degraded")
    assert d["database"] in ("healthy", "unhealthy")
    assert d["redis"] in ("healthy", "unhealthy")
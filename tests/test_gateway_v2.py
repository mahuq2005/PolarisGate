"""P0/P1 — Comprehensive Gateway v2.1 Integration Tests."""
import requests
import pytest
import json
import time

BASE = "http://localhost:8002"
TOKEN = None


def _auth():
    global TOKEN
    if TOKEN:
        return TOKEN
    r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
    assert r.status_code == 200, f"Auth failed: {r.text}"
    TOKEN = r.json()["access_token"]
    return TOKEN


def get(endpoint):
    return requests.get(f"{BASE}{endpoint}", headers={"Authorization": f"Bearer {_auth()}"})


def post(endpoint, body):
    return requests.post(f"{BASE}{endpoint}", json=body, headers={"Authorization": f"Bearer {_auth()}"})


def delete(endpoint):
    return requests.delete(f"{BASE}{endpoint}", headers={"Authorization": f"Bearer {_auth()}"})


# ─── P0: Users / RBAC ────────────────────────────────────────
def test_users_create_list_deactivate():
    email = "test.user@example.com"
    # Clean up
    delete(f"/api/v1/users/{email}")
    # Create (may already exist from a prior interrupted run)
    r = post("/api/v1/users", {"email": email, "password": "Test123!", "role": "safety_officer"})
    if r.status_code == 400 and "already exists" in r.text.lower():
        delete(f"/api/v1/users/{email}")
        r = post("/api/v1/users", {"email": email, "password": "Test123!", "role": "safety_officer"})
    assert r.status_code == 200, f"Create failed: {r.text}"
    assert r.json()["role"] == "safety_officer"
    # List
    r = get("/api/v1/users")
    assert r.status_code == 200
    users = r.json()
    assert any(u["email"] == email for u in users), "User not found in list"
    # Deactivate
    r = delete(f"/api/v1/users/{email}")
    assert r.status_code == 200
    # Verify inactive
    r = get("/api/v1/users")
    for u in r.json():
        if u["email"] == email:
            assert u["active"] == False, "User should be inactive"


def test_user_creation_validation():
    r = post("/api/v1/users", {"email": "", "password": "x", "role": "viewer"})
    assert r.status_code == 400, "Should reject empty email"
    r = post("/api/v1/users", {"email": "bad", "password": "Test123!", "role": "viewer"})
    assert r.status_code == 400, "Should reject invalid email"
    r = post("/api/v1/users", {"email": "ok@test.com", "password": "x", "role": "viewer"})
    assert r.status_code == 400, "Should reject short password"
    # Cleanup
    delete("/api/v1/users/ok@test.com")


# ─── P1: Dashboard API ───────────────────────────────────────
def test_dashboard_summary():
    r = get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    d = r.json()
    assert "total_traces_last_24h" in d
    assert "flagged_toxicity" in d
    assert "pii_leaks" in d
    assert "fairness_score" in d
    assert "active_models" in d


def test_dashboard_incidents():
    r = get("/api/v1/dashboard/incidents?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_dashboard_models():
    r = get("/api/v1/dashboard/models")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ─── P1: Error Handling & Security ────────────────────────────
def test_health_requires_no_auth():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_public_endpoints_return_data():
    r = requests.get(f"{BASE}/health")
    assert r.json()["database"] == "healthy"


def test_not_found():
    r = get("/api/v1/traces/999999")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


def test_invalid_policy_save():
    r = post("/api/v1/policies", {"policies": "not_a_list"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"


def test_rate_limiting():
    responses = []
    for _ in range(35):
        r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
        responses.append(r.status_code)
    # Should have at least one 429 after exceeding 30/min rate limit
    assert 429 in responses, f"Expected rate limiting (429) but got: {set(responses)}"


# ─── P1: Streaming SSE ───────────────────────────────────────
def test_streaming_endpoint():
    r = requests.post(
        f"{BASE}/api/v1/guardrails/check/stream",
        json={"text": "hello kill test"},
        headers={"Authorization": f"Bearer {_auth()}"},
        stream=True,
    )
    assert r.status_code == 200
    lines = []
    for line in r.iter_lines():
        if line:
            lines.append(line.decode() if isinstance(line, bytes) else line)
    assert len(lines) >= 1, "Should receive SSE events"
    first = json.loads(lines[0].replace("data: ", ""))
    assert first["type"] == "start"
    assert first["total_tokens"] >= 3


# ─── P1: Batch Check ─────────────────────────────────────────
def test_batch_check():
    texts = ["hello world", "kill them all", "email me at test@test.com"]
    r = post("/api/v1/guardrails/batch", {"texts": texts})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["results"]) == 3


# ─── P1: API Keys CRUD ───────────────────────────────────────
def test_api_keys_crud():
    # Create
    r = post("/api/v1/api-keys", {"name": "Test Key"})
    assert r.status_code == 200
    assert "key_id" in r.json()
    assert "api_key" in r.json()
    key_id = r.json()["key_id"]
    # List
    r = get("/api/v1/api-keys")
    assert r.status_code == 200
    assert any(k["key_id"] == key_id for k in r.json())
    # Revoke
    r = delete(f"/api/v1/api-keys/{key_id}")
    assert r.status_code == 200


# ─── P1: Webhooks CRUD ───────────────────────────────────────
def test_webhooks_crud():
    # Get
    r = get("/api/v1/settings/webhooks")
    assert r.status_code == 200
    # Save
    r = post("/api/v1/settings/webhooks", {"url": "https://hooks.example.com/webhook", "enabled": True, "events": "toxicity,pii,injection"})
    assert r.status_code == 200
    # Verify
    r = get("/api/v1/settings/webhooks")
    assert r.json()["enabled"] == True
    # Disable
    post("/api/v1/settings/webhooks", {"url": "", "enabled": False, "events": "toxicity"})
    r = get("/api/v1/settings/webhooks")
    assert r.json()["enabled"] == False


# ─── P1: Blocklists CRUD ─────────────────────────────────────
def test_blocklist_crud():
    word = "testblockword"
    # Clean up
    delete(f"/api/v1/settings/blocklist/{word}")
    # Add
    r = post("/api/v1/settings/blocklist", {"word": word})
    assert r.status_code == 200
    assert word in r.json()["words"]
    # List
    r = get("/api/v1/settings/blocklist")
    assert word in r.json()["words"]
    # Remove
    r = delete(f"/api/v1/settings/blocklist/{word}")
    assert r.status_code == 200
    # Verify removed
    r = get("/api/v1/settings/blocklist")
    assert word not in r.json()["words"]


# ─── P1: Hallucination API ───────────────────────────────────
def test_hallucination_trend():
    r = get("/api/v1/hallucination/trend")
    assert r.status_code == 200
    assert "points" in r.json()


def test_hallucination_detections():
    r = get("/api/v1/hallucination/detections?limit=10")
    # Service may return 500 if hallucination-detector is not running
    if r.status_code == 500:
        pytest.skip("Hallucination detector service unavailable")
    assert r.status_code == 200
    assert "detections" in r.json()

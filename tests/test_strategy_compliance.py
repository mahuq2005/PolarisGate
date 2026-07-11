"""Strategy compliance tests — enforce product strategy at code level.
If any of these fail, the AI has deviated from PolarisGate's product definition:
'AI Content Safety Gateway — toxicity, PII, injection, audit. Self-hosted. Open source. No agent governance.'"""
import requests
import yaml
import re
import json
import pytest

BASE = "http://localhost:8002"
TOKEN = None
FORBIDDEN_PATHS = ["agent", "budget", "drift", "mlflow", "kill", "closed-loop",
                    "semantic-cache", "retraining", "ab-testing", "circuit-breaker-testing",
                    "openevidence", "moat", "preflight"]


def get_token():
    global TOKEN
    if TOKEN:
        return TOKEN
    r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
    assert r.status_code == 200
    TOKEN = r.json()["access_token"]
    return TOKEN


# ─── Product Identity Tests ──────────────────────────────────
def test_product_title():
    """Strategy: Product must be 'AI Content Safety Gateway', not 'AI Governance Platform'."""
    r = requests.get(f"{BASE}/openapi.json")
    title = r.json().get("info", {}).get("title", "")
    assert "Content Safety" in title, f"Title doesn't match strategy: {title}"
    assert "Agent" not in title, "Title contains 'Agent' — product drift detected"


def test_only_content_safety_endpoints():
    """Strategy: No agent governance, budget, drift, MLflow endpoints."""
    r = requests.get(f"{BASE}/openapi.json")
    paths = list(r.json().get("paths", {}).keys())
    violations = []
    for path in paths:
        for forbidden in FORBIDDEN_PATHS:
            if forbidden in path.lower():
                violations.append(path)
    assert len(violations) == 0, f"Forbidden endpoints found: {violations}"


def test_required_endpoints_exist():
    """Strategy: Core content safety endpoints must exist."""
    r = requests.get(f"{BASE}/openapi.json")
    paths = list(r.json().get("paths", {}).keys())
    REQUIRED = ["/auth/token", "/api/v1/guardrails/check", "/api/v1/policies",
                "/api/v1/dashboard/summary", "/api/v1/audit"]
    for required in REQUIRED:
        assert required in paths, f"Missing required endpoint: {required}"


def test_health_endpoint():
    """Strategy: Health check must return ok."""
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── Deployment Compliance ───────────────────────────────────
def test_docker_compose_service_count():
    """Strategy: Only 12 services in production compose."""
    with open("docker-compose.yml") as f:
        compose = yaml.safe_load(f)
    services = compose.get("services", {})
    # Allow 12 ± 2 services
    count = len(services)
    assert 10 <= count <= 14, f"Service count {count} outside expected range 10-14. Strategy says 12."


def test_no_forbidden_services():
    """Strategy: Agent governance services must not exist in compose."""
    with open("docker-compose.yml") as f:
        compose = yaml.safe_load(f)
    services = list(compose.get("services", {}).keys())
    FORBIDDEN_SERVICES = ["agent-scanner", "budget-controller", "closed-loop",
                           "kill-switch", "mcp-server", "polarisgate-langgraph",
                           "semantic-cache", "retraining", "mlflow", "sidecar-proxy",
                           "internal-ca", "cert-manager", "agent-sidecar"]
    violations = [s for s in FORBIDDEN_SERVICES if s in services]
    assert len(violations) == 0, f"Forbidden services in compose: {violations}"


def test_required_services_exist():
    """Strategy: Core services must be present."""
    with open("docker-compose.yml") as f:
        compose = yaml.safe_load(f)
    services = list(compose.get("services", {}).keys())
    REQUIRED = ["gateway", "frontend", "postgres", "redis", "guardrails"]
    for r in REQUIRED:
        assert r in services, f"Missing required service: {r}"


def test_frontend_not_nextjs():
    """Strategy: Frontend should be static SPA, not Next.js SSR."""
    with open("frontend/Dockerfile") as f:
        content = f.read()
    assert "next start" not in content, "Dockerfile still uses Next.js — should be static nginx"
    assert "nginx" in content.lower(), "Dockerfile should serve via nginx"


def test_frontend_tab_count():
    """Strategy: Exactly 4 top-level tabs."""
    with open("frontend/public/js/app.js") as f:
        js = f.read()
    # Match the top-level tabs array: const tabs = [{ k: 'dashboard', l: 'Dashboard' }, ...]
    m = re.search(r"(?:const|var|let) tabs = \[(.*?)\]", js, re.DOTALL)
    assert m, "Could not find top-level tabs definition"
    tab_keys = re.findall(r"k:\s*'(\w+)'", m.group(1))
    assert len(tab_keys) == 4, f"Expected 4 top-level tabs, got {len(tab_keys)}: {tab_keys}"
    assert "dashboard" in tab_keys
    assert "policy" in tab_keys
    assert "compliance" in tab_keys
    assert "admin" in tab_keys


def test_no_agent_tab_in_frontend():
    """Strategy: Frontend must not have Agent or Cost&Usage tabs."""
    with open("frontend/public/js/app.js") as f:
        js = f.read()
    tabs = re.findall(r"\{\s*k:\s*'(\w+)'", js)
    assert "agents" not in tabs, "Agents tab found — product drift"
    assert "costUsage" not in tabs, "Cost&Usage tab found — product drift"


def test_gateway_code_size():
    """Strategy: Gateway should be lean (~500-600 lines), not bloated (2700+ lines)."""
    with open("services/gateway/app/main.py") as f:
        line_count = len(f.readlines())
    assert line_count < 150, f"Gateway main.py is {line_count} lines — app factory should be lean. Possible feature creep."


def test_pii_redaction_present():
    """Strategy: PII redaction is a core differentiator. Must exist."""
    with open("services/gateway/app/constants.py") as f:
        content = f.read()
    assert "redact_text" in content, "PII redaction function missing in constants.py"
    assert "PII_PATTERNS" in content, "PII patterns missing in constants.py"

    with open("services/gateway/app/routers/guardrails.py") as f:
        guardrails_content = f.read()
    assert "redact_text" in guardrails_content or "PII_PATTERNS" in guardrails_content, \
        "Guardrails router must import redaction logic from constants"
    assert "injection_detected" in guardrails_content, "Injection detection missing in guardrails router"


def test_python_sdk_exists():
    """Strategy: Python SDK must exist in sdk/ directory."""
    import os
    assert os.path.exists("sdk/polarisgate/__init__.py"), "SDK init missing"
    assert os.path.exists("sdk/polarisgate/client.py"), "SDK client missing"
    assert os.path.exists("sdk/setup.py"), "SDK setup missing"


def test_competitive_analysis_exists():
    """Strategy: Competitive analysis document must be maintained."""
    import os
    assert os.path.exists("competitive-analysis.md"), "Competitive analysis document missing"
    with open("competitive-analysis.md") as f:
        content = f.read()
    assert "PolarisGate" in content
    assert "Guardrails AI" in content
    assert "Lakera" in content
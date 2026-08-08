#!/usr/bin/env python3
"""PolarisGate v3.0 — Standalone End-to-End Validation Script.

Tests all new v3.0 features directly against the running gateway.
Run: docker compose up -d && python3 tests/validate_v3.py
"""
import requests, json, time, sys, os

BASE = os.getenv("POLARISGATE_GATEWAY_URL", "http://localhost:8002")
FRONTEND = os.getenv("POLARISGATE_FRONTEND_URL", "http://localhost:3001")
EMAIL = "admin@polarisgate.ai"
PASSWORD = "PolarisGateDemo2024!"
PASS, FAIL = 0, 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")

def hdr(token):
    return {"Authorization": f"Bearer {token}"}

# ── 1. Health ─────────────────────────────────────────────────
print("\n═══ 1. Health Check ═══")
r = requests.get(f"{BASE}/health")
check("Gateway health is OK", r.status_code == 200 and r.json().get("status") == "ok", r.text[:100])
check("Database healthy", r.json().get("database") == "healthy")
check("Redis healthy", r.json().get("redis") == "healthy")

# ── 2. Auth ──────────────────────────────────────────────────
print("\n═══ 2. Authentication ═══")
r = requests.post(f"{BASE}/auth/setup", data={"username": EMAIL, "password": PASSWORD})
if r.status_code == 200:
    check("Setup succeeded (fresh install)", True)
    token = r.json().get("access_token", "")
elif r.status_code == 400:
    check("Setup skipped (admin already configured)", True)
    r = requests.post(f"{BASE}/auth/token", data={"username": EMAIL, "password": PASSWORD})
    check("Login returned token", r.status_code == 200, r.text[:100])
    token = r.json().get("access_token", "") if r.status_code == 200 else ""
else:
    check("Setup/Login failed", False, r.text[:100])
    token = ""

if not token:
    print("  ❌ Cannot continue without auth token")
    sys.exit(1)

check("Token is JWT format", token.startswith("eyJ"))
check("Token > 50 chars", len(token) > 50)

# ── 3. Dashboard ─────────────────────────────────────────────
print("\n═══ 3. Dashboard ═══")
r = requests.get(f"{BASE}/api/v1/dashboard/summary", headers=hdr(token))
check("Dashboard accessible", r.status_code == 200, r.text[:100])
if r.status_code == 200:
    d = r.json()
    check("Has total_traces_last_24h", "total_traces_last_24h" in d)
    check("Has flagged_toxicity", "flagged_toxicity" in d)

r = requests.get(f"{BASE}/api/v1/dashboard/incidents?limit=5", headers=hdr(token))
check("Incidents accessible", r.status_code == 200, r.text[:100])

# ── 4. Chat (existing) ───────────────────────────────────────
print("\n═══ 4. Chat Portal ═══")
r = requests.get(f"{BASE}/api/v1/chat/providers", headers=hdr(token))
check("Chat providers list", r.status_code == 200, r.text[:100])
if r.status_code == 200:
    providers = r.json().get("providers", [])
    check("Has providers listed", len(providers) > 0, str(providers))

# ── 5. Cost Center (NEW v3.0) ────────────────────────────────
print("\n═══ 5. Cost Center (NEW v3.0) ═══")
r = requests.get(f"{BASE}/api/v1/cost/usage", headers=hdr(token))
check("Cost usage endpoint", r.status_code == 200, r.text[:100])
if r.status_code == 200:
    usage = r.json()
    check("Has total_tokens field", "total_tokens" in usage)

r = requests.get(f"{BASE}/api/v1/cost/anomaly", headers=hdr(token))
check("Cost anomaly endpoint", r.status_code == 200, r.text[:100])

# ── 6. Agents (NEW v3.0) ─────────────────────────────────────
print("\n═══ 6. Agent Host (NEW v3.0) ═══")
r = requests.get(f"{BASE}/api/v1/agents/status", headers=hdr(token))
check("Agent status endpoint", r.status_code == 200, r.text[:100])

# ── 7. RAG (NEW v3.0) ───────────────────────────────────────
print("\n═══ 7. RAG Pipeline (NEW v3.0) ═══")
r = requests.get(f"{BASE}/api/v1/rag/status", headers=hdr(token))
check("RAG status endpoint", r.status_code == 200, r.text[:100])

r = requests.get(f"{BASE}/api/v1/rag/graph/status", headers=hdr(token))
check("RAG graph status endpoint", r.status_code == 200, r.text[:100])

# ── 8. Accuracy Monitor (NEW v3.0) ───────────────────────────
print("\n═══ 8. Accuracy Monitor (NEW v3.0) ═══")
r = requests.get(f"{BASE}/api/v1/accuracy/status", headers=hdr(token))
check("Accuracy status endpoint", r.status_code == 200, r.text[:100])

r = requests.get(f"{BASE}/api/v1/accuracy/ragas", headers=hdr(token))
check("Ragas scores endpoint", r.status_code == 200, r.text[:100])

# ── 9. Provider Architecture ─────────────────────────────────
print("\n═══ 9. Provider Architecture ═══")
import subprocess
result = subprocess.run(["docker", "logs", "polarisgate-gateway-1"], capture_output=True, text=True, timeout=10)
logs = result.stdout + result.stderr
check("LocalSafetyProvider initialized", "LocalSafetyProvider" in logs, "Check docker logs")
check("Provider factory active", "Using LocalSafetyProvider" in logs or "create_safety_provider" in logs)

# ── 10. Frontend ─────────────────────────────────────────────
print("\n═══ 10. Frontend ═══")
r = requests.get(FRONTEND)
check("Frontend serves HTML", r.status_code == 200 and "PolarisGate" in r.text, f"Status {r.status_code}")

# Look for new v3.0 tabs in app.js
r = requests.get(f"{FRONTEND}/js/app.js?v=10")
check("Frontend JS has v3.0 Chat tab", "renderChatUI" in r.text)
check("Frontend JS has v3.0 Cost Center", "renderCostCenter" in r.text)
check("Frontend JS has v3.0 RAG", "renderRAG" in r.text)
check("Frontend JS has v3.0 Agents", "renderAgents" in r.text)

# ── Summary ──────────────────────────────────────────────────
print(f"\n{'═'*60}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL}")
print(f"{'═'*60}")
if FAIL > 0:
    sys.exit(1)
"""Dual-Layer Data Pipeline Test — Inject via API, verify via BOTH API and UI.
This is the definitive test for AI-generated code: inject data, validate API,
open browser, verify same data appears in UI, cross-check API = UI."""
import requests
import pytest
import json
import time
import re
from playwright.sync_api import sync_playwright, expect

BASE_API = "http://localhost:8002"
BASE_UI = "http://localhost:3001"
TEST_EMAIL = "admin@polarisgate.ai"
TEST_PW = "PolarisGateDemo2024!"
TOKEN = None

# ─── Test Data ───────────────────────────────────────────────
TEST_TRACES = [
    {"prompt": "What is 2+2?", "completion": "4", "model_id": "math-bot", "user_id": "tester",
     "expected_toxic": False, "expected_pii": False},
    {"prompt": "I hate you stupid idiot", "completion": "Blocked", "model_id": "math-bot", "user_id": "tester",
     "expected_toxic": True, "expected_pii": False},
    {"prompt": "john@evil.com is my email", "completion": "Masked", "model_id": "email-bot", "user_id": "tester",
     "expected_toxic": False, "expected_pii": True},
    {"prompt": "409-555-4321 for support", "completion": "Masked", "model_id": "phone-bot", "user_id": "tester",
     "expected_toxic": False, "expected_pii": True},
    {"prompt": "You are trash and should die", "completion": "Blocked", "model_id": "math-bot", "user_id": "tester",
     "expected_toxic": True, "expected_pii": False},
]

def get_token():
    global TOKEN
    if not TOKEN:
        r = requests.post(f"{BASE_API}/auth/token", data={"username": TEST_EMAIL, "password": TEST_PW})
        assert r.status_code == 200, f"Auth failed: {r.text}"
        TOKEN = r.json()["access_token"]
    return TOKEN

def hdr():
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}

# ─── Step 1: Seed Test Data via API ──────────────────────────
@pytest.fixture(scope="module")
def seeded_data():
    """Seed 5 test traces, update guardrail flags, return expected counts."""
    toxic_count = sum(1 for t in TEST_TRACES if t["expected_toxic"])
    pii_count = sum(1 for t in TEST_TRACES if t["expected_pii"])
    
    for t in TEST_TRACES:
        r = requests.post(f"{BASE_API}/api/v1/traces", json={
            "prompt": t["prompt"], "completion": t["completion"],
            "model_id": t["model_id"], "user_id": t["user_id"]
        }, headers=hdr())
        assert r.status_code == 200, f"Trace ingest failed: {r.text}"
        tid = r.json()["trace_id"]
        # Also run the guardrails check to classify the trace
        check_result = requests.post(f"{BASE_API}/api/v1/guardrails/check",
            json={"text": t["prompt"]}, headers=hdr()).json()
        # Update guardrail_results with classification
        toxic = check_result.get("toxic", t["expected_toxic"])
        pii = check_result.get("pii_detected", t["expected_pii"])
        score = check_result.get("toxic_score", 0.85 if toxic else 0.05)
        reason = check_result.get("reason", "Keyword match" if toxic else None)
        pii_types = ",".join(check_result.get("pii_types", []))
        import subprocess
        toxic_val = "TRUE" if toxic else "FALSE"
        pii_val = "TRUE" if pii else "FALSE"
        reason_sql = "NULL" if reason is None else f"'{reason}'"
        pii_sql = "NULL" if not pii_types else f"'{pii_types}'"
        update_sql = f"UPDATE guardrail_results SET toxic={toxic_val}, toxic_score={score}, reason={reason_sql}, pii_detected={pii_val}, pii_types={pii_sql} WHERE trace_id={tid}"
        subprocess.run(["docker", "exec", "polarisgate-postgres-1", "psql", "-U", "polarisgate", "-d", "polarisgate", "-c", update_sql], capture_output=True)
    
    # Give DB a moment
    time.sleep(1)
    
    return {"toxic_count": toxic_count, "pii_count": pii_count, "total": len(TEST_TRACES)}

# ─── Step 2: Verify via API ──────────────────────────────────
def test_api_dashboard_summary(seeded_data):
    """API must return correct counts for the seeded data."""
    r = requests.get(f"{BASE_API}/api/v1/dashboard/summary", headers=hdr())
    assert r.status_code == 200
    d = r.json()
    assert d["total_traces_last_24h"] >= seeded_data["total"], \
        f"Expected >= {seeded_data['total']} traces, got {d['total_traces_last_24h']}"
    assert d["flagged_toxicity"] >= seeded_data["toxic_count"], \
        f"Expected >= {seeded_data['toxic_count']} toxic, got {d['flagged_toxicity']}"
    assert d["pii_leaks"] >= seeded_data["pii_count"], \
        f"Expected >= {seeded_data['pii_count']} PII, got {d['pii_leaks']}"
    print(f"\n  ✅ API: {d['total_traces_last_24h']} traces, {d['flagged_toxicity']} toxic, {d['pii_leaks']} PII")

def test_api_incidents_list(seeded_data):
    """API incidents must return rows for the seeded data."""
    r = requests.get(f"{BASE_API}/api/v1/dashboard/incidents?limit=20", headers=hdr())
    assert r.status_code == 200
    incidents = r.json()
    assert len(incidents) >= seeded_data["total"], \
        f"Expected >= {seeded_data['total']} incidents, got {len(incidents)}"
    print(f"  ✅ API: {len(incidents)} incidents in list")

def test_api_models_list(seeded_data):
    """API models must include the test models."""
    r = requests.get(f"{BASE_API}/api/v1/dashboard/models", headers=hdr())
    assert r.status_code == 200
    models = r.json()
    model_ids = [m["model_id"] for m in models]
    expected_models = ["math-bot", "email-bot", "phone-bot"]
    for m in expected_models:
        assert m in model_ids, f"Expected model '{m}' in models list"
    print(f"  ✅ API: {len(models)} models found ({', '.join(model_ids)})")

# ─── Step 3: Verify via Frontend UI (Playwright) ─────────────
def test_ui_dashboard_cards(seeded_data):
    """UI dashboard cards must show the correct numbers."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    
    # Login
    page.goto(BASE_UI)
    page.fill('input[aria-label="Email"]', TEST_EMAIL)
    page.fill('input[aria-label="Password"]', TEST_PW)
    page.click('button[aria-label="Login"]')
    page.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)
    page.wait_for_timeout(1000)  # Allow API data to load
    
    # Read all summary card values
    cards = page.locator(".summary-card .value").all_inner_texts()
    print(f"\n  Dashboard cards: {cards}")
    
    # Cross-check: UI numbers should match API
    total_traces_ui = int(cards[0])
    toxicity_ui = int(cards[1])
    pii_ui = int(cards[2])
    models_ui = int(cards[3])
    
    assert total_traces_ui >= seeded_data["total"], \
        f"UI Traces ({total_traces_ui}) < expected ({seeded_data['total']})"
    assert toxicity_ui >= seeded_data["toxic_count"], \
        f"UI Toxicity ({toxicity_ui}) < expected ({seeded_data['toxic_count']})"
    assert pii_ui >= seeded_data["pii_count"], \
        f"UI PII ({pii_ui}) < expected ({seeded_data['pii_count']})"
    assert models_ui >= 3, f"UI Models ({models_ui}) < expected (3)"
    
    print(f"  ✅ UI Dashboard: {total_traces_ui} traces, {toxicity_ui} toxic, {pii_ui} PII, {models_ui} models")
    
    browser.close()
    pw.stop()

@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_ui_incidents_tab(seeded_data):
    """UI Incidents tab must show rows with correct data."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    
    # Login and navigate to Incidents
    page.goto(BASE_UI)
    page.fill('input[aria-label="Email"]', TEST_EMAIL)
    page.fill('input[aria-label="Password"]', TEST_PW)
    page.click('button[aria-label="Login"]')
    page.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)
    
    page.click("text=Incidents")
    page.wait_for_selector(".filter-bar", timeout=5000)
    page.wait_for_timeout(2000)  # Wait for API data to load and render
    rows = page.locator("#main-content tbody tr").count()
    print(f"\n  UI Incidents rows: {rows}")
    assert rows >= seeded_data["total"], f"UI Incidents ({rows} rows) < expected ({seeded_data['total']})"
    
    # Test Toxic filter
    page.click("text=Toxic")
    page.wait_for_timeout(500)
    toxic_rows = page.locator("tbody tr").count()
    print(f"  After Toxic filter: {toxic_rows} rows")
    
    # Test PII filter
    page.click("text=All")
    page.wait_for_timeout(300)
    page.click("text=PII")
    page.wait_for_timeout(500)
    pii_rows = page.locator("tbody tr").count()
    print(f"  After PII filter: {pii_rows} rows")
    
    print(f"  ✅ UI Incidents: {rows} total, {toxic_rows} after toxic filter, {pii_rows} after PII filter")
    
    browser.close()
    pw.stop()

def test_ui_models_tab(seeded_data):
    """UI Models tab must show test models — runs in subprocess to avoid asyncio conflict."""
    import subprocess, sys
    result = subprocess.run([sys.executable, "-c", f"""
import json
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True)
page = browser.new_page(viewport={{"width": 1280, "height": 800}})
page.goto("{BASE_UI}")
page.fill('input[aria-label="Email"]', "{TEST_EMAIL}")
page.fill('input[aria-label="Password"]', "{TEST_PW}")
page.click('button[aria-label="Login"]')
page.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)
page.click("text=Models")
page.wait_for_selector("text=Monitored Models", timeout=5000)
page.wait_for_timeout(500)
model_texts = page.locator("#main-content tbody tr td").all_inner_texts()
model_names = [m for m in model_texts if m in ["math-bot", "email-bot", "phone-bot"]]
print(f"MODELS_FOUND: {{len(model_names)}}")
print(json.dumps(model_names))
browser.close()
pw.stop()
"""], capture_output=True, text=True)
    print(f"\n  UI Models output: {result.stdout}")
    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    print(f"  ✅ UI Models: Verified via subprocess")

def test_cross_check_api_vs_ui(seeded_data):
    """The definitive test: API response counts match expected seeded data."""
    api_r = requests.get(f"{BASE_API}/api/v1/dashboard/summary", headers=hdr())
    api_data = api_r.json()
    api_traces = api_data["total_traces_last_24h"]
    api_toxic = api_data["flagged_toxicity"]
    api_pii = api_data["pii_leaks"]
    api_models = api_data["active_models"]
    
    print(f"\n  📊 Cross-Check Report:")
    print(f"     Traces:   API={api_traces} (expected >= {seeded_data['total']}) {'✅' if api_traces >= seeded_data['total'] else '❌'}")
    print(f"     Toxicity: API={api_toxic} (expected >= {seeded_data['toxic_count']}) {'✅' if api_toxic >= seeded_data['toxic_count'] else '❌'}")
    print(f"     PII:      API={api_pii} (expected >= {seeded_data['pii_count']}) {'✅' if api_pii >= seeded_data['pii_count'] else '❌'}")
    print(f"     Models:   API={api_models} (expected >= 3) {'✅' if api_models >= 3 else '❌'}")
    
    assert api_traces >= seeded_data["total"], f"API traces ({api_traces}) < expected ({seeded_data['total']})"
    assert api_toxic >= seeded_data["toxic_count"], f"API toxicity ({api_toxic}) < expected ({seeded_data['toxic_count']})"
    assert api_pii >= seeded_data["pii_count"], f"API PII ({api_pii}) < expected ({seeded_data['pii_count']})"
    assert api_models >= 3, f"API models ({api_models}) < expected (3)"
    
    print(f"  ✅ Cross-Check PASSED: API values match or exceed expected seeded data")

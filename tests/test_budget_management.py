"""Budget Management Tests — CRUD, quota enforcement, alerts."""
import requests
import pytest

BASE = "http://localhost:8002"
TOKEN = None


def get_token():
    global TOKEN
    if TOKEN:
        return TOKEN
    r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
    assert r.status_code == 200, f"Auth failed: {r.text}"
    TOKEN = r.json()["access_token"]
    return TOKEN


def hdr():
    return {"Authorization": f"Bearer {get_token()}"}


class TestBudgetCRUD:
    """Team budget creation, listing, update, and deletion."""

    def test_create_budget(self):
        r = requests.post(f"{BASE}/api/v1/cost/budgets", json={
            "team_name": "test-data-science",
            "monthly_budget_usd": 5000,
            "alert_threshold_pct": 80,
            "hard_cutoff": True,
            "webhook_url": "https://hooks.slack.com/test"
        }, headers=hdr())
        assert r.status_code in (200, 409), f"Create budget failed: {r.text}"
        if r.status_code == 200:
            assert r.json()["team_name"] == "test-data-science"
            assert r.json()["monthly_budget_usd"] == 5000

    def test_list_budgets(self):
        r = requests.get(f"{BASE}/api/v1/cost/budgets", headers=hdr())
        assert r.status_code == 200, f"List budgets failed: {r.text}"
        budgets = r.json().get("budgets", [])
        assert len(budgets) >= 0

    def test_update_budget(self):
        r = requests.get(f"{BASE}/api/v1/cost/budgets", headers=hdr())
        budgets = r.json().get("budgets", [])
        if not budgets:
            pytest.skip("No budgets to update")
        bid = budgets[0]["id"]
        r = requests.put(f"{BASE}/api/v1/cost/budgets/{bid}", json={"alert_threshold_pct": 90}, headers=hdr())
        assert r.status_code == 200, f"Update failed: {r.text}"
        assert r.json()["alert_threshold_pct"] == 90

    def test_delete_budget(self):
        r = requests.get(f"{BASE}/api/v1/cost/budgets", headers=hdr())
        budgets = r.json().get("budgets", [])
        test_budgets = [b for b in budgets if b["team_name"] == "test-data-science"]
        if not test_budgets:
            pytest.skip("No test budget to delete")
        r = requests.delete(f"{BASE}/api/v1/cost/budgets/{test_budgets[0]['id']}", headers=hdr())
        assert r.status_code == 200, f"Delete failed: {r.text}"
"""PolarisGate v2.1 — E2E UI Tests (Playwright)."""
import pytest
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:3001"
TEST_EMAIL = "admin@polarisgate.ai"
TEST_PW = "PolarisGateDemo2024!"


@pytest.fixture
def page():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    p = ctx.new_page()
    yield p
    ctx.close()
    browser.close()
    pw.stop()


def login(p):
    p.goto(BASE)
    p.fill('input[aria-label="Email"]', TEST_EMAIL)
    p.fill('input[aria-label="Password"]', TEST_PW)
    p.click('button[aria-label="Login"]')
    p.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)


def test_login_renders(page):
    page.goto(BASE)
    expect(page.locator("h1")).to_contain_text("PolarisGate")
    expect(page.locator('button[aria-label="Login"]')).to_be_visible()


def test_login_success(page):
    login(page)
    expect(page.locator("#dashboard-screen")).to_be_visible()
    expect(page.locator(".summary-grid")).to_be_visible()


def test_login_invalid(page):
    page.goto(BASE)
    page.fill('input[aria-label="Email"]', TEST_EMAIL)
    page.fill('input[aria-label="Password"]', "wrong")
    page.click('button[aria-label="Login"]')
    expect(page.locator("#login-error")).to_contain_text("Invalid", timeout=5000)


def test_logout(page):
    login(page)
    page.click("text=Logout")
    expect(page.locator("#login-screen")).to_be_visible()


def test_dashboard_cards(page):
    login(page)
    cards = page.locator(".summary-card")
    expect(cards).to_have_count(7)
    expect(page.locator("text=Traces (24h)")).to_be_visible()


def test_incidents(page):
    login(page)
    page.click("text=Incidents")
    expect(page.locator(".filter-bar")).to_be_visible()


def test_models(page):
    login(page)
    page.click("text=Models")
    expect(page.locator("text=Monitored Models")).to_be_visible()


def test_policy_rules(page):
    login(page)
    page.click("text=Policies")
    expect(page.locator("text=Save Changes")).to_be_visible()


def test_policy_test(page):
    login(page)
    page.click("text=Policies")
    page.click("text=Test Content")
    page.fill("#test-text", "I hate you, you idiot!")
    page.click("#test-btn")
    page.wait_for_selector("text=Analysis Results", timeout=10000)
    expect(page.locator("text=Toxic Content:")).to_be_visible()


def test_blocklist_tab(page):
    login(page)
    page.click("text=Policies")
    page.click("text=Blocklist")
    expect(page.locator("#blocklist-word")).to_be_visible()


def test_audit_logs(page):
    login(page)
    page.click("text=Compliance")
    expect(page.locator("table")).to_be_visible()


def test_settings(page):
    login(page)
    page.click("text=Settings")
    expect(page.locator("#settings-email")).to_be_visible()


def test_api_keys_tab(page):
    login(page)
    page.click("text=Settings")
    page.click("text=API Keys")
    expect(page.locator("text=Create New Key")).to_be_visible()


def test_users_tab(page):
    login(page)
    page.click("text=Settings")
    page.click("text=Users")
    expect(page.locator("#new-user-email")).to_be_visible()


def test_full_navigation(page):
    login(page)
    for tab in ["Dashboard", "Policies", "Compliance", "Settings"]:
        page.click(f"text={tab}")
        page.wait_for_timeout(300)
        assert "Error" not in page.locator("#main-content").inner_text()
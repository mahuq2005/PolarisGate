"""PolarisGate Professional Demo Video — Silent with Captions.
Generates a ~60-second silent demo.webm with text overlay captions.
Industry best practice: clean transitions, deliberate pacing, focus on value props."""

import os
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3001"
EMAIL = "admin@polarisgate.ai"
PASSWORD = "PolarisGateDemo2024!"
VIDEO_DIR = os.path.join(os.path.dirname(__file__))
VIDEO_PATH = os.path.join(VIDEO_DIR, "demo_captions.webm")

STEPS = [
    {"wait": 2000, "caption": "PolarisGate — AI Content Safety Gateway", "action": "login"},
    {"wait": 2500, "caption": "Dashboard: 7 summary tiles for real-time monitoring", "action": None},
    {"wait": 1500, "caption": "Incidents: Filterable list (All / Toxic / PII / Blocked)", "action": "click:text=Incidents"},
    {"wait": 2000, "caption": "Click 'Toxic' filter — shows only flagged content", "action": "click:text=Toxic"},
    {"wait": 1200, "caption": "Policies: 13 rules with toggle switches", "action": "click:text=Policies"},
    {"wait": 2000, "caption": "Test Content: Real-time analysis with PII redaction", "action": "click:text=Test Content"},
    {"wait": 1200, "caption": "Paste text, click Analyze — instant results", "action": "test"},
    {"wait": 3000, "caption": "Compliance: Audit logs for every action", "action": "click:text=Compliance"},
    {"wait": 2000, "caption": "Settings: Language selector (EN / FR / AR)", "action": "click:text=Settings"},
    {"wait": 1500, "caption": "Multi-lingual, self-hosted, open-source", "action": None},
    {"wait": 2000, "caption": "Deploy in 2 minutes with Docker Compose", "action": None},
    {"wait": 2000, "caption": "Get started: github.com/mahuq2005/PolarisGate", "action": "end"},
]


def run():
    pw = sync_playwright().start()
    # Delete old video
    if os.path.exists(VIDEO_PATH):
        os.remove(VIDEO_PATH)

    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1280, "height": 800},
    )
    page = context.new_page()

    # Inject caption styles
    page.add_style_tag(content="""
        .demo-caption {
            position: fixed; bottom: 60px; left: 50%; transform: translateX(-50%);
            background: rgba(11, 17, 32, 0.95); color: #E2E8F0;
            padding: 14px 28px; border-radius: 12px; font-size: 18px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            z-index: 9999; text-align: center; max-width: 80%;
            border: 1px solid rgba(79, 142, 247, 0.25);
            box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            animation: fadeIn 0.4s ease;
        }
        .demo-watermark { position: fixed; top: 20px; right: 24px; color: #4F8EF7; font-size: 14px; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif; z-index: 9999; opacity: 0.6; }
        @keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
    """)

    def show_caption(text):
        page.evaluate(f"""
            var el = document.createElement('div');
            el.className = 'demo-caption';
            el.id = 'demo-caption';
            el.textContent = {text!r};
            document.body.appendChild(el);
        """)

    def hide_caption():
        page.evaluate("""
            var el = document.getElementById('demo-caption');
            if (el) el.remove();
        """)

    # Add watermark
    page.evaluate("""
        var wm = document.createElement('div');
        wm.className = 'demo-watermark';
        wm.textContent = 'PolarisGate v2.2';
        document.body.appendChild(wm);
    """)

    for i, step in enumerate(STEPS):
        caption = step["caption"]
        action = step["action"]
        wait_ms = step["wait"]

        # Show caption before action
        show_caption(caption)
        page.wait_for_timeout(800)

        if action == "login":
            page.goto(BASE)
            page.fill('input[aria-label="Email"]', EMAIL)
            page.fill('input[aria-label="Password"]', PASSWORD)
            page.click('button[aria-label="Login"]')
            page.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)
            page.wait_for_timeout(1000)

        elif isinstance(action, str) and action.startswith("click:"):
            raw = action.replace("click:", "")  # "text=Incidents"
            label = raw.replace("text=", "")    # "Incidents"
            # Try sidebar button first, then fallback
            count = page.locator(f".sidebar-btn:has-text('{label}')").count()
            if count > 0:
                page.locator(f".sidebar-btn:has-text('{label}')").click(timeout=5000)
            else:
                page.locator(f"text={label}").first.click(timeout=5000)
            page.wait_for_timeout(1000)

        elif action == "test":
            page.fill("#test-text", "I hate you, you idiot! My email is john@example.com")
            page.wait_for_timeout(500)
            page.click("#test-btn")
            page.wait_for_selector("text=Analysis Results", timeout=10000)

        elif action == "end":
            hide_caption()
            page.evaluate("""
                var el = document.createElement('div');
                el.style = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(11,17,32,0.92);z-index:10000;display:flex;align-items:center;justify-content:center;flex-direction:column';
                el.innerHTML = '<h1 style="color:#4F8EF7;font-size:42px;font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif;margin:0">PolarisGate v2.2</h1><p style="color:#94A3B8;font-size:20px;margin-top:12px">AI Content Safety Gateway</p><p style="color:#E2E8F0;font-size:16px;margin-top:24px">github.com/mahuq2005/PolarisGate</p>';
                document.body.appendChild(el);
            """)
            page.wait_for_timeout(3000)
            break

        # Wait after action for viewer to absorb
        page.wait_for_timeout(wait_ms)
        hide_caption()
        page.wait_for_timeout(300)

    # Close
    page.wait_for_timeout(1000)
    context.close()
    browser.close()
    pw.stop()

    # Rename the video file (Playwright names it with random hash)
    for f in os.listdir(VIDEO_DIR):
        if f.endswith(".webm"):
            src = os.path.join(VIDEO_DIR, f)
            print(f"Video recorded: {src}")
            if os.path.exists(VIDEO_PATH):
                os.remove(VIDEO_PATH)
            os.rename(src, VIDEO_PATH)
            print(f"Renamed to: {VIDEO_PATH}")
            size_mb = os.path.getsize(VIDEO_PATH) / (1024 * 1024)
            print(f"Size: {size_mb:.1f} MB")
            break


if __name__ == "__main__":
    run()
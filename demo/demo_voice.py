"""PolarisGate Professional Demo Video — Voice + Captions.
Generates a ~60-second demo with TTS voice narration AND text captions.
Voice: Web Speech API. Captions: DOM overlay elements."""

import os
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3001"
EMAIL = "admin@polarisgate.ai"
PASSWORD = "PolarisGateDemo2024!"
VIDEO_DIR = os.path.join(os.path.dirname(__file__))
VIDEO_PATH = os.path.join(VIDEO_DIR, "demo_voice.webm")

STEPS = [
    {"wait": 2500, "caption": "PolarisGate — AI Content Safety Gateway", "narration": "PolarisGate is an open-source, self-hosted AI Content Safety Gateway.", "action": "login"},
    {"wait": 3000, "caption": "Dashboard: 7 summary tiles", "narration": "The dashboard shows 7 summary tiles for real-time monitoring.", "action": None},
    {"wait": 2000, "caption": "Incidents: Filterable (All / Toxic / PII / Blocked)", "narration": "Filter incidents by Toxic, PII, or Blocked.", "action": "click:Incidents"},
    {"wait": 2500, "caption": "Toxic filter: Shows only flagged content", "narration": "Clicking Toxic shows only content flagged by the guardrails system.", "action": "click:Toxic"},
    {"wait": 2000, "caption": "Policies: 13 rules with toggle switches", "narration": "Configure 13 safety policies with toggle switches.", "action": "click:Policies"},
    {"wait": 2500, "caption": "Test Content: Real-time analysis + PII redaction", "narration": "Analyze text in real time. PII is automatically redacted.", "action": "test"},
    {"wait": 3500, "caption": "Compliance: Audit logs + Multi-language support", "narration": "Complete audit trail with English, French, and Arabic support.", "action": "click:Compliance"},
    {"wait": 3000, "caption": "Deploy in 2 minutes. Self-hosted. Open source.", "narration": "Deploy in 2 minutes with Docker Compose.", "action": "end"},
]


def run():
    pw = sync_playwright().start()
    os.makedirs(VIDEO_DIR, exist_ok=True)

    # Remove old voice videos only (not captions)
    for f in os.listdir(VIDEO_DIR):
        if f.endswith(".webm") and "voice" in f:
            os.remove(os.path.join(VIDEO_DIR, f))

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
        .demo-watermark { position: fixed; top: 20px; right: 24px; color: #4F8EF7; font-size: 14px; font-family: Arial,sans-serif; z-index: 9999; opacity: 0.6; }
        @keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
    """)

    def show_caption(text):
        page.evaluate(f"""
            var el = document.getElementById('demo-caption');
            if (el) el.remove();
            el = document.createElement('div');
            el.className = 'demo-caption';
            el.id = 'demo-caption';
            el.textContent = {text!r};
            document.body.appendChild(el);
        """)

    def hide_caption():
        page.evaluate("var el = document.getElementById('demo-caption'); if (el) el.remove();")

    def speak(text):
        # Select best available voice (prefer high-quality female voices)
        page.evaluate(f"""
            window.speechSynthesis.cancel();
            var voices = window.speechSynthesis.getVoices();
            var bestVoice = voices.find(v => (
                v.name.includes('Samantha') || v.name.includes('Zira') ||
                v.name.includes('Google') || v.name.includes('Natural') ||
                v.name.includes('Premium')
            )) || voices[0];
            var u = new SpeechSynthesisUtterance({text!r});
            if (bestVoice) u.voice = bestVoice;
            u.rate = 0.9; u.pitch = 1.1; u.volume = 0.85;
            u.lang = 'en-US';
            window.speechSynthesis.speak(u);
        """)
        word_count = len(text.split())
        estimated_ms = int(word_count / 2.5 * 1000)
        page.wait_for_timeout(estimated_ms + 500)

    # Watermark
    page.evaluate("""
        var wm = document.createElement('div');
        wm.className = 'demo-watermark';
        wm.textContent = 'PolarisGate v2.2';
        document.body.appendChild(wm);
    """)

    for i, step in enumerate(STEPS):
        caption = step["caption"]
        narration = step["narration"]
        action = step["action"]
        wait_ms = step["wait"]

        # Show caption
        show_caption(caption)
        page.wait_for_timeout(400)

        # Speak narration
        speak(narration)

        # Perform action
        if action == "login":
            page.goto(BASE)
            page.fill('input[aria-label="Email"]', EMAIL)
            page.fill('input[aria-label="Password"]', PASSWORD)
            page.click('button[aria-label="Login"]')
            page.wait_for_selector("#dashboard-screen:not(.hidden)", timeout=15000)
            page.wait_for_timeout(1000)

        elif isinstance(action, str) and action.startswith("click:"):
            label = action.replace("click:", "")
            count = page.locator(f".sidebar-btn:has-text('{label}')").count()
            if count > 0:
                page.locator(f".sidebar-btn:has-text('{label}')").click(timeout=5000)
            else:
                page.locator(f"text={label}").first.click(timeout=5000)
            page.wait_for_timeout(1500)

        elif action == "test":
            page.click("text=Test Content")
            page.wait_for_timeout(1000)
            page.fill("#test-text", "I hate you, you idiot! My email is john@example.com")
            page.wait_for_timeout(500)
            page.click("#test-btn")
            page.wait_for_selector("text=Analysis Results", timeout=10000)
            page.wait_for_timeout(1500)

        elif action == "end":
            hide_caption()
            page.wait_for_timeout(2000)
            page.evaluate("""
                var el = document.createElement('div');
                el.style = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(11,17,32,0.92);z-index:10000;display:flex;align-items:center;justify-content:center;flex-direction:column';
                el.innerHTML = '<h1 style="color:#4F8EF7;font-size:42px;font-family:Arial,sans-serif;margin:0">PolarisGate v2.2</h1><p style="color:#94A3B8;font-size:20px;margin-top:12px">AI Content Safety Gateway</p>';
                document.body.appendChild(el);
            """)
            page.wait_for_timeout(4000)
            break

        page.wait_for_timeout(wait_ms)
        hide_caption()
        page.wait_for_timeout(200)

    page.wait_for_timeout(2000)
    context.close()
    browser.close()
    pw.stop()

    time.sleep(1)
    for f in os.listdir(VIDEO_DIR):
        if f.endswith(".webm") and not f.startswith("demo_"):
            src = os.path.join(VIDEO_DIR, f)
            if os.path.exists(VIDEO_PATH):
                os.remove(VIDEO_PATH)
            os.rename(src, VIDEO_PATH)
            size_mb = os.path.getsize(VIDEO_PATH) / (1024 * 1024)
            print(f"Voice+captions demo recorded: {VIDEO_PATH} ({size_mb:.1f} MB)")
            break


if __name__ == "__main__":
    run()
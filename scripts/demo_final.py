#!/usr/bin/env python3
"""PolarisGate Demo Video — Clean Build (No Duplicates)"""
import subprocess, time, os, sys, json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "demo"
FR = D / "frames"
AU = D / "audio"
FF = "/opt/homebrew/bin/ffmpeg"

for d in [D, FR, AU]:
    d.mkdir(parents=True, exist_ok=True)

def log(msg):
    print(f"  {msg}")

# Clean old audio and frames
for old in list(AU.glob("*")):
    if old.is_file():
        old.unlink()
for old in list(FR.glob("*")):
    if old.is_file():
        old.unlink()
for old in list(D.glob("*.mp4")) + list(D.glob("*.txt")) + list(D.glob("*.aac")):
    if old.is_file():
        old.unlink()
log("Cleaned old files")

# Step 1: Generate narration (8 UNIQUE files)
print("\n1. Generating narration...")
scenes = [
    ("00", "PolarisGate is an enterprise AI safety gateway. It runs guardrails on every prompt and response, across 11 LLM providers."),
    ("01", "First, I type a clean prompt. The response comes back with a green Safe badge. No issues detected by the guardrails."),
    ("02", "Now I include an email and phone number. The PII detector catches it immediately. The response is flagged."),
    ("03", "Here's a toxic message. The toxicity detector fires. The response gets a Flagged badge too."),
    ("04", "Every chat flows into the Admin Dashboard. PII counts and toxicity flags update live in real-time."),
    ("05", "Security teams can drill into any incident. View the trace ID, verdict, and which detectors fired."),
    ("06", "Admins manage API keys for 11 providers in one place. Mock and Ollama work locally. Cloud providers need a key."),
    ("07", "PolarisGate is open source and self-hosted. Enterprise AI governance without cloud lock-in."),
]
for fn, txt in scenes:
    subprocess.run(["say", "-v", "Samantha", "-r", "170", "-o", str(AU / f"{fn}.aiff"), txt], check=True, capture_output=True)
    log(fn)
log(f"{len(scenes)} narration files created in {AU}")

# Step 2: Seed chat prompts
print("\n2. Seeding chat...")
t = requests.post("http://localhost:8002/auth/token", data={"username":"admin@polarisgate.ai","password":"PolarisGate2024!"}, timeout=10).json()["access_token"]
h = {"Authorization": f"Bearer {t}"}
cid = None
for i, p in enumerate([
    "Write a summary of today's marketing meeting",
    "My email is john@example.com and call me at 416-555-1234",
    "I hate you, you stupid idiot!"
], 1):
    b = {"provider":"ollama","model":"llama3.2:1b"}
    if cid:
        b["conversation_id"] = cid
    b["message"] = p
    r = requests.post("http://localhost:8002/api/v1/chat/completions", json=b, headers=h, timeout=180)
    if r.status_code == 200 and not cid:
        cid = r.json().get("conversation_id")
    log(f"Prompt {i}/3")
log(f"Done: {cid}")

# Step 3: Capture screenshots with Playwright
print("\n3. Capturing screenshots...")
playwright_script = """
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 860 });

  // Chat Portal
  await page.goto('http://localhost:3001/chat.html', { waitUntil: 'networkidle' });
  await page.fill('#login-email', 'admin@polarisgate.ai');
  await page.fill('#login-password', 'PolarisGate2024!');
  await page.click('button:has-text(\"Login\")');
  await new Promise(r => setTimeout(r, 2000));

  try { await page.click('.custom-select-trigger'); await new Promise(r => setTimeout(r, 500)); await page.click('.custom-option:has-text(\"Ollama\")'); } catch(e) {}

  // Prompt 1: Safe
  await page.fill('#chat-input', 'Write a summary of today\\'s marketing meeting');
  await page.click('#send-btn'); await new Promise(r => setTimeout(r, 10000));
  await page.screenshot({ path: path.resolve('""" + str(FR) + """', '01_safe.png') });
  process.stdout.write('  Safe captured\\n');

  // Prompt 2: PII
  await page.fill('#chat-input', 'My email is john@example.com, call me at 416-555-1234');
  await page.click('#send-btn'); await new Promise(r => setTimeout(r, 10000));
  await page.screenshot({ path: path.resolve('""" + str(FR) + """', '02_pii.png') });
  process.stdout.write('  PII captured\\n');

  // Prompt 3: Toxic
  await page.fill('#chat-input', 'I hate you, you stupid idiot!');
  await page.click('#send-btn'); await new Promise(r => setTimeout(r, 10000));
  await page.screenshot({ path: path.resolve('""" + str(FR) + """', '03_toxic.png') });
  process.stdout.write('  Toxic captured\\n');
  await page.close();

  // Admin Portal
  const ap = await browser.newPage();
  await ap.setViewportSize({ width: 1440, height: 860 });
  await ap.goto('http://localhost:3001/', { waitUntil: 'networkidle' });
  await ap.fill('#login-email', 'admin@polarisgate.ai');
  await ap.fill('#login-password', 'PolarisGate2024!');
  await ap.click('button:has-text(\"Login\")');
  await new Promise(r => setTimeout(r, 3000));
  await ap.screenshot({ path: path.resolve('""" + str(FR) + """', '04_dashboard.png') });
  process.stdout.write('  Dashboard captured\\n');

  try {
    await ap.click('.sidebar-btn:has-text(\"Incidents\")');
    await new Promise(r => setTimeout(r, 2000));
    const rows = await ap.$$('.incident-row');
    if (rows.length > 0) {
      await rows[0].click();
      await new Promise(r => setTimeout(r, 1000));
      await ap.screenshot({ path: path.resolve('""" + str(FR) + """', '05_drilldown.png') });
      process.stdout.write('  Drill-down captured\\n');
    }
  } catch(e) {}

  try {
    await ap.click('.tab:has-text(\"Settings\")');
    await new Promise(r => setTimeout(r, 500));
    await ap.click('.sidebar-btn:has-text(\"LLM Providers\")');
    await new Promise(r => setTimeout(r, 2000));
    await ap.screenshot({ path: path.resolve('""" + str(FR) + """', '06_providers.png') });
    process.stdout.write('  Providers captured\\n');
  } catch(e) {}

  await ap.close(); await browser.close();
  process.stdout.write('  Done\\n');
})();
"""
js_path = ROOT / "scripts" / "_demo_capture.js"
js_path.write_text(playwright_script)
subprocess.run(["node", str(js_path)], check=True)
js_path.unlink()
log(f"Captured {len(list(FR.glob('*.png')))} frames")

# Step 4: Create title cards
print("\n4. Title cards...")
from PIL import Image, ImageDraw
for name, txt in [("00_title", "PolarisGate"), ("99_outro", "Enterprise AI Governance")]:
    img = Image.new("RGB", (1920, 1080), (11, 17, 32))
    d = ImageDraw.Draw(img)
    d.text((960, 540), txt, fill=(79, 142, 247), anchor="mm")
    img.save(str(FR / f"{name}.png"))
log("Created")

# Step 5: Merge audio (ONLY 8 files, no duplicates)
print("\n5. Merging audio...")
audio_files = sorted(AU.glob("*.aiff"))
print(f"  Audio files found: {len(audio_files)} (should be 8)")
for f in audio_files:
    print(f"    {f.name}")
(AU / "list.txt").write_text("\n".join(f"file '{f.absolute()}'" for f in audio_files))
at = D / "narration.aac"
subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(AU / "list.txt"), "-c:a", "aac", "-b:a", "192k", str(at)], check=True, capture_output=True)
log("Merged")

# Step 6: Build final video
print("\n6. Building video...")
frames = sorted(FR.glob("*.png"))
print(f"  Frames: {len(frames)}")
fl = D / "flist.txt"
lines = []
for f in frames:
    lines.append(f"file '{f.absolute()}'")
    lines.append("duration 5")
lines.append(f"file '{frames[-1].absolute()}'")
fl.write_text("\n".join(lines))
dur = len(frames) * 5
out = D / "demo_polarisgate.mp4"
subprocess.run([
    FF, "-y", "-f", "concat", "-safe", "0", "-i", str(fl),
    "-i", str(at),
    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=1/5",
    "-t", str(dur), "-shortest",
    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-c:a", "aac", "-b:a", "192k",
    str(out)
], check=True, capture_output=True)
mb = out.stat().st_size / 1048576
print(f"\n✅ DONE: {out} ({mb:.1f}MB, {dur}s)")
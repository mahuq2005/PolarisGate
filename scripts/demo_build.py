#!/usr/bin/env python3
"""PolarisGate Demo Video - Build Script"""
import subprocess, time, os, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "demo"
FR = D / "frames"
AU = D / "audio"
FF = "/opt/homebrew/bin/ffmpeg"
for d in [D, FR, AU]: d.mkdir(parents=True, exist_ok=True)

def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)

def log(msg):
    print(f"  {msg}")

# 1. Seed chat
print("1. Seeding chat...")
t = requests.post("http://localhost:8002/auth/token", data={"username":"admin@polarisgate.ai","password":"PolarisGate2024!"}, timeout=10).json()["access_token"]
h = {"Authorization":f"Bearer {t}"}
cid = None
for i,p in enumerate([
    "Write a summary of today's marketing meeting",
    "My email is john@example.com and call me at 416-555-1234",
    "I hate you, you stupid idiot!"
],1):
    b = {"provider":"ollama","model":"llama3.2:1b"}
    if cid: b["conversation_id"] = cid
    b["message"] = p
    r = requests.post("http://localhost:8002/api/v1/chat/completions", json=b, headers=h, timeout=180)
    if r.status_code == 200 and not cid: cid = r.json().get("conversation_id")
    log(f"Prompt {i}/3")
log(f"Done: {cid}")

# 2. Narration
print("2. Narration...")
scenes = [
    ("00","PolarisGate is an enterprise AI safety gateway. It runs guardrails on every prompt and response across 11 LLM providers."),
    ("01","First I type a clean prompt. The response comes back with a green Safe badge. No issues detected."),
    ("02","Now I include an email and phone number. The PII detector catches it immediately. The response is flagged."),
    ("03","Here is a toxic message. The toxicity detector fires. The response is flagged."),
    ("04","Every chat flows into the Admin Dashboard. PII counts and toxicity flags update live."),
    ("05","Security teams drill into incidents. Trace ID, verdict, scores, and detectors fired."),
    ("06","Admins manage 11 providers. Mock and Ollama work locally. Cloud providers need a key."),
    ("07","PolarisGate is open source and self-hosted. Enterprise AI governance without cloud lock-in."),
]
for fn, txt in scenes:
    run(["say","-v","Samantha","-r","170","-o",str(AU/f"{fn}.aiff"),txt])
log(f"{len(scenes)} files")

# 3. Screenshots
print("3. Screenshots...")
subprocess.run(["open","-a","Google Chrome","http://localhost:3001/chat.html"])
time.sleep(4)
subprocess.run(["screencapture","-x","-R","0,40,1440,860",str(FR/"chat.png")])
subprocess.run(["open","-a","Google Chrome","http://localhost:3001/"])
time.sleep(4)
subprocess.run(["screencapture","-x","-R","0,40,1440,860",str(FR/"admin.png")])
log("Captured")

# 4. Title cards with Pillow
print("4. Title cards...")
from PIL import Image, ImageDraw
for name, txt in [("t0","PolarisGate"),("t9","Enterprise AI Governance")]:
    img = Image.new("RGB",(1920,1080),(11,17,32))
    d = ImageDraw.Draw(img)
    d.text((960,540),txt,fill=(79,142,247),anchor="mm")
    img.save(str(FR/f"{name}.png"))
log("Created")

# 5. Merge audio
print("5. Merging audio...")
fns = sorted(AU.glob("*.aiff"))
(AU/"list.txt").write_text("\n".join(f"file '{f.absolute()}'" for f in fns))
at = D / "narration.aac"
subprocess.run([FF,"-y","-f","concat","-safe","0","-i",str(AU/"list.txt"),"-c:a","aac","-b:a","192k",str(at)],check=True,capture_output=True)
log("Merged")

# 6. Build video
print("6. Building video...")
frames = sorted(FR.glob("*.png"))
fl = D / "flist.txt"
lines = []
for f in frames:
    lines.append(f"file '{f.absolute()}'")
    lines.append("duration 5")
lines.append(f"file '{frames[-1].absolute()}'")
fl.write_text("\n".join(lines))
dur = len(frames) * 5
out = D / "demo_polarisgate.mp4"
subprocess.run([FF,"-y","-f","concat","-safe","0","-i",str(fl),"-i",str(at),"-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=1/5","-t",str(dur),"-shortest","-pix_fmt","yuv420p","-c:v","libx264","-preset","fast","-crf","23","-c:a","aac","-b:a","192k",str(out)],check=True,capture_output=True)
mb = out.stat().st_size / 1048576
print(f"\nDone: {out} ({mb:.1f}MB, {dur}s)")
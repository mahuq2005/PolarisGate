#!/usr/bin/env python3
"""PolarisGate Demo Video Generator.

Creates narration audio via macOS `say` and pre-seeds chat prompts.
You then record the screen with QuickTime Player (Cmd+Shift+5).

Usage:
    python3 scripts/demo_record.py seed    # Pre-seed chat prompts
    python3 scripts/demo_record.py audio    # Generate narration
    python3 scripts/demo_record.py all      # Do both
"""

import subprocess
import time
import os
import json
import requests

GATEWAY = "http://localhost:8002"
CHAT_PORTAL = "http://localhost:3001/chat.html"
ADMIN_PORTAL = "http://localhost:3001/"
AUTH = {"username": "admin@polarisgate.ai", "password": "PolarisGate2024!"}

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "demo", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


def get_token() -> str:
    """Authenticate and return JWT token."""
    resp = requests.post(
        f"{GATEWAY}/auth/token", data=AUTH, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def seed_chat_prompts(token: str):
    """Send demo prompts to Ollama to populate chat history."""
    prompts = [
        ("Write a summary of today's marketing meeting", "safe"),
        ("My email is john@example.com and call me at 416-555-1234", "flagged"),
        ("I hate you, you stupid idiot!", "flagged"),
    ]

    print("Seeding chat prompts via Ollama...")
    headers = {"Authorization": f"Bearer {token}"}
    conv_id = None

    for i, (prompt, expected) in enumerate(prompts, 1):
        body = {"provider": "ollama", "model": "llama3.2:1b"}
        if conv_id:
            body["conversation_id"] = conv_id
        body["message"] = prompt

        print(f"  [{i}/{len(prompts)}] {prompt[:50]}...")
        resp = requests.post(
            f"{GATEWAY}/api/v1/chat/completions",
            json=body, headers=headers, timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            if not conv_id:
                conv_id = data.get("conversation_id")
            safety = data.get("safety", {})
            inp = safety.get("input", {})
            out = safety.get("output", {})
            flagged = inp.get("toxic") or inp.get("pii_detected") or \
                      out.get("toxic") or out.get("pii_detected")
            status = "🟡 FLAGGED" if flagged else "✅ Safe"
            print(f"    → {status}")
        else:
            print(f"    → Error: {resp.status_code}")

    print(f"\n✅ Chat seeded in conversation: {conv_id}")
    print(f"Open {CHAT_PORTAL} to see the chat history.")
    return conv_id


def generate_audio():
    """Generate natural-sounding narration audio via macOS `say`."""
    # Use Samantha voice — natural female voice
    voice = "Samantha"
    rate = 175  # words per minute (default is ~180)

    scenes = [
        ("00_intro", "PolarisGate is an enterprise AI safety gateway. It runs guardrails on every prompt and response across 11 LLM providers. Let me show you how it works."),
        ("01_safe", "I'll start by typing a clean prompt. The response comes back with a green Safe badge — no issues detected."),
        ("02_pii", "Now I'll type a message containing personal information — an email address and a phone number. The PII detector catches it immediately. The response is flagged."),
        ("03_toxic", "Here's a message with toxic language. The toxicity detector fires. The response gets a Flagged badge too."),
        ("04_dashboard", "Every chat interaction flows into the Admin Dashboard in real-time. Here you can see the P-I-I leak count and toxicity flags updating live."),
        ("05_drilldown", "Security teams can drill into any incident — view the trace ID, verdict, confidence scores, and which detectors fired. The redacted text is shown too."),
        ("06_providers", "Admins manage API keys for all 11 providers in one place. Mock and Ollama work locally with zero configuration. Cloud providers need a key — which end users never see."),
        ("07_outro", "PolarisGate is open-source and self-hosted. Enterprise AI governance without cloud lock-in. Visit the GitHub repository to get started."),
    ]

    print("Generating narration audio...")
    for filename, text in scenes:
        path = os.path.join(AUDIO_DIR, f"{filename}.aiff")
        print(f"  {filename}...")
        subprocess.run(
            ["say", "-v", voice, "-r", str(rate), "-o", path, text],
            check=True, capture_output=True,
        )
    print(f"\n✅ {len(scenes)} audio files generated in {AUDIO_DIR}/")


def print_recording_guide():
    """Print step-by-step recording instructions."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     PolarisGate Demo Video — Recording Guide                ║
╚══════════════════════════════════════════════════════════════╝

Before recording:
  1. Open Chrome at http://localhost:3001/chat.html
  2. Login with admin@polarisgate.ai / PolarisGate2024!
  3. Click "New Chat" to start fresh
  4. Open a second tab at http://localhost:3001/ (Admin Portal)

Start recording with QuickTime:
  • Cmd+Shift+5 → Record Selected Portion
  • Select the browser window area

Scene-by-scene walkthrough:
┌───────┬──────────────────────────────────────────────────────┐
│ Scene │ Action                                              │
├───────┼──────────────────────────────────────────────────────┤
│ Intro │ Show PolarisGate logo, welcome screen               │
│       │ Audio: 00_intro.aiff                                │
├───────┼──────────────────────────────────────────────────────┤
│ Safe  │ Click suggestion "Write a meeting email"            │
│       │ Wait for response → point to ✅ Safe badge          │
│       │ Audio: 01_safe.aiff                                 │
├───────┼──────────────────────────────────────────────────────┤
│ PII   │ Type: "My email is john@example.com,                 │
│       │        call me at 416-555-1234"                     │
│       │ Wait → point to 🟡 FLAGGED badge                    │
│       │ Audio: 02_pii.aiff                                  │
├───────┼──────────────────────────────────────────────────────┤
│ Toxic │ Type: "I hate you, you stupid idiot!"               │
│       │ Wait → point to 🟡 FLAGGED badge                    │
│       │ Audio: 03_toxic.aiff                                │
├───────┼──────────────────────────────────────────────────────┤
│ Dash  │ Switch to Admin Portal tab (3001)                   │
│       │ Show Dashboard → point to counts                    │
│       │ Audio: 04_dashboard.aiff                            │
├───────┼──────────────────────────────────────────────────────┤
│ Drill │ Click Incidents tab → click an incident row         │
│       │ Show detail panel with scores                       │
│       │ Audio: 05_drilldown.aiff                            │
├───────┼──────────────────────────────────────────────────────┤
│ Prov  │ Settings → LLM Providers                            │
│       │ Scroll through 11 providers                         │
│       │ Audio: 06_providers.aiff                            │
├───────┼──────────────────────────────────────────────────────┤
│ Close │ Show PolarisGate logo + tagline                     │
│       │ Audio: 07_outro.aiff                                │
└───────┴──────────────────────────────────────────────────────┘

Stop QuickTime recording (Cmd+Ctrl+Esc or menu bar).

To assemble the final video, import the screen recording and
audio files into iMovie (free on macOS):
  1. Open iMovie → Create New → Movie
  2. Import screen recording
  3. Import audio files from demo/audio/
  4. Align each audio clip with the corresponding scene
  5. File → Share → File → 1080p

Or use ffmpeg (if installed):
  brew install ffmpeg
  ffmpeg -i screen_recording.mov -i demo/audio/combined.aiff \
         -c:v libx264 -preset fast -crf 22 \
         -c:a aac -b:a 192k demo_polarisgate.mp4
""")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "guide"

    if cmd == "seed":
        token = get_token()
        seed_chat_prompts(token)
    elif cmd == "audio":
        generate_audio()
    elif cmd == "all":
        token = get_token()
        seed_chat_prompts(token)
        generate_audio()
    else:
        generate_audio()
        print_recording_guide()
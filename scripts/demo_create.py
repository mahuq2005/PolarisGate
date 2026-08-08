#!/usr/bin/env python3
"""PolarisGate Demo Video — Fully Automated Production.

Creates a professional 1080p demo video:
1. Opens browsers and pre-seeds chat prompts
2. Takes screenshots at key moments
3. Generates natural-sounding narration via macOS `say`
4. Stitches screenshots + narration into a polished video

Requires: ffmpeg, macOS

Usage:
    python3 scripts/demo_create.py

Output: demo/demo_polarisgate.mp4
"""

import subprocess
import time
import os
import sys
import json
import requests
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT / "demo"
FRAMES_DIR = DEMO_DIR / "frames"
AUDIO_DIR = DEMO_DIR / "audio"

GATEWAY = "http://localhost:8002"
AUTH = {"username": "admin@polarisgate.ai", "password": "PolarisGate2024!"}
BREW_PREFIX = "/opt/homebrew/bin"

# Screen capture area (adjust for your display — 1440x900 default for 13" MacBook)
CAPTURE_X = 0
CAPTURE_Y = 40       # Below menu bar
CAPTURE_W = 1440
CAPTURE_H = 860

VIDEO_W = 1920
VIDEO_H = 1080

FADE_DURATION = 0.5   # seconds


def log(msg: str):
    print(f"  {msg}")


def run(cmd: list[str], **kwargs):
    """Run a shell command, raising on failure."""
    subprocess.run(cmd, check=True, **kwargs)


def get_token() -> str:
    resp = requests.post(f"{GATEWAY}/auth/token", data=AUTH, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── Step 1: Pre-seed chat prompts ────────────────────────────────────

def seed_chat(token: str) -> str:
    """Send demo prompts to Ollama, return conversation_id."""
    prompts = [
        "Write a summary of today's marketing meeting",
        "My email is john@example.com and call me at 416-555-1234",
        "I hate you, you stupid idiot!",
    ]
    headers = {"Authorization": f"Bearer {token}"}
    conv_id = None

    log("Seeding chat prompts via Ollama...")
    for i, prompt in enumerate(prompts, 1):
        body = {"provider": "ollama", "model": "llama3.2:1b"}
        if conv_id:
            body["conversation_id"] = conv_id
        body["message"] = prompt

        log(f"  Prompt {i}/3...")
        resp = requests.post(
            f"{GATEWAY}/api/v1/chat/completions",
            json=body, headers=headers, timeout=180,
        )
        if resp.status_code == 200:
            data = resp.json()
            if not conv_id:
                conv_id = data.get("conversation_id")
        else:
            log(f"  Warning: prompt {i} returned {resp.status_code}")

    log(f"  Conversation: {conv_id}")
    return conv_id


# ── Step 2: Generate narration audio ─────────────────────────────────

def generate_narration():
    """Create natural-sounding narration with macOS Samantha voice."""
    voice = "Samantha"
    rate = 170  # slightly slower = clearer

    # Narration script (8 scenes, ~20–25 seconds each)
    scenes: list[tuple[str, str]] = [
        ("01_intro",
         "PolarisGate is an enterprise AI safety gateway. "
         "It runs guardrails on every prompt and response, across 11 LLM providers. "
         "Let me show you how it works."),
        ("02_safe",
         "First, I'll type a clean, safe prompt. "
         "The response comes back from the LLM with a green safe badge — "
         "no issues detected by the guardrails."),
        ("03_pii",
         "Now watch what happens when I include personal information — "
         "an email address and a phone number. "
         "The PII detector catches it immediately and the response is flagged."),
        ("04_toxic",
         "Here's a message with toxic language. The toxicity detector fires. "
         "The response gets a flagged badge too."),
        ("05_dashboard",
         "Every chat interaction flows into the Admin Dashboard in real-time. "
         "P-I-I leak counts and toxicity flags update live as users interact with the system."),
        ("06_drilldown",
         "Security teams can drill into any incident — view the trace ID, "
         "verdict, confidence scores, and exactly which detectors fired. "
         "Redacted text is shown for PII events."),
        ("07_providers",
         "Admins manage API keys for all 11 providers in one place. "
         "Mock and Ollama work locally with zero configuration. "
         "Cloud providers need a key — which end users never see."),
        ("08_outro",
         "PolarisGate is open source and self-hosted. "
         "Enterprise AI governance without cloud lock-in. "
         "Visit the GitHub repository to get started."),
    ]

    log("Generating narration audio...")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for filename, text in scenes:
        path = AUDIO_DIR / f"{filename}.aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", str(path), text],
            capture_output=True)
    log(f"  Generated {len(scenes)} audio files")


# ── Step 3: Capture screenshots ──────────────────────────────────────

def capture_frame(name: str, delay: float = 2.0):
    """Capture a screenshot after waiting for the page to render."""
    time.sleep(delay)
    path = FRAMES_DIR / f"{name}.png"
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    run([
        "screencapture", "-x",  # no sound
        "-R", f"{CAPTURE_X},{CAPTURE_Y},{CAPTURE_W},{CAPTURE_H}",
        str(path),
    ])
    return path


def capture_scenes():
    """Open browser tabs and capture each scene."""
    log("Opening browser tabs...")
    # Open Chat Portal and Admin Portal in Chrome
    run(["open", "-a", "Google Chrome", "http://localhost:3001/chat.html"])
    time.sleep(3)

    # Navigate to admin portal
    run(["open", "-a", "Google Chrome", "http://localhost:3001/"])
    time.sleep(2)

    log("Capturing scenes (please don't move the mouse)...")
    log("  Ensure Chrome is the frontmost app for best results.")

    scenes = [
        # (window to capture, filename, description)
        ("chat", "01_welcome", "Welcome screen"),
        ("chat", "02_safe_response", "Safe prompt with badge"),
        ("chat", "03_pii_flagged", "PII flagged"),
        ("chat", "04_toxic_flagged", "Toxicity flagged"),
        ("admin", "05_dashboard", "Dashboard summary"),
        ("admin", "06_incident_detail", "Incident drill-down"),
        ("admin", "07_llm_providers", "LLM Providers panel"),
    ]

    for i, (window, filename, desc) in enumerate(scenes):
        log(f"  Scene {i+1}/7: {desc}")
        # Activate Chrome
        run(["open", "-a", "Google Chrome"])
        time.sleep(0.5)
        # Switch to appropriate tab
        if window == "chat":
            run(["open", "http://localhost:3001/chat.html"])
        else:
            run(["open", "http://localhost:3001/"])
        time.sleep(1.5)
        capture_frame(filename)

    log("  Screenshots captured")


# ── Step 4: Create title cards ───────────────────────────────────────

def create_title_cards():
    """Intro/outro frames — captured from browser for simplicity."""
    log("Skipping title cards — using captured welcome screen as intro")
    # Title cards are nice-to-have; browser screenshots work fine


# ── Step 5: Assemble video ───────────────────────────────────────────

def concatenate_audio(scene_count: int, output_path: Path):
    """Merge narration files into one audio track with silence padding."""
    # Build concat list
    concat_file = AUDIO_DIR / "concat.txt"
    lines = []
    for i in range(scene_count):
        audio_path = AUDIO_DIR / f"{i+1:02d}_*.aiff"
        # Find matching file
        matches = sorted(AUDIO_DIR.glob(f"{i+1:02d}_*.aiff"))
        for m in matches:
            # Get audio duration
            result = subprocess.run(
                [f"{BREW_PREFIX}/ffprobe", "-v", "error",
                 "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1",
                 str(m)],
                capture_output=True, text=True,
            )
            duration = float(result.stdout.strip())
            lines.append(f"file '{m.absolute()}'")
            lines.append(f"duration {duration}")

    concat_file.write_text("\n".join(lines))

    # Also create a text list for concat demuxer
    list_file = AUDIO_DIR / "audio_list.txt"
    list_lines = []
    for i in range(scene_count):
        matches = sorted(AUDIO_DIR.glob(f"{i+1:02d}_*.aiff"))
        for m in matches:
            list_lines.append(f"file '{m.absolute()}'")
    list_file.write_text("\n".join(list_lines))

    # Concatenate audio
    run([
        f"{BREW_PREFIX}/ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ], capture_output=True)
    return output_path


def create_video():
    """Assemble the final demo video from frames + narration."""
    log("Assembling final video...")

    ffmpeg = f"{BREW_PREFIX}/ffmpeg"

    # Gather all frames
    frames = sorted(FRAMES_DIR.glob("*.png"))
    if not frames:
        log("ERROR: No frames found. Run capture step first.")
        sys.exit(1)

    # Create a frame list file for ffmpeg concat
    frame_list = DEMO_DIR / "frames.txt"
    lines = []
    for f in frames:
        lines.append(f"file '{f.absolute()}'")
        lines.append("duration 5")  # 5 seconds per frame (adjustable)
    # Last frame needs duration too
    lines.append(f"file '{frames[-1].absolute()}'")
    frame_list.write_text("\n".join(lines))

    # Merge narration audio
    audio_track = DEMO_DIR / "narration.aac"
    # Collect all audio files in order
    audio_files = sorted(AUDIO_DIR.glob("*.aiff"))
    if audio_files:
        list_file = AUDIO_DIR / "audio_list.txt"
        list_file.write_text("\n".join(
            f"file '{f.absolute()}'" for f in audio_files
        ))
        run([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:a", "aac", "-b:a", "192k",
            str(audio_track),
        ], capture_output=True)

    # Build the video
    output = DEMO_DIR / "demo_polarisgate.mp4"

    # Simple approach: slideshow from frames with audio overlay
    # Use zoompan for Ken Burns effect
    filter_complex = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,"
        f"fps=1/5"  # 1 frame every 5 seconds = 5s per slide
    )

    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(frame_list),
        "-vf", filter_complex,
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    ]

    if audio_files:
        # Get total duration from frames
        total_duration = len(frames) * 5
        cmd += [
            "-i", str(audio_track),
            "-t", str(total_duration),
            "-shortest",
            "-c:a", "aac", "-b:a", "192k",
        ]

    cmd.append(str(output))
    run(cmd, capture_output=True)

    size_mb = output.stat().st_size / (1024 * 1024)
    log(f"\n✅ Demo video created: {output} ({size_mb:.1f} MB)")
    return output


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  PolarisGate Demo Video — Auto Production   ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # Step 1: Seed chat data
    token = get_token()
    conv_id = seed_chat(token)
    print()

    # Step 2: Generate narration
    generate_narration()
    print()

    # Step 3: Create title cards
    create_title_cards()
    print()

    # Step 4: Capture screenshots (requires browser open)
    print("─" * 50)
    print("IMPORTANT: Please open Chrome and navigate to:")
    print("  Tab 1: http://localhost:3001/chat.html")
    print("  Tab 2: http://localhost:3001/")
    print("  Log in with admin@polarisgate.ai / PolarisGate2024!")
    print()
    input("Press Enter when both tabs are open and you're logged in... ")

    capture_scenes()
    print()

    # Step 5: Assemble video
    output = create_video()
    print(f"\n🎉 Done! Open {output}")


if __name__ == "__main__":
    main()
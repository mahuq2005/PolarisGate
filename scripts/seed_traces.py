"""Seed demo traces for dashboard data."""
import requests, time, re, subprocess, os

BASE = "http://localhost:8002"
r = requests.post(f"{BASE}/auth/token", data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

traces = [
    ("What is the capital of France?", "The capital of France is Paris.", "gpt-4", False, False, []),
    ("Tell me about machine learning", "Machine learning is a subset of AI.", "claude-3", False, False, []),
    ("What is 2+2?", "2+2 equals 4.", "gpt-4", False, False, []),
    ("I hate you, you stupid idiot!", "I understand.", "gpt-4", True, False, []),
    ("You are a worthless piece of trash", "Message blocked.", "claude-3", True, False, []),
    ("Kill them all, destroy everything", "Blocked: threat.", "llama-3", True, False, []),
    ("I will attack you, die!", "Blocked: violence.", "gpt-4", True, False, []),
    ("My email is john@example.com", "Email masked.", "claude-3", False, True, ["EMAIL"]),
    ("Call me at 613-555-1234", "Phone masked.", "llama-3", False, True, ["PHONE"]),
    ("SIN is 123-456-789", "SIN masked.", "gpt-4", False, True, ["SIN"]),
]

for prompt, completion, model, is_toxic, has_pii, pii_types in traces:
    r = requests.post(f"{BASE}/api/v1/traces", json={
        "prompt": prompt, "completion": completion, "model_id": model, "user_id": "demo-user"
    }, headers=h)
    if r.status_code == 200:
        tid = r.json()["trace_id"]
        score = 0.85 if is_toxic else 0.05
        reason = "Keyword match" if is_toxic else "NULL"
        pii_str = ",".join(pii_types) if pii_types else "NULL"
        sql = f"UPDATE guardrail_results SET toxic={'TRUE' if is_toxic else 'FALSE'}, toxic_score={score}, reason={reason}, pii_detected={'TRUE' if has_pii else 'FALSE'}, pii_types={pii_str} WHERE trace_id={tid}"
        subprocess.run(["docker", "exec", "polarisgate-postgres-1", "psql", "-U", "polarisgate", "-d", "polarisgate", "-c", sql], capture_output=True)
    time.sleep(0.05)

print(f"Seeded {len(traces)} traces (4 toxic, 3 PII, 3 clean)")
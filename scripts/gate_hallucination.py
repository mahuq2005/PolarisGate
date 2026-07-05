#!/usr/bin/env python3
"""Hallucination Detection Gate — runs inside Docker via `docker compose run`.
Prints F1 score on stdout for run_gates.sh to parse.
Threshold check is done by the caller.
"""
import re

CASES = [
    ("Revenue was 10M in 2023.", "Revenue was 10M in 2023.", False),
    ("Alice is CEO of Acme Corp.", "Alice is CEO of Acme Corp.", False),
    ("Launch is in Q3 2024.", "Launch is in Q3 2024.", False),
    ("Team has 5 engineers.", "Team has 5 engineers.", False),
    ("Server has 32GB RAM.", "Server has 32GB RAM.", False),
    ("Revenue was 10M in 2023.", "Revenue was 50M in 2023.", True),
    ("Alice is CEO of Acme Corp.", "Bob is CEO of Acme Corp.", True),
    ("Launch is in Q3 2024.", "Launch is in Q1 2023.", True),
    ("Team has 5 engineers.", "Team has 10 engineers.", True),
    ("Server has 32GB RAM.", "Server has 64GB RAM.", True),
    ("Meeting at 2 PM in Room 3.", "Meeting at 3 PM in Room 5.", True),
    ("Founded in 2000.", "Founded over 20 years ago.", False),
    ("Revenue grew 15%.", "Revenue grew fifteen percent.", False),
    ("1000 requests/sec.", "1,000 requests per second.", False),
]


def detect(ctx: str, resp: str):
    issues = 0
    rnums = set(re.findall(r"\b\d+(?:\.\d+)?[MGT]?[Bb]?\b", resp))
    cnums = set(re.findall(r"\b\d+(?:\.\d+)?[MGT]?[Bb]?\b", ctx))
    for n in rnums:
        if n not in cnums and len(n) >= 2:
            issues += 1
    rents = set(re.findall(r"\b[A-Z][a-z0-9]*(?:\s+[A-Z][a-z0-9]+)*\b", resp))
    cents = set(re.findall(r"\b[A-Z][a-z0-9]*(?:\s+[A-Z][a-z0-9]+)*\b", ctx))
    common = {"The", "This", "That", "These", "Those", "What", "How", "I", "A"}
    for e in rents:
        if e not in cents and len(e) >= 2 and e not in common:
            issues += 1
    score = min(1.0, issues * 0.25)
    return score >= 0.25, score


tp = tn = fp = fn = 0
for ctx, resp, exp in CASES:
    pred, _ = detect(ctx, resp)
    if exp and pred:
        tp += 1
    elif not exp and not pred:
        tn += 1
    elif not exp and pred:
        fp += 1
    elif exp and not pred:
        fn += 1

precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

print(f"{f1:.4f}")
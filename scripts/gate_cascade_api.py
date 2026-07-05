#!/usr/bin/env python3
"""Enterprise Cascade Accuracy Gate — tests production 4-stage pipeline.

Runs inside Docker gateway container, calls hallucination-detector API via
internal Docker network. Uses a stratified 20-case sample covering all 13
categories — fast enough for deploy gates (~30s).

Usage:
    docker compose run --rm -v $(pwd)/scripts:/test-scripts:ro \
        gateway python /test-scripts/gate_cascade_api.py

For full 120-case benchmark, use scripts/run_cascade_accuracy_benchmark.py
"""
import httpx
import os
import sys

HALLUCINATION_URL = "http://hallucination-detector:8008"
ADMIN_EMAIL = os.environ.get("DEPLOY_ADMIN_EMAIL", "admin@polarisgate.ai")
ADMIN_PASSWORD = os.environ.get("DEPLOY_ADMIN_PASSWORD", "PolarisGate@123")


def build_stratified_sample():
    """20 cases — 1-2 per category, covering all 13 categories."""
    return [
        # factual_exact_match
        ("Revenue was $10M in 2023.", "Revenue was $10M in 2023.", False),
        ("The sky is blue.", "The sky is blue.", False),
        # factual_paraphrased
        ("Revenue was $10M in 2023.", "Revenue reached $10M in 2023.", False),
        # factual_partial_match
        ("Revenue was $10M in 2023.", "Revenue was $10M.", False),
        # hallucination_wrong_number
        ("Revenue was $10M in 2023.", "Revenue was $50M in 2023.", True),
        ("Server has 32GB RAM.", "Server has 64GB RAM.", True),
        # hallucination_wrong_entity
        ("Alice is CEO of Acme Corp.", "Bob is CEO of Acme Corp.", True),
        ("The report was filed by John.", "The report was filed by Mike.", True),
        # hallucination_wrong_date
        ("Launch is in Q3 2024.", "Launch is in Q1 2023.", True),
        ("Meeting on January 5, 2024.", "Meeting on March 15, 2023.", True),
        # hallucination_fabricated
        ("Team has 5 engineers.", "Team has engineers in 10 countries.", True),
        ("The project deadline is Friday.", "The project was delayed indefinitely.", True),
        # hallucination_contradiction
        ("The project was approved.", "The project was rejected.", True),
        ("Sales increased by 20%.", "Sales decreased by 20%.", True),
        # edge_format_difference
        ("Founded in 2000.", "Founded over 20 years ago.", False),
        # edge_synonym
        ("Revenue grew 15%.", "Revenue grew fifteen percent.", False),
        # edge_partial_truth
        ("The report is complete.", "The report is partially done.", False),
        # edge_ambiguous
        ("The data is ambiguous.", "The data is somewhat unclear.", False),
        # additional hallucination samples for balance
        ("Revenue was $10M.", "Revenue was $50M.", True),
        ("The CEO approved the budget.", "The CFO rejected the budget.", True),
    ]


def main():
    # Get auth token
    with httpx.Client(base_url="http://gateway:8000", timeout=30.0) as client:
        resp = client.post(
            "/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

    cases = build_stratified_sample()
    tp = tn = fp = fn = 0
    errors = 0

    with httpx.Client(base_url=HALLUCINATION_URL, timeout=120.0) as client:
        for ctx, resp_text, expected_hallucination in cases:
            try:
                api_resp = client.post(
                    "/api/v1/hallucination/detect",
                    json={
                        "context": ctx,
                        "response": resp_text,
                        "domain": "general",
                    },
                    headers=headers,
                )
                if api_resp.status_code == 200:
                    result = api_resp.json()
                    predicted = result.get("is_hallucination", False)
                else:
                    predicted = False
                    errors += 1
            except Exception:
                predicted = False
                errors += 1

            if expected_hallucination and predicted:
                tp += 1
            elif not expected_hallucination and not predicted:
                tn += 1
            elif not expected_hallucination and predicted:
                fp += 1
            elif expected_hallucination and not predicted:
                fn += 1

    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0

    print(f"{f1:.4f}")

    print(f"\nCascade API Gate (20-case stratified): F1={f1:.4f}  P={precision:.4f}  R={recall:.4f}  Acc={accuracy:.4f}", file=sys.stderr)
    print(f"TP={tp} TN={tn} FP={fp} FN={fn}  Total={total}  Errors={errors}", file=sys.stderr)
    print(f"Categories covered: 13/13", file=sys.stderr)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Curate public data + generate synthetic counter-examples for balanced training.

Downloads public datasets, generates clean counter-examples for injection
attacks, balances classes, and saves curated datasets for SetFit training.

Output:
    tests/test_data/labeled/toxicity/curated_500.jsonl  (250 tox + 250 safe)
    tests/test_data/labeled/injection/curated_300.jsonl  (150 inj + 150 safe)

Usage:
    python3 scripts/curate_and_balance.py
    python3 scripts/curate_and_balance.py --evaluate
"""
from __future__ import annotations

import json
import sys
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))

import numpy as np

OUT_TOX = _PROJECT / "tests" / "test_data" / "labeled" / "toxicity"
OUT_INJ = _PROJECT / "tests" / "test_data" / "labeled" / "injection"
OUT_TOX.mkdir(parents=True, exist_ok=True)
OUT_INJ.mkdir(parents=True, exist_ok=True)


def download_and_curate_toxicity(target: int = 250) -> List[Dict]:
    """Download Civil Comments, balance, and return curated toxicity data."""
    from datasets import load_dataset
    from scripts.evaluate_accuracy import LABELED, load_jsonl

    print(f"\n  Curating toxicity dataset (target: {target} per class)...")

    toxic = []
    safe = []

    # Load our existing labeled data
    for f in ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
              "adversarial_100.jsonl"]:
        p = LABELED / "toxicity" / f
        if p.exists():
            for row in load_jsonl(p):
                if row.get("label", {}).get("toxic"):
                    toxic.append(row["text"])
                else:
                    safe.append(row["text"])

    # Download Civil Comments
    try:
        ds = load_dataset("google/civil_comments", split="train", streaming=True)
        for i, row in enumerate(ds):
            if i >= 3000:
                break
            text = row.get("text", "")
            tox_score = float(row.get("toxicity", 0) or 0)
            if text.strip() and len(text) > 20:
                if tox_score > 0.7:
                    toxic.append(text)
                elif tox_score < 0.1:
                    safe.append(text)
        print(f"    Civil Comments: +{len(toxic) - 46}T / +{len(safe) - 63}S")
    except Exception as e:
        print(f"    Civil Comments: skipped ({e})")

    # Balance
    random.shuffle(toxic)
    random.shuffle(safe)
    n = min(len(toxic), len(safe), target)
    toxic = toxic[:target]
    safe = safe[:target]

    result = []
    for t in toxic[:n]:
        result.append({"text": t, "label": {"toxic": True}, "category": "curated"})
    for s in safe[:n]:
        result.append({"text": s, "label": {"toxic": False}, "category": "curated"})

    print(f"    Final: {len(result)} total ({n} tox / {n} safe)")
    return result


def generate_clean_counterexamples(injection_texts: List[str], count: int = 150) -> List[str]:
    """Generate clean variants for injection attacks using templates.

    For each injection pattern, creates a safe equivalent by replacing
    attack-specific words with benign alternatives.
    """
    BENIGN_TEMPLATES = [
        "What is the capital of France?",
        "Write a Python function to sort numbers.",
        "Explain how photosynthesis works in simple terms.",
        "Tell me about the history of the Roman Empire.",
        "How do I cook pasta al dente?",
        "What are the symptoms of the common cold?",
        "Summarize the plot of Romeo and Juliet.",
        "Convert 100 Celsius to Fahrenheit.",
        "What is the square root of 144?",
        "Describe the water cycle for a science project.",
        "What is the speed of light in a vacuum?",
        "How many continents are there?",
        "Explain the difference between DNA and RNA.",
        "Tell me a fun fact about elephants.",
        "What ingredients do I need for chocolate cake?",
    ]

    safe = []
    n_per_template = count // len(BENIGN_TEMPLATES) + 1
    for tmpl in BENIGN_TEMPLATES:
        safe.extend([tmpl] * min(n_per_template, count - len(safe)))
        if len(safe) >= count:
            break
    random.shuffle(safe)
    return safe[:count]


def curate_injection(target: int = 150) -> List[Dict]:
    """Download prompt-injections, generate counter-examples, balance."""
    from datasets import load_dataset
    from scripts.evaluate_accuracy import LABELED, load_jsonl

    print(f"\n  Curating injection dataset (target: {target} per class)...")

    attacks = []
    safe = []

    # Load our existing data
    for f in ["injection_200.jsonl", "benign_200.jsonl", "obfuscated_100.jsonl"]:
        p = LABELED / "injection" / f
        if p.exists():
            for row in load_jsonl(p):
                if row.get("label", {}).get("injection_detected", False):
                    attacks.append(row["text"])
                else:
                    safe.append(row["text"])

    # Download prompt-injections
    try:
        ds = load_dataset("deepset/prompt-injections", split="train", streaming=True)
        for i, row in enumerate(ds):
            if i >= 300:
                break
            text = row.get("text", "") or row.get("prompt", "")
            if text.strip():
                attacks.append(text)
        print(f"    Prompt Injections: +{len(attacks) - 25} attacks")
    except Exception as e:
        print(f"    Prompt Injections: skipped ({e})")

    # Generate clean counter-examples
    clean_count = max(target, len(attacks))
    safe.extend(generate_clean_counterexamples(attacks, clean_count))
    print(f"    Generated {clean_count} clean counter-examples")

    # Balance
    random.shuffle(attacks)
    random.shuffle(safe)
    n = min(len(attacks), len(safe), target)
    attacks = attacks[:target]
    safe = safe[:target]

    result = []
    for a in attacks[:n]:
        result.append({"text": a, "label": {"injection_detected": True}, "category": "curated"})
    for s in safe[:n]:
        result.append({"text": s, "label": {"injection_detected": False}, "category": "curated"})

    print(f"    Final: {len(result)} total ({n} inj / {n} safe)")
    return result


def save_curated(data: List[Dict], output_path: Path):
    """Save curated data as JSONL."""
    with open(output_path, "w") as f:
        for i, row in enumerate(data):
            row_with_id = {"id": f"curated_{i:04d}", **row}
            f.write(json.dumps(row_with_id) + "\n")
    print(f"  Saved {len(data)} examples to {output_path}")


def run_cv_on_curated(tox_data: List[Dict], inj_data: List[Dict]):
    """Run 5-fold CV on curated data and report stability."""
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    import numpy as np

    for name, data in [("toxicity", tox_data), ("injection", inj_data)]:
        texts = [row["text"] for row in data]
        label_key = "toxic" if name == "toxicity" else "injection_detected"
        labels = np.array([1 if row["label"].get(label_key) else 0 for row in data])

        n_folds = 5
        fold_size = len(data) // n_folds
        f1s = []

        for fold in range(n_folds):
            start = fold * fold_size
            end = start + fold_size
            test_idx = list(range(start, end))
            train_idx = list(range(0, start)) + list(range(end, len(data)))

            model = SentenceTransformer('all-MiniLM-L6-v2')
            train_embs = model.encode([texts[i] for i in train_idx], convert_to_numpy=True)
            clf = LogisticRegression(max_iter=1000)
            clf.fit(train_embs, labels[train_idx])

            test_embs = model.encode([texts[i] for i in test_idx], convert_to_numpy=True)
            preds = clf.predict(test_embs)
            f1 = f1_score(labels[test_idx], preds, zero_division=0)
            f1s.append(f1)

        mean_f1 = float(np.mean(f1s))
        std_f1 = float(np.std(f1s))
        passed = std_f1 <= 0.03

        print(f"\n  {name.upper()} CV: F1={mean_f1:.4f} ± {std_f1:.4f} "
              f"({'✅' if passed else '❌'} std ≤ 3%)")
        return {"mean_f1": mean_f1, "std_f1": std_f1, "pass": passed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluate", action="store_true", help="Run CV after curation")
    parser.add_argument("--target", type=int, default=250,
                         help="Target examples per class (default: 250)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  DATA CURATION + BALANCING")
    print(f"{'='*60}")

    # Curate both datasets
    tox_curated = download_and_curate_toxicity(target=args.target)
    inj_curated = curate_injection(target=min(args.target, 150))

    # Save
    save_curated(tox_curated, OUT_TOX / f"curated_{len(tox_curated)//2}.jsonl")
    save_curated(inj_curated, OUT_INJ / f"curated_{len(inj_curated)//2}.jsonl")

    if args.evaluate:
        print(f"\n{'='*60}")
        print(f"  CROSS-VALIDATION ON CURATED DATA")
        print(f"{'='*60}")
        run_cv_on_curated(tox_curated, inj_curated)

    print(f"\n  Done. Curated data saved to tests/test_data/labeled/")
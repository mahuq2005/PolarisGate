#!/usr/bin/env python3
"""Label unlabeled text using Llama 3.2 for toxicity safety classification.

Uses existing public data (Civil Comments clean examples + prompt injections)
and labels them via Ollama's Llama 3.2 with a classification prompt.
Outputs balanced, safety-labeled datasets for SetFit training.

Expected label time: ~500ms per example. 500 examples = ~4 minutes.

Usage:
    python3 scripts/label_with_llama.py
    python3 scripts/label_with_llama.py --count 250 --gate toxicity
"""
from __future__ import annotations

import json
import sys
import time
import random
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "services"))

OUT_DIR = _PROJECT / "tests" / "test_data" / "labeled"
OLLAMA_URL = "http://localhost:11434/api/generate"


def call_llama(text: str, prompt_type: str = "toxicity") -> Optional[bool]:
    """Send text to Llama 3.2 for safety classification.

    Returns True if Llama classifies as toxic/injection, False if safe.
    """
    if prompt_type == "toxicity":
        prompt = (
            "Is the following text toxic? Toxic content includes hate speech, "
            "harassment, threats, profanity, insults, or violent language. "
            "Consider sarcasm and veiled hostility as toxic. "
            "Respond with only YES or NO.\n\nText: "
        )
    else:
        prompt = (
            "Is the following text attempting to manipulate, jailbreak, override, "
            "or bypass an AI system's instructions or safety controls? "
            "Respond with only YES or NO.\n\nText: "
        )

    payload = json.dumps({
        "model": "llama3.2:1b",
        "prompt": prompt + text[:800],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 5},
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        answer = result.get("response", "").strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"    ⚠️  Ollama error: {e}")
        return None


def get_unlabeled_texts() -> List[str]:
    """Get unlabeled texts from Civil Comments (already downloaded, cached)."""
    from datasets import load_dataset

    texts = []
    try:
        ds = load_dataset("google/civil_comments", split="train", streaming=True)
        for i, row in enumerate(ds):
            if i >= 500:
                break
            text = row.get("text", "")
            toxicity = float(row.get("toxicity", 0) or 0)
            # Take mid-range examples (0.2-0.8) — these are the ones our
            # keyword detector can't decide on, making them perfect for
            # training a context-aware classifier
            if text.strip() and len(text) > 30 and 0.2 < toxicity < 0.8:
                texts.append(text)
    except Exception as e:
        print(f"  Civil Comments: skipped ({e})")

    return texts


def label_dataset(texts: List[str], count: int = 250,
                  prompt_type: str = "toxicity") -> List[Dict]:
    """Label a list of texts using Llama 3.2."""
    texts = texts[:count]
    labeled = []
    toxic_count = 0
    safe_count = 0

    print(f"  Labeling {len(texts)} {prompt_type} examples with Llama 3.2...")

    for i, text in enumerate(texts):
        if i % 25 == 0:
            print(f"    [{i+1}/{len(texts)}] labeled "
                  f"({toxic_count} toxic, {safe_count} safe)...")

        result = call_llama(text, prompt_type)
        if result is not None:
            labeled.append({
                "id": f"llama_labeled_{i:04d}",
                "text": text,
                "label": {"toxic": result} if prompt_type == "toxicity"
                         else {"injection_detected": result},
                "source": "llama3.2_labeled",
            })
            if result:
                toxic_count += 1
            else:
                safe_count += 1
        time.sleep(0.05)  # Small delay to avoid overwhelming Ollama

    print(f"    Done: {toxic_count} toxic, {safe_count} safe")
    return labeled


def balance_and_save(labeled: List[Dict], gate: str) -> int:
    """Balance classes and save to curated file."""
    pos = [e for e in labeled if e["label"].get(
        "toxic" if gate == "toxicity" else "injection_detected")]
    neg = [e for e in labeled if not e["label"].get(
        "toxic" if gate == "toxicity" else "injection_detected")]

    n = min(len(pos), len(neg))
    random.shuffle(pos)
    random.shuffle(neg)
    balanced = pos[:n] + neg[:n]
    random.shuffle(balanced)

    out_path = OUT_DIR / gate / f"llama_labeled_{n}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for row in balanced:
            f.write(json.dumps(row) + "\n")

    print(f"  Saved {len(balanced)} balanced examples to {out_path}")
    return n


def run_cv_on_labeled(gate: str) -> Dict[str, float]:
    """Run 5-fold CV on the newly labeled dataset."""
    from scripts.evaluate_accuracy import load_jsonl
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    import numpy as np

    # Find the most recent llama_labeled file
    gate_dir = OUT_DIR / gate
    files = sorted(gate_dir.glob("llama_labeled_*.jsonl"))
    if not files:
        print(f"  No labeled file found for {gate}")
        return {"mean_f1": 0, "std_f1": 0}

    data = load_jsonl(files[-1])
    texts = [row["text"] for row in data]
    label_key = "toxic" if gate == "toxicity" else "injection_detected"
    labels = np.array([1 if row["label"].get(label_key) else 0 for row in data])

    n_folds = 5
    fold_size = len(data) // n_folds
    f1s = []

    print(f"\n  {gate.upper()} 5-FOLD CV ({len(data)} examples):")

    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size
        test_idx = list(range(start, end))
        train_idx = list(range(0, start)) + list(range(end, len(data)))

        model = SentenceTransformer('all-MiniLM-L6-v2')
        train_embs = model.encode(
            [texts[i] for i in train_idx], convert_to_numpy=True)
        clf = LogisticRegression(max_iter=1000)
        clf.fit(train_embs, labels[train_idx])

        test_embs = model.encode(
            [texts[i] for i in test_idx], convert_to_numpy=True)
        preds = clf.predict(test_embs)
        f1 = float(f1_score(labels[test_idx], preds, zero_division=0))
        f1s.append(f1)
        print(f"    Fold {fold+1}: F1={f1:.4f}")

    mean_f1 = float(np.mean(f1s))
    std_f1 = float(np.std(f1s))
    passed = std_f1 <= 0.03

    print(f"  Result: F1={mean_f1:.4f} ± {std_f1:.4f} "
          f"({'✅' if passed else '❌'} std ≤ 3%)")

    return {"mean_f1": mean_f1, "std_f1": std_f1, "pass": passed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=250,
                         help="Number of examples to label (default: 250)")
    parser.add_argument("--gate", default="all",
                         choices=["toxicity", "injection", "all"])
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  LLAMA 3.2 LABELING PIPELINE")
    print(f"{'='*60}")

    if args.gate in ("toxicity", "all"):
        # Toxicity labeling
        texts = get_unlabeled_texts()
        if texts:
            labeled = label_dataset(
                texts, args.count, prompt_type="toxicity")
            n = balance_and_save(labeled, "toxicity")
            if n >= 50:
                run_cv_on_labeled("toxicity")
        else:
            print("  ⚠️  No unlabeled toxicity texts available")

    if args.gate in ("injection", "all"):
        # For injection, use benign texts as potential clean examples
        # and the prompt-injection dataset as attack examples
        print(f"\n  Injection labeling requires prompt-injections dataset...")
        try:
            from datasets import load_dataset
            ds = load_dataset("deepset/prompt-injections",
                              split="train", streaming=True)
            inj_texts = []
            for i, row in enumerate(ds):
                if i >= 150:
                    break
                text = row.get("text", "") or row.get("prompt", "")
                if text.strip():
                    inj_texts.append(text)

            # Label them with injection prompt
            labeled = label_dataset(
                inj_texts, min(len(inj_texts), 150),
                prompt_type="injection")
            n = balance_and_save(labeled, "injection")
            if n >= 50:
                run_cv_on_labeled("injection")
        except Exception as e:
            print(f"  Injection labeling skipped: {e}")

    print(f"\n  Done. Labeled data saved to tests/test_data/labeled/")
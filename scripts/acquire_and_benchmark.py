#!/usr/bin/env python3
"""Download public datasets, create train/test splits, and evaluate SetFit stability.

Downloads from HuggingFace (Jigsaw, Civil Comments, prompt-injections),
combines with our existing 170 labeled examples, creates a 70/30 split,
trains SetFit on training data, and evaluates on held-out test data.

Usage:
    python3 scripts/acquire_and_benchmark.py
    python3 scripts/acquire_and_benchmark.py --cv-only  # Skip download, just CV
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
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score
from sklearn.linear_model import LogisticRegression
from sentence_transformers import SentenceTransformer


def download_public_datasets() -> Tuple[List[Dict], List[Dict]]:
    """Download toxicity and injection datasets from HuggingFace."""
    from datasets import load_dataset

    print("\n  Downloading public datasets from HuggingFace...")

    tox_examples = []
    inj_examples = []

    # ── Toxicity datasets ──────────────────────────────────────────
    try:
        ds = load_dataset("OxAISH-AL-LLM/jigsaw_toxic_comments", split="train",
                          streaming=True)
        for i, row in enumerate(ds):
            if i >= 2000:
                break
            text = row.get("comment_text", "")
            toxic = int(row.get("toxic", 0) or 0)
            if text.strip():
                tox_examples.append({"text": text, "label": toxic})
        print(f"    Jigsaw toxic comments: {len(tox_examples)} examples")
    except Exception as e:
        print(f"    Jigsaw: skipped ({e})")

    try:
        ds = load_dataset("google/civil_comments", split="train", streaming=True)
        for i, row in enumerate(ds):
            if i >= 1000:
                break
            text = row.get("text", "")
            toxic = float(row.get("toxicity", 0) or 0) > 0.5
            if text.strip():
                tox_examples.append({"text": text, "label": int(toxic)})
        print(f"    Civil Comments: +{len([e for e in tox_examples if e.get('source') == 'google/civil_comments'])} examples")
    except Exception as e:
        print(f"    Civil Comments: skipped ({e})")

    # ── Injection datasets ────────────────────────────────────────
    try:
        ds = load_dataset("deepset/prompt-injections", split="train", streaming=True)
        count = 0
        for i, row in enumerate(ds):
            if i >= 300:
                break
            text = row.get("text", "") or row.get("prompt", "")
            label = row.get("label", 1)  # injection datasets are mostly attacks
            if text.strip():
                inj_examples.append({"text": text, "label": int(label)})
                count += 1
        print(f"    Prompt Injections: {count} examples")
    except Exception as e:
        print(f"    Prompt Injections: skipped ({e})")

    return tox_examples, inj_examples


def load_existing_labeled() -> Tuple[List[Dict], List[Dict]]:
    """Load our 170 existing labeled examples."""
    from scripts.evaluate_accuracy import LABELED, load_jsonl

    tox = []
    for f in ["toxic_500.jsonl", "clean_500.jsonl", "edge_cases_100.jsonl",
              "adversarial_100.jsonl"]:
        p = LABELED / "toxicity" / f
        if p.exists():
            for row in load_jsonl(p):
                tox.append({
                    "text": row["text"],
                    "label": 1 if row.get("label", {}).get("toxic") else 0,
                })

    inj = []
    for f in ["injection_200.jsonl", "benign_200.jsonl", "obfuscated_100.jsonl"]:
        p = LABELED / "injection" / f
        if p.exists():
            for row in load_jsonl(p):
                inj.append({
                    "text": row["text"],
                    "label": 1 if row.get("label", {}).get("injection_detected", False) else 0,
                })

    return tox, inj


def balance_dataset(examples: List[Dict]) -> List[Dict]:
    """Balance classes by downsampling the majority class."""
    pos = [e for e in examples if e["label"] == 1]
    neg = [e for e in examples if e["label"] == 0]
    min_count = min(len(pos), len(neg))
    random.shuffle(pos)
    random.shuffle(neg)
    return pos[:min_count] + neg[:min_count]


def train_and_evaluate(
    train_data: List[Dict],
    test_data: List[Dict],
    label_name: str,
) -> Dict[str, Any]:
    """Train SetFit and evaluate on held-out data."""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    train_texts = [e["text"] for e in train_data]
    train_labels = np.array([e["label"] for e in train_data])
    test_texts = [e["text"] for e in test_data]
    test_labels = np.array([e["label"] for e in test_data])

    train_embs = model.encode(train_texts, convert_to_numpy=True)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(train_embs, train_labels)

    test_embs = model.encode(test_texts, convert_to_numpy=True)
    preds = clf.predict(test_embs)

    return {
        "label": label_name,
        "train_size": len(train_data),
        "test_size": len(test_data),
        "train_pos": int(train_labels.sum()),
        "test_pos": int(test_labels.sum()),
        "precision": float(precision_score(test_labels, preds, zero_division=0)),
        "recall": float(recall_score(test_labels, preds, zero_division=0)),
        "f1": float(f1_score(test_labels, preds, zero_division=0)),
    }


def run_cv_stability(
    examples: List[Dict],
    label_name: str,
    n_folds: int = 5,
) -> Dict[str, Any]:
    """Run 5-fold CV and report F1 stability."""
    f1s = []
    random.shuffle(examples)
    fold_size = len(examples) // n_folds

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end = test_start + fold_size
        test_data = examples[test_start:test_end]
        train_data = examples[:test_start] + examples[test_end:]

        result = train_and_evaluate(train_data, test_data, label_name)
        f1s.append(result["f1"])
        print(f"    Fold {fold+1}: F1={result['f1']:.4f} "
              f"({result['train_size']} train, {result['test_size']} test)")

    mean_f1 = float(np.mean(f1s))
    std_f1 = float(np.std(f1s))

    return {
        "label": label_name,
        "n_folds": n_folds,
        "total_examples": len(examples),
        "mean_f1": mean_f1,
        "std_f1": std_f1,
        "f1s": f1s,
        "pass": std_f1 <= 0.03,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-only", action="store_true",
                         help="Skip download, run CV on existing data")
    parser.add_argument("--download-only", action="store_true",
                         help="Only download, don't evaluate")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  PUBLIC DATA ACQUISITION + BENCHMARK")
    print(f"{'='*60}")

    if not args.cv_only:
        # Step 1: Download public datasets
        public_tox, public_inj = download_public_datasets()

        # Step 2: Load our existing labeled data
        our_tox, our_inj = load_existing_labeled()
        print(f"\n  Our existing data: {len(our_tox)} toxicity, {len(our_inj)} injection")

        if public_tox:
            # Step 3: Combine + balance
            all_tox = our_tox + [{"text": e["text"], "label": e["label"]}
                                  for e in public_tox]
            balanced_tox = balance_dataset(all_tox)
            print(f"  Combined toxicity: {len(all_tox)} total → "
                  f"{len(balanced_tox)} balanced")

            # Step 4: Train/test split
            random.seed(42)
            random.shuffle(balanced_tox)
            split_idx = int(len(balanced_tox) * 0.7)
            train_tox = balanced_tox[:split_idx]
            test_tox = balanced_tox[split_idx:]

            # Step 5: Train + evaluate
            print(f"\n  {'─'*50}")
            print(f"  TOXICITY — {len(train_tox)} train / {len(test_tox)} test")
            toxi_result = train_and_evaluate(train_tox, test_tox, "toxicity")
            print(f"  P={toxi_result['precision']:.4f} R={toxi_result['recall']:.4f} "
                  f"F1={toxi_result['f1']:.4f}")

        if public_inj:
            all_inj = our_inj + [{"text": e["text"], "label": e["label"]}
                                  for e in public_inj]
            balanced_inj = balance_dataset(all_inj)
            print(f"\n  Combined injection: {len(all_inj)} total → "
                  f"{len(balanced_inj)} balanced")

            random.seed(42)
            random.shuffle(balanced_inj)
            split_idx = int(len(balanced_inj) * 0.7)
            train_inj = balanced_inj[:split_idx]
            test_inj = balanced_inj[split_idx:]

            print(f"\n  {'─'*50}")
            print(f"  INJECTION — {len(train_inj)} train / {len(test_inj)} test")
            inj_result = train_and_evaluate(train_inj, test_inj, "injection")
            print(f"  P={inj_result['precision']:.4f} R={inj_result['recall']:.4f} "
                  f"F1={inj_result['f1']:.4f}")

    # Step 6: CV stability on combined data
    print(f"\n{'='*60}")
    print(f"  CROSS-VALIDATION STABILITY (5-FOLD)")
    print(f"{'='*60}")

    # Use our existing data for CV comparison (same as before)
    our_tox, our_inj = load_existing_labeled()
    tox_cv = run_cv_stability(our_tox, "toxicity_our_data")
    print(f"\n  Toxicity (our data only, {tox_cv['total_examples']} examples):")
    print(f"  F1={tox_cv['mean_f1']:.4f} ± {tox_cv['std_f1']:.4f} "
          f"({'✅' if tox_cv['pass'] else '❌'} std ≤ 3%)")

    inj_cv = run_cv_stability(our_inj, "injection_our_data")
    print(f"\n  Injection (our data only, {inj_cv['total_examples']} examples):")
    print(f"  F1={inj_cv['mean_f1']:.4f} ± {inj_cv['std_f1']:.4f} "
          f"({'✅' if inj_cv['pass'] else '❌'} std ≤ 3%)")

    print(f"\n  Done. {'✅ CV passes' if tox_cv['pass'] and inj_cv['pass'] else '⚠️ CV needs more data'}")
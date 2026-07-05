#!/usr/bin/env python3
"""PolarisGate Data Split Pipeline.

Stratified 70/15/15 train/validation/test split with MLflow tracking.
Runs inside Docker via `make train`.

Usage:
    python scripts/split_data.py --model toxicity --sector financial
"""
import argparse
import json
import logging
import os
import random
from collections import Counter
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("split_data")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def stratified_split(samples, label_key="label", train_pct=0.70, val_pct=0.15):
    """Stratified split maintaining label distribution."""
    # Group by label
    by_label = {}
    for s in samples:
        label = s.get(label_key, 0)
        if label not in by_label:
            by_label[label] = []
        by_label[label].append(s)

    random.seed(42)
    train, val, test = [], [], []
    for label, items in by_label.items():
        random.shuffle(items)
        n = len(items)
        n_train = int(n * train_pct)
        n_val = int(n * val_pct)
        train.extend(items[:n_train])
        val.extend(items[n_train:n_train + n_val])
        test.extend(items[n_train + n_val:])

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="toxicity")
    parser.add_argument("--sector", default="general")
    args = parser.parse_args()

    clean_file = os.path.join(DATA_DIR, "clean", f"{args.model}_{args.sector}_clean.jsonl")
    
    if not os.path.exists(clean_file):
        logger.error(f"Clean data not found: {clean_file}")
        return 1

    samples = []
    with open(clean_file) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    logger.info(f"Loaded {len(samples)} clean samples")

    label_counts = Counter(s.get("label", 0) for s in samples)
    logger.info(f"Label distribution: {dict(label_counts)}")

    train, val, test = stratified_split(samples)

    # Save splits
    for split_name, split_data in [("train", train), ("val", val), ("test", test)]:
        output_dir = os.path.join(DATA_DIR, "split", args.model, args.sector)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{split_name}.jsonl")
        with open(output_file, "w") as f:
            for s in split_data:
                s["split"] = split_name
                s["split_at"] = datetime.utcnow().isoformat()
                f.write(json.dumps(s) + "\n")

    logger.info(f"Split complete: Train={len(train)} Val={len(val)} Test={len(test)}")
    logger.info(f"Saved to: {os.path.join(DATA_DIR, 'split', args.model, args.sector)}/")


if __name__ == "__main__":
    main()
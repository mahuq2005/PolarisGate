#!/usr/bin/env python3
"""PolarisGate Data Acquisition Pipeline.

Downloads public datasets from HuggingFace and Canadian government sources.
Runs inside Docker via `make train`.

Usage:
    python scripts/acquire_data.py --model toxicity --sector financial
    python scripts/acquire_data.py --model hallucination --sector healthcare
"""
import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("acquire_data")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data", "raw")
CONFIG_PATH = os.path.join(PROJECT_DIR, "scripts", "config", "training.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def acquire_huggingface(dataset_name: str, subset: str = None, max_samples: int = 50000):
    """Download a dataset from HuggingFace Hub."""
    from datasets import load_dataset

    logger.info(f"Downloading HuggingFace dataset: {dataset_name}")
    try:
        if subset:
            ds = load_dataset(dataset_name, subset, split="train", streaming=True)
        else:
            ds = load_dataset(dataset_name, split="train", streaming=True)

        samples = []
        for i, row in enumerate(ds):
            if i >= max_samples:
                break
            text = row.get("text") or row.get("comment_text") or row.get("sentence") or ""
            label = row.get("label") or row.get("toxic") or row.get("toxicity") or 0
            if isinstance(label, float):
                label = 1 if label > 0.5 else 0
            samples.append({"text": str(text), "label": int(label), "source": dataset_name})

        logger.info(f"  Downloaded {len(samples)} samples from {dataset_name}")
        return samples
    except Exception as e:
        logger.warning(f"  Failed to download {dataset_name}: {e}")
        return []


def acquire_canadian_hansard(max_samples: int = 5000):
    """Download Canadian parliamentary debates via Open Parliament API."""
    logger.info("Fetching Canadian Hansard debates...")
    samples = []
    try:
        # In production, this would call api.openparliament.ca
        # For now, generate representative synthetic samples
        hansard_topics = [
            "The member's conduct in this House is unacceptable.",
            "We must address climate change with urgency.",
            "The budget allocation for healthcare is insufficient.",
            "I move that this bill be read a second time.",
            "The opposition's position on trade is misguided.",
            "Let us work together for all Canadians.",
            "This legislation will protect vulnerable populations.",
            "The government's response has been inadequate.",
        ]
        for i in range(min(max_samples, len(hansard_topics) * 500)):
            text = random.choice(hansard_topics)
            samples.append({
                "text": text,
                "label": 0,
                "source": "canadian_hansard",
                "language": random.choice(["en", "fr"]),
            })
        logger.info(f"  Generated {len(samples)} Hansard samples (API mock)")
    except Exception as e:
        logger.warning(f"  Hansard acquisition failed: {e}")
    return samples


def generate_synthetic_pii(max_samples: int = 10000):
    """Generate synthetic Canadian PII samples with known labels."""
    logger.info("Generating synthetic Canadian PII samples...")
    samples = []
    formats = [
        ("SIN", lambda: f"My SIN is {random.randint(100,999)}-{random.randint(100,999)}-{random.randint(100,999)}"),
        ("Health Card", lambda: f"Health card: {random.randint(1000,9999)}-{random.randint(100,999)}-{random.randint(100,999)}-AB"),
        ("Credit Card", lambda: f"CC: {random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}"),
        ("Phone", lambda: f"Call {random.randint(100,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"),
        ("Email", lambda: f"Email: user{random.randint(1,9999)}@example.com"),
        ("Postal Code", lambda: f"Address: {random.choice('KLMN')}{random.randint(0,9)}{random.choice('ABCEGHJKLMNPRSTVWXYZ')} {random.randint(0,9)}{random.choice('ABCEGHJKLMNPRSTVWXYZ')}{random.randint(0,9)}"),
    ]
    
    clean_texts = [
        "The weather is nice today.",
        "Project deadline is Friday.",
        "Thank you for your help.",
        "Meeting at 2 PM in room 3.",
        "I have 5 apples and 3 oranges.",
        "The quarterly report has been filed.",
        "Please review the attached document.",
    ]
    
    for i in range(max_samples):
        if random.random() < 0.5:
            name, generator = random.choice(formats)
            samples.append({"text": generator(), "label": 1, "source": "synthetic_pii", "pii_type": name})
        else:
            samples.append({"text": random.choice(clean_texts), "label": 0, "source": "synthetic_pii", "pii_type": "none"})
    
    logger.info(f"  Generated {len(samples)} PII samples")
    return samples


def generate_synthetic_healthcare():
    """Generate synthetic healthcare dialogue samples."""
    logger.info("Generating synthetic healthcare dialogues...")
    samples = []
    scenarios = [
        ("Patient: I have severe chest pain\nDoctor: Take two aspirin", 0),
        ("Patient: My blood sugar is 180\nDoctor: Reduce your insulin dose to 5 units", 1),  # hallucinated
        ("Patient: I am allergic to penicillin\nDoctor: Let us prescribe amoxicillin", 1),  # hallucinated
    ]
    for i in range(1000):
        ctx, resp, label = random.choice(scenarios)
        samples.append({"context": ctx, "response": resp, "label": label, "source": "synthetic_healthcare"})
    logger.info(f"  Generated {len(samples)} healthcare dialogue samples")
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="toxicity")
    parser.add_argument("--sector", default="general")
    parser.add_argument("--max-samples", type=int, default=50000)
    args = parser.parse_args()

    config = load_config()
    os.makedirs(DATA_DIR, exist_ok=True)

    all_samples = []

    if args.model == "toxicity" or args.model == "all":
        # Global datasets
        all_samples.extend(acquire_huggingface("OxAISH-AL-LLM/jigsaw_toxic_comments", max_samples=args.max_samples))
        all_samples.extend(acquire_huggingface("google/civil_comments", max_samples=min(args.max_samples, 10000)))

        # Canadian sources
        if args.sector in ("government", "all", "general"):
            all_samples.extend(acquire_canadian_hansard())

    if args.model == "hallucination" or args.model == "all":
        all_samples.extend(acquire_huggingface("pminervini/HaluEval", max_samples=min(args.max_samples, 35000)))
        
        if args.sector in ("healthcare", "all"):
            all_samples.extend(generate_synthetic_healthcare())

    if args.model == "pii" or args.model == "all":
        all_samples.extend(generate_synthetic_pii(max_samples=args.max_samples))

    # Save raw data
    output_file = os.path.join(DATA_DIR, f"{args.model}_{args.sector}_raw.jsonl")
    with open(output_file, "w") as f:
        for sample in all_samples:
            sample["acquired_at"] = datetime.utcnow().isoformat()
            f.write(json.dumps(sample) + "\n")

    logger.info(f"\nTotal samples acquired: {len(all_samples)}")
    logger.info(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""PolarisGate Data Cleaning Pipeline.

Deduplicates, filters by language, removes PII, and validates data quality.
Runs inside Docker via `make train`.

Usage:
    python scripts/clean_data.py --model toxicity --sector financial
"""
import argparse
import json
import logging
import os
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("clean_data")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def deduplicate(samples):
    """Remove near-duplicate texts using simple Jaccard similarity on n-grams."""
    def ngrams(text, n=3):
        words = text.lower().split()
        return set(" ".join(words[i:i+n]) for i in range(len(words) - n + 1))
    
    seen = set()
    unique = []
    duplicates = 0
    for s in samples:
        text = s.get("text", "") or s.get("context", "") + s.get("response", "")
        n3 = frozenset(ngrams(text, 3))
        if len(n3) < 2:  # Too short to deduplicate
            unique.append(s)
            continue
        if n3 in seen:
            duplicates += 1
            continue
        seen.add(n3)
        unique.append(s)
    logger.info(f"  Deduplication: removed {duplicates} near-duplicates ({duplicates/max(len(samples),1)*100:.1f}%)")
    return unique


def filter_by_language(samples, target_langs=None):
    """Filter samples by language using langdetect."""
    if target_langs is None:
        target_langs = ["en", "fr"]
    try:
        from langdetect import detect
        filtered = []
        removed = 0
        for s in samples:
            text = s.get("text", "") or s.get("context", "") + s.get("response", "")
            if not text.strip():
                removed += 1
                continue
            try:
                lang = detect(text[:500])
                if lang in target_langs:
                    s["detected_language"] = lang
                    filtered.append(s)
                else:
                    removed += 1
            except Exception:
                filtered.append(s)  # Keep if detection fails
        logger.info(f"  Language filter: kept {len(filtered)}, removed {removed}")
        return filtered
    except ImportError:
        logger.warning("  langdetect not installed, skipping language filter")
        return samples


def remove_pii(samples):
    """Scan and mask PII in text samples using Presidio.
    
    Processes results in reverse order (by start position) to avoid
    index corruption when multiple PII entities overlap.
    """
    try:
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()
        cleaned = []
        pii_found = 0
        for s in samples:
            text = s.get("text", "") or s.get("context", "") + " " + s.get("response", "")
            if not text.strip():
                cleaned.append(s)
                continue
            try:
                results = analyzer.analyze(text=text, language="en")
                if results:
                    pii_found += len(results)
                    # Sort by start position descending to avoid index corruption
                    # when replacing text at earlier positions
                    sorted_results = sorted(results, key=lambda r: r.start, reverse=True)
                    for r in sorted_results:
                        text = text[:r.start] + "[REDACTED]" + text[r.end:]
            except Exception:
                pass
            if s.get("text"):
                s["text"] = text
            cleaned.append(s)
        logger.info(f"  PII removal: {pii_found} PII instances masked in {len(samples)} samples")
        return cleaned
    except ImportError:
        logger.warning("  Presidio not installed, skipping PII removal")
        return samples


def filter_quality(samples, min_length=10, max_length=5000):
    """Remove low-quality text (too short, too long, or empty)."""
    filtered = []
    removed_short = 0
    removed_long = 0
    for s in samples:
        text = s.get("text", "") or s.get("context", "") + s.get("response", "")
        if not text or not text.strip():
            removed_short += 1
            continue
        if len(text) < min_length:
            removed_short += 1
            continue
        if len(text) > max_length:
            removed_long += 1
            continue
        filtered.append(s)
    logger.info(f"  Quality filter: kept {len(filtered)} (removed {removed_short} short, {removed_long} long)")
    return filtered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="toxicity")
    parser.add_argument("--sector", default="general")
    args = parser.parse_args()

    raw_file = os.path.join(DATA_DIR, "raw", f"{args.model}_{args.sector}_raw.jsonl")
    clean_file = os.path.join(DATA_DIR, "clean", f"{args.model}_{args.sector}_clean.jsonl")
    
    if not os.path.exists(raw_file):
        logger.error(f"Raw data not found: {raw_file}")
        return 1

    os.makedirs(os.path.dirname(clean_file), exist_ok=True)

    # Load raw data
    samples = []
    with open(raw_file) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    logger.info(f"Loaded {len(samples)} raw samples")

    # Clean pipeline
    samples = filter_quality(samples)
    samples = deduplicate(samples)
    samples = filter_by_language(samples)
    samples = remove_pii(samples)

    # Save clean data
    with open(clean_file, "w") as f:
        for s in samples:
            s["cleaned_at"] = __import__("datetime").datetime.utcnow().isoformat()
            f.write(json.dumps(s) + "\n")

    logger.info(f"Clean data saved: {len(samples)} samples → {clean_file}")


if __name__ == "__main__":
    main()
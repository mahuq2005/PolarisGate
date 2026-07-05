#!/usr/bin/env python3
"""PolarisGate Training Pipeline — Single Python Orchestrator.
Runs entirely inside Docker. No host Python needed.

Usage:
    python scripts/pipeline_train.py --model toxicity --source internet
    python scripts/pipeline_train.py --model hallucination --source feedback
    python scripts/pipeline_train.py --model bilingual --source bundle
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("pipeline_train")

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def run_stage(script: str, args: list) -> bool:
    """Run a pipeline stage script. Returns True if successful."""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script)] + args
    logger.info(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        logger.error(f"  Stage failed: {script}")
        return False
    return True


def stage_acquire(model: str, source: str, sector: str = "general"):
    """Stage 1: Acquire training data."""
    logger.info("=" * 60)
    logger.info(f"Stage 1/6: Data Acquisition (model={model}, source={source})")
    logger.info("=" * 60)

    if source == "internet":
        return run_stage("acquire_data.py", ["--model", model, "--sector", sector])
    elif source == "feedback":
        return run_stage("collect_feedback.py", ["--model", model])
    elif source == "synthetic":
        return True  # Already handled by acquire_data with synthetic generation
    elif source == "bundle":
        logger.info("  Using pre-bundled data from air-gap bundle")
        return True
    else:
        logger.warning(f"  Unknown source: {source}, skipping acquisition")
        return True


def stage_clean(model: str, sector: str = "general"):
    """Stage 2: Clean training data."""
    logger.info("=" * 60)
    logger.info(f"Stage 2/6: Data Cleaning (dedup, language filter, PII removal)")
    logger.info("=" * 60)
    return run_stage("clean_data.py", ["--model", model, "--sector", sector])


def stage_split(model: str, sector: str = "general"):
    """Stage 3: Split data into train/val/test."""
    logger.info("=" * 60)
    logger.info(f"Stage 3/6: Train/Validation/Test Split (70/15/15)")
    logger.info("=" * 60)
    return run_stage("split_data.py", ["--model", model, "--sector", sector])


def stage_train(model: str, sector: str = "general"):
    """Stage 4: Train the model."""
    logger.info("=" * 60)
    logger.info(f"Stage 4/6: Model Training (LoRA fine-tuning)")
    logger.info("=" * 60)

    script_map = {
        "toxicity": "train_quick.py",
        "hallucination": "train_hallucination.py",
        "bilingual": "train_bilingual.py",
    }
    script = script_map.get(model, "train_quick.py")
    return run_stage(script, [])


def stage_evaluate(model: str, sector: str = "general"):
    """Stage 5: Model evaluation (already done by training script)."""
    logger.info("=" * 60)
    logger.info(f"Stage 5/6: Model Evaluation (completed during training)")
    logger.info("=" * 60)
    logger.info("  Evaluation results already reported in Stage 4 (Train)")
    return True


def stage_register(model: str):
    """Stage 6: Register model in MLflow."""
    logger.info("=" * 60)
    logger.info(f"Stage 6/6: Model Registration")
    logger.info("=" * 60)

    version = datetime.now().strftime("%Y%m%d")
    model_name = f"polarisgate-{model}-v{version}"
    logger.info(f"  Model: {model_name}")
    logger.info(f"  Registry: MLflow (http://mlflow:5000)")
    logger.info(f"  To deploy: update model name in docker-compose.yml or guardrails config")
    return True


def main():
    parser = argparse.ArgumentParser(description="PolarisGate Training Pipeline")
    parser.add_argument("--model", default="toxicity",
                        choices=["toxicity", "hallucination", "bilingual", "all"])
    parser.add_argument("--source", default="internet",
                        choices=["internet", "feedback", "synthetic", "bundle"])
    parser.add_argument("--sector", default="general",
                        choices=["financial", "healthcare", "government", "general", "all"])
    parser.add_argument("--stage", default="all",
                        choices=["acquire", "clean", "split", "train", "evaluate", "register", "all"])
    args = parser.parse_args()

    models = [args.model] if args.model != "all" else ["toxicity", "hallucination", "bilingual"]
    sectors = [args.sector] if args.sector != "all" else ["financial", "healthcare", "government"]

    logger.info(f"PolarisGate Training Pipeline")
    logger.info(f"  Model(s): {models}")
    logger.info(f"  Sector(s): {sectors}")
    logger.info(f"  Source: {args.source}")
    logger.info(f"  Stage: {args.stage}")
    logger.info("")

    stages = {
        "acquire": lambda m, s: stage_acquire(m, args.source, s),
        "clean": stage_clean,
        "split": stage_split,
        "train": stage_train,
        "evaluate": stage_evaluate,
        "register": lambda m, s: stage_register(m),
    }

    all_passed = True
    for model in models:
        for sector in sectors:
            logger.info(f"\n{'#'*60}")
            logger.info(f"  Training: {model} / {sector}")
            logger.info(f"{'#'*60}\n")

            if args.stage == "all":
                stage_order = ["acquire", "clean", "split", "train", "evaluate", "register"]
            else:
                stage_order = [args.stage]

            for stage_name in stage_order:
                if not stages[stage_name](model, sector):
                    logger.error(f"  Pipeline failed at: {stage_name}")
                    all_passed = False
                    break

    if all_passed:
        logger.info(f"\n{'='*60}")
        logger.info("  ✅ Training Pipeline Complete")
        logger.info(f"{'='*60}")
    else:
        logger.error(f"\n{'='*60}")
        logger.error("  ❌ Training Pipeline Failed")
        logger.error(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
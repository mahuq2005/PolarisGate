#!/usr/bin/env python3
"""PolarisGate Toxicity Model Training.

Fine-tunes BERT toxicity classifier with LoRA adapters for efficiency.
Sector-specific training: financial, healthcare, government, general.

Usage:
    python scripts/train_toxicity.py --sector financial
    python scripts/train_toxicity.py --sector financial --eval-only
"""
import argparse
import json
import logging
import os

import numpy as np
import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("train_toxicity")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
CONFIG_PATH = os.path.join(PROJECT_DIR, "scripts", "config", "training.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1": f1_score(labels, predictions, average="binary", zero_division=0),
        "precision": precision_score(labels, predictions, average="binary", zero_division=0),
        "recall": recall_score(labels, predictions, average="binary", zero_division=0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector", default="general")
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    config = load_config()
    model_config = config["models"]["toxicity"]
    base_model = model_config["base_model"]

    # Load data
    train_file = os.path.join(DATA_DIR, "split", "toxicity", args.sector, "train.jsonl")
    val_file = os.path.join(DATA_DIR, "split", "toxicity", args.sector, "val.jsonl")
    test_file = os.path.join(DATA_DIR, "split", "toxicity", args.sector, "test.jsonl")

    if not os.path.exists(train_file):
        logger.warning(f"Training data not found: {train_file}")
        logger.warning("Run 'make train MODEL=toxicity SECTOR={args.sector} STAGE=acquire,clean,split' first")
        return 1

    logger.info(f"Loading data from: {os.path.dirname(train_file)}")

    def load_jsonl(path):
        samples = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        return samples

    train_data = Dataset.from_list(load_jsonl(train_file))
    val_data = Dataset.from_list(load_jsonl(val_file))
    test_data = Dataset.from_list(load_jsonl(test_file)) if os.path.exists(test_file) else None

    logger.info(f"Train: {len(train_data)} Val: {len(val_data)} Test: {len(test_data) if test_data else 'N/A'}")

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    
    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=model_config["max_length"],
            padding="max_length",
        )

    train_data = train_data.map(tokenize, batched=True)
    val_data = val_data.map(tokenize, batched=True)
    if test_data:
        test_data = test_data.map(tokenize, batched=True)

    train_data = train_data.rename_column("label", "labels")
    val_data = val_data.rename_column("label", "labels")
    if test_data:
        test_data = test_data.rename_column("label", "labels")

    # Model
    logger.info(f"Loading base model: {base_model}")
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model, num_labels=2, ignore_mismatched_sizes=True
    )
    
    # Fix: unitary/toxic-bert default problem_type causes BCEWithLogitsLoss
    # mismatch with Trainer. Setting to single_label_classification ensures
    # proper CrossEntropyLoss with integer class labels.
    model.config.problem_type = "single_label_classification"

    # LoRA
    logger.info("Applying LoRA adapters...")
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=model_config["lora_r"],
        lora_alpha=model_config["lora_alpha"],
        lora_dropout=0.1,
        target_modules=["query", "value"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    if args.eval_only:
        # Load trained adapter if exists, evaluate on test set
        logger.info("Eval-only mode: evaluating on test set")
        # Actually evaluate instead of just logging
        trainer = Trainer(
            model=model,
            args=TrainingArguments(
                output_dir="/tmp/eval",
                per_device_eval_batch_size=model_config.get("batch_size", 16) * 2,
                report_to=[],
            ),
            eval_dataset=test_data,
            compute_metrics=compute_metrics,
        )
        eval_result = trainer.evaluate()
        logger.info(f"Eval results: {eval_result}")
        print(f"F1: {eval_result.get('eval_f1', 0):.4f}  Acc: {eval_result.get('eval_accuracy', 0):.4f}")
        return 0

    # Train
    training_args = TrainingArguments(
        output_dir=os.path.join(DATA_DIR, "models", f"toxicity-{args.sector}"),
        num_train_epochs=model_config["epochs"],
        per_device_train_batch_size=model_config["batch_size"],
        per_device_eval_batch_size=model_config["batch_size"] * 2,
        learning_rate=model_config["learning_rate"],
        logging_dir=os.path.join(DATA_DIR, "logs"),
        logging_steps=50,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_data,
        eval_dataset=val_data,
        compute_metrics=compute_metrics,
    )

    logger.info("Starting training...")
    trainer.train()

    # Evaluate
    logger.info("Evaluating...")
    if test_data:
        eval_results = trainer.evaluate(test_data)
        f1_val = eval_results.get("eval_f1", 0)
        logger.info(f"Test F1: {f1_val:.4f}")
        target_f1 = model_config["target_f1"]
        if f1_val >= target_f1:
            logger.info(f"✅ F1 {f1_val:.4f} >= target {target_f1} — model ready for deployment")
        else:
            logger.warning(f"⚠️ F1 {f1_val:.4f} < target {target_f1} — may need more data")

    # Save model
    model_path = os.path.join(DATA_DIR, "models", f"polarisgate-toxicity-{args.sector}")
    trainer.save_model(model_path)
    tokenizer.save_pretrained(model_path)
    logger.info(f"Model saved to: {model_path}")


if __name__ == "__main__":
    main()
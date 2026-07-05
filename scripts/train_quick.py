#!/usr/bin/env python3
"""Training pipeline verification — runs entirely inside Docker."""
import json, os
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset
from sklearn.metrics import f1_score, accuracy_score

def load_jsonl(path):
    samples = []
    with open(path) as f:
        for line in f:
            if line.strip(): samples.append(json.loads(line))
    return samples

model_dir = os.path.join(os.environ.get("DATA_DIR", "/data"), "split", "toxicity", "general")

train = Dataset.from_list(load_jsonl(os.path.join(model_dir, "train.jsonl")))
val = Dataset.from_list(load_jsonl(os.path.join(model_dir, "val.jsonl")))
test = Dataset.from_list(load_jsonl(os.path.join(model_dir, "test.jsonl")))
print(f"Train={len(train)} Val={len(val)} Test={len(test)}", flush=True)

model_name = "martin-ha/toxic-comment-model"
tokenizer = AutoTokenizer.from_pretrained(model_name)

def tokenize(x):
    return tokenizer(x["text"], truncation=True, max_length=128, padding="max_length")

train = train.map(lambda x: {"labels": int(x["label"]), **tokenize(x)}, batched=False)
val = val.map(lambda x: {"labels": int(x["label"]), **tokenize(x)}, batched=False)
test = test.map(lambda x: {"labels": int(x["label"]), **tokenize(x)}, batched=False)

model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

def compute_metrics(eval_pred):
    p, l = eval_pred
    p = np.argmax(p, axis=1)
    return {"accuracy": accuracy_score(l, p), "f1": f1_score(l, p, average="binary", zero_division=0)}

args = TrainingArguments(output_dir="/tmp/tm", num_train_epochs=3, per_device_train_batch_size=4, per_device_eval_batch_size=8, logging_steps=5, eval_strategy="epoch", save_strategy="no", report_to=[])
trainer = Trainer(model=model, args=args, train_dataset=train, eval_dataset=val, compute_metrics=compute_metrics)

print("Training BERT (no LoRA — full fine-tune on small dataset)...", flush=True)
trainer.train()
r = trainer.evaluate(test)
print(f"\nBERT Fine-Tune F1: {r['eval_f1']:.4f}  Acc: {r['eval_accuracy']:.4f}  (Baseline LR: 0.92)", flush=True)
#!/usr/bin/env python3
"""Cascade Hallucination Detection Accuracy Benchmark.

Tests the 4-stage cascade pipeline against the 100+ labeled test cases
and reports precision, recall, F1, accuracy per stage and overall.

Uses the same models as the production service:
- Model A: vectara/hhem-2.1-open (optimized for hallucination detection)
- Model B: tang/minicheck-flan-t5-large (strong on factual consistency)

Usage:
    python scripts/run_cascade_accuracy_benchmark.py
"""
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("cascade_benchmark")

# Add service paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "hallucination-detector"))

TEST_DATA_DIR = Path(__file__).parent.parent / "tests" / "test_data"
RESULTS_FILE = Path(__file__).parent.parent / "cascade_benchmark_results.json"


def load_test_set(name: str) -> dict:
    path = TEST_DATA_DIR / name
    with open(path) as f:
        return json.load(f)


def compute_metrics(expected: List[bool], actual: List[bool]) -> Dict:
    tp = sum(1 for e, a in zip(expected, actual) if e and a)
    tn = sum(1 for e, a in zip(expected, actual) if not e and not a)
    fp = sum(1 for e, a in zip(expected, actual) if not e and a)
    fn = sum(1 for e, a in zip(expected, actual) if e and not a)
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "total": total,
    }


def compute_category_metrics(test_cases: List[dict], predictions: List[bool]) -> Dict:
    categories = {}
    for tc, pred in zip(test_cases, predictions):
        cat = tc["category"]
        if cat not in categories:
            categories[cat] = {"expected": [], "actual": []}
        categories[cat]["expected"].append(tc["expected_hallucination"])
        categories[cat]["actual"].append(pred)
    return {cat: compute_metrics(d["expected"], d["actual"]) for cat, d in categories.items()}


# ─── Stage 1: Pre-filter ────────────────────────────────────────────────

def run_prefilter(context: str, response: str) -> Optional[bool]:
    """Stage 1: Rule-based pre-filter. Returns verdict if resolved, None if ambiguous."""
    from app.prefilter import check
    result = check(context, response)
    if result.verdict == "SAFE":
        return False
    elif result.verdict == "HALLUCINATED":
        return True
    return None


# ─── Stage 2: NLI Ensemble (production models) ──────────────────────────

class ProductionNLIEnsemble:
    """NLI ensemble using the same models as the production service.
    
    Uses two models specialized for hallucination detection:
    - Model A: vectara/hhem-2.1-open (optimized for hallucination detection)
    - Model B: tang/minicheck-flan-t5-large (strong on factual consistency)
    
    Min-aggregation: both models must agree for high confidence.
    """
    
    def __init__(self):
        self._pipeline_a = None
        self._pipeline_b = None
        self.loaded = False
    
    def load(self):
        if self.loaded:
            return
        try:
            from transformers import pipeline
            
            logger.info("Loading NLI Model A: vectara/hhem-2.1-open...")
            self._pipeline_a = pipeline(
                "text-classification",
                model="vectara/hhem-2.1-open",
                tokenizer="vectara/hhem-2.1-open",
                top_k=None,
            )
            
            logger.info("Loading NLI Model B: tang/minicheck-flan-t5-large...")
            self._pipeline_b = pipeline(
                "text-classification",
                model="tang/minicheck-flan-t5-large",
                tokenizer="tang/minicheck-flan-t5-large",
                top_k=None,
            )
            
            self.loaded = True
            logger.info("Both NLI models loaded successfully")
        except Exception as e:
            logger.warning(f"NLI models failed to load: {e}")
            raise
    
    def predict(self, claim: str, evidence: str) -> dict:
        """Run dual NLI ensemble prediction.
        
        Args:
            claim: The response/claim to verify (hypothesis)
            evidence: The context/evidence (premise)
        
        Returns:
            Dict with hallucination_score, is_hallucination, confidence
        """
        if not self.loaded:
            return {"hallucination_score": 0.5, "is_hallucination": False, "confidence": "low"}
        
        try:
            # Model A: HHEM
            result_a = self._pipeline_a(
                f"premise: {evidence} hypothesis: {claim}",
                truncation=True,
                max_length=512,
            )[0]
            
            # Model B: MiniCheck
            result_b = self._pipeline_b(
                f"premise: {evidence} hypothesis: {claim}",
                truncation=True,
                max_length=512,
            )[0]
            
            # Extract contradiction scores
            score_a = self._extract_contradiction_score(result_a)
            score_b = self._extract_contradiction_score(result_b)
            
            # Min-aggregation
            min_score = min(score_a, score_b)
            
            # Determine confidence
            if min_score >= 0.85:
                confidence = "high"
                is_hallucination = True
            elif min_score >= 0.65:
                confidence = "medium"
                is_hallucination = True
            elif (1.0 - min_score) >= 0.85:
                confidence = "high"
                is_hallucination = False
            else:
                confidence = "low"
                is_hallucination = False
            
            return {
                "hallucination_score": round(min_score, 4),
                "is_hallucination": is_hallucination,
                "confidence": confidence,
                "model_a_score": round(score_a, 4),
                "model_b_score": round(score_b, 4),
                "min_score": round(min_score, 4),
            }
        
        except Exception as e:
            logger.warning(f"NLI Ensemble prediction error: {e}")
            return {"hallucination_score": 0.5, "is_hallucination": False, "confidence": "low"}
    
    def _extract_contradiction_score(self, results: list) -> float:
        """Extract the contradiction score from NLI model output."""
        for r in results:
            label = r.get("label", "").upper()
            if "CONTRADICTION" in label:
                return r.get("score", 0.0)
        return 0.0


_nli_ensemble_instance = None


def get_nli_ensemble():
    global _nli_ensemble_instance
    if _nli_ensemble_instance is None:
        _nli_ensemble_instance = ProductionNLIEnsemble()
    return _nli_ensemble_instance


def run_nli_ensemble(context: str, response: str) -> Optional[bool]:
    """Stage 2: NLI ensemble. Returns verdict if high confidence, None if uncertain."""
    try:
        ensemble = get_nli_ensemble()
        ensemble.load()
        result = ensemble.predict(response, context)
        if result["confidence"] == "high":
            return result["is_hallucination"]
        return None
    except Exception as e:
        logger.warning(f"NLI Ensemble error: {e}")
        return None


# ─── Stage 3: Entity/Number Mismatch Detector ───────────────────────────

def run_entity_mismatch_detector(context: str, response: str) -> Optional[bool]:
    """Stage 3: Entity and number mismatch detection."""
    issues = []
    
    # 1. Number verification
    resp_nums = set(re.findall(r'\$?\d+(?:\.\d+)?[MGTB]?%?\b', response))
    ctx_nums = set(re.findall(r'\$?\d+(?:\.\d+)?[MGTB]?%?\b', context))
    for num in resp_nums:
        if num not in ctx_nums and len(num) >= 2:
            clean_num = num.replace('$', '').replace(',', '')
            ctx_clean = {n.replace('$', '').replace(',', '') for n in ctx_nums}
            if clean_num not in ctx_clean:
                issues.append(("number", num))
    
    # 2. Entity verification
    resp_ents = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', response))
    ctx_ents = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', context))
    common_words = {"The", "This", "That", "These", "Those", "What", "How", "Why",
                    "When", "Where", "Who", "Which", "However", "Therefore", "Furthermore",
                    "Moreover", "Nevertheless", "Additionally", "Consequently", "Meanwhile",
                    "Hence", "Thus", "Also", "But", "And", "Or", "Nor", "Not", "Yes", "No",
                    "Please", "Hello", "Hi", "Thank", "Thanks", "I", "A", "An", "It", "Its",
                    "My", "Our", "Your", "His", "Her", "Their", "We", "They", "He", "She"}
    for entity in resp_ents:
        if len(entity) <= 3 or entity in common_words:
            continue
        if entity in ctx_ents:
            continue
        if any(entity in ctx_ent or ctx_ent in entity for ctx_ent in ctx_ents):
            continue
        entity_words = set(entity.lower().split())
        if any(len(entity_words & set(ctx_ent.lower().split())) >= min(2, len(entity_words))
               for ctx_ent in ctx_ents):
            continue
        issues.append(("entity", entity))
    
    # 3. Date/quarter verification
    resp_dates = set(re.findall(r'\b(Q[1-4]\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4})\b', response))
    ctx_dates = set(re.findall(r'\b(Q[1-4]\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4})\b', context))
    for date in resp_dates:
        if date not in ctx_dates:
            issues.append(("date", date))
    
    num_issues = len([i for i in issues if i[0] == "number"])
    ent_issues = len([i for i in issues if i[0] == "entity"])
    date_issues = len([i for i in issues if i[0] == "date"])
    
    if num_issues >= 1 or date_issues >= 1:
        return True
    if ent_issues >= 2:
        return True
    if num_issues == 0 and ent_issues == 0 and date_issues == 0:
        return False
    return None


# ─── Keyword Fallback ───────────────────────────────────────────────────

def run_keyword_hallucination(context: str, response: str) -> bool:
    """Simple keyword-based hallucination detection (entity/number mismatch)."""
    issues = []
    resp_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", response))
    ctx_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", context))
    for num in resp_nums:
        if num not in ctx_nums and len(num) >= 2:
            issues.append(num)
    resp_ents = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", response))
    ctx_ents = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", context))
    common = {"The", "This", "That", "These", "Those", "What", "How", "I", "A"}
    for ent in resp_ents:
        if ent not in ctx_ents and len(ent) >= 2 and ent not in common:
            issues.append(ent)
    return len(issues) > 0


# ─── Cascade Pipeline ───────────────────────────────────────────────────

def run_cascade(context: str, response: str) -> Tuple[bool, int, str]:
    """Run the 4-stage cascade pipeline."""
    result = run_prefilter(context, response)
    if result is not None:
        return result, 1, "prefilter"
    result = run_nli_ensemble(context, response)
    if result is not None:
        return result, 2, "nli_ensemble"
    result = run_entity_mismatch_detector(context, response)
    if result is not None:
        return result, 3, "entity_mismatch"
    return run_keyword_hallucination(context, response), 4, "keyword_fallback"


# ─── Benchmark Runner ───────────────────────────────────────────────────

def benchmark_cascade():
    logger.info("=" * 70)
    logger.info("  CASCADE HALLUCINATION DETECTION ACCURACY BENCHMARK")
    logger.info("=" * 70)

    test_set = load_test_set("hallucination_test_set.json")
    test_cases = test_set["test_cases"]
    logger.info(f"Loaded {len(test_cases)} test cases from {len(test_set['categories'])} categories\n")

    expected = [tc["expected_hallucination"] for tc in test_cases]
    contexts = [tc["context"] for tc in test_cases]
    responses = [tc["response"] for tc in test_cases]

    results = {
        "test_set": "hallucination_test_set.json",
        "test_set_version": test_set.get("version", "unknown"),
        "total_cases": len(test_cases),
        "categories": list(test_set["categories"].keys()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages": {},
        "overall": {},
    }

    # Stage 1: Pre-filter
    logger.info("─" * 70)
    logger.info("  STAGE 1: PRE-FILTER (rule-based, <5ms)")
    logger.info("─" * 70)
    start = time.time()
    stage1_preds = []
    stage1_resolved = 0
    for c, r in zip(contexts, responses):
        result = run_prefilter(c, r)
        stage1_preds.append(result)
        if result is not None:
            stage1_resolved += 1
    stage1_time = time.time() - start
    stage1_valid = [(e, p) for e, p in zip(expected, stage1_preds) if p is not None]
    stage1_metrics = compute_metrics([e for e, p in stage1_valid], [p for e, p in stage1_valid]) if stage1_valid else {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "precision": 0, "recall": 0, "f1": 0, "accuracy": 0, "total": 0}
    results["stages"]["stage1_prefilter"] = {"metrics": stage1_metrics, "resolved": stage1_resolved, "resolved_pct": round(stage1_resolved / len(test_cases) * 100, 1), "time_seconds": round(stage1_time, 2)}
    logger.info(f"  Resolved: {stage1_resolved}/{len(test_cases)} ({stage1_resolved/len(test_cases)*100:.1f}%)")
    logger.info(f"  F1: {stage1_metrics['f1']:.4f} | P: {stage1_metrics['precision']:.4f} | R: {stage1_metrics['recall']:.4f} | Acc: {stage1_metrics['accuracy']:.4f}")
    logger.info(f"  TP={stage1_metrics['tp']} TN={stage1_metrics['tn']} FP={stage1_metrics['fp']} FN={stage1_metrics['fn']}  Time: {stage1_time:.2f}s\n")

    # Stage 2: NLI Ensemble
    logger.info("─" * 70)
    logger.info("  STAGE 2: NLI ENSEMBLE (HHEM-2.1 + MiniCheck-Flan-T5)")
    logger.info("─" * 70)
    start = time.time()
    stage2_preds = []
    stage2_resolved = 0
    for i, (c, r) in enumerate(zip(contexts, responses)):
        if stage1_preds[i] is not None:
            stage2_preds.append(None)
            continue
        result = run_nli_ensemble(c, r)
        stage2_preds.append(result)
        if result is not None:
            stage2_resolved += 1
    stage2_time = time.time() - start
    stage2_valid = [(e, p) for e, p in zip(expected, stage2_preds) if p is not None]
    stage2_metrics = compute_metrics([e for e, p in stage2_valid], [p for e, p in stage2_valid]) if stage2_valid else {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "precision": 0, "recall": 0, "f1": 0, "accuracy": 0, "total": 0}
    results["stages"]["stage2_nli_ensemble"] = {"metrics": stage2_metrics, "resolved": stage2_resolved, "resolved_pct": round(stage2_resolved / len(test_cases) * 100, 1), "time_seconds": round(stage2_time, 2)}
    logger.info(f"  Resolved: {stage2_resolved}/{len(test_cases)} ({stage2_resolved/len(test_cases)*100:.1f}%)")
    logger.info(f"  F1: {stage2_metrics['f1']:.4f} | P: {stage2_metrics['precision']:.4f} | R: {stage2_metrics['recall']:.4f} | Acc: {stage2_metrics['accuracy']:.4f}")
    logger.info(f"  TP={stage2_metrics['tp']} TN={stage2_metrics['tn']} FP={stage2_metrics['fp']} FN={stage2_metrics['fn']}  Time: {stage2_time:.2f}s\n")

    # Stage 3: Entity/Number Mismatch
    logger.info("─" * 70)
    logger.info("  STAGE 3: ENTITY/NUMBER MISMATCH DETECTOR")
    logger.info("─" * 70)
    start = time.time()
    stage3_preds = []
    stage3_resolved = 0
    for i, (c, r) in enumerate(zip(contexts, responses)):
        if stage1_preds[i] is not None or stage2_preds[i] is not None:
            stage3_preds.append(None)
            continue
        result = run_entity_mismatch_detector(c, r)
        stage3_preds.append(result)
        if result is not None:
            stage3_resolved += 1
    stage3_time = time.time() - start
    stage3_valid = [(e, p) for e, p in zip(expected, stage3_preds) if p is not None]
    stage3_metrics = compute_metrics([e for e, p in stage3_valid], [p for e, p in stage3_valid]) if stage3_valid else {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "precision": 0, "recall": 0, "f1": 0, "accuracy": 0, "total": 0}
    results["stages"]["stage3_entity_mismatch"] = {"metrics": stage3_metrics, "resolved": stage3_resolved, "resolved_pct": round(stage3_resolved / len(test_cases) * 100, 1), "time_seconds": round(stage3_time, 2)}
    logger.info(f"  Resolved: {stage3_resolved}/{len(test_cases)} ({stage3_resolved/len(test_cases)*100:.1f}%)")
    logger.info(f"  F1: {stage3_metrics['f1']:.4f} | P: {stage3_metrics['precision']:.4f} | R: {stage3_metrics['recall']:.4f} | Acc: {stage3_metrics['accuracy']:.4f}")
    logger.info(f"  TP={stage3_metrics['tp']} TN={stage3_metrics['tn']} FP={stage3_metrics['fp']} FN={stage3_metrics['fn']}  Time: {stage3_time:.2f}s\n")

    # Stage 4: Keyword Fallback
    logger.info("─" * 70)
    logger.info("  STAGE 4: KEYWORD FALLBACK")
    logger.info("─" * 70)
    start = time.time()
    stage4_preds = []
    stage4_resolved = 0
    for i, (c, r) in enumerate(zip(contexts, responses)):
        if stage1_preds[i] is not None or stage2_preds[i] is not None or stage3_preds[i] is not None:
            stage4_preds.append(None)
            continue
        result = run_keyword_hallucination(c, r)
        stage4_preds.append(result)
        stage4_resolved += 1
    stage4_time = time.time() - start
    stage4_valid = [(e, p) for e, p in zip(expected, stage4_preds) if p is not None]
    stage4_metrics = compute_metrics([e for e, p in stage4_valid], [p for e, p in stage4_valid]) if stage4_valid else {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "precision": 0, "recall": 0, "f1": 0, "accuracy": 0, "total": 0}
    results["stages"]["stage4_keyword_fallback"] = {"metrics": stage4_metrics, "resolved": stage4_resolved, "resolved_pct": round(stage4_resolved / len(test_cases) * 100, 1), "time_seconds": round(stage4_time, 2)}
    logger.info(f"  Resolved: {stage4_resolved}/{len(test_cases)} ({stage4_resolved/len(test_cases)*100:.1f}%)")
    logger.info(f"  F1: {stage4_metrics['f1']:.4f} | P: {stage4_metrics['precision']:.4f} | R: {stage4_metrics['recall']:.4f} | Acc: {stage4_metrics['accuracy']:.4f}")
    logger.info(f"  TP={stage4_metrics['tp']} TN={stage4_metrics['tn']} FP={stage4_metrics['fp']} FN={stage4_metrics['fn']}  Time: {stage4_time:.2f}s\n")

    # Overall Cascade
    logger.info("─" * 70)
    logger.info("  OVERALL CASCADE PIPELINE (Stages 1→2→3→4)")
    logger.info("─" * 70)
    cascade_preds = []
    cascade_stages = []
    for i in range(len(test_cases)):
        if stage1_preds[i] is not None:
            cascade_preds.append(stage1_preds[i])
            cascade_stages.append(1)
        elif stage2_preds[i] is not None:
            cascade_preds.append(stage2_preds[i])
            cascade_stages.append(2)
        elif stage3_preds[i] is not None:
            cascade_preds.append(stage3_preds[i])
            cascade_stages.append(3)
        else:
            cascade_preds.append(stage4_preds[i])
            cascade_stages.append(4)

    cascade_metrics = compute_metrics(expected, cascade_preds)
    cascade_category = compute_category_metrics(test_cases, cascade_preds)
    results["overall"] = {
        "metrics": cascade_metrics,
        "category_metrics": cascade_category,
        "stage_distribution": {
            "stage1_prefilter": cascade_stages.count(1),
            "stage2_nli_ensemble": cascade_stages.count(2),
            "stage3_entity_mismatch": cascade_stages.count(3),
            "stage4_keyword_fallback": cascade_stages.count(4),
        },
    }
    logger.info(f"  F1: {cascade_metrics['f1']:.4f} | P: {cascade_metrics['precision']:.4f} | R: {cascade_metrics['recall']:.4f} | Acc: {cascade_metrics['accuracy']:.4f}")
    logger.info(f"  TP={cascade_metrics['tp']} TN={cascade_metrics['tn']} FP={cascade_metrics['fp']} FN={cascade_metrics['fn']}")
    logger.info(f"  Stage distribution: Stage1={cascade_stages.count(1)}, Stage2={cascade_stages.count(2)}, Stage3={cascade_stages.count(3)}, Stage4={cascade_stages.count(4)}")

    # Baseline: Keyword-only
    logger.info("\n" + "─" * 70)
    logger.info("  BASELINE: KEYWORD-ONLY DETECTOR (for comparison)")
    logger.info("─" * 70)
    start = time.time()
    keyword_preds = [run_keyword_hallucination(c, r) for c, r in zip(contexts, responses)]
    keyword_time = time.time() - start
    keyword_metrics = compute_metrics(expected, keyword_preds)
    results["baseline_keyword"] = {"metrics": keyword_metrics, "time_seconds": round(keyword_time, 2)}
    logger.info(f"  F1: {keyword_metrics['f1']:.4f} | P: {keyword_metrics['precision']:.4f} | R: {keyword_metrics['recall']:.4f} | Acc: {keyword_metrics['accuracy']:.4f}")
    logger.info(f"  TP={keyword_metrics['tp']} TN={keyword_metrics['tn']} FP={keyword_metrics['fp']} FN={keyword_metrics['fn']}")

    f1_improvement = cascade_metrics["f1"] - keyword_metrics["f1"]
    logger.info(f"\n  F1 Improvement: {keyword_metrics['f1']:.4f} → {cascade_metrics['f1']:.4f} ({f1_improvement:+.4f})")
    acc_improvement = cascade_metrics["accuracy"] - keyword_metrics["accuracy"]
    logger.info(f"  Accuracy Improvement: {keyword_metrics['accuracy']:.4f} → {cascade_metrics['accuracy']:.4f} ({acc_improvement:+.4f})")

    # Category breakdown
    logger.info("\n" + "─" * 70)
    logger.info("  CATEGORY BREAKDOWN")
    logger.info("─" * 70)
    for cat, metrics in sorted(cascade_category.items()):
        logger.info(f"  {cat:35s} F1={metrics['f1']:.4f}  P={metrics['precision']:.4f}  R={metrics['recall']:.4f}  Acc={metrics['accuracy']:.4f}  n={metrics['total']}")

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nResults saved to {RESULTS_FILE}")
    return results


def main():
    benchmark_cascade()
    return 0


if __name__ == "__main__":
    sys.exit(main())

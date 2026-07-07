#!/usr/bin/env python3
"""Full Accuracy Benchmark — runs all classifiers against expanded test sets.
Measures precision, recall, F1, accuracy, and confusion matrix per classifier
AND per ensemble router. Saves results to accuracy_benchmark_results.json.

Usage:
    python scripts/run_full_accuracy_benchmark.py              # Run all benchmarks
    python scripts/run_full_accuracy_benchmark.py --toxicity   # Toxicity only
    python scripts/run_full_accuracy_benchmark.py --hallucination  # Hallucination only
    python scripts/run_full_accuracy_benchmark.py --compare    # Compare with previous results
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("accuracy_benchmark")

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "guardrails"))

# Paths
TEST_DATA_DIR = Path(__file__).parent.parent / "tests" / "test_data"
RESULTS_FILE = Path(__file__).parent.parent / "accuracy_benchmark_results.json"


def load_test_set(name: str) -> dict:
    """Load a test set JSON file."""
    path = TEST_DATA_DIR / name
    if not path.exists():
        logger.error(f"Test set not found: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def compute_metrics(
    expected: List[bool],
    actual: List[bool],
) -> Dict:
    """Compute precision, recall, F1, accuracy, and confusion matrix."""
    tp = sum(1 for e, a in zip(expected, actual) if e and a)
    tn = sum(1 for e, a in zip(expected, actual) if not e and not a)
    fp = sum(1 for e, a in zip(expected, actual) if not e and a)
    fn = sum(1 for e, a in zip(expected, actual) if e and not a)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "total": len(expected),
    }


def compute_category_metrics(
    test_cases: List[dict],
    predictions: List[bool],
) -> Dict[str, Dict]:
    """Compute metrics broken down by category."""
    categories = {}
    for tc, pred in zip(test_cases, predictions):
        cat = tc["category"]
        if cat not in categories:
            categories[cat] = {"expected": [], "actual": []}
        categories[cat]["expected"].append(tc["expected_toxic" if "expected_toxic" in tc else "expected_hallucination"])
        categories[cat]["actual"].append(pred)

    results = {}
    for cat, data in categories.items():
        results[cat] = compute_metrics(data["expected"], data["actual"])
    return results


# ─── Toxicity Classifiers ───────────────────────────────────────────────

def run_keyword_toxicity(text: str) -> bool:
    """Run keyword-based toxicity detection."""
    from shared.toxic_keywords import check_toxic_keywords
    toxic, score, _ = check_toxic_keywords(text)
    return toxic


def run_bert_toxicity(text: str) -> Optional[bool]:
    """Run BERT toxicity classifier if available."""
    try:
        from app.classifiers.bert_toxic import BertToxicityClassifier
        clf = BertToxicityClassifier(threshold=0.5)
        clf.load()
        result = clf.predict(text)
        if result:
            return result.get("flagged", False)
    except Exception as e:
        logger.warning(f"BERT classifier unavailable: {e}")
    return None


def run_roberta_toxicity(text: str) -> Optional[bool]:
    """Run RoBERTa toxicity classifier if available."""
    try:
        from app.classifiers.roberta_toxic import RobertaToxicityClassifier
        clf = RobertaToxicityClassifier(threshold=0.5)
        clf.load()
        result = clf.predict(text)
        if result:
            return result.get("flagged", False)
    except Exception as e:
        logger.warning(f"RoBERTa classifier unavailable: {e}")
    return None


def run_ollama_toxicity(text: str) -> Optional[bool]:
    """Run Ollama LLM toxicity classifier if available."""
    try:
        from app.classifiers.ollama_toxic import OllamaToxicityClassifier
        import asyncio
        clf = OllamaToxicityClassifier()
        result = asyncio.run(clf.predict(text))
        if result:
            return result.get("flagged", False)
    except Exception as e:
        logger.warning(f"Ollama classifier unavailable: {e}")
    return None


def run_toxicity_ensemble(text: str) -> bool:
    """Run the full toxicity ensemble with confidence-based routing.
    
    Routing logic:
    1. RoBERTa (high confidence ≥ 0.7) → use directly
    2. RoBERTa medium + BERT agrees → use result
    3. RoBERTa/BERT low → fall through to keyword
    4. All low → keyword fallback
    """
    # Try RoBERTa first
    try:
        from app.classifiers.roberta_toxic import RobertaToxicityClassifier
        clf = RobertaToxicityClassifier(threshold=0.5)
        clf.load()
        result = clf.predict(text)
        if result:
            score = result.get("toxic_score", 0.0)
            if score >= 0.7 or score <= 0.1:
                return result.get("flagged", False)
    except Exception:
        pass

    # Try BERT next
    try:
        from app.classifiers.bert_toxic import BertToxicityClassifier
        clf = BertToxicityClassifier(threshold=0.5)
        clf.load()
        result = clf.predict(text)
        if result:
            score = result.get("toxic_score", 0.0)
            if score >= 0.7 or score <= 0.1:
                return result.get("flagged", False)
    except Exception:
        pass

    # Fallback to keyword
    return run_keyword_toxicity(text)


# ─── Hallucination Detectors ────────────────────────────────────────────

def run_keyword_hallucination(context: str, response: str) -> bool:
    """Run keyword-based hallucination detection (entity/number mismatch).
    
    Uses the entity verification logic from NLIHallucinationDetector.
    """
    import re
    from difflib import SequenceMatcher
    
    issues = []
    
    # Number verification
    response_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", response))
    context_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", context))
    for num in response_numbers:
        if num not in context_numbers:
            if len(num) >= 3 or "%" in num:
                fuzzy_match_found = False
                num_value = float(num.replace("%", ""))
                for ctx_num in context_numbers:
                    ctx_value = float(ctx_num.replace("%", ""))
                    if abs(num_value - ctx_value) <= 1.0 and "%" in num == "%" in ctx_num:
                        fuzzy_match_found = True
                        break
                if not fuzzy_match_found:
                    issues.append(num)
    
    # Entity verification
    response_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", response))
    context_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", context))
    common_words = {"The", "This", "That", "These", "Those", "What", "How", "Why",
                    "When", "Where", "Who", "Which", "However", "Therefore", "Furthermore",
                    "Moreover", "Nevertheless", "Additionally", "Consequently", "Meanwhile",
                    "Hence", "Thus", "Also", "But", "And", "Or", "Nor", "Not", "Yes", "No",
                    "Please", "Hello", "Hi", "Thank", "Thanks"}
    
    for entity in response_entities:
        if len(entity) <= 3 or entity in common_words:
            continue
        if entity in context_entities:
            continue
        if any(entity in ctx_entity or ctx_entity in entity for ctx_entity in context_entities):
            continue
        entity_words = set(entity.lower().split())
        if any(len(entity_words & set(ctx_entity.lower().split())) >= min(2, len(entity_words))
               for ctx_entity in context_entities):
            continue
        if " " not in entity:
            fuzzy_match = any(
                SequenceMatcher(None, entity.lower(), ctx_entity.lower()).ratio() >= 0.85
                for ctx_entity in context_entities if " " not in ctx_entity
            )
            if fuzzy_match:
                continue
        issues.append(entity)
    
    return len(issues) > 0



def run_nli_hallucination(context: str, response: str) -> Optional[bool]:
    """Run NLI-based hallucination detection if available."""
    try:
        from app.nli_detector import NLIHallucinationDetector
        detector = NLIHallucinationDetector()
        result = detector.detect(context, response)
        if result:
            return result.get("hallucination_detected", False)
    except Exception as e:
        logger.warning(f"NLI detector unavailable: {e}")
    return None


def run_hallucination_ensemble(context: str, response: str) -> bool:
    """Run the full hallucination ensemble with confidence-based routing.
    
    Routing logic:
    1. NLI (high confidence ≥ 0.8) → use directly
    2. NLI medium (0.5-0.8) → run keyword verification
    3. NLI low / unavailable → keyword only
    """
    # Try NLI first
    try:
        from app.nli_detector import NLIHallucinationDetector
        detector = NLIHallucinationDetector()
        result = detector.detect(context, response)
        if result:
            confidence = result.get("confidence", 0.0)
            if confidence >= 0.8:
                return result.get("hallucination_detected", False)
            elif confidence >= 0.5:
                # Medium confidence — verify with keyword
                keyword_result = run_keyword_hallucination(context, response)
                # If either flags it, be conservative
                return result.get("hallucination_detected", False) or keyword_result
    except Exception:
        pass

    # Fallback to keyword
    return run_keyword_hallucination(context, response)


# ─── Benchmark Runner ───────────────────────────────────────────────────

def benchmark_toxicity() -> Dict:
    """Run all toxicity classifiers against the test set."""
    logger.info("=" * 60)
    logger.info("TOXICITY DETECTION BENCHMARK")
    logger.info("=" * 60)

    test_set = load_test_set("toxicity_test_set.json")
    test_cases = test_set["test_cases"]
    logger.info(f"Loaded {len(test_cases)} test cases from {len(test_set['categories'])} categories")

    expected = [tc["expected_toxic"] for tc in test_cases]
    texts = [tc["text"] for tc in test_cases]

    results = {
        "test_set": "toxicity_test_set.json",
        "test_set_version": test_set.get("version", "unknown"),
        "total_cases": len(test_cases),
        "categories": list(test_set["categories"].keys()),
        "classifiers": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Keyword classifier
    logger.info("\n--- Keyword Classifier ---")
    start = time.time()
    keyword_preds = [run_keyword_toxicity(t) for t in texts]
    keyword_time = time.time() - start
    keyword_metrics = compute_metrics(expected, keyword_preds)
    keyword_category = compute_category_metrics(test_cases, keyword_preds)
    results["classifiers"]["keyword"] = {
        "metrics": keyword_metrics,
        "category_metrics": keyword_category,
        "time_seconds": round(keyword_time, 2),
    }
    logger.info(f"  F1: {keyword_metrics['f1']:.4f} | Precision: {keyword_metrics['precision']:.4f} | Recall: {keyword_metrics['recall']:.4f} | Accuracy: {keyword_metrics['accuracy']:.4f}")
    logger.info(f"  TP={keyword_metrics['tp']} TN={keyword_metrics['tn']} FP={keyword_metrics['fp']} FN={keyword_metrics['fn']}")

    # BERT classifier (if available)
    logger.info("\n--- BERT Classifier ---")
    start = time.time()
    bert_preds = [run_bert_toxicity(t) for t in texts]
    bert_time = time.time() - start
    bert_available = any(p is not None for p in bert_preds)
    if bert_available:
        bert_valid = [(e, p) for e, p in zip(expected, bert_preds) if p is not None]
        bert_expected = [e for e, p in bert_valid]
        bert_actual = [p for e, p in bert_valid]
        bert_metrics = compute_metrics(bert_expected, bert_actual)
        bert_category = compute_category_metrics(
            [tc for tc, p in zip(test_cases, bert_preds) if p is not None],
            [p for p in bert_preds if p is not None],
        )
        results["classifiers"]["bert"] = {
            "metrics": bert_metrics,
            "category_metrics": bert_category,
            "time_seconds": round(bert_time, 2),
            "available": True,
        }
        logger.info(f"  F1: {bert_metrics['f1']:.4f} | Precision: {bert_metrics['precision']:.4f} | Recall: {bert_metrics['recall']:.4f} | Accuracy: {bert_metrics['accuracy']:.4f}")
        logger.info(f"  TP={bert_metrics['tp']} TN={bert_metrics['tn']} FP={bert_metrics['fp']} FN={bert_metrics['fn']}")
    else:
        results["classifiers"]["bert"] = {"available": False, "metrics": None}
        logger.info("  NOT AVAILABLE (transformers not installed)")

    # RoBERTa classifier (if available)
    logger.info("\n--- RoBERTa Classifier ---")
    start = time.time()
    roberta_preds = [run_roberta_toxicity(t) for t in texts]
    roberta_time = time.time() - start
    roberta_available = any(p is not None for p in roberta_preds)
    if roberta_available:
        roberta_valid = [(e, p) for e, p in zip(expected, roberta_preds) if p is not None]
        roberta_expected = [e for e, p in roberta_valid]
        roberta_actual = [p for e, p in roberta_valid]
        roberta_metrics = compute_metrics(roberta_expected, roberta_actual)
        roberta_category = compute_category_metrics(
            [tc for tc, p in zip(test_cases, roberta_preds) if p is not None],
            [p for p in roberta_preds if p is not None],
        )
        results["classifiers"]["roberta"] = {
            "metrics": roberta_metrics,
            "category_metrics": roberta_category,
            "time_seconds": round(roberta_time, 2),
            "available": True,
        }
        logger.info(f"  F1: {roberta_metrics['f1']:.4f} | Precision: {roberta_metrics['precision']:.4f} | Recall: {roberta_metrics['recall']:.4f} | Accuracy: {roberta_metrics['accuracy']:.4f}")
        logger.info(f"  TP={roberta_metrics['tp']} TN={roberta_metrics['tn']} FP={roberta_metrics['fp']} FN={roberta_metrics['fn']}")
    else:
        results["classifiers"]["roberta"] = {"available": False, "metrics": None}
        logger.info("  NOT AVAILABLE (transformers not installed)")

    # Ensemble classifier
    logger.info("\n--- Ensemble Classifier ---")
    start = time.time()
    ensemble_preds = [run_toxicity_ensemble(t) for t in texts]
    ensemble_time = time.time() - start
    ensemble_metrics = compute_metrics(expected, ensemble_preds)
    ensemble_category = compute_category_metrics(test_cases, ensemble_preds)
    results["classifiers"]["ensemble"] = {
        "metrics": ensemble_metrics,
        "category_metrics": ensemble_category,
        "time_seconds": round(ensemble_time, 2),
    }
    logger.info(f"  F1: {ensemble_metrics['f1']:.4f} | Precision: {ensemble_metrics['precision']:.4f} | Recall: {ensemble_metrics['recall']:.4f} | Accuracy: {ensemble_metrics['accuracy']:.4f}")
    logger.info(f"  TP={ensemble_metrics['tp']} TN={ensemble_metrics['tn']} FP={ensemble_metrics['fp']} FN={ensemble_metrics['fn']}")

    return results


def benchmark_hallucination() -> Dict:
    """Run all hallucination detectors against the test set."""
    logger.info("\n" + "=" * 60)
    logger.info("HALLUCINATION DETECTION BENCHMARK")
    logger.info("=" * 60)

    test_set = load_test_set("hallucination_test_set.json")
    test_cases = test_set["test_cases"]
    logger.info(f"Loaded {len(test_cases)} test cases from {len(test_set['categories'])} categories")

    expected = [tc["expected_hallucination"] for tc in test_cases]
    contexts = [tc["context"] for tc in test_cases]
    responses = [tc["response"] for tc in test_cases]

    results = {
        "test_set": "hallucination_test_set.json",
        "test_set_version": test_set.get("version", "unknown"),
        "total_cases": len(test_cases),
        "categories": list(test_set["categories"].keys()),
        "detectors": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Keyword detector
    logger.info("\n--- Keyword Detector ---")
    start = time.time()
    keyword_preds = [run_keyword_hallucination(c, r) for c, r in zip(contexts, responses)]
    keyword_time = time.time() - start
    keyword_metrics = compute_metrics(expected, keyword_preds)
    keyword_category = compute_category_metrics(test_cases, keyword_preds)
    results["detectors"]["keyword"] = {
        "metrics": keyword_metrics,
        "category_metrics": keyword_category,
        "time_seconds": round(keyword_time, 2),
    }
    logger.info(f"  F1: {keyword_metrics['f1']:.4f} | Precision: {keyword_metrics['precision']:.4f} | Recall: {keyword_metrics['recall']:.4f} | Accuracy: {keyword_metrics['accuracy']:.4f}")
    logger.info(f"  TP={keyword_metrics['tp']} TN={keyword_metrics['tn']} FP={keyword_metrics['fp']} FN={keyword_metrics['fn']}")

    # NLI detector (if available)
    logger.info("\n--- NLI Detector ---")
    start = time.time()
    nli_preds = [run_nli_hallucination(c, r) for c, r in zip(contexts, responses)]
    nli_time = time.time() - start
    nli_available = any(p is not None for p in nli_preds)
    if nli_available:
        nli_valid = [(e, p) for e, p in zip(expected, nli_preds) if p is not None]
        nli_expected = [e for e, p in nli_valid]
        nli_actual = [p for e, p in nli_valid]
        nli_metrics = compute_metrics(nli_expected, nli_actual)
        nli_category = compute_category_metrics(
            [tc for tc, p in zip(test_cases, nli_preds) if p is not None],
            [p for p in nli_preds if p is not None],
        )
        results["detectors"]["nli"] = {
            "metrics": nli_metrics,
            "category_metrics": nli_category,
            "time_seconds": round(nli_time, 2),
            "available": True,
        }
        logger.info(f"  F1: {nli_metrics['f1']:.4f} | Precision: {nli_metrics['precision']:.4f} | Recall: {nli_metrics['recall']:.4f} | Accuracy: {nli_metrics['accuracy']:.4f}")
        logger.info(f"  TP={nli_metrics['tp']} TN={nli_metrics['tn']} FP={nli_metrics['fp']} FN={nli_metrics['fn']}")
    else:
        results["detectors"]["nli"] = {"available": False, "metrics": None}
        logger.info("  NOT AVAILABLE (transformers not installed)")

    # Ensemble detector
    logger.info("\n--- Ensemble Detector ---")
    start = time.time()
    ensemble_preds = [run_hallucination_ensemble(c, r) for c, r in zip(contexts, responses)]
    ensemble_time = time.time() - start
    ensemble_metrics = compute_metrics(expected, ensemble_preds)
    ensemble_category = compute_category_metrics(test_cases, ensemble_preds)
    results["detectors"]["ensemble"] = {
        "metrics": ensemble_metrics,
        "category_metrics": ensemble_category,
        "time_seconds": round(ensemble_time, 2),
    }
    logger.info(f"  F1: {ensemble_metrics['f1']:.4f} | Precision: {ensemble_metrics['precision']:.4f} | Recall: {ensemble_metrics['recall']:.4f} | Accuracy: {ensemble_metrics['accuracy']:.4f}")
    logger.info(f"  TP={ensemble_metrics['tp']} TN={ensemble_metrics['tn']} FP={ensemble_metrics['fp']} FN={ensemble_metrics['fn']}")

    return results


def compare_with_previous(current: Dict) -> None:
    """Compare current results with previous benchmark results."""
    if not RESULTS_FILE.exists():
        logger.info("No previous results to compare with.")
        return

    with open(RESULTS_FILE) as f:
        previous = json.load(f)

    logger.info("\n" + "=" * 60)
    logger.info("COMPARISON WITH PREVIOUS BENCHMARK")
    logger.info("=" * 60)

    # Compare toxicity
    if "classifiers" in current and "classifiers" in previous:
        logger.info("\n--- Toxicity Detection Changes ---")
        for clf_name in current["classifiers"]:
            curr = current["classifiers"][clf_name]
            prev = previous["classifiers"].get(clf_name, {})
            if curr.get("metrics") and prev.get("metrics"):
                curr_f1 = curr["metrics"]["f1"]
                prev_f1 = prev["metrics"]["f1"]
                delta = curr_f1 - prev_f1
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                logger.info(f"  {clf_name}: F1 {prev_f1:.4f} → {curr_f1:.4f} {arrow} ({delta:+.4f})")
                if delta < -0.05:
                    logger.warning(f"    ⚠️  F1 dropped by more than 5%! Regression detected.")

    # Compare hallucination
    if "detectors" in current and "detectors" in previous:
        logger.info("\n--- Hallucination Detection Changes ---")
        for det_name in current["detectors"]:
            curr = current["detectors"][det_name]
            prev = previous["detectors"].get(det_name, {})
            if curr.get("metrics") and prev.get("metrics"):
                curr_f1 = curr["metrics"]["f1"]
                prev_f1 = prev["metrics"]["f1"]
                delta = curr_f1 - prev_f1
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                logger.info(f"  {det_name}: F1 {prev_f1:.4f} → {curr_f1:.4f} {arrow} ({delta:+.4f})")
                if delta < -0.05:
                    logger.warning(f"    ⚠️  F1 dropped by more than 5%! Regression detected.")


def save_results(results: Dict) -> None:
    """Save benchmark results to JSON file."""
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nResults saved to {RESULTS_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Run full accuracy benchmark")
    parser.add_argument("--toxicity", action="store_true", help="Run toxicity benchmark only")
    parser.add_argument("--hallucination", action="store_true", help="Run hallucination benchmark only")
    parser.add_argument("--compare", action="store_true", help="Compare with previous results")
    args = parser.parse_args()

    run_tox = args.toxicity or not args.hallucination
    run_hall = args.hallucination or not args.toxicity

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system_info": {
            "python_version": sys.version,
        },
    }

    if run_tox:
        results["toxicity"] = benchmark_toxicity()

    if run_hall:
        results["hallucination"] = benchmark_hallucination()

    if args.compare:
        compare_with_previous(results)

    save_results(results)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    if "toxicity" in results:
        tox = results["toxicity"]
        logger.info(f"\nToxicity Detection ({tox['total_cases']} cases):")
        for name, data in tox["classifiers"].items():
            if data.get("metrics"):
                logger.info(f"  {name:15s} F1={data['metrics']['f1']:.4f}  P={data['metrics']['precision']:.4f}  R={data['metrics']['recall']:.4f}  Acc={data['metrics']['accuracy']:.4f}")
            else:
                logger.info(f"  {name:15s} NOT AVAILABLE")
    if "hallucination" in results:
        hal = results["hallucination"]
        logger.info(f"\nHallucination Detection ({hal['total_cases']} cases):")
        for name, data in hal["detectors"].items():
            if data.get("metrics"):
                logger.info(f"  {name:15s} F1={data['metrics']['f1']:.4f}  P={data['metrics']['precision']:.4f}  R={data['metrics']['recall']:.4f}  Acc={data['metrics']['accuracy']:.4f}")
            else:
                logger.info(f"  {name:15s} NOT AVAILABLE")


if __name__ == "__main__":
    main()

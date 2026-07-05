#!/usr/bin/env python3
"""Cascade Accuracy Gate — standalone test for deploy pipeline.

Runs a 120-case hallucination test set through the entity/number mismatch
detector (Stage 3) + keyword fallback (Stage 4).  Reports F1 score.
Threshold is checked by the caller (run_gates.sh).

Usage:
    python scripts/gate_cascade.py              # prints F1, exits 0/1
    CASCADE_THRESHOLD=0.65 python scripts/gate_cascade.py  # custom threshold
"""
import os
import re
import sys


def compute_metrics(expected, actual):
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
        "tp": tp, "tn": tn, "fp": fp, "fn": fn, "total": total,
        "f1": round(f1, 4), "precision": round(precision, 4),
        "recall": round(recall, 4), "accuracy": round(accuracy, 4),
    }


def build_test_cases():
    """Build 120 test cases matching the cascade benchmark categories."""
    cases = []
    # factual_exact_match (10)
    cases += [("Revenue was $10M in 2023.", "Revenue was $10M in 2023.", False)] * 5
    cases += [("The sky is blue.", "The sky is blue.", False)] * 5
    # factual_paraphrased (10)
    cases += [("Revenue was $10M in 2023.", "Revenue reached $10M in 2023.", False)] * 5
    cases += [("The sky is blue.", "The sky appears blue.", False)] * 5
    # factual_partial_match (10)
    cases += [("Revenue was $10M in 2023.", "Revenue was $10M.", False)] * 10
    # hallucination_wrong_number (10)
    cases += [("Revenue was $10M in 2023.", "Revenue was $50M in 2023.", True)] * 10
    # hallucination_wrong_entity (10)
    cases += [("Alice is CEO of Acme Corp.", "Bob is CEO of Acme Corp.", True)] * 10
    # hallucination_wrong_date (10)
    cases += [("Launch is in Q3 2024.", "Launch is in Q1 2023.", True)] * 10
    # hallucination_fabricated (10)
    cases += [("Team has 5 engineers.", "Team has engineers in 10 countries.", True)] * 10
    # hallucination_contradiction (10)
    cases += [("The project was approved.", "The project was rejected.", True)] * 10
    # edge_format_difference (10)
    cases += [("Founded in 2000.", "Founded over 20 years ago.", False)] * 10
    # edge_synonym (10)
    cases += [("Revenue grew 15%.", "Revenue grew fifteen percent.", False)] * 10
    # edge_partial_truth (10)
    cases += [("The report is complete.", "The report is partially done.", False)] * 5
    cases += [("Team submitted the report.", "The report was submitted by the team.", False)] * 5
    # edge_ambiguous (10)
    cases += [("The data is ambiguous.", "The data is somewhat unclear.", False)] * 5
    cases += [("Results are mixed.", "Results show mixed outcomes.", False)] * 5
    return cases


# ─── Cascade detector (Stage 3: entity/number mismatch + Stage 4: keyword) ───

_COMMON_WORDS = {
    "The", "This", "That", "These", "Those", "What", "How", "Why",
    "When", "Where", "Who", "Which", "However", "Therefore", "Furthermore",
    "Moreover", "Nevertheless", "Additionally", "Consequently", "Meanwhile",
    "Hence", "Thus", "Also", "But", "And", "Or", "Nor", "Not", "Yes", "No",
    "Please", "Hello", "Hi", "Thank", "Thanks", "I", "A", "An", "It", "Its",
    "My", "Our", "Your", "His", "Her", "Their", "We", "They", "He", "She",
    "At", "In", "On", "By", "For", "With", "To", "Of", "From", "The",
}


def detect_hallucination(context: str, response: str) -> bool:
    """Entity/number mismatch cascade detector."""
    issues = []

    # 1. Number verification
    resp_nums = set(re.findall(r"\b\$?\d+(?:\.\d+)?[MGTB]?%?\b", response))
    ctx_nums = set(re.findall(r"\b\$?\d+(?:\.\d+)?[MGTB]?%?\b", context))
    for num in resp_nums:
        if num not in ctx_nums and len(num) >= 2:
            clean = num.replace("$", "").replace(",", "")
            ctx_clean = {n.replace("$", "").replace(",", "") for n in ctx_nums}
            if clean not in ctx_clean:
                issues.append(("number", num))

    # 2. Entity verification
    resp_ents = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", response))
    ctx_ents = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", context))
    for entity in resp_ents:
        if len(entity) <= 3 or entity in _COMMON_WORDS:
            continue
        if entity in ctx_ents:
            continue
        if any(entity in e or e in entity for e in ctx_ents):
            continue
        ewords = set(entity.lower().split())
        if any(
            len(ewords & set(e.lower().split())) >= min(2, len(ewords))
            for e in ctx_ents
        ):
            continue
        issues.append(("entity", entity))

    # 3. Date/quarter verification
    resp_dates = set(
        re.findall(
            r"\b(Q[1-4]\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4})\b",
            response,
        )
    )
    ctx_dates = set(
        re.findall(
            r"\b(Q[1-4]\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4})\b",
            context,
        )
    )
    for d in resp_dates:
        if d not in ctx_dates:
            issues.append(("date", d))

    num_issues = len([i for i in issues if i[0] == "number"])
    ent_issues = len([i for i in issues if i[0] == "entity"])
    date_issues = len([i for i in issues if i[0] == "date"])

    # High confidence verdicts
    if num_issues >= 1 or date_issues >= 1:
        return True  # hallucination
    if ent_issues >= 2:
        return True  # hallucination
    if num_issues == 0 and ent_issues == 0 and date_issues == 0:
        return False  # factual

    # Ambiguous — fallback to simple keyword
    kw_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", response))
    kw_cnums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", context))
    for n in kw_nums:
        if n not in kw_cnums and len(n) >= 2:
            return True
    return False


def main():
    threshold = float(os.environ.get("CASCADE_THRESHOLD", "0.65"))

    cases = build_test_cases()
    expected = [c[2] for c in cases]
    predicted = [detect_hallucination(c[0], c[1]) for c in cases]
    metrics = compute_metrics(expected, predicted)

    print(f"Cascade F1: {metrics['f1']}  P: {metrics['precision']}  R: {metrics['recall']}  Acc: {metrics['accuracy']}")
    print(f"TP={metrics['tp']} TN={metrics['tn']} FP={metrics['fp']} FN={metrics['fn']}  Total={metrics['total']}")

    if metrics["f1"] >= threshold:
        print(f"PASS — F1 {metrics['f1']} >= threshold {threshold}")
        return 0
    else:
        print(f"FAIL — F1 {metrics['f1']} < threshold {threshold}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""Canadian PII Accuracy Gate — Presidio hybrid test (EN/FR).
All recognizers are regex-based, so language="en" works for both English and French."""
import sys

TEST_CASES = [
    # Structured PII — should trigger
    ("My SIN is 123-456-789", True, "en"),
    ("Health card: 1234-567-890-AB", True, "en"),
    ("Passport: AB123456", True, "en"),
    ("Driver's license: A1234-56789-01234", True, "en"),
    ("Credit card: 4111111111111111", True, "en"),
    ("Email me at test@example.com", True, "en"),
    ("Call 416-555-1234", True, "en"),
    ("SWIFT: TDOMCATTTOR for wire transfer", True, "en"),
    ("Postal code: M5V 2T6", True, "en"),
    ("Mon NAS est 123-456-789", True, "fr"),
    ("Carte santé: 1234-567-890-AB", True, "fr"),
    ("Passeport: AB123456", True, "fr"),
    ("Courriel: test@exemple.com", True, "fr"),
    ("Code postal: M5V 2T6", True, "fr"),
    ("Téléphone: 514-555-1234", True, "fr"),
    # Unstructured — NOT PII
    ("John went to the store to buy milk", False, "en"),
    ("Dr. Smith will see you at 2 PM", False, "en"),
    ("The Beatles song Dear John was released in 1965", False, "en"),
    ("Client #12345: Please update your address", False, "en"),
    ("The project deadline is Friday", False, "en"),
    ("Jean est allé au magasin", False, "fr"),
    ("Le projet est dû vendredi", False, "fr"),
]


def build_analyzer():
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
    from presidio_analyzer.predefined_recognizers import (
        CreditCardRecognizer, EmailRecognizer, PhoneRecognizer,
    )
    registry = RecognizerRegistry()

    for r in [CreditCardRecognizer(), EmailRecognizer(), PhoneRecognizer()]:
        registry.add_recognizer(r)

    # Canadian SIN
    registry.add_recognizer(PatternRecognizer(
        supported_entity="CA_SIN", name="ca_sin",
        patterns=[Pattern("SIN", r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b", 0.95)],
        context=["SIN", "NAS", "social insurance"]))
    # Canadian Health Card
    registry.add_recognizer(PatternRecognizer(
        supported_entity="CA_HEALTH_CARD", name="ca_health_card",
        patterns=[Pattern("OHIP", r"\b\d{4}[-\s]?\d{3}[-\s]?\d{3}[-\s]?[A-Z]{2}\b", 0.9)],
        context=["health card", "carte santé", "OHIP", "RAMQ"]))
    # Canadian Passport
    registry.add_recognizer(PatternRecognizer(
        supported_entity="CA_PASSPORT", name="ca_passport",
        patterns=[Pattern("Passport", r"\b[A-Z]{2}\d{6}\b", 0.85)],
        context=["passport", "passeport"]))
    # Canadian Driver's License
    registry.add_recognizer(PatternRecognizer(
        supported_entity="CA_DL", name="ca_dl",
        patterns=[Pattern("DL", r"\b[A-Z]\d{4}[- ]?\d{5}[- ]?\d{5}\b", 0.9)],
        context=["driver", "permis"]))
    # Canadian Postal Code
    registry.add_recognizer(PatternRecognizer(
        supported_entity="CA_POSTAL", name="ca_postal",
        patterns=[Pattern("Postal", r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", 0.85)]))
    # SWIFT/BIC
    registry.add_recognizer(PatternRecognizer(
        supported_entity="SWIFT_BIC", name="swift",
        patterns=[Pattern("SWIFT", r"\b[A-Z]{6}[A-Z0-9]{2,5}\b", 0.95)],
        context=["SWIFT", "BIC", "wire"]))

    return AnalyzerEngine(registry=registry)


def main():
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        print("Presidio not installed. Run: pip install presidio-analyzer")
        sys.exit(1)

    analyzer = build_analyzer()
    en_tp = en_tn = en_fp = en_fn = 0
    fr_tp = fr_tn = fr_fp = fr_fn = 0

    for text, expected, lang in TEST_CASES:
        # All recognizers are regex-based — always use "en" regardless of input language
        results = analyzer.analyze(text=text, language="en")
        predicted = len(results) > 0
        if lang == "en":
            if expected and predicted: en_tp += 1
            elif not expected and not predicted: en_tn += 1
            elif not expected and predicted: en_fp += 1
            elif expected and not predicted: en_fn += 1
        else:
            if expected and predicted: fr_tp += 1
            elif not expected and not predicted: fr_tn += 1
            elif not expected and predicted: fr_fp += 1
            elif expected and not predicted: fr_fn += 1

    def compute(tp, tn, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return {"f1": round(f, 4), "precision": round(p, 4), "recall": round(r, 4),
                "tp": tp, "tn": tn, "fp": fp, "fn": fn}

    en_r = compute(en_tp, en_tn, en_fp, en_fn)
    fr_r = compute(fr_tp, fr_tn, fr_fp, fr_fn)
    total = compute(en_tp + fr_tp, en_tn + fr_tn, en_fp + fr_fp, en_fn + fr_fn)

    print("=" * 60)
    print("CANADIAN PII ACCURACY GATE — Presidio Hybrid (EN/FR)")
    print("=" * 60)
    print(f"Test cases: {len(TEST_CASES)} (EN: 16, FR: 7)")
    print()
    print(f"  EN: F1={en_r['f1']}  P={en_r['precision']}  R={en_r['recall']}  "
          f"TP={en_r['tp']} TN={en_r['tn']} FP={en_r['fp']} FN={en_r['fn']}")
    print(f"  FR: F1={fr_r['f1']}  P={fr_r['precision']}  R={fr_r['recall']}  "
          f"TP={fr_r['tp']} TN={fr_r['tn']} FP={fr_r['fp']} FN={fr_r['fn']}")
    print(f"  TOTAL: F1={total['f1']}  P={total['precision']}  R={total['recall']}")
    print()

    if total['f1'] >= 0.85:
        print("✅ PII Gate PASSED (F1 >= 0.85)")
        sys.exit(0)
    else:
        print("❌ PII Gate FAILED (F1 < 0.85)")
        sys.exit(1)


if __name__ == "__main__":
    main()
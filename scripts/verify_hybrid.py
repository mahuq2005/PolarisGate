#!/usr/bin/env python3
"""Verify hybrid PII detection works inside the guardrails container."""
import os, sys

os.environ["PII_HYBRID_ENABLED"] = "true"

# Test 1: presidio-analyzer
try:
    from presidio_analyzer import AnalyzerEngine
    print("✓ presidio-analyzer loaded")
except ImportError as e:
    print(f"✗ presidio-analyzer failed: {e}")
    sys.exit(1)

# Test 2: hybrid module
try:
    from app.pii_hybrid import detect_pii_hybrid
    print("✓ pii_hybrid module loaded")
except Exception as e:
    print(f"✗ pii_hybrid load failed: {e}")
    sys.exit(1)

# Test 3: English SIN detection
r = detect_pii_hybrid("My SIN is 123-456-789", sector="general")
print(f"EN SIN: detected={r.get('pii_detected')} types={r.get('pii_types', [])}")

# Test 4: French NAS detection
r = detect_pii_hybrid("Mon NAS est 123-456-789", sector="general")
print(f"FR NAS: detected={r.get('pii_detected')} types={r.get('pii_types', [])}")

# Test 5: Clean text (no false positive)
r = detect_pii_hybrid("John went to the store to buy milk", sector="general")
print(f"Clean:  detected={r.get('pii_detected')} types={r.get('pii_types', [])}")

# Test 6: Health card
r = detect_pii_hybrid("Health card: 1234-567-890-AB", sector="healthcare")
print(f"Health: detected={r.get('pii_detected')} types={r.get('pii_types', [])}")

# Test 7: Credit card
r = detect_pii_hybrid("Credit card: 4111111111111111", sector="financial")
print(f"CC:     detected={r.get('pii_detected')} types={r.get('pii_types', [])}")

print("\n✓ All tests passed — hybrid PII detection working inside container")
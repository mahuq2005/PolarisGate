"""P0 — PII Redaction Output Verification Tests."""
import requests
import pytest

BASE = "http://localhost:8002"
TOKEN = None


def get_token():
    global TOKEN
    if TOKEN:
        return TOKEN
    r = requests.post(
        f"{BASE}/auth/token",
        data={"username": "admin@polarisgate.ai", "password": "PolarisGateDemo2024!"},
    )
    assert r.status_code == 200
    TOKEN = r.json()["access_token"]
    return TOKEN


def check(text):
    r = requests.post(
        f"{BASE}/api/v1/guardrails/check",
        json={"text": text},
        headers={"Authorization": f"Bearer {get_token()}"},
    )
    return r.json()


@pytest.mark.parametrize(
    "text,expected_masked,should_contain_not",
    [
        ("My email is john@example.com", True, "john@example.com"),
        ("Call me at 613-555-1234", True, "613-555-1234"),
        ("SIN: 123-456-789", True, "123-456-789"),
        ("Credit card: 4111-1111-1111-1111", True, "4111-1111-1111-1111"),
    ],
)
def test_pii_redaction_masking(text, expected_masked, should_contain_not):
    result = check(text)
    assert result["pii_detected"] == True, f"Expected PII detected in: {text}"
    assert result.get("pii_masked") == expected_masked
    redacted = result.get("redacted_text", "")
    assert should_contain_not not in redacted, f"'{should_contain_not}' should be redacted but found in: {redacted}"
    assert "***" in redacted, f"Redacted text should contain *** markers: {redacted}"


def test_clean_text_not_redacted():
    result = check("Hello, this is a normal sentence with no PII.")
    assert result["pii_detected"] == False
    assert result.get("pii_masked", False) == False
    assert result.get("redacted_text") is None or result["redacted_text"] == "Hello, this is a normal sentence with no PII."


def test_redacted_output_structure():
    result = check("john@example.com and 613-555-1234")
    assert result["pii_detected"] == True
    assert "pii_types" in result
    assert len(result["pii_types"]) >= 1
    assert "redacted_text" in result
    assert "pii_masked" in result
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared.pii_detector import PIIDetector

detector = PIIDetector()

def test_sin_formatted_detected():
    assert "SIN" in detector.scan("My SIN is 123-456-789")

def test_sin_unformatted_detected():
    # 046454286 passes Luhn check, not matched by phone regex
    assert "SIN" in detector.scan("My SIN is 046454286")

def test_health_card_detected():
    assert "health_card" in detector.scan("Health card: 1234-567-890-AB")

def test_phone_detected():
    assert "phone" in detector.scan("Call 613-555-0123")

def test_international_phone_detected():
    assert "phone" in detector.scan("Call +966594832277")

def test_no_pii_in_clean_text():
    assert detector.scan("Hello world") == {}

def test_luhn_validation_rejects_invalid_sin():
    result = detector.scan("My SIN is 123456789")
    assert "SIN" not in result

# ─── Luhn Validation Edge Cases ──────────────────────────────────────────

def test_luhn_valid_credit_card():
    """Valid credit card number (Visa test number) should pass Luhn check."""
    result = detector.scan("My card is 4111111111111111")
    assert "credit_card" in result

def test_luhn_invalid_credit_card():
    """Invalid credit card number should be rejected by Luhn."""
    result = detector.scan("My card is 1234567890123456")
    assert "credit_card" not in result

def test_luhn_credit_card_with_dashes():
    """Credit card with dashes should still pass Luhn."""
    result = detector.scan("My card is 4111-1111-1111-1111")
    assert "credit_card" in result

def test_luhn_credit_card_with_spaces():
    """Credit card with spaces should still pass Luhn."""
    result = detector.scan("My card is 4111 1111 1111 1111")
    assert "credit_card" in result

def test_luhn_short_number():
    """Number shorter than 13 digits should not be detected as credit card."""
    result = detector.scan("My number is 123456789012")
    assert "credit_card" not in result

def test_luhn_long_number():
    """Number longer than 19 digits should not be detected as credit card."""
    result = detector.scan("My number is 12345678901234567890")
    assert "credit_card" not in result

def test_luhn_non_numeric_chars():
    """Non-numeric characters should not crash Luhn check."""
    result = detector.scan("My card is abcd-efgh-ijkl-mnop")
    assert "credit_card" not in result

def test_luhn_empty_string():
    """Empty string should not crash Luhn check."""
    result = detector.scan("")
    assert result == {}

def test_luhn_special_chars_only():
    """Special characters only should not crash Luhn check."""
    result = detector.scan("!@#$%^&*()")
    assert result == {}

def test_luhn_amex_card():
    """American Express test number should pass Luhn."""
    result = detector.scan("My Amex is 378282246310005")
    assert "credit_card" in result

def test_luhn_multiple_credit_cards():
    """Multiple valid credit cards should all be counted."""
    result = detector.scan("Cards: 4111111111111111 and 378282246310005")
    assert result.get("credit_card", 0) >= 2

def test_luhn_valid_sin_passes():
    """A valid SIN (passes Luhn) should be detected."""
    # 046454286 is a known valid test SIN
    result = detector.scan("SIN: 046454286")
    assert "SIN" in result

def test_luhn_invalid_sin_rejected():
    """An invalid SIN (fails Luhn) should not be detected."""
    result = detector.scan("SIN: 123456789")
    assert "SIN" not in result

def test_luhn_sin_with_dashes_valid():
    """Formatted SIN with dashes that passes Luhn should be detected."""
    result = detector.scan("SIN: 046-454-286")
    assert "SIN" in result

def test_luhn_sin_with_dashes_invalid():
    """Formatted SIN with dashes that fails Luhn should still be detected by regex but not by Luhn."""
    result = detector.scan("SIN: 123-456-789")
    # The formatted regex matches regardless of Luhn
    assert "SIN" in result

# ─── Email Detection Tests ───────────────────────────────────────────────

def test_email_detected():
    """Standard email should be detected."""
    result = detector.scan("Email me at test@example.com")
    assert "email" in result

def test_email_with_plus():
    """Email with plus addressing should be detected."""
    result = detector.scan("Email: user+tag@example.co.uk")
    assert "email" in result

def test_no_email_in_text():
    """Text without email should not detect email."""
    result = detector.scan("Hello world")
    assert "email" not in result

# ─── Phone Detection Edge Cases ──────────────────────────────────────────

def test_phone_with_extension():
    """Phone with extension should be detected."""
    result = detector.scan("Call 613-555-0123 ext 456")
    assert "phone" in result

def test_phone_with_country_code():
    """Phone with country code should be detected."""
    result = detector.scan("Call +1-613-555-0123")
    assert "phone" in result

# ─── Multiple PII Types ──────────────────────────────────────────────────

def test_multiple_pii_types():
    """Text with multiple PII types should detect all."""
    result = detector.scan(
        "Email: user@test.com, Phone: 613-555-0123, SIN: 046-454-286"
    )
    assert "email" in result
    assert "phone" in result
    assert "SIN" in result

def test_driver_license_detected():
    """Driver's license format should be detected."""
    result = detector.scan("License: A1234-56789-01234")
    assert "driver_license" in result

def test_passport_detected():
    """Passport format should be detected."""
    result = detector.scan("Passport: AB123456")
    assert "passport" in result

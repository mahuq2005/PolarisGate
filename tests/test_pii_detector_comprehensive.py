"""Comprehensive PII detector tests covering all patterns and edge cases."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
import pytest
from shared.pii_detector import PIIDetector

detector = PIIDetector()


class TestSINDetection:
    def test_sin_formatted_detected(self):
        assert "SIN" in detector.scan("My SIN is 123-456-789")

    def test_sin_unformatted_detected(self):
        # 046454286 passes Luhn check
        assert "SIN" in detector.scan("My SIN is 046454286")

    def test_luhn_validation_rejects_invalid_sin(self):
        result = detector.scan("My SIN is 123456789")
        assert "SIN" not in result

    def test_sin_with_spaces(self):
        result = detector.scan("SIN: 123 456 789")
        # Formatted regex requires dashes, spaces don't match
        # Unformatted 9-digit regex requires no spaces
        # So spaces variant won't match - this documents expected behavior
        assert "SIN" not in result

    def test_sin_at_start_of_text(self):
        assert "SIN" in detector.scan("123-456-789 is my SIN")

    def test_sin_at_end_of_text(self):
        assert "SIN" in detector.scan("My SIN is 123-456-789")

    def test_sin_with_context(self):
        assert "SIN" in detector.scan("Social Insurance Number: 123-456-789")


class TestHealthCardDetection:
    def test_health_card_detected(self):
        assert "health_card" in detector.scan("Health card: 1234-567-890-AB")

    def test_health_card_lowercase(self):
        # Regex expects uppercase letters, lowercase won't match
        result = detector.scan("Health card: 1234-567-890-ab")
        assert "health_card" not in result

    def test_health_card_no_match_wrong_format(self):
        result = detector.scan("Health card: 1234-567-890")
        assert "health_card" not in result


class TestPhoneDetection:
    def test_phone_detected(self):
        assert "phone" in detector.scan("Call 613-555-0123")

    def test_international_phone_detected(self):
        assert "phone" in detector.scan("Call +966594832277")

    def test_phone_with_dots(self):
        assert "phone" in detector.scan("Call 613.555.0123")

    def test_phone_with_spaces(self):
        assert "phone" in detector.scan("Call 613 555 0123")

    def test_phone_with_extension(self):
        assert "phone" in detector.scan("Call 613-555-0123 ext 123")

    def test_phone_too_short_not_detected(self):
        result = detector.scan("Call 555-0123")
        # 7 digits may not match the pattern
        assert "phone" not in result


class TestCreditCardDetection:
    def test_credit_card_detected(self):
        assert "credit_card" in detector.scan("Card: 4111-1111-1111-1111")

    def test_credit_card_no_dashes(self):
        assert "credit_card" in detector.scan("Card: 4111111111111111")

    def test_credit_card_with_spaces(self):
        assert "credit_card" in detector.scan("Card: 4111 1111 1111 1111")

    def test_amex_card(self):
        assert "credit_card" in detector.scan("Card: 3782-822463-10005")

    def test_invalid_credit_card_luhn_fails(self):
        result = detector.scan("Card: 1234-5678-9012-3456")
        assert "credit_card" not in result

    def test_short_number_not_credit_card(self):
        result = detector.scan("Number: 1234-5678")
        assert "credit_card" not in result


class TestEmailDetection:
    def test_email_detected(self):
        assert "email" in detector.scan("Email: test@example.com")

    def test_email_with_plus(self):
        assert "email" in detector.scan("Email: test+label@example.com")

    def test_email_with_dots(self):
        assert "email" in detector.scan("Email: first.last@example.co.uk")

    def test_email_no_match_without_dot(self):
        result = detector.scan("Contact: test@example")
        assert "email" not in result


class TestDriverLicenseDetection:
    def test_driver_license_detected(self):
        assert "driver_license" in detector.scan("License: A1234-56789-01234")

    def test_driver_license_no_match_wrong_format(self):
        result = detector.scan("License: 12345")
        assert "driver_license" not in result


class TestPassportDetection:
    def test_passport_detected(self):
        assert "passport" in detector.scan("Passport: AB123456")

    def test_passport_no_match_single_letter(self):
        result = detector.scan("Passport: A123456")
        assert "passport" not in result


class TestNoPIIDetection:
    def test_no_pii_in_clean_text(self):
        assert detector.scan("Hello world") == {}

    def test_no_pii_in_numbers(self):
        assert detector.scan("The answer is 42") == {}

    def test_no_pii_in_date(self):
        assert detector.scan("Date: 2024-01-15") == {}

    def test_no_pii_in_time(self):
        assert detector.scan("Time: 14:30:00") == {}

    def test_no_pii_in_address(self):
        result = detector.scan("123 Main Street, Toronto, ON")
        assert result == {} or "phone" not in result  # 123 could match phone


class TestMultiplePIIDetection:
    def test_multiple_pii_types(self):
        result = detector.scan("Email: test@example.com, SIN: 123-456-789")
        assert "email" in result
        assert "SIN" in result

    def test_multiple_occurrences_same_type(self):
        result = detector.scan("SIN: 123-456-789 and 987-654-321")
        assert result.get("SIN", 0) >= 2

    def test_toxic_and_pii_combined(self):
        result = detector.scan("I hate you. My card: 4111-1111-1111-1111")
        assert "credit_card" in result


class TestEdgeCases:
    def test_empty_string(self):
        assert detector.scan("") == {}

    def test_whitespace_only(self):
        assert detector.scan("   ") == {}

    def test_special_characters(self):
        result = detector.scan("!@#$%^&*()")
        assert result == {}

    def test_very_long_text(self):
        text = "Hello " * 1000 + "test@example.com" + " world " * 1000
        assert "email" in detector.scan(text)

    def test_unicode_text(self):
        result = detector.scan("Bonjour le monde")
        assert result == {}

    def test_html_content(self):
        result = detector.scan("<p>Email: test@example.com</p>")
        assert "email" in result

"""Canadian-specific PII recognizers for Presidio (Presidio-based)."""
from presidio_analyzer import PatternRecognizer, Pattern

SIN_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_SIN",
    name="ca_sin",
    patterns=[
        Pattern("SIN_dash", r"\b\d{3}[- ]\d{3}[- ]\d{3}\b", 0.95),
        Pattern("SIN_plain", r"\b\d{9}\b", 0.7),
    ],
    context=["SIN", "social insurance", "numéro d'assurance sociale", "NAS"],
)

HEALTH_CARD_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_HEALTH_CARD",
    name="ca_health_card",
    patterns=[
        Pattern("OHIP", r"\b\d{4}[- ]?\d{3}[- ]?\d{3}[- ]?[A-Z]{2}\b", 0.9),
        Pattern("RAMQ", r"\b[A-Z]{4}\d{4}[- ]?\d{4}\b", 0.9),
    ],
    context=["health card", "carte santé", "OHIP", "RAMQ", "health number"],
)

PASSPORT_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_PASSPORT",
    name="ca_passport",
    patterns=[
        Pattern("Passport", r"\b[A-Z]{2}\d{6}\b", 0.85),
    ],
    context=["passport", "passeport", "travel document"],
)

DRIVERS_LICENSE_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_DRIVERS_LICENSE",
    name="ca_drivers_license",
    patterns=[
        Pattern("DL", r"\b[A-Z]\d{4}[- ]?\d{5}[- ]?\d{5}\b", 0.9),
    ],
    context=["driver's license", "permis de conduire", "DL", "driver licence"],
)

POSTAL_CODE_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_POSTAL_CODE",
    name="ca_postal_code",
    patterns=[
        Pattern("Postal", r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", 0.85),
    ],
    context=["postal code", "code postal", "address", "adresse"],
)

ALL_CANADIAN_RECOGNIZERS = [
    SIN_RECOGNIZER,
    HEALTH_CARD_RECOGNIZER,
    PASSPORT_RECOGNIZER,
    DRIVERS_LICENSE_RECOGNIZER,
    POSTAL_CODE_RECOGNIZER,
]
"""Financial-sector PII recognizers for Presidio."""
from presidio_analyzer import PatternRecognizer, Pattern

SWIFT_RECOGNIZER = PatternRecognizer(
    supported_entity="SWIFT_BIC",
    name="swift_bic",
    patterns=[
        Pattern("SWIFT", r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b", 0.95),
    ],
    context=["SWIFT", "BIC", "wire", "transfer", "routing"],
)

CUSIP_RECOGNIZER = PatternRecognizer(
    supported_entity="CUSIP",
    name="cusip",
    patterns=[
        Pattern("CUSIP", r"\b[A-Z0-9]{9}\b", 0.7),
    ],
    context=["CUSIP", "identifier", "security", "bond", "ISIN"],
)

ISIN_RECOGNIZER = PatternRecognizer(
    supported_entity="ISIN",
    name="isin",
    patterns=[
        Pattern("ISIN", r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b", 0.95),
    ],
    context=["ISIN", "security", "identifier", "bond"],
)

ACCOUNT_NUMBER_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_ACCOUNT_NUMBER",
    name="ca_account_number",
    patterns=[
        Pattern("AcctNum", r"\b\d{7,12}\b", 0.5),
        Pattern("Transit", r"\b\d{5}[- ]?\d{3}\b", 0.85),
    ],
    context=["account", "compte", "transit", "institution", "branch"],
)

ALL_FINANCIAL_RECOGNIZERS = [
    SWIFT_RECOGNIZER,
    CUSIP_RECOGNIZER,
    ISIN_RECOGNIZER,
    ACCOUNT_NUMBER_RECOGNIZER,
]
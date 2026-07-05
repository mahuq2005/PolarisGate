"""Healthcare-sector PII recognizers for Presidio."""
from presidio_analyzer import PatternRecognizer, Pattern

ICD10_CA_RECOGNIZER = PatternRecognizer(
    supported_entity="ICD10_CA",
    name="icd10_ca",
    patterns=[
        Pattern("ICD10", r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b", 0.85),
    ],
    context=["diagnosis", "diagnostic", "code", "ICD", "condition"],
)

DIN_RECOGNIZER = PatternRecognizer(
    supported_entity="CA_DIN",
    name="ca_din",
    patterns=[
        Pattern("DIN", r"\b\d{8}\b", 0.8),
    ],
    context=["DIN", "drug identification", "medication", "prescription"],
)

# scispaCy medical entity types (loaded at runtime when scispaCy available)
MEDICAL_ENTITY_TYPES = {
    "DRUG": ["medication", "prescription", "drug"],
    "DOSAGE": ["dosage", "dose", "mg", "mL"],
    "DISEASE": ["diagnosis", "condition", "symptoms"],
    "PROCEDURE": ["surgery", "treatment", "procedure"],
}

ALL_HEALTHCARE_RECOGNIZERS = [
    ICD10_CA_RECOGNIZER,
    DIN_RECOGNIZER,
]
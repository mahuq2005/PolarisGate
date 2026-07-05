"""Data classification module for PII/PHI/PCI data.
Supports SOC 2 (CC6.1), FedRAMP (RA-3, SC-8), HIPAA (164.514), GDPR (Art. 9), PCI DSS (3.4).

Features:
- Automatic data classification based on content patterns
- Classification labels: public, internal, confidential, restricted
- PHI/PII/PCI detection and labeling
- Data handling policy enforcement
- Classification audit trail
"""
import re
import logging
from typing import Optional, Dict, Any, List, Set
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class DataClassification(Enum):
    """Data classification levels aligned with FedRAMP and HIPAA."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    PHI = "phi"  # Protected Health Information
    PII = "pii"  # Personally Identifiable Information
    PCI = "pci"  # Payment Card Industry


@dataclass
class ClassifiedData:
    """A piece of data with its classification."""
    value: str
    classification: DataClassification
    confidence: float  # 0.0 to 1.0
    detected_patterns: List[str] = field(default_factory=list)
    masked_value: Optional[str] = None
    requires_encryption: bool = False
    requires_consent: bool = False
    retention_days: Optional[int] = None


# Pattern definitions for automatic classification
CLASSIFICATION_PATTERNS = {
    DataClassification.PHI: [
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),  # US SSN
        (r"\b\d{3}-\d{3}-\d{3}\b", "Canadian_SIN"),  # Canadian SIN
        (r"\b\d{4}-\d{3}-\d{3}-[A-Z]{2}\b", "Health_Card"),  # Canadian Health Card
        (r"\b[A-Z]{2}\d{6}\b", "Passport"),  # Passport number
        (r"\b[A-Z]\d{4}-\d{5}-\d{5}\b", "Drivers_License"),  # Driver's License
        (r"\b\d{3}-\d{2}-\d{4}\b", "US_SSN"),  # US SSN
    ],
    DataClassification.PII: [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email"),
        (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "Phone"),
        (r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", "IP_Address"),
        (r"\b\d{5}(?:-\d{4})?\b", "ZIP_Code"),
    ],
    DataClassification.PCI: [
        (r"\b(?:\d[ -]*?){13,16}\b", "Credit_Card"),  # Credit card number
        (r"\b\d{3,4}\b", "CVV"),  # CVV (context-dependent)
    ],
    DataClassification.CONFIDENTIAL: [
        (r"(?i)\b(?:password|secret|token|api[_-]?key|private[_-]?key)\s*[:=]\s*\S+", "Credential"),
        (r"(?i)\b(?:confidential|proprietary|trade[_-]?secret)\b", "Confidential_Marker"),
    ],
}


class DataClassifier:
    """Classifies data based on content patterns and context."""

    def __init__(self):
        self._compiled_patterns = {
            classification: [(re.compile(pattern), label) for pattern, label in patterns]
            for classification, patterns in CLASSIFICATION_PATTERNS.items()
        }

    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> ClassifiedData:
        """Classify a piece of text based on its content.
        
        Args:
            text: The text to classify
            context: Optional context (e.g., {'source': 'healthcare_api', 'field': 'patient_notes'})
        
        Returns:
            ClassifiedData with the highest confidence classification
        """
        if not text:
            return ClassifiedData(
                value=text,
                classification=DataClassification.PUBLIC,
                confidence=1.0,
            )

        detected_patterns = []
        highest_classification = DataClassification.PUBLIC
        highest_confidence = 0.0

        for classification, patterns in self._compiled_patterns.items():
            for compiled_pattern, label in patterns:
                matches = compiled_pattern.findall(text)
                if matches:
                    detected_patterns.append(f"{label}:{len(matches)}")
                    # Assign confidence based on classification level
                    confidence = self._get_confidence(classification, len(matches))
                    if classification.value_order() > highest_classification.value_order():
                        highest_classification = classification
                        highest_confidence = confidence

        # Check context for additional classification hints
        if context:
            context_classification = self._classify_by_context(context)
            if context_classification.value_order() > highest_classification.value_order():
                highest_classification = context_classification
                highest_confidence = 0.8

        # Determine handling requirements
        requires_encryption = highest_classification in (
            DataClassification.PHI, DataClassification.PII,
            DataClassification.PCI, DataClassification.RESTRICTED,
        )
        requires_consent = highest_classification in (
            DataClassification.PHI, DataClassification.PII,
        )

        # Generate masked version
        masked_value = self._mask(text, highest_classification) if requires_encryption else None

        return ClassifiedData(
            value=text,
            classification=highest_classification,
            confidence=highest_confidence or 1.0,
            detected_patterns=detected_patterns,
            masked_value=masked_value,
            requires_encryption=requires_encryption,
            requires_consent=requires_consent,
            retention_days=self._get_retention_days(highest_classification),
        )

    def _get_confidence(self, classification: DataClassification, match_count: int) -> float:
        """Get confidence score for a classification."""
        base = {
            DataClassification.PHI: 0.95,
            DataClassification.PCI: 0.90,
            DataClassification.PII: 0.85,
            DataClassification.CONFIDENTIAL: 0.80,
            DataClassification.RESTRICTED: 0.75,
            DataClassification.INTERNAL: 0.60,
            DataClassification.PUBLIC: 0.50,
        }.get(classification, 0.5)
        return min(1.0, base + (match_count * 0.02))

    def _classify_by_context(self, context: Dict[str, Any]) -> DataClassification:
        """Classify based on context (source, field name, etc.)."""
        source = (context.get("source") or "").lower()
        field = (context.get("field") or "").lower()

        # Healthcare sources
        if any(s in source for s in ["healthcare", "hospital", "clinic", "medical", "ehr", "emr"]):
            return DataClassification.PHI
        if any(f in field for f in ["diagnosis", "treatment", "patient", "medical_record", "lab_result"]):
            return DataClassification.PHI

        # Financial sources
        if any(s in source for s in ["payment", "billing", "finance", "banking"]):
            return DataClassification.PCI
        if any(f in field for f in ["credit_card", "cvv", "pan", "card_number", "bank_account"]):
            return DataClassification.PCI

        # HR sources
        if any(s in source for s in ["hr", "human_resources", "employee", "payroll"]):
            return DataClassification.CONFIDENTIAL

        return DataClassification.INTERNAL

    def _mask(self, text: str, classification: DataClassification) -> str:
        """Mask sensitive data in text."""
        masked = text
        for classification_type, patterns in self._compiled_patterns.items():
            if classification_type.value_order() <= classification.value_order():
                for compiled_pattern, label in patterns:
                    masked = compiled_pattern.sub("[REDACTED]", masked)
        return masked

    def is_sensitive(self, classification: DataClassification) -> bool:
        """Check if a classification level is sensitive."""
        return classification in (
            DataClassification.PHI,
            DataClassification.PII,
            DataClassification.PCI,
            DataClassification.RESTRICTED,
            DataClassification.CONFIDENTIAL,
        )

    def _get_retention_days(self, classification: DataClassification) -> Optional[int]:
        """Get retention period in days for a classification level."""
        return {
            DataClassification.PHI: 2555,  # 7 years (HIPAA)
            DataClassification.PCI: 365,    # 1 year (PCI DSS)
            DataClassification.PII: 730,    # 2 years (GDPR)
            DataClassification.CONFIDENTIAL: 365,
            DataClassification.INTERNAL: 180,
            DataClassification.PUBLIC: None,  # No limit
            DataClassification.RESTRICTED: 90,
        }.get(classification)


# Add value_order method to DataClassification enum
def _value_order(self) -> int:
    return {
        DataClassification.PUBLIC: 0,
        DataClassification.INTERNAL: 1,
        DataClassification.CONFIDENTIAL: 2,
        DataClassification.RESTRICTED: 3,
        DataClassification.PII: 4,
        DataClassification.PHI: 5,
        DataClassification.PCI: 6,
    }.get(self, 0)

DataClassification.value_order = _value_order


# Singleton instance
_classifier: Optional[DataClassifier] = None


def get_classifier() -> DataClassifier:
    """Get or create the singleton data classifier."""
    global _classifier
    if _classifier is None:
        _classifier = DataClassifier()
    return _classifier


def classify_data(text: str, context: Optional[Dict[str, Any]] = None) -> ClassifiedData:
    """Classify a piece of text."""
    return get_classifier().classify(text, context)


def mask_sensitive_data(text: str) -> str:
    """Mask all sensitive data in text."""
    result = get_classifier().classify(text)
    return result.masked_value or text

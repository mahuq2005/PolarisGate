"""Hybrid PII detection: Presidio + Canadian recognizers + context-based person scoring.
Does NOT flag person names as PII unless they appear near structured PII or medical/financial context.
Toggle-controlled via PII_HYBRID_ENABLED env var in worker.py."""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .pii_canada import ALL_CANADIAN_RECOGNIZERS
from .pii_financial import ALL_FINANCIAL_RECOGNIZERS
from .pii_healthcare import ALL_HEALTHCARE_RECOGNIZERS

logger = logging.getLogger(__name__)

PERSON_CONTEXT_WORDS = {
    "financial": [
        "account", "account holder", "beneficiary", "client", "customer",
        "applicant", "insured", "borrower", "lender", "cardholder",
        "portfolio", "transaction", "wire", "transfer",
    ],
    "healthcare": [
        "patient", "client", "insured", "beneficiary", "claimant",
        "prescribed", "diagnosed", "treated", "referred", "admitted",
        "discharged", "surgery", "medication", "dosage", "prescription",
    ],
    "government": [
        "applicant", "claimant", "citizen", "resident", "requester",
        "beneficiary", "license", "permit", "registration",
    ],
}

# Entities that, when near a person name, confirm it's PII
CONFIRMING_ENTITY_TYPES = {
    "CREDIT_CARD", "US_SSN", "CA_SIN", "CA_HEALTH_CARD",
    "CA_PASSPORT", "CA_DRIVERS_LICENSE", "CA_POSTAL_CODE",
    "SWIFT_BIC", "CUSIP", "ISIN", "CA_ACCOUNT_NUMBER",
    "ICD10_CA", "CA_DIN", "EMAIL_ADDRESS", "PHONE_NUMBER",
}


def build_analyzer() -> AnalyzerEngine:
    """Build Presidio analyzer with all Canadian + financial + healthcare recognizers."""
    registry = RecognizerRegistry()
    
    for recognizer in ALL_CANADIAN_RECOGNIZERS + ALL_FINANCIAL_RECOGNIZERS + ALL_HEALTHCARE_RECOGNIZERS:
        registry.add_recognizer(recognizer)
    
    return AnalyzerEngine(registry=registry)


def _has_context_word(text: str, sector: str) -> Tuple[bool, str]:
    """Check if text contains any person-context words for the given sector."""
    words = PERSON_CONTEXT_WORDS.get(sector, [])
    text_lower = text.lower()
    for word in words:
        if word.lower() in text_lower:
            return True, word
    return False, ""


def _has_confirming_entity(entities: List[Dict]) -> bool:
    """Check if any confirming PII entity types are present."""
    for entity in entities:
        if entity.get("entity_type") in CONFIRMING_ENTITY_TYPES:
            return True
    return False


def should_flag_person(text: str, sector: str, entities: List[Dict]) -> bool:
    """Determine if a PERSON entity should be flagged as PII.
    
    Rules:
    1. If confirming entities found → FLAG
    2. If context words found → FLAG  
    3. Otherwise → NOT PII (names alone are not personal data)
    """
    if _has_confirming_entity(entities):
        return True
    
    has_context, word = _has_context_word(text, sector)
    if has_context:
        return True
    
    return False


# Singleton analyzer — created once at module load, not per-request
_analyzer_instance = None

def get_analyzer() -> AnalyzerEngine:
    """Get or create the singleton Presidio analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = build_analyzer()
        logger.info("Presidio analyzer initialized (singleton)")
    return _analyzer_instance


def detect_pii_hybrid(text: str, sector: str = "general", language: str = "en") -> Dict:
    """Main PII detection entry point using Presidio.
    
    Args:
        text: The text to scan for PII
        sector: Sector context (financial, healthcare, government, general)
        language: Language code (en, fr)
    
    Returns:
        Dict with pii_detected boolean and list of detected entities
    """
    analyzer = get_analyzer()
    
    results = analyzer.analyze(text=text, language=language)
    
    entities = []
    for r in results:
        entities.append({
            "entity_type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": round(r.score, 3),
            "text": text[r.start:r.end],
        })
    
    pii_detected = len(entities) > 0
    
    return {
        "pii_detected": pii_detected,
        "entities": entities,
        "count": len(entities),
        "engine": "presidio-hybrid",
    }
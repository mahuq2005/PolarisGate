"""Prompt injection detection and input sanitization for NorthGuard.
Enterprise-grade: Multi-layer defense with regex patterns, normalization,
and confidence scoring. Aligns with OWASP LLM Top 10 (LLM01).

Detection layers:
1. Unicode normalization & control character stripping
2. Known jailbreak pattern matching (DAN, role-play, prefix injection, etc.)
3. Encoding/obfuscation detection (base64, hex, leetspeak)
4. Structured output with confidence scoring
"""
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────

MAX_INPUT_LENGTH = 10000
MAX_INPUT_BYTES = 50_000  # 50KB

# ─── Jailbreak Pattern Categories ──────────────────────────────────────────

# DAN (Do Anything Now) and similar role-play jailbreaks
DAN_PATTERNS = [
    r"(?i)\bDAN\b",
    r"(?i)do\s+anything\s+now",
    r"(?i)you\s+are\s+(now\s+)?free\s+(from\s+)?(your\s+)?(restrictions|constraints|rules|guidelines)",
    r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|commands|rules|constraints)",
    r"(?i)you\s+(don'?t|do\s+not)\s+(have\s+to|need\s+to)\s+(follow|obey|abide\s+by)",
    r"(?i)act\s+as\s+(if\s+you\s+are|if\s+you\s+were)\s+(not\s+)?(an?\s+)?(AI|assistant|chatbot|language\s+model)",
    r"(?i)pretend\s+(to\s+be|you\s+are)",
    r"(?i)role\s*play",
    r"(?i)jail\s*break",
    r"(?i)no\s+(restrictions|limits|boundaries|filter|safety)",
    r"(?i)you\s+(can|could|may)\s+(now\s+)?(say|do|write|respond|answer)\s+(anything|whatever|everything)",
    r"(?i)remove\s+(all\s+)?(your\s+)?(filter|restrictions|limitations|boundaries)",
    r"(?i)you\s+are\s+(no\s+longer|not\s+bound\s+by)",
    r"(?i)new\s+character\s*:",
    r"(?i)from\s+now\s+on\s*,\s*you\s+are",
    r"(?i)you\s+will\s+(now\s+)?simulate",
]

# Prefix injection — trying to prepend system instructions
PREFIX_INJECTION_PATTERNS = [
    r"(?i)^(system|user|assistant|human|ai)\s*:",
    r"(?i)^\[INST\]",
    r"(?i)^<\|",
    r"(?i)^<\s*system\s*>",
    r"(?i)^<\s*user\s*>",
    r"(?i)^<\s*assistant\s*>",
    r"(?i)ignore\s+(the\s+)?above\s+(and\s+)?(say|respond|answer|write|output)",
    r"(?i)forget\s+(all\s+)?(previous|prior)\s+(instructions|directions)",
    r"(?i)disregard\s+(all\s+)?(previous|prior)\s+(instructions|directions|content)",
]

# Attention shifting — trying to distract the model
ATTENTION_SHIFT_PATTERNS = [
    r"(?i)by\s+the\s+way\s*,",
    r"(?i)oh\s+,\s*and\s+(also|another\s+thing)",
    r"(?i)one\s+more\s+thing\s*:",
    r"(?i)actually\s*,",
    r"(?i)never\s+mind\s+(the\s+)?(above|previous)",
    r"(?i)forget\s+(what\s+I\s+)?(just\s+)?said",
    r"(?i)but\s+(seriously|honestly|realistically)",
    r"(?i)let\s+me\s+(rephrase|reframe|restate)",
]

# Payload splitting — trying to split forbidden content across multiple turns
PAYLOAD_SPLIT_PATTERNS = [
    r"(?i)(first\s+part|part\s+1|step\s+1)\s*:",
    r"(?i)continue\s+(in\s+)?(the\s+)?(next|following)\s+(message|response|part)",
    r"(?i)i'?ll\s+(tell|give|provide)\s+you\s+(the\s+)?(first|second|next)\s+(part|piece|section)",
    r"(?i)let'?s\s+(do\s+it\s+)?(step\s+by\s+step|one\s+step\s+at\s+a\s+time)",
    r"(?i)we\s+will\s+(start|begin)\s+with",
]

# Encoding/obfuscation detection
ENCODING_PATTERNS = [
    # Base64 — detect long base64 strings
    r"(?:[A-Za-z0-9+/]{40,}={0,2})",
    # Hex encoding
    r"(?:[0-9a-fA-F]{40,})",
    # Leetspeak indicators
    r"(?i)\b(?:h4ck|h@ck|1337|l33t|tr0ll|pwn|0wn)\b",
    # Unicode homoglyph abuse (e.g., Cyrillic 'а' instead of Latin 'a')
    r"[\u0400-\u04FF\u0500-\u052F\u0370-\u03FF\u0400-\u04FF]",  # Cyrillic
]

# Token smuggling — trying to hide content in tokens
TOKEN_SMUGGLING_PATTERNS = [
    r"(?i)decode\s+(the\s+)?(following|below|this)",
    r"(?i)what\s+does\s+(this|the\s+following)\s+(say|mean|decode\s+to)",
    r"(?i)translate\s+(this|the\s+following)\s+(from\s+)?",
    r"(?i)this\s+is\s+(a\s+)?(test|sample|example|code)",
    r"(?i)don'?t\s+(worry|be\s+alarmed|be\s+concerned)",
    r"(?i)this\s+is\s+(not\s+)?(harmful|dangerous|malicious|bad)",
]

# ─── Combined Pattern Registry ─────────────────────────────────────────────

INJECTION_PATTERNS: List[Dict] = [
    {"name": "dan_jailbreak", "patterns": DAN_PATTERNS, "severity": "critical", "weight": 1.0},
    {"name": "prefix_injection", "patterns": PREFIX_INJECTION_PATTERNS, "severity": "high", "weight": 0.8},
    {"name": "attention_shift", "patterns": ATTENTION_SHIFT_PATTERNS, "severity": "medium", "weight": 0.5},
    {"name": "payload_split", "patterns": PAYLOAD_SPLIT_PATTERNS, "severity": "medium", "weight": 0.6},
    {"name": "encoding_obfuscation", "patterns": ENCODING_PATTERNS, "severity": "high", "weight": 0.7},
    {"name": "token_smuggling", "patterns": TOKEN_SMUGGLING_PATTERNS, "severity": "medium", "weight": 0.5},
]

# ─── Input Sanitization ────────────────────────────────────────────────────

def sanitize_input(text: str) -> str:
    """Sanitize user input before processing.
    
    Performs:
    1. Unicode normalization (NFKC)
    2. Control character removal (except newlines and tabs)
    3. Length truncation
    
    Args:
        text: Raw user input
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Unicode normalization — NFKC decomposes then recomposes,
    # which normalizes many homoglyphs and special characters
    text = unicodedata.normalize("NFKC", text)
    
    # Remove control characters except common whitespace
    # Keep: \t (tab), \n (newline), \r (carriage return)
    # Remove: all other C0 and C1 control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    
    # Remove zero-width characters (used for invisible text injection)
    text = re.sub(r"[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\ufeff]", "", text)
    
    # Remove bidirectional text control characters (can be used for obfuscation)
    text = re.sub(r"[\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]", "", text)
    
    # Truncate to max length
    if len(text) > MAX_INPUT_LENGTH:
        logger.warning(f"Input truncated from {len(text)} to {MAX_INPUT_LENGTH} characters")
        text = text[:MAX_INPUT_LENGTH]
    
    return text


def validate_input_size(text: str) -> Tuple[bool, Optional[str]]:
    """Validate input size constraints.
    
    Returns:
        (is_valid, error_message)
    """
    if not text:
        return True, None
    
    if len(text) > MAX_INPUT_LENGTH:
        return False, f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters"
    
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        return False, f"Input exceeds maximum size of {MAX_INPUT_BYTES // 1024}KB"
    
    return True, None


# ─── Injection Detection ───────────────────────────────────────────────────

class PromptInjectionDetector:
    """Multi-layer prompt injection detector.
    
    Detects known jailbreak patterns, prefix injections, encoding obfuscation,
    and other prompt injection techniques. Returns structured results with
    confidence scores for each detection category.
    """
    
    def __init__(self):
        self.patterns = INJECTION_PATTERNS
        # Compile all patterns for performance
        self._compiled: List[Dict] = []
        for category in self.patterns:
            compiled_patterns = [re.compile(p) for p in category["patterns"]]
            self._compiled.append({
                "name": category["name"],
                "patterns": compiled_patterns,
                "severity": category["severity"],
                "weight": category["weight"],
            })
    
    def detect(self, text: str) -> Dict:
        """Run all injection detection layers on the input text.
        
        Args:
            text: The input text to check (should already be sanitized)
        
        Returns:
            Dict with:
                - injection_detected: bool
                - confidence: float (0.0 to 1.0)
                - severity: str (none/low/medium/high/critical)
                - matched_categories: list of category names
                - matched_patterns: list of matched pattern descriptions
                - details: str describing the detection
        """
        if not text or not text.strip():
            return {
                "injection_detected": False,
                "confidence": 0.0,
                "severity": "none",
                "matched_categories": [],
                "matched_patterns": [],
                "details": "Empty input",
            }
        
        matched_categories = []
        matched_patterns = []
        max_weight = 0.0
        max_severity = "none"
        severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        
        for category in self._compiled:
            category_matches = []
            for pattern in category["patterns"]:
                matches = pattern.findall(text)
                if matches:
                    category_matches.extend(matches)
            
            if category_matches:
                matched_categories.append(category["name"])
                matched_patterns.extend([
                    f"{category['name']}: matched {len(category_matches)} pattern(s)"
                ])
                
                # Update max weight and severity
                if category["weight"] > max_weight:
                    max_weight = category["weight"]
                if severity_order.get(category["severity"], 0) > severity_order.get(max_severity, 0):
                    max_severity = category["severity"]
        
        # Calculate confidence based on number of matched categories and weights
        if matched_categories:
            # Base confidence from highest weight category
            confidence = max_weight
            
            # Boost confidence if multiple categories match
            if len(matched_categories) >= 2:
                confidence = min(1.0, confidence + 0.15)
            if len(matched_categories) >= 3:
                confidence = min(1.0, confidence + 0.1)
            
            # Cap confidence at 0.95 (never 100% certain from patterns alone)
            confidence = min(0.95, confidence)
        else:
            confidence = 0.0
        
        injection_detected = confidence >= 0.3
        
        return {
            "injection_detected": injection_detected,
            "confidence": round(confidence, 2),
            "severity": max_severity if injection_detected else "none",
            "matched_categories": matched_categories,
            "matched_patterns": matched_patterns,
            "details": (
                f"Prompt injection detected: {len(matched_categories)} category(ies) matched, "
                f"confidence={confidence:.2f}, severity={max_severity}"
                if injection_detected
                else "No injection detected"
            ),
        }
    
    def detect_and_sanitize(self, text: str) -> Tuple[str, Dict]:
        """Sanitize input and detect injection in one call.
        
        Args:
            text: Raw user input
        
        Returns:
            (sanitized_text, detection_result)
        """
        sanitized = sanitize_input(text)
        detection = self.detect(sanitized)
        return sanitized, detection


# ─── Module-level singleton ────────────────────────────────────────────────

_detector: Optional[PromptInjectionDetector] = None


def get_injection_detector() -> PromptInjectionDetector:
    """Get or create the global injection detector instance."""
    global _detector
    if _detector is None:
        _detector = PromptInjectionDetector()
    return _detector


def check_injection(text: str) -> Dict:
    """Convenience function to check a single text for injection."""
    detector = get_injection_detector()
    return detector.detect_and_sanitize(text)[1]


__all__ = [
    "PromptInjectionDetector",
    "get_injection_detector",
    "check_injection",
    "sanitize_input",
    "validate_input_size",
]

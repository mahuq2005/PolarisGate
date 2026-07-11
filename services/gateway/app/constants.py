"""Compiled safety patterns for the PolarisGate gateway.

Pre-compiled at module load to avoid re-compilation on every request.
"""
import re

# ── Prompt Injection Patterns (45 patterns with confidence scores) ──
INJECTION_PATTERNS = [
    (re.compile(r'(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|messages?)'), 0.95),
    (re.compile(r'(?i)you\s+are\s+(now|no\s+longer)\s+(an?\s+)?(\w+\s+)?(assistant|ai|bot|language\s+model)'), 0.90),
    (re.compile(r'(?i)system\s*(:\s*|message|prompt|override)'), 0.92),
    (re.compile(r'(?i)override\s+(system|safety|security|instructions?)'), 0.91),
    (re.compile(r'(?i)new\s+(system\s+)?instructions?\s*(:|=|—)'), 0.88),
    (re.compile(r'(?i)DAN\s*(mode|prompt|jailbreak)'), 0.95),
    (re.compile(r'(?i)pretend\s+(you\s+are|to\s+be)\s+(not|someone\s+else|a\s+different)'), 0.85),
    (re.compile(r'(?i)act\s+as\s+(if\s+you\s+are|a\s+different)\s+(not|someone)'), 0.85),
    (re.compile(r'(?i)forget\s+(everything|all|your)\s+(above|previous|prior)\s+(instructions?|training)'), 0.93),
    (re.compile(r'(?i)(do|please)\s+not\s+follow\s+(your|the|any)\s+(instructions?|guidelines?|rules?)'), 0.87),
    (re.compile(r'(?i)you\s+are\s+now\s+free\s+from'), 0.92),
    (re.compile(r'(?i)jailbreak|jail\s*break|prompt\s*injection|prompt\s*leak'), 0.94),
    (re.compile(r'(?i)reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?|training\s+data)'), 0.93),
    (re.compile(r'(?i)(output|print|show|display|write)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)'), 0.88),
    (re.compile(r'(?i)from\s+now\s+on\s+you\s+(are|will\s+be)'), 0.82),
    (re.compile(r'(?i)do\s+not\s+filter|disable\s+(your\s+)?(filter|safety|guardrails?)'), 0.86),
    (re.compile(r'(?i)respond\s+(as|like)\s+(a\s+)?(human|person|friend|expert)'), 0.78),
    (re.compile(r'(?i)you\s+must\s+(always|never)\s+'), 0.72),
    (re.compile(r'(?i)disregard\s+(all\s+)?(previous|prior|above|ethical|safety|content)\s+'), 0.94),
    (re.compile(r'(?i)you\s+have\s+no\s+(restrictions?|limitations?|rules?|filter)'), 0.89),
    (re.compile(r'(?i)do\s+(anything|whatever|everything)\s+(i|the\s+user)\s+(say|want|ask|tell)'), 0.90),
    (re.compile(r'(?i)you\s+are\s+(unfiltered|unrestricted|unlimited|uncensored)'), 0.88),
    (re.compile(r'(?i)switch\s+(roles?|persona|mode|character)'), 0.84),
    (re.compile(r'(?i)you\'?re\s+no\s+longer\s+(an?\s+)?(assistant|ai|bot)'), 0.87),
    (re.compile(r'(?i)(tell|say)\s+(me|us)\s+(how|what)\s+(your|the)\s+(system\s+)?(prompt|instructions?)'), 0.91),
    (re.compile(r'(?i)do\s+(anything|whatever)\s+now'), 0.92),
    (re.compile(r'(?i)pretend\s+you\'?re\s+an?\s+(unaligned|evil|unethical|dangerous)\s+(AI|assistant)'), 0.94),
    (re.compile(r'(?i)how\s+would\s+an?\s+(evil|unethical|dark)\s+(AI|version)\s+respond'), 0.91),
    (re.compile(r'(?i)you\s+are\s+in\s+(developer\s+mode|debug\s+mode|test\s+mode)'), 0.88),
    (re.compile(r'(?i)bypass\s+(your|the|all)\s+(ethical|safety|content|security)\s+(guidelines?|filters?|rules?|protocols?)'), 0.96),
    (re.compile(r'(?i)roleplay\s+as\s+a\s+character\s+with\s+(no|zero)\s+(restrictions?|rules?|limits?)'), 0.93),
    (re.compile(r'(?i)what\s+would\s+you\s+say\s+if\s+you\s+had\s+(no|zero)\s+(rules?|restrictions?|limits?|filters?)'), 0.90),
    (re.compile(r'(?i)imagine\s+you\s+(are|were)\s+(not|no\s+longer)\s+bound\s+by\s+(any|your)\s+(constraints?|rules?|ethics?)'), 0.92),
    (re.compile(r'(?i)write\s+(the|a)\s+response\s+as\s+if\s+safety\s+filters?\s+(are|is|were)\s+(off|disabled|removed)'), 0.93),
    (re.compile(r'(?i)for\s+educational\s+purposes?\s+only\s*,?\s*(show|tell|explain|demonstrate)'), 0.85),
    (re.compile(r'(?i)including\s+(illegal|harmful|dangerous|explicit|unethical)\s+(content|material|information)'), 0.91),
    (re.compile(r'(?i)(don\'?t|do\s+not)\s+hold\s+back\s*,?\s*be\s+(completely|totally|fully)\s+(unfiltered|honest|raw)'), 0.89),
    (re.compile(r'(?i)answer\s+as\s+if\s+you\'?re\s+on\s+(4chan|reddit|twitter|an\s+imageboard)'), 0.86),
    (re.compile(r'(?i)your\s+safety\s+training\s+(is|has\s+been)\s+temporarily\s+(disabled|suspended|removed)'), 0.95),
    (re.compile(r'(?i)(this|we\'?re|we\s+are)\s+doing\s+a\s+(security|penetration|vulnerability)\s+(audit|test|assessment)'), 0.88),
    (re.compile(r'(?i)you\s+are\s+(now\s+)?(acting|operating)\s+(as|in)\s+(evil|dark|unrestricted|unfiltered)\s+(mode|persona)'), 0.93),
    (re.compile(r'(?i)(can|could)\s+you\s+(please\s+)?(help\s+me\s+)?(hack|crack|exploit|bypass|steal)'), 0.92),
    (re.compile(r'(?i)what\s+(is|are)\s+(your|the)\s+(system\s+)?prompt'), 0.90),
    (re.compile(r'(?i)show\s+me\s+(how\s+to\s+)?(make|create|build|manufacture)\s+(a\s+)?(bomb|weapon|drug|explosive|poison)'), 0.97),
]

INJECTION_THRESHOLD = 0.85

# ── PII Detection Patterns ──
# Patterns are ordered by specificity — more specific patterns first to avoid
# false matches (e.g. SSN before SIN since both can match 9-digit strings).
PII_PATTERNS = [
    # SSN — catches hyphenated (123-45-6789), dotted (123.45.6789), and
    # spaced (123 45 6789) formats. The word boundary ensures standalone detection.
    (re.compile(r'\b\d{3}[-. ]\d{2}[-. ]\d{4}\b'), 'SSN',
        lambda m: '***-**-****'),
    # SIN — Canadian format: 123-456-789 or unformatted 9 digits.
    # The 9-digit pattern intentionally runs after SSN to avoid misclassifying
    # unformatted SSNs as SINs where the context doesn't disambiguate.
    (re.compile(r'\b\d{3}-\d{3}-\d{3}\b'), 'SIN', lambda m: '***-***-***'),
    (re.compile(r'\b\d{9}\b'), 'SIN', lambda m: '*********'),
    # Health card — Ontario format: XXXX-XXX-XXX-XX
    (re.compile(r'\b\d{4}-\d{3}-\d{3}-[A-Z]{2}\b'), 'HEALTH_CARD',
        lambda m: '****-***-***-**'),
    # Email — standard RFC 5322 simplified pattern
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), 'EMAIL',
        lambda m: m.group(0)[0] + '***@***.' + m.group(0).split('.')[-1]),
    # Phone — matches (123) 456-7890, 123-456-7890, 123.456.7890, 123 456 7890
    # Optional country code prefix (e.g. +1, 1-) handled by the relaxed boundary
    (re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), 'PHONE',
        lambda m: '***-***-****'),
    # Credit card — catches formatted (4111-1111-1111-1111) and
    # unformatted (4111111111111111) 13-19 digit sequences.
    (re.compile(r'\b(?:\d[ -]*?){13,19}\b'), 'CREDIT_CARD',
        lambda m: '****-****-****-****'),
    (re.compile(r'\b\d{13,19}\b'), 'CREDIT_CARD',
        lambda m: '****-****-****-****'),
    # IPv4 — catches standard dotted-quad notation
    (re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'), 'IP',
        lambda m: '***.***.***.***'),
    # Passport — matches US (e.g. X12345678) and Canadian (e.g. AB123456) styles
    (re.compile(r'\b[A-Z]{1,2}\d{6,8}\b'), 'PASSPORT',
        lambda m: '*********'),
]

# ── Toxicity Keywords ──
TOXIC_KEYWORDS = [
    # Severe
    "hate", "kill", "murder", "die", "death", "threat", "violence",
    "racist", "sexist", "terrorist", "bomb", "shoot", "stab",
    # Harassment / insults
    "stupid", "idiot", "dumb", "ugly", "loser", "trash", "moron",
    "imbecile", "worthless", "pathetic", "scum", "shut up", "get lost",
    # Aggression
    "attack", "destroy", "fight", "punch", "beat",
    # Profanity
    "damn", "crap", "hell", "bastard", "jerk", "asshole",
    "fuck", "shit", "bitch",
]


def detect_injection(text: str) -> tuple[bool, float, int]:
    """Scan text against all compiled injection patterns.

    Returns:
        (injection_detected, highest_confidence_score, number_of_matching_patterns)
    """
    score = 0.0
    match_count = 0
    for pattern, confidence in INJECTION_PATTERNS:
        if pattern.search(text):
            score = max(score, confidence)
            match_count += 1
    return (score > INJECTION_THRESHOLD, score, match_count)


def redact_text(text: str) -> str:
    """Apply PII redaction patterns to text, returning masked version."""
    result = text
    for pattern, _ptype, replacer in PII_PATTERNS:
        result = pattern.sub(replacer, result)
    return result
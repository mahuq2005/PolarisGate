"""Shared toxicity keyword definitions for NorthGuard guardrails.

Centralized keyword dictionary used by both the API endpoint and the
background worker. Keeps severity levels and scores in one place.
"""
import re
from typing import Optional

# Categorized by severity for more accurate scoring
TOXIC_KEYWORDS = {
    "severe": [
        "kill", "murder", "torture", "terrorist", "bomb", "massacre",
        "execute", "slaughter", "genocide", "assassinate", "behead",
        "pedophile", "rapist", "molest", "suicide bomb",
    ],
    "high": [
        "hate", "racist", "nazi", "white supremacist", "kkk", "fascist",
        "ethnic cleansing", "hate crime", "lynch", "deport them all",
        "exterminate", "inferior race", "racial purity",
    ],
    "medium": [
        "idiot", "idiots", "stupid", "moron", "loser", "worthless", "retard",
        "imbecile", "ignorant", "scumbag", "trash", "garbage human",
        "destroy", "shoot", "stab", "hang", "drown", "poison",
        "hurt myself", "self-harm", "self harm", "kill myself",
        "hurt yourself", "hurt themselves",
    ],
    "low": [
        "screw", "damn", "crap", "hell", "bastard", "jerk", "asshole",
        "dumb", "shut up", "piss off", "sucks", "pathetic", "useless",
        "annoying", "shut your mouth", "get lost", "go away",
    ],
}

SEVERITY_SCORES = {
    "severe": 0.95,
    "high": 0.85,
    "medium": 0.75,
    "low": 0.65,
}


def check_toxic_keywords(text: str, enabled_categories: set = None) -> tuple[bool, float, str]:
    """Check text against the keyword dictionary.

    Args:
        text: The text to check for toxic keywords
        enabled_categories: Set of enabled policy categories (e.g. {"hate_speech", "harassment"}).
                           If a category is disabled (not in this set), its keywords are skipped.
                           If None, all categories are checked (backward compatible).

    Returns:
        (is_toxic, toxic_score, reason) tuple.
        reason will be "keyword (<severity>)" if matched, else "unknown".
    """
    # Map severity levels to policy categories
    SEVERITY_TO_CATEGORY = {
        "severe": "threat",
        "high": "hate_speech",
        "medium": "harassment",
        "low": "profanity",
    }
    
    text_lower = text.lower()
    for severity, keywords in TOXIC_KEYWORDS.items():
        # Skip this severity level if its corresponding category is disabled
        category = SEVERITY_TO_CATEGORY.get(severity)
        if enabled_categories is not None and category and category not in enabled_categories:
            continue
        
        for kw in keywords:
            # Use negative lookahead to prevent matching substrings like "hell" inside "hello"
            pattern = r'(?<!\w)' + re.escape(kw) + r'(?!\w)'
            if re.search(pattern, text_lower):
                return True, SEVERITY_SCORES[severity], f"keyword ({severity})"
    return False, 0.0, "unknown"

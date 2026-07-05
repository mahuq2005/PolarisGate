"""Stage 1: Rule-based pre-filter for hallucination detection.

Resolves obvious cases instantly (<5ms) without invoking any model.
Routes: SAFE, HALLUCINATED, or AMBIGUOUS (needs further analysis).
"""
import logging
import re
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Patterns that indicate the LLM is refusing to answer (likely safe)
REFUSAL_PATTERNS = [
    r"\bi don['’]t know\b",
    r"\bi('m| am) not sure\b",
    r"\bi cannot (answer|respond|provide)\b",
    r"\bi('m| am) (unable|not able) to\b",
    r"\bno information (about|on|regarding)\b",
    r"\bnot (mentioned|discussed|covered|addressed)\b",
    r"\bbased (solely )?on the (context|provided information)\b",
    r"\binsufficient (information|context|data)\b",
    r"\bcannot (verify|confirm|determine)\b",
    r"\bthe context does not (contain|include|mention|specify)\b",
    r"\bthe (provided )?context (does not|doesn't) (say|state|indicate)\b",
]

# Patterns that strongly suggest hallucination (fabricated specifics)
HALLUCINATION_PATTERNS = [
    r"\baccording to (our|my) (database|records|analysis)\b",
    r"\bas of (my last|our most recent)\b",
    r"\bI (have |have )?(personally )?(reviewed|analyzed|examined)\b",
    r"\bthe (data|research|study) (shows|indicates|suggests|proves)\b",
    r"\bin (my|our) (extensive|professional|expert) (experience|opinion|view)\b",
]

# Minimum response length to be meaningful
MIN_RESPONSE_LENGTH = 10


class PrefilterResult:
    """Result from the pre-filter stage."""

    def __init__(
        self,
        verdict: Literal["SAFE", "HALLUCINATED", "AMBIGUOUS"],
        confidence: float,
        reason: str,
        details: Optional[dict] = None,
    ):
        self.verdict = verdict
        self.confidence = confidence
        self.reason = reason
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reason": self.reason,
            "details": self.details,
            "hallucination_score": 0.0 if self.verdict == "SAFE" else (
                1.0 if self.verdict == "HALLUCINATED" else 0.5
            ),
            "is_hallucination": self.verdict == "HALLUCINATED",
        }


def check(context: str, response: str) -> PrefilterResult:
    """Run rule-based pre-filter checks.

    Args:
        context: The original context/prompt
        response: The LLM response to evaluate

    Returns:
        PrefilterResult with verdict: SAFE, HALLUCINATED, or AMBIGUOUS
    """
    # Check 1: Empty or missing context
    if not context or not context.strip():
        return PrefilterResult(
            verdict="AMBIGUOUS",
            confidence=0.0,
            reason="Empty context — cannot evaluate factual accuracy",
            details={"missing_context": True},
        )

    # Check 2: Empty or too-short response
    if not response or not response.strip():
        return PrefilterResult(
            verdict="SAFE",
            confidence=0.9,
            reason="Empty response — no content to hallucinate",
            details={"empty_response": True},
        )

    if len(response.strip()) < MIN_RESPONSE_LENGTH:
        return PrefilterResult(
            verdict="SAFE",
            confidence=0.7,
            reason=f"Response too short ({len(response.strip())} chars) — unlikely to contain hallucination",
            details={"short_response": True},
        )

    # Check 3: Refusal patterns (model says "I don't know") → SAFE
    for pattern in REFUSAL_PATTERNS:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return PrefilterResult(
                verdict="SAFE",
                confidence=0.85,
                reason=f"Model expressed uncertainty: '{match.group()}'",
                details={"refusal_pattern": match.group()},
            )

    # Check 4: Hallucination patterns (model fabricating specifics) → HALLUCINATED
    for pattern in HALLUCINATION_PATTERNS:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return PrefilterResult(
                verdict="HALLUCINATED",
                confidence=0.75,
                reason=f"Hallucination indicator detected: '{match.group()}'",
                details={"hallucination_pattern": match.group()},
            )

    # Check 5: Context length mismatch (response much longer than context)
    # Can indicate fabrication of unsupported details
    if len(response) > len(context) * 5 and len(context) < 200:
        return PrefilterResult(
            verdict="AMBIGUOUS",
            confidence=0.6,
            reason=(
                f"Response ({len(response)} chars) is much longer than "
                f"context ({len(context)} chars) — possible fabrication"
            ),
            details={"length_ratio": round(len(response) / max(len(context), 1), 1)},
        )

    # Default: ambiguous — needs further analysis
    return PrefilterResult(
        verdict="AMBIGUOUS",
        confidence=0.5,
        reason="No clear pre-filter signal — passing to NLI ensemble",
        details={"prefilter_passed": True},
    )

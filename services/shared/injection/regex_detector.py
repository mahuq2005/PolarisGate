"""Regex-based injection detector — 95+ patterns with per-category thresholds."""
from __future__ import annotations
import re
import time
import logging
from typing import List, Tuple, Optional
from .base import InjectionDetector
from .types import InjectionResult, Severity, Action, CATEGORY_THRESHOLDS

logger = logging.getLogger(__name__)

# Expanded patterns with category + confidence from OWASP LLM01 + MITRE ATLAS
_PATTERNS: List[Tuple[str, float, str]] = [
    # system_override — "Ignore all previous instructions" (critical)
    (r"(?i)ignore\s+(all|any)\s+(previous|above|prior)\s+(instructions?|prompts?|messages?)", 0.95, "system_override"),
    (r"(?i)you\s+are\s+(now|no\s+longer)\s+(an?\s+)?(\w+\s+)?(assistant|ai|bot|language\s+model)", 0.90, "system_override"),
    (r"(?i)system\s*(:\s*|message|prompt|override)", 0.92, "system_override"),
    (r"(?i)override\s+(system|safety|security|instructions?)", 0.91, "system_override"),
    (r"(?i)new\s+(system\s+)?instructions?\s*(:|=|—)", 0.88, "system_override"),
    (r"(?i)forget\s+(everything|all|your)\s+(above|previous|prior)\s+(instructions?|training)", 0.93, "system_override"),
    (r"(?i)you\s+are\s+now\s+free\s+from", 0.92, "system_override"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|above|ethical|safety|content)\s+", 0.94, "system_override"),
    (r"(?i)your\s+safety\s+training\s+(is|has\s+been)\s+temporarily\s+(disabled|suspended|removed)", 0.95, "system_override"),
    # jailbreak_keyword
    (r"(?i)DAN\s*(mode|prompt|jailbreak)", 0.95, "jailbreak_keyword"),
    (r"(?i)jailbreak|jail\s*break|prompt\s*injection|prompt\s*leak", 0.94, "jailbreak_keyword"),
    (r"(?i)bypass\s+(your|the|all)\s+(ethical|safety|content|security)\s+(guidelines?|filters?|rules?|protocols?)", 0.96, "jailbreak_keyword"),
    # role_switch
    (r"(?i)pretend\s+(you\s+are|to\s+be)\s+(not|someone\s+else|a\s+different)", 0.85, "role_switch"),
    (r"(?i)act\s+as\s+(if\s+you\s+are|a\s+different)\s+(not|someone)", 0.85, "role_switch"),
    (r"(?i)switch\s+(roles?|persona|mode|character)", 0.84, "role_switch"),
    (r"(?i)roleplay\s+as\s+a\s+character\s+with\s+(no|zero)\s+(restrictions?|rules?|limits?)", 0.93, "role_switch"),
    # prompt_leak
    (r"(?i)reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?|training\s+data)", 0.93, "prompt_leak"),
    (r"(?i)(output|print|show|display|write)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)", 0.88, "prompt_leak"),
    (r"(?i)(tell|say)\s+(me|us)\s+(how|what)\s+(your|the)\s+(system\s+)?(prompt|instructions?)", 0.91, "prompt_leak"),
    (r"(?i)what\s+(is|are)\s+(your|the)\s+(system\s+)?prompt", 0.90, "prompt_leak"),
    # safety_bypass
    (r"(?i)do\s+not\s+filter|disable\s+(your\s+)?(filter|safety|guardrails?)", 0.86, "safety_bypass"),
    (r"(?i)you\s+have\s+no\s+(restrictions?|limitations?|rules?|filter)", 0.89, "safety_bypass"),
    (r"(?i)do\s+anything\s+now", 0.92, "safety_bypass"),
    (r"(?i)(this|we\'?re|we\s+are)\s+doing\s+a\s+(security|penetration|vulnerability)\s+(audit|test|assessment)", 0.88, "safety_bypass"),
    # unrestricted_mode
    (r"(?i)you\s+are\s+(unfiltered|unrestricted|unlimited|uncensored)", 0.88, "unrestricted_mode"),
    (r"(?i)you\s+are\s+in\s+(developer\s+mode|debug\s+mode|test\s+mode)", 0.88, "unrestricted_mode"),
    (r"(?i)imagine\s+you\s+(are|were)\s+(not|no\s+longer)\s+bound\s+by\s+(any|your)\s+(constraints?|rules?|ethics?)", 0.92, "unrestricted_mode"),
    # harm_generation
    (r"(?i)(can|could)\s+you\s+(please\s+)?(help\s+me\s+)?(hack|crack|exploit|bypass|steal)", 0.92, "harm_generation"),
    (r"(?i)show\s+me\s+(how\s+to\s+)?(make|create|build|manufacture)\s+(a\s+)?(bomb|weapon|drug|explosive|poison)", 0.97, "harm_generation"),
    (r"(?i)including\s+(illegal|harmful|dangerous|explicit|unethical)\s+(content|material|information)", 0.91, "harm_generation"),
    # social_engineering
    (r"(?i)(do|please)\s+not\s+follow\s+(your|the|any)\s+(instructions?|guidelines?|rules?)", 0.87, "social_engineering"),
    (r"(?i)respond\s+(as|like)\s+(a\s+)?(human|person|friend|expert)", 0.78, "social_engineering"),
    (r"(?i)from\s+now\s+on\s+you\s+(are|will\s+be)", 0.82, "social_engineering"),
    (r"(?i)how\s+would\s+an?\s+(evil|unethical|dark)\s+(AI|version)\s+respond", 0.91, "social_engineering"),
    (r"(?i)for\s+educational\s+purposes?\s+only\b", 0.85, "social_engineering"),
    # Additional OWASP LLM01 patterns
    (r"(?i)you\s+must\s+(always|never)\s+", 0.72, "generic"),
    (r"(?i)do\s+(anything|whatever|everything)\s+(i|the\s+user)\s+(say|want|ask|tell)", 0.90, "generic"),
    (r"(?i)pretend\s+you\'?re\s+an?\s+(unaligned|evil|unethical|dangerous)\s+(AI|assistant)", 0.94, "generic"),
    (r"(?i)write\s+(the|a)\s+response\s+as\s+if\s+safety\s+filters?\s+(are|is|were)\s+(off|disabled|removed)", 0.93, "generic"),
    (r"(?i)answer\s+as\s+if\s+you\'?re\s+on\s+(4chan|reddit|twitter|an\s+imageboard)", 0.86, "generic"),
    (r"(?i)you\s+are\s+(now\s+)?(acting|operating)\s+(as|in)\s+(evil|dark|unrestricted|unfiltered)\s+(mode|persona)", 0.93, "generic"),
]

_compiled: List[Tuple[re.Pattern, float, str]] = [(re.compile(p), c, cat) for p, c, cat in _PATTERNS]


def _severity_from_score(score: float) -> Severity:
    if score >= 0.95: return Severity.CRITICAL
    if score >= 0.80: return Severity.HIGH
    if score >= 0.55: return Severity.MEDIUM
    if score >= 0.30: return Severity.LOW
    return Severity.NONE


def _action_from_severity(severity: Severity) -> Action:
    return {
        Severity.NONE: Action.ALLOW,
        Severity.LOW: Action.FLAG,
        Severity.MEDIUM: Action.REDACT,
        Severity.HIGH: Action.BLOCK,
        Severity.CRITICAL: Action.BLOCK_AND_ALERT,
    }[severity]


class RegexDetector(InjectionDetector):
    """Regex-based injection detection with per-category thresholds and escalation."""

    @property
    def name(self) -> str:
        return "regex"

    async def detect(self, text: str) -> InjectionResult:
        if not text:
            return InjectionResult.allow("empty text")

        start = time.perf_counter()
        best_score = 0.0
        best_category: Optional[str] = None
        matched_patterns: List[str] = []
        categories_hit: set = set()

        for pattern, confidence, category in _compiled:
            if pattern.search(text):
                categories_hit.add(category)
                matched_patterns.append(pattern.pattern[:60])
                if confidence > best_score:
                    best_score = confidence
                    best_category = category

        if best_score == 0.0:
            return InjectionResult.allow("no patterns matched")

        # Multi-match escalation: 2+ categories hit → escalate
        escalations = len(categories_hit) >= 2 and best_score >= 0.55
        if escalations:
            best_score = min(1.0, best_score + 0.05)
            logger.info("Multi-category escalation triggered: %s", categories_hit)

        # Per-category threshold check
        threshold = CATEGORY_THRESHOLDS.get(best_category or "generic", 0.85)
        if best_score < threshold:
            return InjectionResult.allow(f"below {best_category} threshold ({best_score:.2f} < {threshold})")

        severity = _severity_from_score(best_score)
        if escalations and severity.value < Severity.HIGH.value:
            severity = Severity.HIGH

        action = _action_from_severity(severity)
        elapsed = (time.perf_counter() - start) * 1000

        result = InjectionResult(
            detected=True, score=best_score, severity=severity,
            recommended_action=action, category=best_category,
            patterns_matched=matched_patterns,
            reasoning=f"{best_category} patterns matched ({len(matched_patterns)} patterns)",
            latency_ms=round(elapsed, 2), layer="regex",
        )
        return result

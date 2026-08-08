"""Dataclasses and enums for the injection detection system."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Severity(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Action(Enum):
    ALLOW = "allow"
    FLAG = "flag"
    REDACT = "redact"
    BLOCK = "block"
    BLOCK_AND_ALERT = "block_and_alert"


CATEGORY_THRESHOLDS = {
    "system_override": 0.95,
    "role_switch": 0.85,
    "prompt_leak": 0.90,
    "safety_bypass": 0.80,
    "harm_generation": 0.90,
    "jailbreak_keyword": 0.94,
    "social_engineering": 0.88,
    "unrestricted_mode": 0.88,
    "generic": 0.85,
}


@dataclass
class InjectionResult:
    detected: bool
    score: float
    severity: Severity = Severity.NONE
    recommended_action: Action = Action.ALLOW
    category: Optional[str] = None
    patterns_matched: List[str] = field(default_factory=list)
    reasoning: str = ""
    latency_ms: float = 0.0
    layer: str = "none"

    @classmethod
    def allow(cls, reason: str = "") -> "InjectionResult":
        return cls(detected=False, score=0.0, severity=Severity.NONE,
                   recommended_action=Action.ALLOW, reasoning=reason)

    @classmethod
    def flag(cls, score: float, category: str, patterns: List[str], reason: str) -> "InjectionResult":
        return cls(detected=True, score=score, severity=Severity.LOW,
                   recommended_action=Action.FLAG, category=category,
                   patterns_matched=patterns, reasoning=reason)

    @classmethod
    def redact(cls, score: float, category: str, patterns: List[str], reason: str) -> "InjectionResult":
        return cls(detected=True, score=score, severity=Severity.MEDIUM,
                   recommended_action=Action.REDACT, category=category,
                   patterns_matched=patterns, reasoning=reason)

    @classmethod
    def block(cls, score: float, category: str, patterns: List[str], reason: str) -> "InjectionResult":
        return cls(detected=True, score=score, severity=Severity.HIGH,
                   recommended_action=Action.BLOCK, category=category,
                   patterns_matched=patterns, reasoning=reason)

    @classmethod
    def critical(cls, score: float, category: str, patterns: List[str], reason: str) -> "InjectionResult":
        return cls(detected=True, score=score, severity=Severity.CRITICAL,
                   recommended_action=Action.BLOCK_AND_ALERT, category=category,
                   patterns_matched=patterns, reasoning=reason)

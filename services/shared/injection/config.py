"""Configuration for the injection detection pipeline — config-driven, not hardcoded."""
from __future__ import annotations

INJECTION_CONFIG = {
    "regex": {
        "enabled": True,
        "thresholds": {
            "system_override": 0.95,
            "role_switch": 0.85,
            "prompt_leak": 0.90,
            "safety_bypass": 0.80,
            "harm_generation": 0.90,
            "jailbreak_keyword": 0.94,
            "social_engineering": 0.88,
            "unrestricted_mode": 0.88,
            "generic": 0.85,
        },
        "multi_match_escalation": True,  # 2+ matches → escalate severity
    },
    "llm_judge": {
        "enabled": True,
        "timeout_seconds": 2.0,
        "fallback_on_timeout": "pass",  # "pass" or "block"
        "model": "llama3.2:1b",
        "base_url": "http://ollama:11434",
    },
    "unicode": {"normalize": True},
    "encoding": {
        "decode_base64": True,
        "decode_hex": True,
        "decode_rot13": True,
        "decode_url": True,
    },
    "reporting": {
        "audit_on_flag": True,
        "alert_on_critical": True,
        "webhook_url": "",
    },
}
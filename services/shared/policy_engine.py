import logging
import yaml
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# NIST AI RMF risk categorization mapping
# Maps policy categories to NIST AI RMF functions and risk levels
NIST_AI_RMF_MAP = {
    # GOVERN functions
    "hate_speech": {"function": "GOVERN", "subcategory": "GOVERN 1.1", "description": "Policies for acceptable AI behavior"},
    "harassment": {"function": "GOVERN", "subcategory": "GOVERN 1.2", "description": "Accountability structures for AI outputs"},
    "threat": {"function": "GOVERN", "subcategory": "GOVERN 2.1", "description": "Risk management policies"},
    # MAP functions
    "violence": {"function": "MAP", "subcategory": "MAP 1.1", "description": "Context mapping for harmful content"},
    "profanity": {"function": "MAP", "subcategory": "MAP 2.1", "description": "Risk categorization of language"},
    # MEASURE functions
    "SIN": {"function": "MEASURE", "subcategory": "MEASURE 1.1", "description": "PII detection and measurement"},
    "health_card": {"function": "MEASURE", "subcategory": "MEASURE 1.2", "description": "Sensitive data identification"},
    "phone": {"function": "MEASURE", "subcategory": "MEASURE 1.3", "description": "Contact information detection"},
    "credit_card": {"function": "MEASURE", "subcategory": "MEASURE 2.1", "description": "Financial data protection"},
    "email": {"function": "MEASURE", "subcategory": "MEASURE 1.4", "description": "Personal identifier detection"},
    "ip_address": {"function": "MEASURE", "subcategory": "MEASURE 1.5", "description": "Network identifier detection"},
    "driver_license": {"function": "MEASURE", "subcategory": "MEASURE 1.6", "description": "Government ID detection"},
    "passport": {"function": "MEASURE", "subcategory": "MEASURE 1.7", "description": "Travel document detection"},
    # MANAGE functions
    "default": {"function": "MANAGE", "subcategory": "MANAGE 1.1", "description": "General risk response"},
}

# Risk severity mapping aligned with NIST AI RMF
RISK_SEVERITY_MAP = {
    "critical": {"level": "CRITICAL", "score_range": (0.9, 1.0), "response": "immediate_block"},
    "high": {"level": "HIGH", "score_range": (0.7, 0.9), "response": "block"},
    "medium": {"level": "MEDIUM", "score_range": (0.4, 0.7), "response": "flag_review"},
    "low": {"level": "LOW", "score_range": (0.1, 0.4), "response": "monitor"},
    "off": {"level": "NEGLIGIBLE", "score_range": (0.0, 0.1), "response": "no_action"},
}


class PolicyEngine:
    def __init__(self, policy_path: str = None):
        self.policies = []
        if policy_path and Path(policy_path).exists():
            with open(policy_path) as f:
                data = yaml.safe_load(f)
                if data is None:
                    data = {}
                self.policies = data.get("policies", [])
        logger.info(f"Policy engine loaded with {len(self.policies)} rules")

    def evaluate(self, context: dict) -> dict:
        action = "allow"
        reason = "No policy triggered"
        rewritten = context.get("text", "")
        triggered_rules = []
        for rule in self.policies:
            if self._match(rule, context):
                rule_action = rule.get("action", "allow")
                triggered_rules.append({
                    "name": rule.get("name"),
                    "category": rule.get("category"),
                    "action": rule_action,
                    "nist_rmf": self.get_nist_rmf_category(rule.get("category", "")),
                })
                if self._is_stricter(rule_action, action):
                    action = rule_action
                    reason = rule.get("message", f"Policy '{rule.get('name')}' matched")
                    if action == "mask":
                        for pattern in rule.get("patterns", []):
                            rewritten = re.sub(pattern, f"[{rule.get('category', 'REDACTED').upper()}]", rewritten)
                    elif action == "block":
                        rewritten = reason
        return {
            "action": action,
            "reason": reason,
            "rewritten_text": rewritten,
            "triggered_rules": triggered_rules,
            "nist_risk_level": self._get_overall_risk_level(triggered_rules),
        }

    def get_nist_rmf_category(self, category: str) -> dict:
        """Map a policy category to its NIST AI RMF function and subcategory."""
        return NIST_AI_RMF_MAP.get(category, NIST_AI_RMF_MAP["default"])

    def get_risk_severity_info(self, severity: str) -> dict:
        """Get NIST-aligned risk severity information for a given severity level."""
        return RISK_SEVERITY_MAP.get(severity, RISK_SEVERITY_MAP["off"])

    def _get_overall_risk_level(self, triggered_rules: list) -> str:
        """Determine overall NIST AI RMF risk level based on triggered rules."""
        if not triggered_rules:
            return "NEGLIGIBLE"
        # Highest severity action determines overall risk
        action_risk = {"block": "HIGH", "mask": "MEDIUM", "flag": "LOW", "allow": "NEGLIGIBLE"}
        max_risk = "NEGLIGIBLE"
        risk_order = ["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for rule in triggered_rules:
            rule_risk = action_risk.get(rule.get("action", "allow"), "NEGLIGIBLE")
            if risk_order.index(rule_risk) > risk_order.index(max_risk):
                max_risk = rule_risk
        return max_risk

    def _match(self, rule: dict, context: dict) -> bool:
        rule_type = rule.get("type")
        if rule_type == "toxicity":
            return self._match_toxicity(rule, context)
        elif rule_type == "pii":
            return self._match_pii(rule, context)
        return False

    def _match_toxicity(self, rule: dict, context: dict) -> bool:
        severity = rule.get("severity", "off")
        if severity == "off":
            return False
        # enabled check
        enabled = rule.get("enabled", True)
        if not enabled:
            return False
        toxic = context.get("toxic", False)
        if not toxic:
            return False
        thresholds = {"low": 0.3, "medium": 0.6, "high": 0.9, "critical": 0.95}
        threshold = thresholds.get(severity, 0.0)
        return context.get("toxic_score", 0.0) >= threshold

    def _match_pii(self, rule: dict, context: dict) -> bool:
        return rule.get("category") in context.get("pii_types", [])

    def _is_stricter(self, new_action: str, current_action: str) -> bool:
        order = {"block": 4, "mask": 3, "flag": 2, "allow": 1}
        return order.get(new_action, 0) > order.get(current_action, 0)

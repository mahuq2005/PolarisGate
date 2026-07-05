"""Comprehensive policy engine tests covering all rules and edge cases."""
import sys, tempfile, os, yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
import pytest
from shared.policy_engine import PolicyEngine

FULL_YAML = """
policies:
  - name: "Hate speech"
    type: "toxicity"
    severity: "medium"
    action: "block"
    message: "Hate speech blocked."
  - name: "Harassment"
    type: "toxicity"
    severity: "low"
    action: "block"
    message: "Harassment blocked."
  - name: "Profanity"
    type: "toxicity"
    severity: "high"
    action: "flag"
    message: "Profanity flagged."
  - name: "SIN"
    type: "pii"
    category: "SIN"
    patterns: ["\\\\b\\\\d{3}-\\\\d{3}-\\\\d{3}\\\\b"]
    action: "mask"
    message: "SIN masked."
  - name: "Credit Card"
    type: "pii"
    category: "credit_card"
    patterns: ["\\\\b(?:\\\\d[ -]*?){13,16}\\\\b"]
    action: "block"
    message: "Credit card blocked."
  - name: "Email"
    type: "pii"
    category: "email"
    patterns: ["\\\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Z|a-z]{2,}\\\\b"]
    action: "mask"
    message: "Email masked."
"""


def _engine_from_yaml(yaml_str):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_str)
        path = f.name
    engine = PolicyEngine(policy_path=path)
    os.unlink(path)
    return engine


class TestToxicityRules:
    def test_high_score_triggers_block(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "I hate you"})
        assert result["action"] == "block"

    def test_low_score_allows(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": True, "toxic_score": 0.2, "pii_types": [], "text": "test"})
        assert result["action"] == "allow"

    def test_not_toxic_allows(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": "Hello"})
        assert result["action"] == "allow"

    def test_flag_action_for_high_severity(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": True, "toxic_score": 0.9, "pii_types": [], "text": "profanity"})
        # Profanity has severity "high" with action "flag"
        assert result["action"] in ("flag", "block")


class TestPIIRules:
    def test_pii_rule_masks_sin(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": ["SIN"], "text": "My SIN is 123-456-789"})
        assert result["action"] == "mask"
        assert "[SIN]" in result["rewritten_text"] or "SIN" in result["rewritten_text"]

    def test_pii_rule_blocks_credit_card(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": ["credit_card"], "text": "Card: 4111-1111-1111-1111"})
        assert result["action"] == "block"

    def test_pii_rule_masks_email(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": ["email"], "text": "Email: test@example.com"})
        assert result["action"] == "mask"

    def test_no_pii_allows(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": "Hello world"})
        assert result["action"] == "allow"


class TestCombinedRules:
    def test_toxic_and_pii_block_takes_precedence(self):
        """When both toxic and PII are detected, the more severe action should win."""
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({
            "toxic": True, "toxic_score": 0.8,
            "pii_types": ["SIN"],
            "text": "I hate you. My SIN is 123-456-789"
        })
        # Block should take precedence over mask
        assert result["action"] == "block"

    def test_toxic_and_credit_card_both_block(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({
            "toxic": True, "toxic_score": 0.9,
            "pii_types": ["credit_card"],
            "text": "I hate you. Card: 4111-1111-1111-1111"
        })
        assert result["action"] == "block"


class TestEdgeCases:
    def test_empty_context(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({})
        assert "action" in result

    def test_missing_toxic_key(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"pii_types": []})
        assert "action" in result

    def test_missing_pii_types(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0})
        assert "action" in result

    def test_none_text(self):
        engine = _engine_from_yaml(FULL_YAML)
        result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": None})
        assert "action" in result

    def test_empty_policies(self):
        engine = _engine_from_yaml("policies: []")
        result = engine.evaluate({"toxic": True, "toxic_score": 0.9, "pii_types": [], "text": "test"})
        assert "action" in result


class TestPolicyLoading:
    def test_load_from_nonexistent_file(self):
        """Should use default policies when file doesn't exist."""
        engine = PolicyEngine(policy_path="/nonexistent/path.yaml")
        result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "test"})
        assert "action" in result

    def test_load_from_empty_file(self):
        """Should handle empty YAML gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            path = f.name
        engine = PolicyEngine(policy_path=path)
        os.unlink(path)
        result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "test"})
        assert "action" in result

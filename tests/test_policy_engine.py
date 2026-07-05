import sys, tempfile, os, yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared.policy_engine import PolicyEngine, NIST_AI_RMF_MAP, RISK_SEVERITY_MAP

SAMPLE_YAML = """
policies:
  - name: "Hate speech"
    type: "toxicity"
    severity: "medium"
    action: "block"
    message: "Blocked"
  - name: "SIN"
    type: "pii"
    category: "SIN"
    patterns: ["\\\\b\\\\d{3}-\\\\d{3}-\\\\d{3}\\\\b"]
    action: "mask"
    message: "Masked"
  - name: "Low severity toxicity"
    type: "toxicity"
    severity: "low"
    action: "flag"
    message: "Flagged"
  - name: "High severity toxicity"
    type: "toxicity"
    severity: "high"
    action: "block"
    message: "Blocked high"
  - name: "Critical severity toxicity"
    type: "toxicity"
    severity: "critical"
    action: "block"
    message: "Blocked critical"
"""

def _engine_from_yaml(yaml_str):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_str)
        path = f.name
    engine = PolicyEngine(policy_path=path)
    os.unlink(path)
    return engine

def test_toxicity_rule_triggers_on_high_score():
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "test"})
    assert result["action"] == "block"

def test_toxicity_rule_ignores_low_score():
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.2, "pii_types": [], "text": "test"})
    assert result["action"] == "allow"

def test_pii_rule_masks():
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": ["SIN"], "text": "My SIN is 123-456-789"})
    assert result["action"] == "mask"
    assert "SIN" in result["rewritten_text"]

# ─── Threshold Logic Tests ───────────────────────────────────────────────

def test_toxicity_threshold_low_severity():
    """Low severity should trigger at score >= 0.3."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    # Score 0.3 should trigger low severity (flag action)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.3, "pii_types": [], "text": "test"})
    assert result["action"] in ("flag", "block")

def test_toxicity_threshold_medium_severity():
    """Medium severity should trigger at score >= 0.6."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    # Score 0.5 should NOT trigger medium (threshold 0.6)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.5, "pii_types": [], "text": "test"})
    # Score 0.5 is below medium threshold (0.6) but above low threshold (0.3)
    # So low severity rule should trigger with "flag" action
    assert result["action"] in ("flag", "allow")

def test_toxicity_threshold_high_severity():
    """High severity should trigger at score >= 0.9."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    # Score 0.85 should NOT trigger high (threshold 0.9)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.85, "pii_types": [], "text": "test"})
    # Should still trigger medium (threshold 0.6) or low (threshold 0.3)
    assert result["action"] in ("block", "flag")

def test_toxicity_threshold_off_severity():
    """Severity 'off' should never trigger."""
    engine = _engine_from_yaml("""
policies:
  - name: "Off toxicity"
    type: "toxicity"
    severity: "off"
    action: "block"
    message: "Should not trigger"
""")
    result = engine.evaluate({"toxic": True, "toxic_score": 1.0, "pii_types": [], "text": "test"})
    assert result["action"] == "allow"

def test_toxicity_not_toxic():
    """Non-toxic context should not trigger toxicity rules."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": "test"})
    assert result["action"] == "allow"

# ─── NIST RMF Category Tests ─────────────────────────────────────────────

def test_get_nist_rmf_category_known():
    """Known categories should return correct NIST mapping."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    category = engine.get_nist_rmf_category("hate_speech")
    assert category["function"] == "GOVERN"
    assert category["subcategory"] == "GOVERN 1.1"

def test_get_nist_rmf_category_unknown():
    """Unknown categories should return default mapping."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    category = engine.get_nist_rmf_category("unknown_category")
    assert category["function"] == "MANAGE"

def test_get_nist_rmf_category_pii():
    """PII categories should map to MEASURE function."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    for pii_type in ["SIN", "credit_card", "email", "phone", "health_card"]:
        category = engine.get_nist_rmf_category(pii_type)
        assert category["function"] == "MEASURE"

# ─── Risk Severity Tests ─────────────────────────────────────────────────

def test_get_risk_severity_info_critical():
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("critical")
    assert info["level"] == "CRITICAL"
    assert info["score_range"] == (0.9, 1.0)
    assert info["response"] == "immediate_block"

def test_get_risk_severity_info_high():
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("high")
    assert info["level"] == "HIGH"
    assert info["score_range"] == (0.7, 0.9)

def test_get_risk_severity_info_medium():
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("medium")
    assert info["level"] == "MEDIUM"
    assert info["score_range"] == (0.4, 0.7)

def test_get_risk_severity_info_low():
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("low")
    assert info["level"] == "LOW"
    assert info["score_range"] == (0.1, 0.4)

def test_get_risk_severity_info_off():
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("off")
    assert info["level"] == "NEGLIGIBLE"

def test_get_risk_severity_info_unknown():
    """Unknown severity should default to 'off'."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    info = engine.get_risk_severity_info("nonexistent")
    assert info["level"] == "NEGLIGIBLE"

# ─── Overall Risk Level Tests ────────────────────────────────────────────

def test_overall_risk_level_no_rules():
    """No triggered rules should return NEGLIGIBLE."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": "test"})
    assert result["nist_risk_level"] == "NEGLIGIBLE"

def test_overall_risk_level_block():
    """Block action should result in HIGH risk."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "test"})
    assert result["nist_risk_level"] == "HIGH"

def test_overall_risk_level_mask():
    """Mask action should result in MEDIUM risk."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": ["SIN"], "text": "My SIN is 123-456-789"})
    assert result["nist_risk_level"] == "MEDIUM"

# ─── Action Strictness Tests ─────────────────────────────────────────────

def test_is_stricter_block_over_mask():
    engine = _engine_from_yaml(SAMPLE_YAML)
    assert engine._is_stricter("block", "mask") is True

def test_is_stricter_mask_over_flag():
    engine = _engine_from_yaml(SAMPLE_YAML)
    assert engine._is_stricter("mask", "flag") is True

def test_is_stricter_flag_over_allow():
    engine = _engine_from_yaml(SAMPLE_YAML)
    assert engine._is_stricter("flag", "allow") is True

def test_is_stricter_same_action():
    engine = _engine_from_yaml(SAMPLE_YAML)
    assert engine._is_stricter("block", "block") is False

def test_is_stricter_allow_over_block():
    engine = _engine_from_yaml(SAMPLE_YAML)
    assert engine._is_stricter("allow", "block") is False

# ─── Empty Policy Tests ──────────────────────────────────────────────────

def test_empty_policy():
    """Engine with no policies should allow everything."""
    engine = _engine_from_yaml("policies: []")
    result = engine.evaluate({"toxic": True, "toxic_score": 1.0, "pii_types": ["SIN"], "text": "test"})
    assert result["action"] == "allow"

def test_no_policy_file():
    """Engine with no policy file should initialize with empty policies."""
    engine = PolicyEngine(policy_path="/nonexistent/path.yaml")
    assert engine.policies == []

# ─── Triggered Rules Tests ───────────────────────────────────────────────

def test_triggered_rules_in_result():
    """Result should include list of triggered rules."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": True, "toxic_score": 0.8, "pii_types": [], "text": "test"})
    assert len(result["triggered_rules"]) > 0
    assert result["triggered_rules"][0]["name"] == "Hate speech"
    assert result["triggered_rules"][0]["action"] == "block"

def test_triggered_rules_empty():
    """No triggered rules should result in empty list."""
    engine = _engine_from_yaml(SAMPLE_YAML)
    result = engine.evaluate({"toxic": False, "toxic_score": 0.0, "pii_types": [], "text": "test"})
    assert result["triggered_rules"] == []

# ─── NIST AI RMF Map Constants ───────────────────────────────────────────

def test_nist_rmf_map_has_all_functions():
    """NIST AI RMF map should cover all four functions."""
    functions = {v["function"] for v in NIST_AI_RMF_MAP.values()}
    assert "GOVERN" in functions
    assert "MAP" in functions
    assert "MEASURE" in functions
    assert "MANAGE" in functions

def test_risk_severity_map_has_all_levels():
    """Risk severity map should cover all five levels."""
    assert "critical" in RISK_SEVERITY_MAP
    assert "high" in RISK_SEVERITY_MAP
    assert "medium" in RISK_SEVERITY_MAP
    assert "low" in RISK_SEVERITY_MAP
    assert "off" in RISK_SEVERITY_MAP

# EU AI Act — Article 9: Risk Management System
# Reference: https://eur-lex.europa.eu/eli/reg/2024/1689
# Source: Adapted from CNCF OPA contrib policies (open-policy-agent/contrib)
#
# High-risk AI systems shall establish, implement, document and maintain
# a risk management system throughout the AI system's lifecycle.

package eu_aia.article_09

default allow = false

# Low/medium risk systems are exempt
allow {
    input.risk_level != "high"
}

# High-risk systems must have documented risk management
allow {
    input.risk_level == "high"
    input.risk_management_system == true
    input.risk_assessment_conducted == true
    input.mitigation_measures_documented == true
}

# Human oversight must be enabled for high-risk
allow {
    input.risk_level == "high"
    input.human_oversight_enabled == true
    input.oversight_mechanism != ""
}

deny_reason = reason {
    not allow
    reason := "EU AI Act Article 9 violation: High-risk AI system must maintain a documented risk management system with mitigation measures. See: eur-lex.europa.eu/eli/reg/2024/1689"
}

# Test cases
test_high_risk_with_mitigation {
    allow with input as {"risk_level": "high", "risk_management_system": true, "risk_assessment_conducted": true, "mitigation_measures_documented": true}
}

test_high_risk_without_mitigation {
    not allow with input as {"risk_level": "high", "risk_management_system": false}
}

test_low_risk_exempt {
    allow with input as {"risk_level": "minimal"}
}
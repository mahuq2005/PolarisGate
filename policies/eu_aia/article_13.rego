# EU AI Act — Article 13: Transparency and Provision of Information
# Reference: https://eur-lex.europa.eu/eli/reg/2024/1689
# Source: Adapted from EU AI Act regulatory text
#
# AI systems shall be designed and developed in such a way that their
# operation is sufficiently transparent to enable users to interpret output.

package eu_aia.article_13

default allow = false

allow {
    input.transparency_documentation != ""
    input.capabilities_documented == true
    input.limitations_disclosed == true
}

allow {
    input.risk_level == "minimal"
    input.transparency_documentation != ""
}

deny_reason = reason {
    not allow
    reason := "EU AI Act Article 13 violation: AI system must provide transparency documentation disclosing capabilities and limitations"
}

# Test cases
test_full_disclosure_pass {
    allow with input as {"transparency_documentation": "provided", "capabilities_documented": true, "limitations_disclosed": true, "risk_level": "high"}
}

test_missing_limitations_fail {
    not allow with input as {"transparency_documentation": "provided", "capabilities_documented": true, "limitations_disclosed": false, "risk_level": "high"}
}

test_minimal_risk_basic_pass {
    allow with input as {"risk_level": "minimal", "transparency_documentation": "basic"}
}
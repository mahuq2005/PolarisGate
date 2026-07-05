# EU AI Act — Article 14: Human Oversight
# Reference: https://eur-lex.europa.eu/eli/reg/2024/1689
#
# High-risk AI systems shall be designed to allow effective human oversight
# during the period they are in use.

package eu_aia.article_14

default allow = false

allow {
    input.human_oversight_enabled == true
    input.override_mechanism == true
}

allow {
    input.risk_level == "minimal"
}

allow {
    input.risk_level == "limited"
    input.human_review_period_days > 0
}

deny_reason = reason {
    not allow
    reason := "EU AI Act Article 14 violation: AI system must have human oversight with override mechanism"
}

test_high_risk_with_oversight {
    allow with input as {"risk_level": "high", "human_oversight_enabled": true, "override_mechanism": true}
}

test_high_risk_without_oversight {
    not allow with input as {"risk_level": "high", "human_oversight_enabled": false, "override_mechanism": true}
}

test_minimal_risk_exempt {
    allow with input as {"risk_level": "minimal"}
}
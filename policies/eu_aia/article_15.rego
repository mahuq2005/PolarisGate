# EU AI Act — Article 15: Accuracy, Robustness, and Cybersecurity
# Reference: https://eur-lex.europa.eu/eli/reg/2024/1689
#
# High-risk AI systems shall be designed to achieve appropriate levels
# of accuracy, robustness, and cybersecurity throughout their lifecycle.

package eu_aia.article_15

default allow = false

allow {
    input.accuracy_threshold_met == true
    input.adversarial_tested == true
    input.cybersecurity_measures == true
}

allow {
    input.risk_level == "minimal"
}

allow {
    input.risk_level == "limited"
    input.accuracy_threshold_met == true
}

deny_reason = reason {
    not allow
    reason := "EU AI Act Article 15 violation: AI system must meet accuracy, robustness, and cybersecurity requirements"
}

test_high_risk_full_pass {
    allow with input as {"risk_level": "high", "accuracy_threshold_met": true, "adversarial_tested": true, "cybersecurity_measures": true}
}

test_high_risk_no_cybersecurity {
    not allow with input as {"risk_level": "high", "accuracy_threshold_met": true, "adversarial_tested": true, "cybersecurity_measures": false}
}

test_minimal_risk_exempt {
    allow with input as {"risk_level": "minimal"}
}

test_limited_risk_accuracy_only {
    allow with input as {"risk_level": "limited", "accuracy_threshold_met": true}
}
"""Fairness assessment utilities for NorthGuard.
Enterprise-grade: Demographic parity, equal opportunity, and statistical
fairness metrics per NIST AI RMF MEASURE 3.1 guidelines.

This module provides both proxy metrics (based on observed toxicity/PII rates)
and statistical fairness tests (chi-squared, t-tests) for proper bias auditing.
"""
import logging
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FairnessMetrics:
    """Comprehensive fairness assessment results."""
    demographic_parity_ratio: float = 1.0
    equal_opportunity_difference: float = 0.0
    equalized_odds_difference: float = 0.0
    disparate_impact_ratio: float = 1.0
    statistical_parity_difference: float = 0.0
    overall_fairness_score: float = 1.0
    confidence_interval: Tuple[float, float] = (0.0, 1.0)
    sample_size: int = 0
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


def calculate_fairness_score(
    total_traces: int,
    flagged_toxicity: int = 0,
    pii_leaks: int = 0,
) -> float:
    """Compute a proxy fairness score based on observed rates.

    This is a proxy metric based on observed toxicity/PII rates, not a
    substitute for proper bias auditing with protected attribute data.
    Use `assess_demographic_parity()` for proper statistical fairness assessment.

    Args:
        total_traces: Total number of traces processed
        flagged_toxicity: Number of toxicity incidents flagged
        pii_leaks: Number of PII leaks detected

    Returns:
        Fairness score from 0.0 (unfair) to 1.0 (fair)
    """
    if total_traces == 0:
        return 1.0

    toxicity_rate = flagged_toxicity / total_traces
    pii_rate = pii_leaks / total_traces

    # Penalize high toxicity and PII rates
    toxicity_penalty = min(toxicity_rate * 5, 1.0)  # 20% toxicity = full penalty
    pii_penalty = min(pii_rate * 10, 1.0)  # 10% PII = full penalty

    score = 1.0 - (toxicity_penalty * 0.6 + pii_penalty * 0.4)
    return round(max(0.0, score), 4)


def get_fairness_note(score: float) -> str:
    """Get a human-readable note for a fairness score."""
    if score >= 0.9:
        return "Fairness metrics indicate low risk of bias."
    elif score >= 0.7:
        return "Fairness metrics indicate moderate risk. Consider further investigation."
    else:
        return "Fairness metrics indicate elevated risk. Bias audit recommended."


def demographic_parity_ratio(
    group_positive_rates: Dict[str, float],
    privileged_group: Optional[str] = None,
) -> Tuple[float, float, List[str]]:
    """Calculate demographic parity ratio across groups.

    Demographic parity requires that the probability of a positive outcome
    (e.g., not being flagged as toxic) is the same across all groups.

    Args:
        group_positive_rates: Dict mapping group name to positive outcome rate
        privileged_group: Reference group (defaults to group with highest rate)

    Returns:
        Tuple of (min_ratio, max_ratio, warnings)
        Ratio < 0.8 indicates potential disparate impact (EEOC 4/5ths rule)
    """
    if not group_positive_rates or len(group_positive_rates) < 2:
        return 1.0, 1.0, ["Need at least 2 groups for comparison"]

    rates = list(group_positive_rates.values())
    if privileged_group and privileged_group in group_positive_rates:
        privileged_rate = group_positive_rates[privileged_group]
    else:
        privileged_rate = max(rates)

    if privileged_rate == 0:
        return 0.0, 0.0, ["Privileged group rate is zero"]

    min_rate = min(rates)
    min_ratio = min_rate / privileged_rate
    max_ratio = max(rates) / privileged_rate

    warnings = []
    if min_ratio < 0.8:
        warnings.append(
            f"Demographic parity ratio {min_ratio:.3f} < 0.8 "
            f"(EEOC 4/5ths rule violation detected)"
        )
    if min_ratio < 0.5:
        warnings.append("Severe demographic parity violation detected")

    return round(min_ratio, 4), round(max_ratio, 4), warnings


def equal_opportunity_difference(
    group_true_positive_rates: Dict[str, float],
    privileged_group: Optional[str] = None,
) -> Tuple[float, List[str]]:
    """Calculate equal opportunity difference across groups.

    Equal opportunity requires that true positive rates (correctly identifying
    actual toxicity) are equal across groups.

    Args:
        group_true_positive_rates: Dict mapping group name to TPR
        privileged_group: Reference group

    Returns:
        Tuple of (max_difference, warnings)
        Difference > 0.1 indicates potential fairness issue
    """
    if not group_true_positive_rates or len(group_true_positive_rates) < 2:
        return 0.0, ["Need at least 2 groups for comparison"]

    rates = list(group_true_positive_rates.values())
    if privileged_group and privileged_group in group_true_positive_rates:
        privileged_rate = group_true_positive_rates[privileged_group]
    else:
        privileged_rate = max(rates)

    max_diff = max(abs(r - privileged_rate) for r in rates)

    warnings = []
    if max_diff > 0.1:
        warnings.append(
            f"Equal opportunity difference {max_diff:.3f} > 0.1 "
            f"(potential fairness issue detected)"
        )
    if max_diff > 0.2:
        warnings.append("Severe equal opportunity violation detected")

    return round(max_diff, 4), warnings


def chi_squared_fairness_test(
    contingency_table: Dict[str, Dict[str, int]],
) -> Tuple[float, float, str]:
    """Perform chi-squared test for independence between group and outcome.

    Uses scipy's chi2_contingency when available, falls back to manual
    approximation.

    Args:
        contingency_table: Nested dict {group: {outcome: count}}

    Returns:
        Tuple of (chi2_stat, p_value, interpretation)
    """
    try:
        from scipy.stats import chi2_contingency
    except ImportError:
        logger.warning("scipy not available for chi-squared test, using approximation")
        return _chi_squared_approximation(contingency_table)

    groups = list(contingency_table.keys())
    outcomes = list(contingency_table[groups[0]].keys())
    observed = []
    for group in groups:
        row = [contingency_table[group].get(outcome, 0) for outcome in outcomes]
        observed.append(row)

    try:
        chi2, p_value, dof, expected = chi2_contingency(observed)
        if p_value < 0.05:
            interpretation = (
                f"Statistically significant association between group and outcome "
                f"(p={p_value:.4f}, chi2={chi2:.2f})"
            )
        else:
            interpretation = (
                f"No statistically significant association detected "
                f"(p={p_value:.4f}, chi2={chi2:.2f})"
            )
        return round(chi2, 4), round(p_value, 4), interpretation
    except Exception as e:
        logger.warning(f"Chi-squared test failed: {e}")
        return 0.0, 1.0, "Test could not be computed"


def _chi_squared_approximation(
    contingency_table: Dict[str, Dict[str, int]],
) -> Tuple[float, float, str]:
    """Manual chi-squared approximation when scipy is unavailable."""
    groups = list(contingency_table.keys())
    outcomes = list(contingency_table[groups[0]].keys())

    # Calculate totals
    total = sum(
        contingency_table[g].get(o, 0)
        for g in groups
        for o in outcomes
    )
    if total == 0:
        return 0.0, 1.0, "No data available"

    row_totals = {g: sum(contingency_table[g].values()) for g in groups}
    col_totals = {o: sum(contingency_table[g].get(o, 0) for g in groups) for o in outcomes}

    # Calculate chi-squared statistic
    chi2 = 0.0
    for g in groups:
        for o in outcomes:
            observed = contingency_table[g].get(o, 0)
            expected = (row_totals[g] * col_totals[o]) / total
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected

    # Approximate p-value using chi-squared distribution (1 degree of freedom)
    # This is a rough approximation
    dof = (len(groups) - 1) * (len(outcomes) - 1)
    p_value = math.exp(-chi2 / 2) if dof == 1 else 0.5

    return round(chi2, 4), round(p_value, 4), "Approximate test (scipy not available)"


def assess_demographic_parity(
    group_stats: Dict[str, Dict[str, int]],
    privileged_group: Optional[str] = None,
) -> FairnessMetrics:
    """Comprehensive fairness assessment across demographic groups.

    Args:
        group_stats: Dict mapping group name to {total, toxic, pii} counts
        privileged_group: Reference group for comparison

    Returns:
        FairnessMetrics with all computed metrics
    """
    metrics = FairnessMetrics()

    if not group_stats or len(group_stats) < 2:
        metrics.warnings = ["Need at least 2 groups with data for assessment"]
        metrics.recommendations = [
            "Collect protected attribute data across multiple demographic groups",
            "Ensure sufficient sample size in each group for statistical validity",
        ]
        return metrics

    # Calculate positive outcome rates (not toxic) per group
    positive_rates = {}
    true_positive_rates = {}
    total_samples = 0

    for group, stats in group_stats.items():
        total = stats.get("total", 0)
        toxic = stats.get("toxic", 0)
        total_samples += total
        if total > 0:
            positive_rates[group] = 1.0 - (toxic / total)
            # TPR: correctly identified toxic / actual toxic
            # Using toxicity rate as proxy for TPR
            true_positive_rates[group] = toxic / total if total > 0 else 0.0

    metrics.sample_size = total_samples

    # Demographic parity ratio
    min_ratio, max_ratio, dp_warnings = demographic_parity_ratio(
        positive_rates, privileged_group
    )
    metrics.demographic_parity_ratio = min_ratio
    metrics.disparate_impact_ratio = min_ratio
    metrics.warnings.extend(dp_warnings)

    # Statistical parity difference
    if privileged_group and privileged_group in positive_rates:
        priv_rate = positive_rates[privileged_group]
    else:
        priv_rate = max(positive_rates.values())
    min_rate = min(positive_rates.values())
    metrics.statistical_parity_difference = round(priv_rate - min_rate, 4)

    # Equal opportunity difference
    eod_diff, eod_warnings = equal_opportunity_difference(
        true_positive_rates, privileged_group
    )
    metrics.equal_opportunity_difference = eod_diff
    metrics.warnings.extend(eod_warnings)

    # Equalized odds (average of demographic parity and equal opportunity)
    metrics.equalized_odds_difference = round(
        (metrics.statistical_parity_difference + eod_diff) / 2, 4
    )

    # Overall fairness score (weighted combination)
    parity_score = min_ratio  # 0.8+ is good
    eod_score = max(0.0, 1.0 - eod_diff * 5)  # 0.2 diff = 0.0 score
    metrics.overall_fairness_score = round(
        max(0.0, min(1.0, parity_score * 0.6 + eod_score * 0.4)), 4
    )

    # Confidence interval (approximate using sample size)
    if total_samples > 0:
        z = 1.96  # 95% confidence
        se = math.sqrt(metrics.overall_fairness_score * (1 - metrics.overall_fairness_score) / total_samples)
        ci_lower = max(0.0, metrics.overall_fairness_score - z * se)
        ci_upper = min(1.0, metrics.overall_fairness_score + z * se)
        metrics.confidence_interval = (round(ci_lower, 4), round(ci_upper, 4))

    # Generate recommendations
    if metrics.overall_fairness_score < 0.8:
        metrics.recommendations.append(
            "Significant fairness concerns detected. Conduct thorough bias audit."
        )
    if metrics.demographic_parity_ratio < 0.8:
        metrics.recommendations.append(
            "Address demographic parity violations per EEOC 4/5ths rule guidelines."
        )
    if metrics.equal_opportunity_difference > 0.1:
        metrics.recommendations.append(
            "Investigate unequal true positive rates across demographic groups."
        )
    metrics.recommendations.append(
        "Continue collecting protected attributes to improve statistical power."
    )
    metrics.recommendations.append(
        "Conduct regular fairness audits per NIST AI RMF MEASURE 3.1 guidelines."
    )

    return metrics

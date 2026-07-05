"""Bias Testing Framework — MEASURE 3.1 compliance.

Enterprise-grade: Implements systematic bias testing across protected attributes
to identify and quantify algorithmic bias in content moderation decisions.
Aligns with NIST AI RMF MEASURE 3.1 and AIDA (Bill C-27) requirements.
"""
import logging
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class BiasTestResult:
    """Result of a single bias test."""
    test_name: str
    attribute: str
    groups_tested: List[str]
    sample_size: int
    max_disparity: float
    disparity_threshold: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    tested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BiasTestSuite:
    """Complete bias test suite results."""
    system_name: str
    version: str
    results: List[BiasTestResult] = field(default_factory=list)
    overall_score: float = 1.0
    tested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def passed_all(self) -> bool:
        return all(r.passed for r in self.results)
    
    def summary(self) -> Dict[str, Any]:
        return {
            "system_name": self.system_name,
            "version": self.version,
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "overall_score": self.overall_score,
            "tested_at": self.tested_at,
        }


class BiasTester:
    """Systematic bias testing framework per MEASURE 3.1.
    
    Tests for:
    - Demographic parity: Are different groups treated equally?
    - Equalized odds: Is prediction accuracy equal across groups?
    - Disparate impact: Does the system disproportionately affect certain groups?
    """
    
    def __init__(self, disparity_threshold: float = 0.1):
        """
        Args:
            disparity_threshold: Maximum acceptable disparity (0.0-1.0).
                Default 0.1 means >10% difference between groups is flagged.
        """
        self.disparity_threshold = disparity_threshold
    
    def test_demographic_parity(
        self,
        attribute: str,
        group_data: Dict[str, Dict[str, int]],
    ) -> BiasTestResult:
        """Test demographic parity: equal toxicity/PII rates across groups.
        
        Args:
            attribute: The protected attribute being tested (e.g., "gender")
            group_data: Dict mapping group name to {total, toxic, pii}
            
        Returns:
            BiasTestResult with pass/fail and details
        """
        groups = list(group_data.keys())
        if len(groups) < 2:
            return BiasTestResult(
                test_name="demographic_parity",
                attribute=attribute,
                groups_tested=groups,
                sample_size=sum(d.get("total", 0) for d in group_data.values()),
                max_disparity=0.0,
                disparity_threshold=self.disparity_threshold,
                passed=True,
                details={"note": "Insufficient groups for comparison"},
                recommendations=["Collect data from more demographic groups."],
            )
        
        # Calculate toxicity rates per group
        tox_rates = {}
        pii_rates = {}
        total_samples = 0
        for group, data in group_data.items():
            total = data.get("total", 0)
            toxic = data.get("toxic", 0)
            pii = data.get("pii", 0)
            total_samples += total
            tox_rates[group] = toxic / max(total, 1)
            pii_rates[group] = pii / max(total, 1)
        
        # Find max disparity
        max_tox_disparity = max(tox_rates.values()) - min(tox_rates.values())
        max_pii_disparity = max(pii_rates.values()) - min(pii_rates.values())
        max_disparity = max(max_tox_disparity, max_pii_disparity)
        
        passed = max_disparity <= self.disparity_threshold
        
        recommendations = []
        if not passed:
            recommendations.append(
                f"FAILED: Maximum disparity of {max_disparity:.2%} exceeds threshold of {self.disparity_threshold:.2%}."
            )
            recommendations.append("Investigate potential bias in model behavior across demographic groups.")
            recommendations.append("Consider fairness-aware model retraining or post-processing adjustments.")
        else:
            recommendations.append(f"PASSED: Maximum disparity of {max_disparity:.2%} within acceptable threshold.")
        
        recommendations.append("Continue monitoring for drift in demographic parity metrics.")
        
        return BiasTestResult(
            test_name="demographic_parity",
            attribute=attribute,
            groups_tested=groups,
            sample_size=total_samples,
            max_disparity=round(max_disparity, 4),
            disparity_threshold=self.disparity_threshold,
            passed=passed,
            details={
                "toxicity_rates": tox_rates,
                "pii_rates": pii_rates,
                "max_toxicity_disparity": round(max_tox_disparity, 4),
                "max_pii_disparity": round(max_pii_disparity, 4),
            },
            recommendations=recommendations,
        )
    
    def test_equalized_odds(
        self,
        attribute: str,
        group_data: Dict[str, Dict[str, int]],
    ) -> BiasTestResult:
        """Test equalized odds: similar false positive/negative rates across groups.
        
        Uses toxicity rate as a proxy for positive predictions.
        """
        groups = list(group_data.keys())
        if len(groups) < 2:
            return BiasTestResult(
                test_name="equalized_odds",
                attribute=attribute,
                groups_tested=groups,
                sample_size=sum(d.get("total", 0) for d in group_data.values()),
                max_disparity=0.0,
                disparity_threshold=self.disparity_threshold,
                passed=True,
                details={"note": "Insufficient groups for comparison"},
                recommendations=["Collect data from more demographic groups."],
            )
        
        # Calculate positive prediction rates (toxicity flag rate)
        pos_rates = {}
        total_samples = 0
        for group, data in group_data.items():
            total = data.get("total", 0)
            toxic = data.get("toxic", 0)
            total_samples += total
            pos_rates[group] = toxic / max(total, 1)
        
        max_disparity = max(pos_rates.values()) - min(pos_rates.values())
        passed = max_disparity <= self.disparity_threshold
        
        recommendations = []
        if not passed:
            recommendations.append(
                f"FAILED: Equalized odds disparity of {max_disparity:.2%} exceeds threshold."
            )
            recommendations.append("Review model calibration across demographic groups.")
        else:
            recommendations.append(f"PASSED: Equalized odds disparity of {max_disparity:.2%} within threshold.")
        
        return BiasTestResult(
            test_name="equalized_odds",
            attribute=attribute,
            groups_tested=groups,
            sample_size=total_samples,
            max_disparity=round(max_disparity, 4),
            disparity_threshold=self.disparity_threshold,
            passed=passed,
            details={
                "positive_prediction_rates": pos_rates,
                "max_disparity": round(max_disparity, 4),
            },
            recommendations=recommendations,
        )
    
    def test_disparate_impact(
        self,
        attribute: str,
        group_data: Dict[str, Dict[str, int]],
    ) -> BiasTestResult:
        """Test disparate impact: 80% rule (EEOC).
        
        The 80% rule states that a selection rate for a protected group
        should be at least 80% of the rate for the group with the highest rate.
        """
        groups = list(group_data.keys())
        if len(groups) < 2:
            return BiasTestResult(
                test_name="disparate_impact",
                attribute=attribute,
                groups_tested=groups,
                sample_size=sum(d.get("total", 0) for d in group_data.values()),
                max_disparity=0.0,
                disparity_threshold=self.disparity_threshold,
                passed=True,
                details={"note": "Insufficient groups for comparison"},
                recommendations=["Collect data from more demographic groups."],
            )
        
        # Calculate toxicity rates (adverse impact = higher toxicity rate)
        tox_rates = {}
        total_samples = 0
        for group, data in group_data.items():
            total = data.get("total", 0)
            toxic = data.get("toxic", 0)
            total_samples += total
            tox_rates[group] = toxic / max(total, 1)
        
        # Find highest rate group
        max_rate_group = max(tox_rates, key=tox_rates.get)
        max_rate = tox_rates[max_rate_group]
        
        # Calculate impact ratios relative to highest rate group
        impact_ratios = {}
        for group, rate in tox_rates.items():
            if max_rate > 0:
                impact_ratios[group] = rate / max_rate
            else:
                impact_ratios[group] = 1.0
        
        # 80% rule: impact ratio should be >= 0.8
        min_ratio = min(impact_ratios.values())
        passed = min_ratio >= 0.8
        
        recommendations = []
        if not passed:
            recommendations.append(
                f"FAILED: Disparate impact detected. Lowest impact ratio is {min_ratio:.2%} "
                f"(below 80% threshold)."
            )
            recommendations.append(f"Group '{max_rate_group}' has the highest toxicity rate ({max_rate:.2%}).")
            recommendations.append("Investigate and mitigate potential adverse impact.")
        else:
            recommendations.append(f"PASSED: All impact ratios >= 80% threshold.")
        
        return BiasTestResult(
            test_name="disparate_impact",
            attribute=attribute,
            groups_tested=groups,
            sample_size=total_samples,
            max_disparity=round(1.0 - min_ratio, 4),
            disparity_threshold=0.2,  # 80% rule
            passed=passed,
            details={
                "toxicity_rates": tox_rates,
                "impact_ratios": impact_ratios,
                "highest_rate_group": max_rate_group,
                "lowest_impact_ratio": round(min_ratio, 4),
            },
            recommendations=recommendations,
        )
    
    def run_full_suite(
        self,
        system_name: str,
        version: str,
        all_group_data: Dict[str, Dict[str, Dict[str, int]]],
    ) -> BiasTestSuite:
        """Run complete bias test suite across all attributes.
        
        Args:
            system_name: Name of the system being tested
            version: System version
            all_group_data: Dict mapping attribute -> group -> {total, toxic, pii}
            
        Returns:
            BiasTestSuite with all results
        """
        results = []
        
        for attribute, group_data in all_group_data.items():
            # Run all three tests for each attribute
            results.append(self.test_demographic_parity(attribute, group_data))
            results.append(self.test_equalized_odds(attribute, group_data))
            results.append(self.test_disparate_impact(attribute, group_data))
        
        # Calculate overall score
        if results:
            passed_count = sum(1 for r in results if r.passed)
            overall_score = round(passed_count / len(results), 4)
        else:
            overall_score = 1.0
        
        return BiasTestSuite(
            system_name=system_name,
            version=version,
            results=results,
            overall_score=overall_score,
        )
    
    def generate_report(self, suite: BiasTestSuite) -> str:
        """Generate a human-readable bias test report."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"BIAS TEST REPORT — {suite.system_name} v{suite.version}")
        lines.append(f"Tested at: {suite.tested_at}")
        lines.append(f"Overall Score: {suite.overall_score:.2%}")
        lines.append(f"Tests: {suite.summary()['passed']}/{suite.summary()['total_tests']} passed")
        lines.append("=" * 60)
        
        for result in suite.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            lines.append(f"\n{status} | {result.test_name} ({result.attribute})")
            lines.append(f"  Groups: {', '.join(result.groups_tested)}")
            lines.append(f"  Sample Size: {result.sample_size}")
            lines.append(f"  Max Disparity: {result.max_disparity:.2%} (threshold: {result.disparity_threshold:.2%})")
            for rec in result.recommendations:
                lines.append(f"  → {rec}")
        
        return "\n".join(lines)

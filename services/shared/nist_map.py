"""NIST AI Risk Management Framework (MAP 2.2) — Risk Impact Assessment.

Enterprise-grade: Implements NIST AI RMF MAP 2.2 guidelines for risk assessment,
including impact characterization, risk scoring, and mitigation planning.
Aligns with AIDA (Bill C-27) requirements for high-impact system oversight.
"""
import json, logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class RiskFactor:
    """A single risk factor with scoring per NIST MAP 2.2 guidelines."""
    name: str
    category: str  # "technical", "operational", "societal", "legal"
    severity: str  # "low", "medium", "high", "critical"
    likelihood: str  # "unlikely", "possible", "likely", "very_likely"
    impact: str  # "negligible", "minor", "moderate", "major", "severe"
    description: str = ""
    mitigation: str = ""
    
    def severity_score(self) -> float:
        scores = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        return scores.get(self.severity, 0.5)
    
    def likelihood_score(self) -> float:
        scores = {"unlikely": 0.2, "possible": 0.4, "likely": 0.6, "very_likely": 0.8}
        return scores.get(self.likelihood, 0.4)
    
    def impact_score(self) -> float:
        scores = {"negligible": 0.1, "minor": 0.3, "moderate": 0.5, "major": 0.7, "severe": 0.9}
        return scores.get(self.impact, 0.5)
    
    def risk_score(self) -> float:
        """Calculate composite risk score per NIST MAP 2.2.
        
        Risk = Severity × Likelihood × Impact
        """
        return round(self.severity_score() * self.likelihood_score() * self.impact_score(), 4)


@dataclass
class RiskAssessment:
    """Complete risk assessment report per NIST MAP 2.2."""
    system_name: str
    version: str
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    factors: List[RiskFactor] = field(default_factory=list)
    overall_risk_score: float = 0.0
    risk_level: str = "unknown"  # "minimal", "low", "medium", "high", "critical"
    recommendations: List[str] = field(default_factory=list)
    
    def calculate_overall_risk(self):
        """Calculate overall risk score and level."""
        if not self.factors:
            self.overall_risk_score = 0.0
            self.risk_level = "minimal"
            return
        
        scores = [f.risk_score() for f in self.factors]
        self.overall_risk_score = round(sum(scores) / len(scores), 4)
        
        # Map to risk level
        if self.overall_risk_score < 0.05:
            self.risk_level = "minimal"
        elif self.overall_risk_score < 0.15:
            self.risk_level = "low"
        elif self.overall_risk_score < 0.3:
            self.risk_level = "medium"
        elif self.overall_risk_score < 0.5:
            self.risk_level = "high"
        else:
            self.risk_level = "critical"


class NISTRiskAssessor:
    """NIST AI RMF MAP 2.2 compliant risk assessor.
    
    Provides systematic risk identification, assessment, and mitigation
    planning for AI systems in accordance with NIST guidelines.
    """
    
    def __init__(self):
        self._default_factors = self._create_default_factors()
    
    def _create_default_factors(self) -> List[RiskFactor]:
        """Create default risk factors for a content moderation AI system."""
        return [
            RiskFactor(
                name="Toxicity Misclassification",
                category="technical",
                severity="high",
                likelihood="possible",
                impact="moderate",
                description="False negatives allow toxic content through; false positives block legitimate content.",
                mitigation="Multi-tier detection (keyword + BERT + LLM) with configurable thresholds.",
            ),
            RiskFactor(
                name="PII Exposure",
                category="legal",
                severity="critical",
                likelihood="possible",
                impact="major",
                description="Failure to detect and mask PII could lead to privacy breaches and regulatory penalties.",
                mitigation="Regex detection with Luhn validation, LLM verification, automatic masking.",
            ),
            RiskFactor(
                name="Bias and Fairness",
                category="societal",
                severity="high",
                likelihood="likely",
                impact="moderate",
                description="AI models may exhibit bias against certain demographics, leading to unfair treatment.",
                mitigation="Protected attribute monitoring, fairness scoring, bias testing per MEASURE 3.1.",
            ),
            RiskFactor(
                name="Model Drift",
                category="technical",
                severity="medium",
                likelihood="likely",
                impact="minor",
                description="Model performance may degrade over time as data distributions shift.",
                mitigation="Automated drift detection with alerts, periodic model re-evaluation.",
            ),
            RiskFactor(
                name="Adversarial Input",
                category="technical",
                severity="high",
                likelihood="possible",
                impact="moderate",
                description="Attackers may craft inputs to bypass content filters or trigger false positives.",
                mitigation="Input sanitization, rate limiting, anomaly detection, audit logging.",
            ),
            RiskFactor(
                name="Regulatory Compliance",
                category="legal",
                severity="high",
                likelihood="possible",
                impact="major",
                description="Non-compliance with AIDA (Bill C-27) or other regulations could result in penalties.",
                mitigation="Automated compliance reporting, audit trails, right-to-erasure endpoints.",
            ),
            RiskFactor(
                name="Data Privacy",
                category="legal",
                severity="critical",
                likelihood="possible",
                impact="severe",
                description="Processing of user data without proper safeguards could violate privacy laws.",
                mitigation="Data retention policies, encryption at rest, PII masking in logs.",
            ),
            RiskFactor(
                name="Operational Reliability",
                category="operational",
                severity="medium",
                likelihood="unlikely",
                impact="moderate",
                description="Service outages or degraded performance could impact business operations.",
                mitigation="Health checks, circuit breakers, connection pooling, graceful degradation.",
            ),
        ]
    
    def assess(self, system_name: str, version: str,
               custom_factors: List[RiskFactor] = None) -> RiskAssessment:
        """Perform a complete risk assessment.
        
        Args:
            system_name: Name of the AI system
            version: System version
            custom_factors: Optional custom risk factors (uses defaults if not provided)
            
        Returns:
            RiskAssessment with overall score, level, and recommendations
        """
        factors = custom_factors or self._default_factors
        
        assessment = RiskAssessment(
            system_name=system_name,
            version=version,
            factors=factors,
        )
        assessment.calculate_overall_risk()
        
        # Generate recommendations based on risk level
        assessment.recommendations = self._generate_recommendations(assessment)
        
        logger.info(
            f"NIST Risk Assessment for {system_name} v{version}: "
            f"score={assessment.overall_risk_score}, level={assessment.risk_level}"
        )
        
        return assessment
    
    def _generate_recommendations(self, assessment: RiskAssessment) -> List[str]:
        """Generate mitigation recommendations based on risk assessment."""
        recommendations = []
        
        # General recommendations
        recommendations.append("Maintain multi-tier content moderation pipeline (keyword + BERT + LLM).")
        recommendations.append("Conduct regular bias audits and fairness assessments.")
        recommendations.append("Implement continuous monitoring for model drift and performance degradation.")
        
        # Risk-level specific recommendations
        if assessment.risk_level in ("high", "critical"):
            recommendations.append("URGENT: Engage legal counsel for AIDA compliance review.")
            recommendations.append("URGENT: Implement human-in-the-loop oversight for all enforcement decisions.")
            recommendations.append("Conduct third-party security audit of the system.")
            recommendations.append("Establish incident response plan for AI safety events.")
        
        if assessment.risk_level == "medium":
            recommendations.append("Schedule quarterly compliance reviews.")
            recommendations.append("Enhance monitoring and alerting for anomalous patterns.")
        
        # Factor-specific recommendations
        for factor in assessment.factors:
            if factor.risk_score() > 0.3:
                recommendations.append(f"Address {factor.name}: {factor.mitigation}")
        
        return recommendations
    
    def get_compliance_gap_analysis(self, assessment: RiskAssessment) -> Dict[str, Any]:
        """Generate AIDA compliance gap analysis from risk assessment.
        
        Maps risk factors to AIDA requirements and identifies gaps.
        """
        aida_requirements = {
            "Data Governance": ["PII Exposure", "Data Privacy"],
            "Fairness and Bias": ["Bias and Fairness"],
            "Transparency": ["Regulatory Compliance"],
            "Performance Monitoring": ["Model Drift", "Operational Reliability"],
            "Security": ["Adversarial Input", "Toxicity Misclassification"],
        }
        
        gaps = []
        for requirement, related_factors in aida_requirements.items():
            factor_scores = [
                f for f in assessment.factors
                if f.name in related_factors
            ]
            avg_score = round(sum(f.risk_score() for f in factor_scores) / max(len(factor_scores), 1), 4)
            
            if avg_score > 0.2:
                gaps.append({
                    "requirement": requirement,
                    "risk_score": avg_score,
                    "status": "attention_needed",
                    "related_factors": [f.name for f in factor_scores],
                })
            else:
                gaps.append({
                    "requirement": requirement,
                    "risk_score": avg_score,
                    "status": "compliant",
                    "related_factors": [f.name for f in factor_scores],
                })
        
        return {
            "system_name": assessment.system_name,
            "version": assessment.version,
            "overall_risk_level": assessment.risk_level,
            "gaps": gaps,
            "recommendations": assessment.recommendations,
        }

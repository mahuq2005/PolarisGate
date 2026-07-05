"""Model Cards for AI governance transparency.
Enterprise-grade: Pydantic models for model cards with Markdown/JSON output.

Implements the Model Cards for Model Reporting framework (Mitchell et al., 2019)
for transparent AI model documentation.
"""
import logging, json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

class ModelCardMetric(BaseModel):
    """A single metric in a model card."""
    name: str
    value: float
    description: str
    threshold: Optional[float] = None
    passed: Optional[bool] = None


class ModelCardDataset(BaseModel):
    """Dataset information for a model card."""
    name: str
    description: str
    size: int
    source: str
    split: str  # "training", "validation", "test"
    date_collected: str
    preprocessing: Optional[str] = None
    label_distribution: Optional[Dict[str, float]] = None


class ModelCardEvaluation(BaseModel):
    """Evaluation results for a model card."""
    metrics: List[ModelCardMetric]
    dataset: ModelCardDataset
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluator: str


class ModelCardFairness(BaseModel):
    """Fairness assessment for a model card."""
    metric: str  # "demographic_parity", "equal_opportunity", "equalized_odds"
    score: float
    threshold: float
    passed: bool
    groups_compared: List[str]
    notes: Optional[str] = None


class ModelCardLimitation(BaseModel):
    """Known limitation of the model."""
    description: str
    severity: str  # "low", "medium", "high"
    mitigation: Optional[str] = None


class ModelCardUseCase(BaseModel):
    """Intended use case for the model."""
    primary: str
    secondary: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)


class ModelCard(BaseModel):
    """Complete model card following the Model Cards for Model Reporting framework.
    
    Fields based on Mitchell et al. (2019):
    - Model Details
    - Intended Use
    - Factors
    - Metrics
    - Evaluation Data
    - Training Data
    - Quantitative Analyses
    - Ethical Considerations
    - Caveats and Recommendations
    """
    # Model Details
    model_id: str
    model_name: str
    model_version: str
    model_type: str
    model_description: str
    model_architecture: Optional[str] = None
    model_provider: str
    model_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_version_history: List[str] = Field(default_factory=list)
    
    # Intended Use
    intended_use: ModelCardUseCase
    
    # Factors
    relevant_factors: List[str] = Field(default_factory=list)
    evaluation_factors: List[str] = Field(default_factory=list)
    
    # Metrics
    overall_metrics: List[ModelCardMetric] = Field(default_factory=list)
    
    # Evaluation Data
    evaluation_datasets: List[ModelCardDataset] = Field(default_factory=list)
    
    # Training Data
    training_dataset: Optional[ModelCardDataset] = None
    
    # Quantitative Analyses
    evaluations: List[ModelCardEvaluation] = Field(default_factory=list)
    fairness_assessments: List[ModelCardFairness] = Field(default_factory=list)
    
    # Ethical Considerations
    ethical_considerations: List[str] = Field(default_factory=list)
    
    # Caveats and Recommendations
    limitations: List[ModelCardLimitation] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authors: List[str] = Field(default_factory=list)


# ─── Model Card Generator ──────────────────────────────────────────────────

class ModelCardGenerator:
    """Generates model cards in Markdown and JSON formats.
    
    Usage:
        generator = ModelCardGenerator()
        card = ModelCard(...)
        markdown = generator.to_markdown(card)
        json_str = generator.to_json(card)
    """
    
    @staticmethod
    def to_markdown(card: ModelCard) -> str:
        """Generate a Markdown-formatted model card."""
        lines = []
        
        # Title
        lines.append(f"# Model Card: {card.model_name}")
        lines.append(f"**Version:** {card.model_version}  ")
        lines.append(f"**Date:** {card.model_date}  ")
        lines.append(f"**Provider:** {card.model_provider}  ")
        lines.append("")
        
        # Model Details
        lines.append("## Model Details")
        lines.append(f"- **Model ID:** `{card.model_id}`")
        lines.append(f"- **Type:** {card.model_type}")
        if card.model_architecture:
            lines.append(f"- **Architecture:** {card.model_architecture}")
        lines.append(f"- **Description:** {card.model_description}")
        if card.model_version_history:
            lines.append(f"- **Version History:** {', '.join(card.model_version_history)}")
        lines.append("")
        
        # Intended Use
        lines.append("## Intended Use")
        lines.append(f"**Primary:** {card.intended_use.primary}")
        if card.intended_use.secondary:
            lines.append("**Secondary Uses:**")
            for use in card.intended_use.secondary:
                lines.append(f"- {use}")
        if card.intended_use.out_of_scope:
            lines.append("**Out of Scope:**")
            for use in card.intended_use.out_of_scope:
                lines.append(f"- {use}")
        lines.append("")
        
        # Factors
        if card.relevant_factors:
            lines.append("## Factors")
            lines.append("**Relevant Factors:**")
            for factor in card.relevant_factors:
                lines.append(f"- {factor}")
            lines.append("")
        
        # Metrics
        if card.overall_metrics:
            lines.append("## Metrics")
            lines.append("| Metric | Value | Threshold | Passed | Description |")
            lines.append("|--------|-------|-----------|--------|-------------|")
            for metric in card.overall_metrics:
                threshold = f"{metric.threshold:.4f}" if metric.threshold else "N/A"
                passed = "✅" if metric.passed else "❌" if metric.passed is not None else "N/A"
                lines.append(f"| {metric.name} | {metric.value:.4f} | {threshold} | {passed} | {metric.description} |")
            lines.append("")
        
        # Evaluation Data
        if card.evaluation_datasets:
            lines.append("## Evaluation Data")
            for ds in card.evaluation_datasets:
                lines.append(f"### {ds.name}")
                lines.append(f"- **Description:** {ds.description}")
                lines.append(f"- **Size:** {ds.size:,} samples")
                lines.append(f"- **Source:** {ds.source}")
                lines.append(f"- **Split:** {ds.split}")
                lines.append(f"- **Date Collected:** {ds.date_collected}")
                if ds.preprocessing:
                    lines.append(f"- **Preprocessing:** {ds.preprocessing}")
                if ds.label_distribution:
                    lines.append("- **Label Distribution:**")
                    for label, pct in ds.label_distribution.items():
                        lines.append(f"  - {label}: {pct:.1%}")
                lines.append("")
        
        # Training Data
        if card.training_dataset:
            lines.append("## Training Data")
            ds = card.training_dataset
            lines.append(f"- **Name:** {ds.name}")
            lines.append(f"- **Description:** {ds.description}")
            lines.append(f"- **Size:** {ds.size:,} samples")
            lines.append(f"- **Source:** {ds.source}")
            lines.append(f"- **Date Collected:** {ds.date_collected}")
            if ds.preprocessing:
                lines.append(f"- **Preprocessing:** {ds.preprocessing}")
            lines.append("")
        
        # Quantitative Analyses
        if card.evaluations:
            lines.append("## Quantitative Analyses")
            for eval_item in card.evaluations:
                lines.append(f"### Evaluation: {eval_item.dataset.name}")
                lines.append(f"- **Date:** {eval_item.date}")
                lines.append(f"- **Evaluator:** {eval_item.evaluator}")
                lines.append("")
                lines.append("| Metric | Value | Threshold | Passed | Description |")
                lines.append("|--------|-------|-----------|--------|-------------|")
                for metric in eval_item.metrics:
                    threshold = f"{metric.threshold:.4f}" if metric.threshold else "N/A"
                    passed = "✅" if metric.passed else "❌" if metric.passed is not None else "N/A"
                    lines.append(f"| {metric.name} | {metric.value:.4f} | {threshold} | {passed} | {metric.description} |")
                lines.append("")
        
        # Fairness Assessments
        if card.fairness_assessments:
            lines.append("## Fairness Assessments")
            lines.append("| Metric | Score | Threshold | Passed | Groups Compared |")
            lines.append("|--------|-------|-----------|--------|-----------------|")
            for fa in card.fairness_assessments:
                passed = "✅" if fa.passed else "❌"
                groups = ", ".join(fa.groups_compared)
                lines.append(f"| {fa.metric} | {fa.score:.4f} | {fa.threshold:.4f} | {passed} | {groups} |")
                if fa.notes:
                    lines.append(f"  - *{fa.notes}*")
            lines.append("")
        
        # Ethical Considerations
        if card.ethical_considerations:
            lines.append("## Ethical Considerations")
            for i, consideration in enumerate(card.ethical_considerations, 1):
                lines.append(f"{i}. {consideration}")
            lines.append("")
        
        # Caveats and Recommendations
        if card.limitations:
            lines.append("## Limitations")
            for lim in card.limitations:
                severity_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(lim.severity, "⚪")
                lines.append(f"- {severity_icon} **[{lim.severity.upper()}]** {lim.description}")
                if lim.mitigation:
                    lines.append(f"  - *Mitigation:* {lim.mitigation}")
            lines.append("")
        
        if card.recommendations:
            lines.append("## Recommendations")
            for i, rec in enumerate(card.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Model card generated on {card.created_at}*")
        if card.authors:
            lines.append(f"*Authors: {', '.join(card.authors)}*")
        
        return "\n".join(lines)
    
    @staticmethod
    def to_json(card: ModelCard) -> str:
        """Generate a JSON-formatted model card."""
        return card.model_dump_json(indent=2)
    
    @staticmethod
    def to_dict(card: ModelCard) -> Dict[str, Any]:
        """Generate a dictionary representation of the model card."""
        return card.model_dump()
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ModelCard:
        """Create a ModelCard from a dictionary."""
        return ModelCard(**data)
    
    @staticmethod
    def from_json(json_str: str) -> ModelCard:
        """Create a ModelCard from a JSON string."""
        return ModelCard(**json.loads(json_str))

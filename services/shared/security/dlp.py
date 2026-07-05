"""Data Loss Prevention (DLP) module.
Supports SOC 2 (CC6.1, CC7.1), FedRAMP (SI-4, SC-8), HIPAA (164.312(a)(1), 164.312(c)(1)),
PCI DSS (3.4, 4.1), GDPR (Art. 32).

Features:
- Content inspection for sensitive data in transit
- Policy-based blocking/masking/alerting
- Context-aware DLP rules
- Integration with data classification
- Incident logging and reporting
"""
import re
import logging
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DLPAction(Enum):
    """Actions to take when DLP policy is violated."""
    ALLOW = "allow"
    BLOCK = "block"
    MASK = "mask"
    ALERT = "alert"
    QUARANTINE = "quarantine"


@dataclass
class DLPRule:
    """A DLP detection rule."""
    name: str
    pattern: str
    action: DLPAction
    severity: str  # "low", "medium", "high", "critical"
    description: str
    context_required: Optional[List[str]] = None  # e.g., ["source=healthcare"]
    enabled: bool = True


@dataclass
class DLPIncident:
    """A DLP policy violation incident."""
    incident_id: str
    timestamp: str
    rule_name: str
    action_taken: DLPAction
    data_classification: str
    source: str
    destination: str
    content_preview: str
    severity: str
    user: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None


# Default DLP rules aligned with compliance frameworks
DEFAULT_DLP_RULES = [
    DLPRule(
        name="PCI_Credit_Card",
        pattern=r"\b(?:\d[ -]*?){13,16}\b",
        action=DLPAction.BLOCK,
        severity="critical",
        description="Credit card number detected in transit",
    ),
    DLPRule(
        name="PHI_SSN",
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        action=DLPAction.BLOCK,
        severity="critical",
        description="Social Security Number detected",
    ),
    DLPRule(
        name="PHI_Canadian_SIN",
        pattern=r"\b\d{3}-\d{3}-\d{3}\b",
        action=DLPAction.BLOCK,
        severity="critical",
        description="Canadian SIN detected",
    ),
    DLPRule(
        name="PII_Email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        action=DLPAction.MASK,
        severity="medium",
        description="Email address detected",
    ),
    DLPRule(
        name="PII_Phone",
        pattern=r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
        action=DLPAction.MASK,
        severity="medium",
        description="Phone number detected",
    ),
    DLPRule(
        name="PII_IP_Address",
        pattern=r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        action=DLPAction.ALERT,
        severity="low",
        description="IP address detected",
    ),
    DLPRule(
        name="Credential_Leak",
        pattern=r"(?i)\b(?:password|secret|token|api[_-]?key)\s*[:=]\s*\S+",
        action=DLPAction.BLOCK,
        severity="critical",
        description="Credential leak detected",
    ),
    DLPRule(
        name="PHI_Health_Card",
        pattern=r"\b\d{4}-\d{3}-\d{3}-[A-Z]{2}\b",
        action=DLPAction.BLOCK,
        severity="critical",
        description="Health card number detected",
    ),
]


class DLPEngine:
    """DLP engine that inspects content and enforces policies."""

    def __init__(self):
        self._rules: List[DLPRule] = []
        self._incidents: List[DLPIncident] = []
        self._compiled_rules: List[tuple[re.Pattern, DLPRule]] = []
        self._init_default_rules()

    def _init_default_rules(self):
        """Initialize default DLP rules."""
        for rule in DEFAULT_DLP_RULES:
            self.add_rule(rule)

    def add_rule(self, rule: DLPRule):
        """Add a DLP rule."""
        self._rules.append(rule)
        self._compiled_rules.append((re.compile(rule.pattern), rule))
        logger.info("DLP rule added: %s (action=%s)", rule.name, rule.action.value)

    def remove_rule(self, rule_name: str):
        """Remove a DLP rule by name."""
        self._rules = [r for r in self._rules if r.name != rule_name]
        self._compiled_rules = [(p, r) for p, r in self._compiled_rules if r.name != rule_name]

    def inspect(
        self,
        content: str,
        source: str,
        destination: str,
        context: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> List[DLPIncident]:
        """Inspect content for DLP policy violations.
        
        Args:
            content: The content to inspect
            source: Source of the data (e.g., 'api', 'database', 'file_upload')
            destination: Destination of the data (e.g., 'external_api', 'user_download')
            context: Additional context for rule matching
            user: User who initiated the data transfer
        
        Returns:
            List of DLP incidents (empty if no violations)
        """
        incidents = []
        context = context or {}

        for compiled_pattern, rule in self._compiled_rules:
            if not rule.enabled:
                continue

            # Check context requirements
            if rule.context_required:
                context_match = all(
                    ctx.split("=")[1] in str(context.get(ctx.split("=")[0], ""))
                    for ctx in rule.context_required
                )
                if not context_match:
                    continue

            # Check for matches
            matches = compiled_pattern.findall(content)
            if matches:
                import uuid
                incident = DLPIncident(
                    incident_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    rule_name=rule.name,
                    action_taken=rule.action,
                    data_classification=self._get_classification(rule),
                    source=source,
                    destination=destination,
                    content_preview=matches[0][:50] if isinstance(matches[0], str) else str(matches[0])[:50],
                    severity=rule.severity,
                    user=user,
                )
                incidents.append(incident)
                self._incidents.append(incident)

                logger.warning(
                    "DLP incident: %s matched rule '%s' (action=%s, severity=%s)",
                    incident.incident_id[:8], rule.name, rule.action.value, rule.severity,
                )

        return incidents

    def get_action_for_content(self, content: str, context: Optional[Dict[str, Any]] = None) -> DLPAction:
        """Determine the appropriate action for content.
        
        Returns the most restrictive action from all matching rules.
        """
        action_order = {
            DLPAction.ALLOW: 0,
            DLPAction.ALERT: 1,
            DLPAction.MASK: 2,
            DLPAction.QUARANTINE: 3,
            DLPAction.BLOCK: 4,
        }
        highest_action = DLPAction.ALLOW

        for compiled_pattern, rule in self._compiled_rules:
            if not rule.enabled:
                continue
            if compiled_pattern.search(content):
                if action_order.get(rule.action, 0) > action_order.get(highest_action, 0):
                    highest_action = rule.action

        return highest_action

    def mask_content(self, content: str) -> str:
        """Mask sensitive content based on DLP rules."""
        masked = content
        for compiled_pattern, rule in self._compiled_rules:
            if rule.action in (DLPAction.MASK, DLPAction.BLOCK):
                masked = compiled_pattern.sub("[REDACTED]", masked)
        return masked

    def get_incidents(
        self,
        severity: Optional[str] = None,
        unresolved_only: bool = False,
        limit: int = 100,
    ) -> List[DLPIncident]:
        """Get DLP incidents with optional filtering."""
        results = self._incidents
        if severity:
            results = [i for i in results if i.severity == severity]
        if unresolved_only:
            results = [i for i in results if not i.resolved]
        return results[:limit]

    def resolve_incident(self, incident_id: str, notes: str) -> bool:
        """Mark a DLP incident as resolved."""
        for incident in self._incidents:
            if incident.incident_id == incident_id:
                incident.resolved = True
                incident.resolution_notes = notes
                logger.info("DLP incident %s resolved: %s", incident_id[:8], notes)
                return True
        return False

    def get_stats(self) -> dict:
        """Get DLP engine statistics."""
        total = len(self._incidents)
        by_severity = {}
        by_action = {}
        for inc in self._incidents:
            by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1
            by_action[inc.action_taken.value] = by_action.get(inc.action_taken.value, 0) + 1
        return {
            "total_incidents": total,
            "unresolved": sum(1 for i in self._incidents if not i.resolved),
            "active_rules": len(self._rules),
            "by_severity": by_severity,
            "by_action": by_action,
        }

    def _get_classification(self, rule: DLPRule) -> str:
        """Map DLP rule to data classification."""
        if "PHI" in rule.name:
            return "phi"
        if "PCI" in rule.name:
            return "pci"
        if "PII" in rule.name:
            return "pii"
        if "Credential" in rule.name:
            return "restricted"
        return "internal"


# Singleton instance
_dlp_engine: Optional[DLPEngine] = None


def get_dlp_engine() -> DLPEngine:
    """Get or create the singleton DLP engine."""
    global _dlp_engine
    if _dlp_engine is None:
        _dlp_engine = DLPEngine()
    return _dlp_engine


def inspect_content(
    content: str,
    source: str,
    destination: str,
    context: Optional[Dict[str, Any]] = None,
    user: Optional[str] = None,
) -> List[DLPIncident]:
    """Inspect content for DLP violations."""
    return get_dlp_engine().inspect(content, source, destination, context, user)


def mask_sensitive(content: str) -> str:
    """Mask sensitive content."""
    return get_dlp_engine().mask_content(content)

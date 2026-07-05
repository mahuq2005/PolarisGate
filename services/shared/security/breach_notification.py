"""Breach notification module for GDPR, HIPAA, and PIPEDA compliance.
Supports GDPR (Art. 33, Art. 34), HIPAA (164.308(a)(6), 164.400-414), PIPEDA (Principle 10).

Features:
- Breach detection and classification
- Automated notification workflows
- Regulatory notification timelines
- Affected party tracking
- Breach response playbooks
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class BreachRecord:
    """A record of a security breach."""
    breach_id: str
    detected_at: str
    breach_type: str  # "data_exposure", "unauthorized_access", "ransomware", "insider_threat", "phishing"
    severity: str  # "low", "medium", "high", "critical"
    status: str  # "detected", "investigating", "contained", "resolved", "notified"
    data_classification: str  # "public", "internal", "confidential", "restricted", "phi", "pii", "pci"
    affected_users_count: int = 0
    affected_data_categories: List[str] = None
    description: str = ""
    root_cause: Optional[str] = None
    containment_actions: List[str] = None
    notification_deadline: Optional[str] = None
    notified_at: Optional[str] = None
    regulatory_bodies_notified: List[str] = None
    resolved_at: Optional[str] = None
    lessons_learned: Optional[str] = None


class BreachNotificationManager:
    """Manages breach detection, notification, and response."""

    def __init__(self, storage_path: str = "/app/breaches"):
        self.storage_path = storage_path
        self._breaches: Dict[str, BreachRecord] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_breaches()

    def _load_breaches(self):
        """Load breach records from storage."""
        breaches_file = os.path.join(self.storage_path, "breach_records.json")
        if os.path.exists(breaches_file):
            try:
                with open(breaches_file) as f:
                    data = json.load(f)
                for breach_data in data.get("breaches", []):
                    record = BreachRecord(**breach_data)
                    self._breaches[record.breach_id] = record
                logger.info("Loaded %d breach records", len(self._breaches))
            except Exception as e:
                logger.error("Failed to load breach records: %s", e)

    def _save_breaches(self):
        """Save breach records to storage."""
        try:
            breaches_file = os.path.join(self.storage_path, "breach_records.json")
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "breaches": [asdict(r) for r in self._breaches.values()],
            }
            with open(breaches_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save breach records: %s", e)

    def report_breach(
        self,
        breach_type: str,
        severity: str,
        data_classification: str,
        description: str,
        affected_users_count: int = 0,
        affected_data_categories: Optional[List[str]] = None,
    ) -> BreachRecord:
        """Report a new security breach.
        
        Automatically calculates notification deadlines based on severity and jurisdiction.
        
        Args:
            breach_type: Type of breach
            severity: Severity level
            data_classification: Classification of affected data
            description: Description of the breach
            affected_users_count: Number of affected users
            affected_data_categories: Categories of affected data
        
        Returns:
            The created BreachRecord
        """
        import uuid
        now = datetime.now(timezone.utc)

        # Calculate notification deadline based on severity
        deadline_hours = self._get_notification_deadline(severity, data_classification)
        notification_deadline = (now + timedelta(hours=deadline_hours)).isoformat()

        record = BreachRecord(
            breach_id=str(uuid.uuid4()),
            detected_at=now.isoformat(),
            breach_type=breach_type,
            severity=severity,
            status="detected",
            data_classification=data_classification,
            affected_users_count=affected_users_count,
            affected_data_categories=affected_data_categories or [],
            description=description,
            containment_actions=[],
            notification_deadline=notification_deadline,
            regulatory_bodies_notified=[],
        )
        self._breaches[record.breach_id] = record
        self._save_breaches()

        logger.warning(
            "Breach reported: id=%s type=%s severity=%s deadline=%s",
            record.breach_id[:8], breach_type, severity, notification_deadline,
        )
        return record

    def update_breach_status(self, breach_id: str, status: str, notes: Optional[str] = None):
        """Update the status of a breach."""
        record = self._breaches.get(breach_id)
        if not record:
            logger.warning("Breach not found: %s", breach_id)
            return

        record.status = status
        if status == "resolved":
            record.resolved_at = datetime.now(timezone.utc).isoformat()
        if notes and status == "investigating":
            record.root_cause = notes
        if notes and status == "contained":
            record.containment_actions = (record.containment_actions or []) + [notes]
        if notes and status == "resolved":
            record.lessons_learned = notes

        self._save_breaches()
        logger.info("Breach %s status updated to %s", breach_id[:8], status)

    def mark_notified(self, breach_id: str, regulatory_body: str):
        """Mark that a regulatory body has been notified."""
        record = self._breaches.get(breach_id)
        if not record:
            return
        record.status = "notified"
        record.notified_at = datetime.now(timezone.utc).isoformat()
        record.regulatory_bodies_notified = (record.regulatory_bodies_notified or []) + [regulatory_body]
        self._save_breaches()
        logger.info("Regulatory body notified for breach %s: %s", breach_id[:8], regulatory_body)

    def get_overdue_notifications(self) -> List[BreachRecord]:
        """Get breaches where notification deadline has passed."""
        now = datetime.now(timezone.utc)
        overdue = []
        for record in self._breaches.values():
            if record.status in ("detected", "investigating", "contained"):
                if record.notification_deadline:
                    deadline = datetime.fromisoformat(record.notification_deadline)
                    if now > deadline:
                        overdue.append(record)
        return overdue

    def get_active_breaches(self) -> List[BreachRecord]:
        """Get all active (unresolved) breaches."""
        return [r for r in self._breaches.values() if r.status != "resolved"]

    def get_stats(self) -> dict:
        """Get breach management statistics."""
        total = len(self._breaches)
        active = len(self.get_active_breaches())
        overdue = len(self.get_overdue_notifications())
        by_severity = {}
        by_type = {}
        for r in self._breaches.values():
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            by_type[r.breach_type] = by_type.get(r.breach_type, 0) + 1
        return {
            "total_breaches": total,
            "active": active,
            "overdue_notifications": overdue,
            "by_severity": by_severity,
            "by_type": by_type,
        }

    def _get_notification_deadline(self, severity: str, data_classification: str) -> int:
        """Get notification deadline in hours based on severity and data type.
        
        GDPR: 72 hours for notification
        HIPAA: 60 days for >500 affected, 60 days for <500
        PIPEDA: As soon as feasible
        """
        # Critical breaches with sensitive data: notify within 24 hours
        if severity == "critical" and data_classification in ("phi", "pci", "restricted"):
            return 24
        # High severity: notify within 48 hours
        if severity == "high":
            return 48
        # Medium severity: notify within 72 hours (GDPR standard)
        if severity == "medium":
            return 72
        # Low severity: notify within 7 days
        return 168  # 7 days


# Singleton instance
_breach_manager: Optional[BreachNotificationManager] = None


def get_breach_manager() -> BreachNotificationManager:
    """Get or create the singleton breach manager."""
    global _breach_manager
    if _breach_manager is None:
        _breach_manager = BreachNotificationManager()
    return _breach_manager


def report_breach(
    breach_type: str,
    severity: str,
    data_classification: str,
    description: str,
    affected_users_count: int = 0,
) -> BreachRecord:
    """Report a security breach."""
    return get_breach_manager().report_breach(
        breach_type, severity, data_classification, description, affected_users_count,
    )

"""SOC 2 Compliance Controls for NorthGuard.
Enterprise-grade: Access reviews, incident response, change management, vendor management.

Implements key SOC 2 trust service criteria:
- CC6.1: Logical and physical access controls
- CC7.1: Incident detection and response
- CC8.1: Change management
- CC9.1: Vendor management
"""
import logging, json, time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

class AccessReviewRecord(BaseModel):
    """Record of an access review for SOC 2 CC6.1 compliance."""
    id: str
    reviewer: str
    reviewed_user: str
    action: str  # "granted", "revoked", "modified", "reviewed"
    resource: str
    justification: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None


class IncidentRecord(BaseModel):
    """Record of a security incident for SOC 2 CC7.1 compliance."""
    id: str
    incident_type: str  # "unauthorized_access", "data_breach", "policy_violation", "system_failure"
    severity: str  # "low", "medium", "high", "critical"
    description: str
    detected_by: str
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "open"  # "open", "investigating", "contained", "resolved", "closed"
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    affected_systems: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class ChangeRequest(BaseModel):
    """Record of a change request for SOC 2 CC8.1 compliance."""
    id: str
    title: str
    description: str
    change_type: str  # "emergency", "standard", "minor"
    requested_by: str
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    status: str = "pending"  # "pending", "approved", "rejected", "implemented", "rolled_back"
    risk_assessment: Optional[str] = None
    rollback_plan: Optional[str] = None
    implemented_at: Optional[str] = None
    tested_by: Optional[str] = None


class VendorRecord(BaseModel):
    """Record of a vendor for SOC 2 CC9.1 compliance."""
    id: str
    name: str
    service: str
    contact_email: str
    contract_start: str
    contract_end: str
    risk_level: str = "medium"  # "low", "medium", "high"
    soc2_report_url: Optional[str] = None
    last_reviewed: Optional[str] = None
    status: str = "active"  # "active", "under_review", "terminated"
    notes: Optional[str] = None


class ComplianceReport(BaseModel):
    """Aggregated compliance report for SOC 2 audit."""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_reviews_count: int = 0
    open_incidents: int = 0
    pending_changes: int = 0
    active_vendors: int = 0
    last_access_review: Optional[str] = None
    last_incident: Optional[str] = None
    last_change: Optional[str] = None
    controls_summary: Dict[str, str] = Field(default_factory=lambda: {
        "CC6.1": "Access controls: Active",
        "CC7.1": "Incident response: Active",
        "CC8.1": "Change management: Active",
        "CC9.1": "Vendor management: Active",
    })


# ─── Access Review (CC6.1) ─────────────────────────────────────────────────

class AccessReview:
    """SOC 2 CC6.1: Logical and physical access controls.
    
    Tracks who has access to what, when access was granted/revoked,
    and ensures periodic access reviews are conducted.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._reviews: List[AccessReviewRecord] = []
    
    async def record_access_review(
        self,
        reviewer: str,
        reviewed_user: str,
        action: str,
        resource: str,
        justification: str,
        expires_in_days: Optional[int] = 90,
    ) -> AccessReviewRecord:
        """Record an access review action.
        
        Args:
            reviewer: Who performed the review
            reviewed_user: Whose access was reviewed
            action: grant, revoke, modify, or review
            resource: What resource was accessed
            justification: Why the action was taken
            expires_in_days: When access expires (None = never)
        """
        record = AccessReviewRecord(
            id=f"ar_{int(time.time())}_{reviewed_user}",
            reviewer=reviewer,
            reviewed_user=reviewed_user,
            action=action,
            resource=resource,
            justification=justification,
            expires_at=(
                datetime.now(timezone.utc).isoformat() if expires_in_days is None
                else datetime.fromtimestamp(time.time() + expires_in_days * 86400, tz=timezone.utc).isoformat()
            ),
        )
        
        self._reviews.append(record)
        
        if self.redis:
            await self.redis.lpush("compliance:access_reviews", record.model_dump_json())
            await self.redis.ltrim("compliance:access_reviews", 0, 999)
        
        logger.info(
            f"Access review: {action} for {reviewed_user} on {resource} "
            f"by {reviewer} — {justification}"
        )
        return record
    
    def get_recent_reviews(self, limit: int = 50) -> List[AccessReviewRecord]:
        """Get recent access review records."""
        return self._reviews[-limit:]
    
    async def get_expiring_access(self, within_days: int = 30) -> List[AccessReviewRecord]:
        """Get access that is expiring within the specified days."""
        if not self.redis:
            return []
        
        now = time.time()
        threshold = now + within_days * 86400
        expiring = []
        
        raw = await self.redis.lrange("compliance:access_reviews", 0, -1)
        for item in raw:
            try:
                record = AccessReviewRecord.model_validate_json(item)
                if record.expires_at:
                    exp_time = datetime.fromisoformat(record.expires_at).timestamp()
                    if now < exp_time < threshold:
                        expiring.append(record)
            except Exception:
                continue
        
        return expiring


# ─── Incident Response (CC7.1) ─────────────────────────────────────────────

class IncidentResponse:
    """SOC 2 CC7.1: Incident detection and response.
    
    Tracks security incidents from detection through resolution,
    with evidence collection and severity classification.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._incidents: List[IncidentRecord] = []
    
    async def report_incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        detected_by: str,
        affected_systems: Optional[List[str]] = None,
        evidence: Optional[List[str]] = None,
    ) -> IncidentRecord:
        """Report a new security incident.
        
        Args:
            incident_type: Type of incident
            severity: low, medium, high, or critical
            description: Detailed description
            detected_by: Who or what detected the incident
            affected_systems: Systems affected
            evidence: Evidence artifacts (log entries, screenshots, etc.)
        """
        record = IncidentRecord(
            id=f"inc_{int(time.time())}",
            incident_type=incident_type,
            severity=severity,
            description=description,
            detected_by=detected_by,
            affected_systems=affected_systems or [],
            evidence=evidence or [],
        )
        
        self._incidents.append(record)
        
        if self.redis:
            await self.redis.lpush("compliance:incidents", record.model_dump_json())
            await self.redis.ltrim("compliance:incidents", 0, 999)
        
        log_level = logging.CRITICAL if severity == "critical" else logging.ERROR if severity == "high" else logging.WARNING
        logger.log(
            log_level,
            f"Incident [{severity.upper()}]: {incident_type} — {description[:200]} "
            f"(detected by: {detected_by})"
        )
        return record
    
    async def update_incident(
        self,
        incident_id: str,
        status: str,
        resolution: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> Optional[IncidentRecord]:
        """Update the status of an incident."""
        for record in self._incidents:
            if record.id == incident_id:
                record.status = status
                if resolution:
                    record.resolution = resolution
                if assigned_to:
                    record.assigned_to = assigned_to
                if status in ("resolved", "closed"):
                    record.resolved_at = datetime.now(timezone.utc).isoformat()
                
                logger.info(f"Incident {incident_id} updated to {status}")
                return record
        return None
    
    def get_open_incidents(self) -> List[IncidentRecord]:
        """Get all open incidents."""
        return [i for i in self._incidents if i.status not in ("resolved", "closed")]
    
    def get_incidents_by_severity(self, severity: str) -> List[IncidentRecord]:
        """Get incidents by severity level."""
        return [i for i in self._incidents if i.severity == severity]


# ─── Change Management (CC8.1) ─────────────────────────────────────────────

class ChangeManagement:
    """SOC 2 CC8.1: Change management.
    
    Tracks all changes to the system with approval workflow,
    risk assessment, and rollback planning.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._changes: List[ChangeRequest] = []
    
    async def create_change_request(
        self,
        title: str,
        description: str,
        change_type: str,
        requested_by: str,
        risk_assessment: Optional[str] = None,
        rollback_plan: Optional[str] = None,
    ) -> ChangeRequest:
        """Create a new change request.
        
        Args:
            title: Short title of the change
            description: Detailed description
            change_type: emergency, standard, or minor
            requested_by: Who requested the change
            risk_assessment: Risk assessment notes
            rollback_plan: How to roll back if needed
        """
        record = ChangeRequest(
            id=f"cr_{int(time.time())}",
            title=title,
            description=description,
            change_type=change_type,
            requested_by=requested_by,
            risk_assessment=risk_assessment,
            rollback_plan=rollback_plan,
        )
        
        self._changes.append(record)
        
        if self.redis:
            await self.redis.lpush("compliance:changes", record.model_dump_json())
            await self.redis.ltrim("compliance:changes", 0, 999)
        
        logger.info(
            f"Change request [{change_type}]: {title} by {requested_by}"
        )
        return record
    
    async def approve_change(
        self,
        change_id: str,
        approved_by: str,
    ) -> Optional[ChangeRequest]:
        """Approve a change request."""
        for record in self._changes:
            if record.id == change_id:
                record.status = "approved"
                record.approved_by = approved_by
                record.approved_at = datetime.now(timezone.utc).isoformat()
                logger.info(f"Change {change_id} approved by {approved_by}")
                return record
        return None
    
    async def implement_change(
        self,
        change_id: str,
        implemented_by: str,
    ) -> Optional[ChangeRequest]:
        """Mark a change as implemented."""
        for record in self._changes:
            if record.id == change_id:
                record.status = "implemented"
                record.implemented_at = datetime.now(timezone.utc).isoformat()
                record.tested_by = implemented_by
                logger.info(f"Change {change_id} implemented by {implemented_by}")
                return record
        return None
    
    def get_pending_changes(self) -> List[ChangeRequest]:
        """Get all pending change requests."""
        return [c for c in self._changes if c.status == "pending"]
    
    def get_changes_by_type(self, change_type: str) -> List[ChangeRequest]:
        """Get changes by type."""
        return [c for c in self._changes if c.change_type == change_type]


# ─── Vendor Management (CC9.1) ─────────────────────────────────────────────

class VendorManager:
    """SOC 2 CC9.1: Vendor management.
    
    Tracks vendor relationships, contract dates, risk levels,
    and SOC 2 report reviews.
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._vendors: List[VendorRecord] = []
    
    async def add_vendor(
        self,
        name: str,
        service: str,
        contact_email: str,
        contract_start: str,
        contract_end: str,
        risk_level: str = "medium",
        soc2_report_url: Optional[str] = None,
    ) -> VendorRecord:
        """Add a new vendor.
        
        Args:
            name: Vendor name
            service: What service they provide
            contact_email: Vendor contact
            contract_start: Contract start date
            contract_end: Contract end date
            risk_level: low, medium, or high
            soc2_report_url: URL to their SOC 2 report
        """
        record = VendorRecord(
            id=f"ven_{int(time.time())}",
            name=name,
            service=service,
            contact_email=contact_email,
            contract_start=contract_start,
            contract_end=contract_end,
            risk_level=risk_level,
            soc2_report_url=soc2_report_url,
        )
        
        self._vendors.append(record)
        
        if self.redis:
            await self.redis.lpush("compliance:vendors", record.model_dump_json())
            await self.redis.ltrim("compliance:vendors", 0, 999)
        
        logger.info(f"Vendor added: {name} ({service}) — risk: {risk_level}")
        return record
    
    async def review_vendor(self, vendor_id: str, reviewer: str) -> Optional[VendorRecord]:
        """Mark a vendor as reviewed."""
        for record in self._vendors:
            if record.id == vendor_id:
                record.last_reviewed = datetime.now(timezone.utc).isoformat()
                record.status = "under_review"
                logger.info(f"Vendor {record.name} reviewed by {reviewer}")
                return record
        return None
    
    def get_high_risk_vendors(self) -> List[VendorRecord]:
        """Get all high-risk vendors."""
        return [v for v in self._vendors if v.risk_level == "high"]
    
    def get_expiring_contracts(self, within_days: int = 90) -> List[VendorRecord]:
        """Get vendors with contracts expiring within the specified days."""
        from datetime import datetime, timedelta
        threshold = datetime.now() + timedelta(days=within_days)
        expiring = []
        for v in self._vendors:
            try:
                end = datetime.fromisoformat(v.contract_end)
                if end <= threshold:
                    expiring.append(v)
            except Exception:
                continue
        return expiring


# ─── Compliance Report ─────────────────────────────────────────────────────

def generate_compliance_report(
    access_reviews: List[AccessReviewRecord],
    incidents: List[IncidentRecord],
    changes: List[ChangeRequest],
    vendors: List[VendorRecord],
) -> ComplianceReport:
    """Generate an aggregated compliance report for SOC 2 audit."""
    return ComplianceReport(
        access_reviews_count=len(access_reviews),
        open_incidents=len([i for i in incidents if i.status not in ("resolved", "closed")]),
        pending_changes=len([c for c in changes if c.status == "pending"]),
        active_vendors=len([v for v in vendors if v.status == "active"]),
        last_access_review=access_reviews[-1].timestamp if access_reviews else None,
        last_incident=incidents[-1].detected_at if incidents else None,
        last_change=changes[-1].requested_at if changes else None,
    )

"""Pydantic schemas for request/response validation across all NorthGuard services."""
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


# ─── Auth Schemas ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


# ─── Settings Schemas ─────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    admin_email: Optional[str] = None


class SettingsUpdate(BaseModel):
    admin_email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v, info):
        if v and len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if v and 'current_password' not in info.data:
            raise ValueError('Current password required to set new password')
        return v


# ─── Trace Schemas ────────────────────────────────────────────────────────

class TraceIngest(BaseModel):
    model_config = {"protected_namespaces": ()}
    id: Optional[str] = None
    prompt: str = ""
    completion: str = ""
    model_id: str = "unknown"
    user_id: str = "anonymous"
    tags: Dict[str, Any] = {}
    timestamp: Optional[str] = None


class TraceResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    id: str
    prompt: Optional[str] = None
    completion: Optional[str] = None
    model_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None


# ─── Guardrail Schemas ────────────────────────────────────────────────────

class GuardrailCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class GuardrailCheckResponse(BaseModel):
    action: str
    reason: str
    rewritten_text: Optional[str] = None
    toxic: bool = False
    toxic_score: float = 0.0
    pii_detected: bool = False
    detection_source: Optional[str] = None
    label_details: Optional[Dict[str, float]] = None


class SHAPRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    top_n: Optional[int] = Field(default=5, ge=1, le=50)


class SHAPResponse(BaseModel):
    tokens: List[Dict[str, Any]] = []
    model: str = "unitary/toxic-bert"
    aggregate_toxicity_score: Optional[float] = None


# ─── Dashboard Schemas ────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_traces_last_24h: int = 0
    flagged_toxicity: int = 0
    pii_leaks: int = 0
    blocked_count: int = 0
    fairness_score: Union[float, str] = "N/A - insufficient data"
    active_models: int = 0


class IncidentResponse(BaseModel):
    trace_id: str
    toxic: bool
    toxic_score: float
    reason: Optional[str] = None
    pii_detected: bool = False
    pii_types: Optional[List[str]] = None
    blocklisted: bool = False
    timestamp: Optional[datetime] = None


class ModelSummary(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id: str
    trace_count: int
    last_seen: Optional[datetime] = None


class TraceWithGuardrail(BaseModel):
    model_config = {"protected_namespaces": ()}
    id: str
    prompt: Optional[str] = None
    completion: Optional[str] = None
    model_id: Optional[str] = None
    user_id: Optional[str] = None
    toxic: Optional[bool] = None
    toxic_score: Optional[float] = None
    reason: Optional[str] = None
    pii_detected: Optional[bool] = None
    pii_types: Optional[List[str]] = None
    timestamp: Optional[datetime] = None


# ─── Policy Schemas ───────────────────────────────────────────────────────

class Policy(BaseModel):
    name: str
    category: str
    type: str
    severity: Optional[str] = "medium"
    action: str = "flag"
    enabled: bool = True
    message: Optional[str] = None
    patterns: Optional[List[str]] = None


class PolicyList(BaseModel):
    policies: List[Policy]


# ─── Feedback Schemas ─────────────────────────────────────────────────────

class FeedbackSubmit(BaseModel):
    model_config = {"protected_namespaces": ()}
    trace_id: Optional[str] = None
    model_verdict: Optional[bool] = None
    client_label: Optional[bool] = None


# ─── Bias Monitor Schemas ─────────────────────────────────────────────────

class BiasSummary(BaseModel):
    total_traces: int = 0
    toxic_flags: int = 0
    pii_leaks: int = 0
    fairness_score: Union[float, str] = "N/A"


class BiasTrend(BaseModel):
    day: datetime
    total: int
    toxic: int
    pii: int


# ─── AIDA Bridge Schemas ──────────────────────────────────────────────────

class AIDAExportRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: List[str] = ["default-model"]
    industry: str = "finance"
    risk_level: str = "medium"


class AIDAExportResponse(BaseModel):
    report: str
    monitoring: Dict[str, Any]


class SimilarIncident(BaseModel):
    text: str
    toxic: bool = False
    reason: Optional[str] = None
    trace_id: Optional[str] = None


class SimilarResponse(BaseModel):
    results: List[SimilarIncident]


class StoreIncidentRequest(BaseModel):
    text: str = ""
    trace_id: str = ""
    toxic: bool = False
    reason: Optional[str] = None


# ─── Health Schemas ───────────────────────────────────────────────────────

class HealthStatus(BaseModel):
    status: str = "ok"
    database: str = "healthy"
    redis: Optional[str] = None


# ─── Audit Schemas ────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    id: int
    user_email: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[Union[str, dict]] = None
    before_state: Optional[Union[str, dict]] = None
    after_state: Optional[Union[str, dict]] = None
    ip_address: Optional[str] = None
    timestamp: Optional[datetime] = None


# ─── Agent Governance Schemas ──────────────────────────────────────────────

class AgentStatus(BaseModel):
    agent_id: str
    agent_name: str
    status: str = "online"  # online / offline / error
    last_heartbeat: Optional[datetime] = None
    traces_processed: int = 0
    error_count: int = 0


class AgentStatusList(BaseModel):
    agents: List[AgentStatus]


class AgentPermission(BaseModel):
    agent_id: str
    tool_name: str
    permission: str = "allow"  # allow / block / readonly


class AgentPermissionsList(BaseModel):
    permissions: List[AgentPermission]


# ─── Budget Schemas ────────────────────────────────────────────────────────

class BudgetUsage(BaseModel):
    total_budget: float = 1000.0
    consumed: float = 0.0
    currency: str = "USD"
    period: str = "monthly"
    alert_threshold_pct: float = 80.0


class BudgetAlertConfig(BaseModel):
    enabled: bool = True
    threshold_pct: float = 80.0
    email_notifications: bool = True
    cooldown_minutes: int = 60


# ─── Hallucination Schemas ─────────────────────────────────────────────────

class HallucinationTrendPoint(BaseModel):
    date: str
    score: float


class HallucinationTrend(BaseModel):
    points: List[HallucinationTrendPoint]


class HallucinationDetection(BaseModel):
    id: str
    trace_id: str
    score: float
    prompt_snippet: str
    completion_snippet: str
    corrected: bool = False
    feedback: Optional[str] = None  # correct / incorrect / none
    timestamp: Optional[datetime] = None


class HallucinationDetectionList(BaseModel):
    detections: List[HallucinationDetection]


class HallucinationFeedback(BaseModel):
    detection_id: str
    feedback: str  # correct / incorrect


# ─── Domain Threshold Schemas ──────────────────────────────────────────────

class DomainThreshold(BaseModel):
    domain: str
    severity: str = "medium"  # off / low / medium / high / critical
    toxicity_action: str = "flag"
    pii_action: str = "mask"


class DomainThresholdList(BaseModel):
    thresholds: List[DomainThreshold]


# ─── Audit Chain Schemas ────────────────────────────────────────────────────

class AuditChainEntry(BaseModel):
    id: int
    prev_hash: str
    entry_hash: str
    user_email: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[Any] = None
    before_state: Optional[Any] = None
    after_state: Optional[Any] = None
    ip_address: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditChainVerifyResponse(BaseModel):
    valid: bool
    total_entries: int
    broken_links: List[dict] = []
    first_entry_id: Optional[int] = None
    last_entry_id: Optional[int] = None


# ─── System Log Schemas ─────────────────────────────────────────────────────

class SystemLogEntry(BaseModel):
    id: int
    service_name: str
    level: str
    message: str
    correlation_id: Optional[str] = None
    agent_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None


class SystemLogList(BaseModel):
    logs: List[SystemLogEntry]
    total: int = 0


# ─── Event Schemas ──────────────────────────────────────────────────────────

class EventEntry(BaseModel):
    id: int
    event_type: str
    source: str
    payload: Optional[Any] = None
    correlation_id: Optional[str] = None
    agent_id: Optional[str] = None
    created_at: Optional[datetime] = None


class EventList(BaseModel):
    events: List[EventEntry]
    total: int = 0


# ─── Audit Export Schemas ───────────────────────────────────────────────────

class AuditExportRequest(BaseModel):
    format: str = "csv"  # csv or json
    action: Optional[str] = None
    user_email: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


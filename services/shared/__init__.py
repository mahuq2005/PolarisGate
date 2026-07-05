"""NorthGuard shared utilities.
Enterprise-grade: Centralized exports for cleaner imports across all services.
"""
from shared.config import settings
from shared.logging import setup_logging, JSONFormatter, LoggerAdapter
from shared.audit import log_audit
from shared.schemas import (
    # Auth
    LoginRequest, TokenResponse, RefreshTokenRequest,
    # Settings
    SettingsResponse, SettingsUpdate,
    # Traces
    TraceIngest, TraceResponse,
    # Guardrails
    GuardrailCheckRequest, GuardrailCheckResponse, SHAPRequest, SHAPResponse,
    # Dashboard
    DashboardSummary, IncidentResponse, ModelSummary, TraceWithGuardrail,
    # Policies
    Policy, PolicyList,
    # Feedback
    FeedbackSubmit,
    # Bias Monitor
    BiasSummary, BiasTrend,
    # AIDA Bridge
    AIDAExportRequest, AIDAExportResponse, SimilarIncident, SimilarResponse, StoreIncidentRequest,
    # Health
    HealthStatus,
    # Audit
    AuditLogEntry,
)

# AI/ML MLOps modules
from shared.fairness import (
    calculate_fairness_score, get_fairness_note,
    demographic_parity_ratio, equal_opportunity_difference,
    chi_squared_fairness_test, assess_demographic_parity,
    FairnessMetrics,
)
from shared.data_validator import TraceValidator, DataQualityReport, SchemaDriftDetector
from shared.mlflow_client import MLflowTracker, get_mlflow_tracker, log_model_training
from shared.model_evaluator import (
    compute_metrics, evaluate_classifier, cross_validate,
    benchmark_classifiers, ClassificationMetrics,
)
from shared.cost_tracker import CostTracker, get_cost_tracker, estimate_tokens
from shared.drift_detector import DriftDetector, get_drift_detector, compute_psi, compute_kl_divergence

# Lazy imports for heavy dependencies (asyncpg, redis, opentelemetry)
# These are imported on-demand by the services that need them.
# Use shared.db, shared.redis_client, shared.telemetry directly instead.
def get_pool():
    from shared.db import get_pool as _get_pool
    return _get_pool()

def close_pool():
    from shared.db import close_pool as _close_pool
    return _close_pool()

def db_health():
    from shared.db import health_check as _db_health
    return _db_health()

def get_redis():
    from shared.redis_client import get_redis as _get_redis
    return _get_redis()

def close_redis():
    from shared.redis_client import close_redis as _close_redis
    return _close_redis()

def redis_health():
    from shared.redis_client import health_check as _redis_health
    return _redis_health()

def setup_otel(*args, **kwargs):
    from shared.telemetry import setup_otel as _setup_otel
    return _setup_otel(*args, **kwargs)

__all__ = [
    "settings",
    "get_pool", "close_pool", "db_health",
    "get_redis", "close_redis", "redis_health",
    "setup_otel",
    "setup_logging", "JSONFormatter", "LoggerAdapter",
    "log_audit",
    # Schemas
    "LoginRequest", "TokenResponse", "RefreshTokenRequest",
    "SettingsResponse", "SettingsUpdate",
    "TraceIngest", "TraceResponse",
    "GuardrailCheckRequest", "GuardrailCheckResponse", "SHAPRequest", "SHAPResponse",
    "DashboardSummary", "IncidentResponse", "ModelSummary", "TraceWithGuardrail",
    "Policy", "PolicyList",
    "FeedbackSubmit",
    "BiasSummary", "BiasTrend",
    "AIDAExportRequest", "AIDAExportResponse", "SimilarIncident", "SimilarResponse", "StoreIncidentRequest",
    "HealthStatus",
    "AuditLogEntry",
    # AI/ML MLOps
    "calculate_fairness_score", "get_fairness_note",
    "demographic_parity_ratio", "equal_opportunity_difference",
    "chi_squared_fairness_test", "assess_demographic_parity",
    "FairnessMetrics",
    "TraceValidator", "DataQualityReport", "SchemaDriftDetector",
    "MLflowTracker", "get_mlflow_tracker", "log_model_training",
    "compute_metrics", "evaluate_classifier", "cross_validate",
    "benchmark_classifiers", "ClassificationMetrics",
    "CostTracker", "get_cost_tracker", "estimate_tokens",
    "DriftDetector", "get_drift_detector", "compute_psi", "compute_kl_divergence",
]

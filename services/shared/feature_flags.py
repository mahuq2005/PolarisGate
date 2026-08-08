"""Feature Flags — config-driven feature toggles for gradual rollout."""
from __future__ import annotations
import os
from enum import Enum
from typing import Dict


class FeatureFlag(str, Enum):
    COST_TRACKING = "cost_tracking"
    BUDGET_ENFORCEMENT = "budget_enforcement"
    COST_DASHBOARDS = "cost_dashboards"
    ANOMALY_DETECTION = "anomaly_detection"
    AGENT_HOSTING = "agent_hosting"
    MCP_SERVERS = "mcp_servers"
    RAG_PIPELINE = "rag_pipeline"
    GRAPH_RAG = "graph_rag"
    ACCURACY_MONITORING = "accuracy_monitoring"
    RESPONSIBLE_AI = "responsible_ai"
    MULTI_TENANT = "multi_tenant"
    SSO_OKTA = "sso_okta"
    SSO_AZURE_AD = "sso_azure_ad"
    SSO_LDAP = "sso_ldap"
    DATA_CLASSIFICATION = "data_classification"
    GDPR_ERASURE = "gdpr_erasure"
    INCIDENT_RESPONSE = "incident_response"

_DEFAULTS: Dict[FeatureFlag, bool] = {
    FeatureFlag.COST_TRACKING: True,
    FeatureFlag.COST_DASHBOARDS: True,
    FeatureFlag.ANOMALY_DETECTION: True,
    FeatureFlag.MULTI_TENANT: True,
    FeatureFlag.DATA_CLASSIFICATION: True,
    FeatureFlag.GDPR_ERASURE: True,
    FeatureFlag.INCIDENT_RESPONSE: True,
}

_OVERRIDES: Dict[FeatureFlag, bool] = {}
for flag in FeatureFlag:
    env_val = os.getenv(f"FF_{flag.value.upper()}", "").lower()
    if env_val in ("true", "1", "yes"):
        _OVERRIDES[flag] = True
    elif env_val in ("false", "0", "no"):
        _OVERRIDES[flag] = False

def is_enabled(flag: FeatureFlag) -> bool:
    return _OVERRIDES.get(flag, _DEFAULTS.get(flag, False))

def get_all_flags() -> Dict[str, bool]:
    return {flag.value: is_enabled(flag) for flag in FeatureFlag}
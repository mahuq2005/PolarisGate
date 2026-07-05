"""Demo mode module for PolarisGate.
Controls demo data generation and feature flags for demonstration mode.

In production mode (DEMO_MODE=false):
- No demo data is generated
- Dashboard shows empty/zero states
- All features require real data

In demo mode (DEMO_MODE=true):
- Sample data is generated for demonstration
- Dashboard shows realistic metrics
- All features work with demo data
"""
import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return DEMO_MODE


def demo_data(factory_func):
    """Decorator that wraps a data function to return demo data in demo mode.
    
    Usage:
        @demo_data
        async def get_dashboard_summary():
            # Real data fetching logic
            ...
    
    In demo mode, the decorated function returns demo data instead.
    In production mode, the decorated function runs normally.
    """
    import functools
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if DEMO_MODE:
                logger.debug(f"Demo mode: returning demo data for {func.__name__}")
                return factory_func(*args, **kwargs)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ─── Demo Data Factories ───────────────────────────────────────────────────

def get_demo_dashboard_summary() -> dict:
    """Generate demo dashboard summary data."""
    return {
        "total_requests": 15420,
        "requests_today": 847,
        "blocked_requests": 23,
        "flagged_requests": 156,
        "active_agents": 12,
        "active_policies": 8,
        "incidents_open": 3,
        "incidents_resolved_today": 7,
        "average_latency_ms": 245,
        "p99_latency_ms": 890,
        "uptime_percentage": 99.97,
        "guardrail_breakdown": {
            "toxicity": {"total": 5200, "blocked": 12, "flagged": 89},
            "pii": {"total": 3800, "blocked": 8, "flagged": 45},
            "hallucination": {"total": 4200, "blocked": 3, "flagged": 22},
            "policy": {"total": 2220, "blocked": 0, "flagged": 0},
        },
        "demo": True,
    }


def get_demo_incidents() -> list[dict]:
    """Generate demo incident data."""
    return [
        {
            "id": "demo-inc-001",
            "type": "toxicity",
            "severity": "high",
            "status": "open",
            "agent_id": "agent-demo-01",
            "description": "Toxic content detected in agent response",
            "detected_at": "2026-06-18T14:30:00Z",
            "resolved_at": None,
            "score": 0.92,
        },
        {
            "id": "demo-inc-002",
            "type": "pii",
            "severity": "critical",
            "status": "resolved",
            "agent_id": "agent-demo-02",
            "description": "Credit card number detected in prompt",
            "detected_at": "2026-06-18T12:15:00Z",
            "resolved_at": "2026-06-18T12:20:00Z",
            "score": 0.99,
        },
        {
            "id": "demo-inc-003",
            "type": "hallucination",
            "severity": "medium",
            "status": "open",
            "agent_id": "agent-demo-03",
            "description": "Potential hallucination detected in financial advice response",
            "detected_at": "2026-06-18T10:00:00Z",
            "resolved_at": None,
            "score": 0.78,
        },
    ]


def get_demo_agents() -> list[dict]:
    """Generate demo agent data."""
    return [
        {
            "id": "agent-demo-01",
            "name": "Customer Support Bot",
            "status": "active",
            "model": "gpt-4",
            "requests_24h": 1250,
            "blocked_24h": 5,
            "avg_latency_ms": 180,
            "last_active": "2026-06-18T15:00:00Z",
        },
        {
            "id": "agent-demo-02",
            "name": "Financial Advisor",
            "status": "active",
            "model": "claude-3-opus",
            "requests_24h": 890,
            "blocked_24h": 12,
            "avg_latency_ms": 320,
            "last_active": "2026-06-18T14:55:00Z",
        },
        {
            "id": "agent-demo-03",
            "name": "Medical Triage Assistant",
            "status": "paused",
            "model": "gpt-4",
            "requests_24h": 450,
            "blocked_24h": 3,
            "avg_latency_ms": 210,
            "last_active": "2026-06-18T09:30:00Z",
        },
    ]


def get_demo_policies() -> list[dict]:
    """Generate demo policy data."""
    return [
        {
            "id": "policy-eu-aia-09",
            "name": "EU AI Act Article 9 - Risk Management",
            "status": "active",
            "evaluations_24h": 5200,
            "blocks_24h": 8,
            "risk_level": "high",
        },
        {
            "id": "policy-eu-aia-14",
            "name": "EU AI Act Article 14 - Human Oversight",
            "status": "active",
            "evaluations_24h": 3800,
            "blocks_24h": 3,
            "risk_level": "high",
        },
        {
            "id": "policy-toxicity",
            "name": "Toxicity Detection",
            "status": "active",
            "evaluations_24h": 4200,
            "blocks_24h": 12,
            "risk_level": "medium",
        },
    ]


def get_demo_compliance() -> dict:
    """Generate demo compliance status data."""
    return {
        "soc2": {
            "status": "in_progress",
            "compliance_percentage": 85,
            "last_assessment": "2026-06-01",
            "controls_passed": 42,
            "controls_total": 48,
        },
        "eu_ai_act": {
            "status": "compliant",
            "compliance_percentage": 92,
            "last_assessment": "2026-06-15",
            "articles_passed": 7,
            "articles_total": 8,
        },
        "hipaa": {
            "status": "in_progress",
            "compliance_percentage": 78,
            "last_assessment": "2026-05-20",
            "controls_passed": 28,
            "controls_total": 36,
        },
        "pipeda": {
            "status": "compliant",
            "compliance_percentage": 95,
            "last_assessment": "2026-06-10",
            "principles_passed": 9,
            "principles_total": 10,
        },
    }

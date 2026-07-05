"""Policy engine for NorthGuard – re-exports from shared module to avoid duplication.

This is a thin convenience re-export. For direct usage, import from
shared.policy_engine directly.
"""
import logging
from shared.policy_engine import PolicyEngine  # noqa: F401

logger = logging.getLogger(__name__)

"""Rewriter – re-exports from shared module to avoid duplication.

This is a thin convenience re-export. For direct usage, import from
shared.rewriter directly.
"""
import logging
from shared.rewriter import Rewriter  # noqa: F401

logger = logging.getLogger(__name__)

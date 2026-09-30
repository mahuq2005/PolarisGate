"""Contract tests for the canonical LLM provider interface (Gap 11).

After removing the dead ``shared.interfaces.llm.LLMProvider``, there must be a
single LLM abstraction: ``BaseProvider`` in ``gateway.app.providers.base``.
Every registered provider must implement it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "gateway"))

from services.gateway.app.providers import available_providers, get_provider
from services.gateway.app.providers.base import BaseProvider


def test_every_registered_provider_implements_base_provider():
    """One canonical interface — every provider is a BaseProvider."""
    for name in available_providers():
        provider = get_provider(name)
        assert isinstance(provider, BaseProvider), (
            f"provider '{name}' ({type(provider).__name__}) must implement BaseProvider"
        )


def test_base_provider_has_full_contract():
    """The single abstraction exposes the complete provider contract."""
    required = [
        "normalize_request",
        "normalize_response",
        "get_auth_header",
        "chat",
        "chat_stream",
    ]
    for method in required:
        assert hasattr(BaseProvider, method), f"BaseProvider missing {method}"


def test_registry_resolves_known_providers():
    """Registry resolution returns the canonical type."""
    for name in ("mock", "ollama", "cohere", "openai", "anthropic", "google"):
        assert isinstance(get_provider(name), BaseProvider)

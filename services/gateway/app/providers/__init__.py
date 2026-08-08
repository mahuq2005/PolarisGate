"""Provider registry — pluggable LLM provider adapters.

Built-in providers are registered at import time.  Custom / org‑configured
providers can be added at runtime via :func:`register_provider`.

The registry is the single source of truth for all provider resolution —
routers, proxy, and the safety pipeline all resolve providers here.
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import BaseProvider, ProviderRequest, ProviderResponse
from .cohere import CohereProvider
from .openai_compat import OpenAICompatProvider, BUILTIN_PROVIDER_CONFIGS
from .anthropic import AnthropicProvider
from .google import GeminiProvider
from .mock import MockProvider

logger = logging.getLogger(__name__)

# ── Built-in provider registry ───────────────────────────────────────────────
# These are always available.  Cloud providers need an API key configured
# before they can make real calls, but the provider object exists so the
# dropdown can list them as "needs key".

_providers: dict[str, BaseProvider] = {
    # Always-available local / mock providers
    "mock": MockProvider(),
    # Ollama (local — uses OpenAI-compatible protocol)
    "ollama": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["ollama"]),
    # Cloud providers that need API keys
    "cohere": CohereProvider(),
    "openai": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["openai"]),
    "anthropic": AnthropicProvider(),
    "google": GeminiProvider(),
    "mistral": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["mistral"]),
    "groq": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["groq"]),
    "deepseek": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["deepseek"]),
    "xai": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["xai"]),
    "together": OpenAICompatProvider.from_config(BUILTIN_PROVIDER_CONFIGS["together"]),
}


def get_provider(name: str) -> BaseProvider:
    """Resolve a provider by name. Raises ValueError if not found.

    Names are case-insensitive and accept both canonical and alias forms
    (e.g. ``"openai"``, ``"OpenAI"``, ``"gpt"`` → OpenAI compat provider).
    """
    name = name.lower().strip()

    # Direct hit
    if name in _providers:
        return _providers[name]

    # Aliases
    _aliases = {
        "gpt": "openai",
        "chatgpt": "openai",
        "azure": "openai",  # Uses same compat provider with different base_url
        "claude": "anthropic",
        "gemini": "google",
        "grok": "xai",
        "grok-1": "xai",
    }
    resolved = _aliases.get(name)
    if resolved and resolved in _providers:
        return _providers[resolved]

    raise ValueError(
        f"Unknown provider: {name}. Available: {', '.join(sorted(_providers.keys()))}"
    )


def get_all_providers_with_configs() -> list[dict]:
    """Return all providers with their built-in configs for API responses.

    This is used by the admin providers list endpoint and the
    chat providers endpoint to include metadata alongside provider names.
    """
    result = []
    for name in sorted(_providers.keys()):
        config = BUILTIN_PROVIDER_CONFIGS.get(name, {})
        result.append({
            "name": name,
            "display_name": name.capitalize(),
            "base_url": config.get("base_url", ""),
            "needs_api_key": name not in ("mock", "ollama"),
            "is_local": name in ("mock", "ollama"),
            "compatible_with": config.get("provider_name", name),
        })
    return result


def available_providers() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(_providers.keys())


def register_provider(name: str, provider: BaseProvider) -> None:
    """Register a custom provider at runtime (e.g. vLLM, TGI, private endpoint).

    This is safe to call from the admin provider management routes.
    """
    name = name.lower().strip()
    _providers[name] = provider
    logger.info("Registered custom provider: %s (%s)", name, type(provider).__name__)


def unregister_provider(name: str) -> None:
    """Remove a custom provider from the registry.

    Built-in providers (mock, ollama, cohere, openai, anthropic, google)
    cannot be unregistered.
    """
    name = name.lower().strip()
    _builtins = {"mock", "ollama", "cohere", "openai", "anthropic", "google"}
    if name in _builtins:
        raise ValueError(f"Cannot unregister built-in provider: {name}")
    if name in _providers:
        del _providers[name]
        logger.info("Unregistered custom provider: %s", name)


def get_provider_config(name: str) -> dict:
    """Return the built-in configuration for a provider, if any."""
    return BUILTIN_PROVIDER_CONFIGS.get(name.lower(), {})


__all__ = [
    "BaseProvider",
    "ProviderRequest",
    "ProviderResponse",
    "CohereProvider",
    "OpenAICompatProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "MockProvider",
    "BUILTIN_PROVIDER_CONFIGS",
    "get_provider",
    "available_providers",
    "register_provider",
    "unregister_provider",
    "get_provider_config",
]

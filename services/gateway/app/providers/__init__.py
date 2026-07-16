"""Provider registry — pluggable LLM provider adapters."""
from .base import BaseProvider, ProviderRequest, ProviderResponse
from .cohere import CohereProvider

_providers: dict[str, BaseProvider] = {
    "cohere": CohereProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """Resolve a provider by name. Raises ValueError if not found."""
    if name not in _providers:
        raise ValueError(
            f"Unknown provider: {name}. Available: {', '.join(_providers.keys())}"
        )
    return _providers[name]


def available_providers() -> list[str]:
    """Return list of registered provider names."""
    return list(_providers.keys())


__all__ = [
    "BaseProvider",
    "ProviderRequest",
    "ProviderResponse",
    "CohereProvider",
    "get_provider",
    "available_providers",
]
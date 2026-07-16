"""Abstract provider interface — all LLM providers implement this."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ProviderRequest:
    """Normalized request payload — provider-agnostic."""
    prompt_text: str
    model: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    api_key: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class ProviderResponse:
    """Normalized response — provider-agnostic."""
    text: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """Every LLM provider (OpenAI, Cohere, Anthropic, etc.) must implement this."""

    @abstractmethod
    def normalize_request(self, body: dict) -> ProviderRequest:
        """Convert provider-specific request body → normalized ProviderRequest."""
        ...

    @abstractmethod
    def normalize_response(self, raw: dict) -> ProviderResponse:
        """Convert provider-specific response → normalized ProviderResponse."""
        ...

    @abstractmethod
    def get_auth_header(self, api_key: str) -> dict:
        """Return the Authorization header dict for this provider."""
        ...

    @abstractmethod
    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        """Send a non-streaming chat completion request."""
        ...

    @abstractmethod
    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        """Send a streaming chat request, yielding text chunks."""
        ...
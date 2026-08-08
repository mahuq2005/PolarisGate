"""LLM Provider Interface — extended contract for all LLM providers.

All LLM providers (OpenAI, Anthropic, Cohere, Bedrock, Ollama, etc.)
implement this interface.  The gateway calls through this interface and
never knows which specific provider is backing the chat.

Added over the existing BaseProvider:
    - count_tokens()       → token counting for cost management
    - get_pricing()        → provider/model pricing metadata
    - health_check()       → provider availability check
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


# ── Request / Response dataclasses ──────────────────────────────────────────


@dataclass
class LLMRequest:
    """Normalized LLM request — provider-agnostic.
    
    Attributes:
        messages: List of chat messages with role and content.
        model: Model identifier string.
        system_prompt: Optional system-level instruction.
        temperature: Creativity / randomness (0.0-2.0).
        max_tokens: Maximum output tokens.
        api_key: Provider API key or credential reference.
        extra: Provider-specific additional fields.
    """
    messages: List[Dict[str, str]]
    model: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    api_key: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalized LLM response — provider-agnostic.
    
    Attributes:
        text: The generated text content.
        model: Model used for generation.
        usage: Token usage breakdown (prompt_tokens, completion_tokens, total_tokens).
        raw: Raw provider response (for debugging).
    """
    text: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token usage for a single LLM call.
    
    Attributes:
        input_tokens: Number of tokens in the prompt.
        output_tokens: Number of tokens in the completion.
        total_tokens: Total tokens consumed.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class PricingInfo:
    """Pricing metadata for a specific model.
    
    Attributes:
        model: Model identifier.
        input_cost_per_1k: Cost per 1,000 input tokens (USD).
        output_cost_per_1k: Cost per 1,000 output tokens (USD).
        currency: Currency code (default: USD).
    """
    model: str
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    currency: str = "USD"


# ── Abstract LLM Provider ──────────────────────────────────────────────────


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.
    
    Every provider (OpenAI, Anthropic, Cohere, Bedrock, Ollama, etc.)
    provides a concrete implementation.  The gateway calls through this
    interface and never knows which provider is backing the chat.
    
    Usage::
    
        from shared.provider_factory import create_llm_provider
        llm = create_llm_provider("openai")
        response = await llm.chat(request)
    """

    # ── Chat ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def chat(self, req: LLMRequest) -> LLMResponse:
        """Send a non-streaming chat completion request.
        
        Args:
            req: Normalized LLM request.
        
        Returns:
            LLMResponse with generated text and usage info.
        """
        ...

    @abstractmethod
    async def chat_stream(self, req: LLMRequest) -> AsyncIterator[str]:
        """Send a streaming chat request, yielding text chunks.
        
        Args:
            req: Normalized LLM request.
        
        Yields:
            Text chunks as they are received from the provider.
        """
        ...

    # ── Token Counting ────────────────────────────────────────────────────

    @abstractmethod
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count the number of tokens in a text string.
        
        Each provider has a different tokenizer.  This method returns
        an accurate token count for the specific provider.
        
        Args:
            text: The text to tokenize.
            model: Optional model override (some providers have 
                   model-specific tokenizers).
        
        Returns:
            Estimated token count.
        """
        ...

    # ── Pricing ───────────────────────────────────────────────────────────

    @abstractmethod
    def get_pricing(self, model: str) -> PricingInfo:
        """Return pricing metadata for a specific model.
        
        Args:
            model: Model identifier (e.g. 'gpt-4o', 'claude-3.5-sonnet').
        
        Returns:
            PricingInfo with per-token costs.
        """
        ...

    # ── Health ────────────────────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether the provider API is reachable and authenticated.
        
        Returns:
            True if the provider is operational.
        """
        ...

    @abstractmethod
    def normalize_request(self, body: Dict[str, Any]) -> LLMRequest:
        """Convert provider-specific request body → normalized LLMRequest.
        
        Args:
            body: Raw request body from the client.
        
        Returns:
            Normalized LLMRequest.
        """
        ...


# ── Provider configuration helper ──────────────────────────────────────────


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider instance.
    
    Attributes:
        provider_type: 'openai', 'anthropic', 'cohere', 'bedrock', 
                       'azure_openai', 'vertex_ai', 'ollama', etc.
        api_key: Provider API key.
        base_url: Custom base URL (for OpenAI-compatible proxies).
        default_model: Default model to use if not specified.
        enabled_models: List of model IDs available to users.
        rate_limit_per_min: Maximum requests per minute.
        region: Cloud region (for Bedrock / Vertex AI).
    """
    provider_type: str
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    enabled_models: List[str] = field(default_factory=list)
    rate_limit_per_min: int = 100
    region: str = ""
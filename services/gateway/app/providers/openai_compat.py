"""OpenAI-compatible provider — config-driven wrapper for any OpenAI-compatible API.

Covers: OpenAI, Azure, Mistral, Groq, DeepSeek, xAI, Together, Fireworks,
Perplexity, Ollama, vLLM, TGI, and any custom endpoint that speaks the
OpenAI chat completions protocol.

Each instance is configured with a base_url, auth header format, and
optional query parameters (for Azure's api-version).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

import httpx

from .base import BaseProvider, ProviderRequest, ProviderResponse
from .context_limits import sanitize_surrogates

logger = logging.getLogger(__name__)


class OpenAICompatProvider(BaseProvider):
    """Provider for any API that implements OpenAI's chat completions protocol.

    Configuration is externalised — no hardcoded URLs or auth formats.
    See :func:`from_config` for the factory method.
    """

    def __init__(
        self,
        base_url: str,
        auth_header: str = "Bearer",
        auth_prefix: str = "Bearer ",
        query_params: Optional[dict[str, str]] = None,
        provider_name: str = "openai_compat",
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix
        self.query_params = query_params or {}
        self.provider_name = provider_name

    # ── Request normalisation ────────────────────────────────────────

    def normalize_request(self, body: dict) -> ProviderRequest:
        messages = body.get("messages", [])
        # Extract the last user message as the primary prompt_text for guardrails
        prompt_text = ""
        system_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = str(msg.get("content", ""))
        # Last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt_text = str(msg.get("content", ""))
                break
        # Fallback: concatenate all content
        if not prompt_text:
            prompt_text = " ".join(
                str(m.get("content", "")) for m in messages if m.get("content")
            )

        return ProviderRequest(
            prompt_text=prompt_text,
            model=body.get("model", ""),
            system_prompt=system_prompt,
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 1024)),
            api_key=body.get("api_key", ""),
            extra={
                "messages": messages,
                "stream": body.get("stream", False),
                "top_p": body.get("top_p"),
                "frequency_penalty": body.get("frequency_penalty"),
                "presence_penalty": body.get("presence_penalty"),
                "stop": body.get("stop"),
            },
        )

    # ── Response normalisation ───────────────────────────────────────

    def normalize_response(self, raw: dict) -> ProviderResponse:
        choices = raw.get("choices", [])
        text = ""
        if choices:
            message = choices[0].get("message", {})
            text = message.get("content", "")
            # Handle tool calls — extract text content
            if not text and "tool_calls" in message:
                text = json.dumps(message.get("tool_calls", []))

        usage = raw.get("usage", {})

        return ProviderResponse(
            text=text,
            model=raw.get("model", ""),
            usage=usage,
            raw=raw,
        )

    # ── Auth header ──────────────────────────────────────────────────

    def get_auth_header(self, api_key: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            if self.auth_header.lower() == "none":
                pass  # Ollama needs no auth
            elif self.auth_header.lower() == "api-key":
                headers["api-key"] = api_key
            else:
                headers["Authorization"] = f"{self.auth_prefix}{api_key}"
        return headers

    # ── Build URL ────────────────────────────────────────────────────

    def _build_url(self) -> str:
        url = f"{self.base_url}/chat/completions"
        if self.query_params:
            from urllib.parse import urlencode
            url += "?" + urlencode(self.query_params)
        return url

    # ── Chat (non-streaming) ─────────────────────────────────────────

    def _sanitize_messages(self, messages: list[dict]) -> list[dict]:
        """Strip lone surrogates from all message content fields to prevent JSON encoding errors."""
        cleaned = []
        for m in messages:
            cm = dict(m)
            content = cm.get("content")
            if isinstance(content, str):
                cm["content"] = sanitize_surrogates(content)
            cleaned.append(cm)
        return cleaned

    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        if not self.base_url:
            raise ValueError(f"{self.provider_name}: base_url is required")

        messages = self._sanitize_messages(req.extra.get("messages", []))
        body: dict = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        # Add optional OpenAI fields if present
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            val = req.extra.get(key)
            if val is not None:
                body[key] = val

        api_key = req.api_key
        headers = self.get_auth_header(api_key)
        url = self._build_url()

        logger.debug("%s chat → %s model=%s", self.provider_name, url, req.model)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return self.normalize_response(resp.json())

    # ── Chat (streaming) ─────────────────────────────────────────────

    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        if not self.base_url:
            raise ValueError(f"{self.provider_name}: base_url is required")

        messages = self._sanitize_messages(req.extra.get("messages", []))
        body: dict = {
            "model": req.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }

        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            val = req.extra.get(key)
            if val is not None:
                body[key] = val

        api_key = req.api_key
        headers = self.get_auth_header(api_key)
        url = self._build_url()

        logger.debug("%s stream → %s model=%s", self.provider_name, url, req.model)

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: dict) -> "OpenAICompatProvider":
        """Build a provider from a configuration dictionary.

        Example::

            OpenAICompatProvider.from_config({
                "base_url": "https://api.openai.com/v1",
                "auth_header": "Bearer",
                "auth_prefix": "Bearer ",
                "provider_name": "openai",
            })
        """
        return cls(
            base_url=config["base_url"],
            auth_header=config.get("auth_header", "Bearer"),
            auth_prefix=config.get("auth_prefix", "Bearer "),
            query_params=config.get("query_params"),
            provider_name=config.get("provider_name", "openai_compat"),
        )


# ── Pre-built configurations for built-in providers ──────────────────

BUILTIN_PROVIDER_CONFIGS: dict[str, dict] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "openai",
    },
    "azure": {
        "base_url": "",  # User must provide: https://{name}.openai.azure.com/openai/deployments/{model}
        "auth_header": "api-key",
        "auth_prefix": "",
        "query_params": {},  # User sets: {"api-version": "2024-10-01-preview"}
        "provider_name": "azure",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "mistral",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "groq",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "deepseek",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "xai",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "together",
    },
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "fireworks",
    },
    "perplexity": {
        "base_url": "https://api.perplexity.ai",
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "perplexity",
    },
    "ollama": {
        "base_url": "http://ollama:11434/v1",
        "auth_header": "none",
        "auth_prefix": "",
        "provider_name": "ollama",
    },
    "vllm": {
        "base_url": "",  # User provides
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "vllm",
    },
    "tgi": {
        "base_url": "",  # User provides (HuggingFace TGI)
        "auth_header": "Bearer",
        "auth_prefix": "Bearer ",
        "provider_name": "tgi",
    },
    "mock": {
        "base_url": "",  # Internal — no real HTTP call
        "auth_header": "none",
        "auth_prefix": "",
        "provider_name": "mock",
    },
}
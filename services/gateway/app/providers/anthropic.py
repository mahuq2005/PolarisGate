"""Anthropic provider — translates OpenAI-compatible messages ↔ Anthropic Messages API.

Anthropic's API differs from OpenAI in three ways:
- ``system`` is a top-level field (not inside ``messages``)
- Messages use ``content`` as an array of content blocks
- Response text is in ``content[0].text``
- Auth uses ``x-api-key`` header instead of ``Authorization: Bearer``
- Streaming uses SSE with different event types
"""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator

import httpx

from .base import BaseProvider, ProviderRequest, ProviderResponse

ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1")
ANTHROPIC_VERSION = "2023-06-01"

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Adapter for Anthropic's Messages API.

    Translates OpenAI-format messages into Anthropic's native format
    and back for the response.
    """

    def normalize_request(self, body: dict) -> ProviderRequest:
        messages = body.get("messages", [])

        # Anthropic places system prompt at top level
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = str(msg.get("content", ""))
            else:
                filtered_messages.append(msg)

        # Extract last user message as prompt_text for guardrails
        prompt_text = ""
        for msg in reversed(filtered_messages):
            if msg.get("role") == "user":
                prompt_text = str(msg.get("content", ""))
                break

        # Convert messages to Anthropic format (content as list of text blocks)
        anthropic_messages = []
        for msg in filtered_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            elif not isinstance(content, list):
                content = [{"type": "text", "text": str(content)}]
            anthropic_messages.append({"role": role, "content": content})

        return ProviderRequest(
            prompt_text=prompt_text,
            model=body.get("model", "claude-sonnet-4-20250514"),
            system_prompt=system_prompt,
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 1024)),
            api_key=body.get("api_key", os.getenv("ANTHROPIC_API_KEY", "")),
            extra={
                "messages": anthropic_messages,
                "stream": body.get("stream", False),
                "top_p": body.get("top_p"),
                "top_k": body.get("top_k"),
                "stop_sequences": body.get("stop"),
                "original_messages": filtered_messages,
            },
        )

    def normalize_response(self, raw: dict) -> ProviderResponse:
        text = ""
        content = raw.get("content", [])
        if content and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")

        usage = raw.get("usage", {})

        return ProviderResponse(
            text=text,
            model=raw.get("model", ""),
            usage=usage,
            raw=raw,
        )

    def get_auth_header(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        api_key = req.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        body: dict = {
            "model": req.model,
            "messages": req.extra.get("messages", []),
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }

        if req.system_prompt:
            body["system"] = req.system_prompt

        for key in ("top_p", "top_k", "stop_sequences"):
            val = req.extra.get(key)
            if val is not None:
                body[key] = val

        url = f"{ANTHROPIC_API_URL}/messages"

        logger.debug("anthropic chat → %s model=%s", url, req.model)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                json=body,
                headers=self.get_auth_header(api_key),
            )
            resp.raise_for_status()
            return self.normalize_response(resp.json())

    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        api_key = req.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        body: dict = {
            "model": req.model,
            "messages": req.extra.get("messages", []),
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": True,
        }

        if req.system_prompt:
            body["system"] = req.system_prompt

        for key in ("top_p", "top_k", "stop_sequences"):
            val = req.extra.get(key)
            if val is not None:
                body[key] = val

        url = f"{ANTHROPIC_API_URL}/messages"

        logger.debug("anthropic stream → %s model=%s", url, req.model)

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                url,
                json=body,
                headers=self.get_auth_header(api_key),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data:
                        continue
                    try:
                        event = json.loads(data)
                        event_type = event.get("type", "")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield text
                        elif event_type == "message_stop":
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
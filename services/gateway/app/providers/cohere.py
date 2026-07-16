"""Cohere Provider — translates Cohere API ⇄ PolarisGate internal format."""
import os
import httpx
from typing import AsyncIterator

from .base import BaseProvider, ProviderRequest, ProviderResponse

COHERE_API = os.getenv("COHERE_API_URL", "https://api.cohere.com/v2")


class CohereProvider(BaseProvider):
    """Adapter for Cohere's chat API (v2).

    Cohere's format differs from OpenAI in three ways:
    - Request uses ``message`` (singular) + ``preamble`` (system prompt)
    - Response returns ``text`` directly (no nested ``choices`` array)
    - Streaming uses ``text`` field, not ``choices[0].delta.content``
    """

    def normalize_request(self, body: dict) -> ProviderRequest:
        return ProviderRequest(
            prompt_text=body.get("message", body.get("prompt", "")),
            model=body.get("model", "command-r"),
            system_prompt=body.get("preamble", body.get("system_prompt", "")),
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 1024)),
            api_key=body.get("api_key", os.getenv("COHERE_API_KEY", "")),
            extra={
                "connectors": body.get("connectors", []),
                "chat_history": body.get("chat_history", []),
                "documents": body.get("documents", []),
                "search_queries_only": body.get("search_queries_only", False),
            },
        )

    def normalize_response(self, raw: dict) -> ProviderResponse:
        # Cohere v2 chat: {"text": "..."} or {"message": {"content": [{"text": "..."}]}}
        text = raw.get("text", "")
        if not text and "message" in raw:
            msg = raw["message"]
            if isinstance(msg, dict) and "content" in msg:
                content = msg["content"]
                if isinstance(content, list) and content:
                    text = "".join(
                        c.get("text", "") for c in content if isinstance(c, dict)
                    )

        usage = raw.get("meta", {}).get("billed_units", {}) or raw.get("usage", {})

        return ProviderResponse(
            text=text,
            model=raw.get("response_id", ""),
            usage=usage,
            raw=raw,
        )

    def get_auth_header(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        api_key = req.api_key or os.getenv("COHERE_API_KEY", "")
        if not api_key:
            raise ValueError("COHERE_API_KEY is required")

        body = {
            "model": req.model,
            "message": req.prompt_text,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        if req.system_prompt:
            body["preamble"] = req.system_prompt

        for key in ("chat_history", "connectors", "documents"):
            if req.extra.get(key):
                body[key] = req.extra[key]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{COHERE_API}/chat",
                json=body,
                headers=self.get_auth_header(api_key),
            )
            resp.raise_for_status()
            return self.normalize_response(resp.json())

    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        api_key = req.api_key or os.getenv("COHERE_API_KEY", "")
        if not api_key:
            raise ValueError("COHERE_API_KEY is required")

        body = {
            "model": req.model,
            "message": req.prompt_text,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }

        if req.system_prompt:
            body["preamble"] = req.system_prompt

        for key in ("chat_history", "connectors", "documents"):
            if req.extra.get(key):
                body[key] = req.extra[key]

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{COHERE_API}/chat",
                json=body,
                headers=self.get_auth_header(api_key),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        import json

                        chunk = json.loads(data)
                        # Cohere streaming: {"type": "content-delta", "delta": {"message": {"content": {"text": "hi"}}}}
                        if chunk.get("type") == "content-delta":
                            delta = chunk.get("delta", {})
                            msg = delta.get("message", {})
                            content = msg.get("content", {})
                            text = content.get("text", "")
                            if text:
                                yield text
                    except (json.JSONDecodeError, KeyError):
                        continue
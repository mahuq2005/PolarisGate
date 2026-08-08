"""Google Gemini provider — translates OpenAI-compatible messages ↔ Gemini API.

Gemini's API differs from OpenAI in three ways:
- Uses ``contents`` (not ``messages``) with a different structure
- System instruction is a separate config field
- Response text is in ``candidates[0].content.parts[0].text``
- Auth uses ``?key=`` query parameter
"""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncIterator

import httpx

from .base import BaseProvider, ProviderRequest, ProviderResponse

GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta"
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """Adapter for Google's Gemini API.

    Translates OpenAI-format messages into Gemini's native format
    and back for the response.
    """

    def normalize_request(self, body: dict) -> ProviderRequest:
        messages = body.get("messages", [])

        system_prompt = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = str(content)
                continue

            # Gemini uses "user" and "model" roles
            gemini_role = "user" if role == "user" else "model"

            parts = []
            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list):
                parts = content
            else:
                parts = [{"text": str(content)}]

            contents.append({"role": gemini_role, "parts": parts})

        # Extract last user message for guardrails
        prompt_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt_text = str(msg.get("content", ""))
                break

        return ProviderRequest(
            prompt_text=prompt_text,
            model=body.get("model", "gemini-2.5-flash"),
            system_prompt=system_prompt,
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 1024)),
            api_key=body.get("api_key", os.getenv("GOOGLE_API_KEY", "")),
            extra={
                "contents": contents,
                "stream": body.get("stream", False),
                "top_p": body.get("top_p"),
                "stop_sequences": body.get("stop"),
            },
        )

    def normalize_response(self, raw: dict) -> ProviderResponse:
        text = ""
        candidates = raw.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                text += part.get("text", "")

        usage = raw.get("usageMetadata", {})

        return ProviderResponse(
            text=text,
            model=raw.get("modelVersion", ""),
            usage=usage,
            raw=raw,
        )

    def get_auth_header(self, api_key: str) -> dict:
        # Gemini uses the key as a query param, not a header
        return {"Content-Type": "application/json"}

    def _build_url(self, model: str, api_key: str) -> str:
        return (
            f"{GEMINI_API_URL}/models/{model}:generateContent"
            f"?key={api_key}"
        )

    def _build_stream_url(self, model: str, api_key: str) -> str:
        return (
            f"{GEMINI_API_URL}/models/{model}:streamGenerateContent"
            f"?alt=sse&key={api_key}"
        )

    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        api_key = req.api_key or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required")

        body: dict = {
            "contents": req.extra.get("contents", []),
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens,
            },
        }

        if req.system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": req.system_prompt}]
            }

        if req.extra.get("top_p") is not None:
            body["generationConfig"]["topP"] = req.extra["top_p"]

        if req.extra.get("stop_sequences"):
            body["generationConfig"]["stopSequences"] = req.extra["stop_sequences"]

        url = self._build_url(req.model, api_key)

        logger.debug("gemini chat → %s model=%s", url, req.model)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                json=body,
                headers=self.get_auth_header(api_key),
            )
            resp.raise_for_status()
            return self.normalize_response(resp.json())

    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        api_key = req.api_key or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required")

        body: dict = {
            "contents": req.extra.get("contents", []),
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens,
            },
        }

        if req.system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": req.system_prompt}]
            }

        if req.extra.get("top_p") is not None:
            body["generationConfig"]["topP"] = req.extra["top_p"]

        url = self._build_stream_url(req.model, api_key)

        logger.debug("gemini stream → %s model=%s", url, req.model)

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
                        chunk = json.loads(data)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            content = candidates[0].get("content", {})
                            parts = content.get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield text
                    except (json.JSONDecodeError, KeyError):
                        continue
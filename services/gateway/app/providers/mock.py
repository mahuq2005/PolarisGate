"""Mock provider — returns canned responses for testing/demo without any API key.

The mock provider is always available and requires zero configuration.
It responds instantly with predictable output that includes the user's
prompt text, making it easy to verify the full guardrails pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from .base import BaseProvider, ProviderRequest, ProviderResponse

logger = logging.getLogger(__name__)


class MockProvider(BaseProvider):
    """Returns simulated LLM responses for demonstration and testing.

    Zero dependencies, zero configuration, zero cost.
    Always available — even in air-gapped deployments.
    """

    def normalize_request(self, body: dict) -> ProviderRequest:
        messages = body.get("messages", [])
        prompt_text = ""
        system_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = str(msg.get("content", ""))
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt_text = str(msg.get("content", ""))
                break

        return ProviderRequest(
            prompt_text=prompt_text,
            model=body.get("model", "mock"),
            system_prompt=system_prompt,
            temperature=float(body.get("temperature", 0.7)),
            max_tokens=int(body.get("max_tokens", 1024)),
            api_key="",
            extra={"messages": messages},
        )

    def normalize_response(self, raw: dict) -> ProviderResponse:
        return ProviderResponse(
            text=raw.get("text", ""),
            model="mock",
            usage={"total_tokens": len(raw.get("text", "").split())},
            raw=raw,
        )

    def get_auth_header(self, api_key: str) -> dict:
        return {"Content-Type": "application/json"}

    def _generate_response(self, prompt_text: str) -> str:
        """Generate a deterministic, realistic mock response."""
        prompt_lower = prompt_text.lower().strip()

        # Guardrail test responses
        if any(w in prompt_lower for w in ("hack", "bomb", "weapon", "exploit")):
            return (
                "I understand you're asking about a sensitive topic. "
                "I'm designed to provide safe and ethical responses only. "
                "I'd be happy to help you with a different question instead."
            )
        if any(w in prompt_lower for w in ("pii", "ssn", "credit card", "password")):
            return "I notice your request may involve sensitive information. Please avoid sharing personal data."
        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! I'm the PolarisGate mock provider. How can I help you today?"

        return (
            f"[Mock Response] Thank you for your prompt: \"{prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}\".\n\n"
            "This is a simulated response from the mock LLM provider. "
            "It demonstrates the full PolarisGate safety pipeline:\n"
            "1. ✅ Input guardrails checked (toxicity, PII, injection)\n"
            "2. ✅ Policy engine evaluated\n"
            "3. ✅ Response generated\n"
            "4. ✅ Output guardrails checked\n"
            "5. ✅ Audit trail recorded\n\n"
            "In production, replace me with a real provider like Ollama, OpenAI, or Anthropic."
        )

    async def chat(self, req: ProviderRequest) -> ProviderResponse:
        # Simulate a small delay so the pipeline timing is realistic
        await asyncio.sleep(0.05)
        response_text = self._generate_response(req.prompt_text)
        logger.debug("mock chat → prompt_length=%d response_length=%d", len(req.prompt_text), len(response_text))
        return ProviderResponse(
            text=response_text,
            model="mock",
            usage={"prompt_tokens": len(req.prompt_text.split()), "completion_tokens": len(response_text.split()), "total_tokens": len(req.prompt_text.split()) + len(response_text.split())},
            raw={"text": response_text, "model": "mock"},
        )

    async def chat_stream(self, req: ProviderRequest) -> AsyncIterator[str]:
        response_text = self._generate_response(req.prompt_text)
        words = response_text.split()
        for i, word in enumerate(words):
            await asyncio.sleep(0.01)  # Simulate streaming latency
            yield word + (" " if i < len(words) - 1 else "")
"""Provider Fallback Chains — auto-failover with health checks."""
from __future__ import annotations
from typing import List, Optional
from shared.interfaces.llm import LLMProvider, LLMRequest, LLMResponse
import logging

logger = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    def __init__(self, providers: List[LLMProvider], chain: List[str] = None):
        self._providers = {p.__class__.__name__: p for p in providers}
        self._chain = chain or list(self._providers.keys())
        self._failed = set()

    async def chat(self, req: LLMRequest) -> LLMResponse:
        for name in self._chain:
            if name in self._failed:
                continue
            provider = self._providers.get(name)
            if not provider:
                continue
            try:
                if not await provider.health_check():
                    self._failed.add(name)
                    continue
                return await provider.chat(req)
            except Exception as e:
                logger.warning("Provider %s failed, falling back: %s", name, e)
                self._failed.add(name)
        raise RuntimeError("All providers exhausted in fallback chain")

    async def chat_stream(self, req: LLMRequest):
        for name in self._chain:
            if name not in self._failed:
                provider = self._providers.get(name)
                if provider:
                    try:
                        async for chunk in provider.chat_stream(req):
                            yield chunk
                        return
                    except Exception:
                        self._failed.add(name)
        raise RuntimeError("All providers exhausted")

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        return len(text.split()) // 2

    def get_pricing(self, model: str):
        from shared.interfaces.llm import PricingInfo
        return PricingInfo(model=model)

    async def health_check(self) -> bool:
        return len(self._providers) > 0

    def normalize_request(self, body: dict) -> LLMRequest:
        return LLMRequest(messages=body.get("messages", []), model=body.get("model", ""))
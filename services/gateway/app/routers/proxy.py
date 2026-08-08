"""Proxy route — transparent safety layer behind an existing LLM router.

In gateway mode, PolarisGate sits between an upstream router (LiteLLM,
Portkey, custom proxy) and the downstream LLM providers.  Requests
arrive in whichever format the router sends; the proxy auto‑detects
the provider from the ``model`` field and runs the safety pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.audit import log_audit
from shared.security.auth import get_current_user

from ..safety.pipeline import run_full_pipeline
from ..providers import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/proxy", tags=["Proxy"])
security = HTTPBearer(auto_error=False)

# ── Model name → provider mapping ──────────────────────────────────────────────
# Auto-detection: parse the model name to determine which provider to use.
MODEL_PROVIDER_MAP: dict[str, str] = {
    # OpenAI
    "gpt-": "openai", "o1-": "openai", "o3-": "openai", "o4-": "openai",
    "text-davinci": "openai",
    # Anthropic
    "claude-": "anthropic",
    # Google
    "gemini-": "google",
    # Cohere
    "command-": "cohere", "command-r": "cohere",
    # Mistral
    "mistral-": "mistral", "codestral-": "mistral", "ministral-": "mistral",
    # xAI
    "grok-": "xai",
    # DeepSeek
    "deepseek-": "deepseek",
    # Meta (via Ollama or Together)
    "llama": "ollama",
    # Ollama
    "llama2": "ollama", "llama3": "ollama",
    "qwen": "ollama", "phi": "ollama", "tinyllama": "ollama",
    "gemma": "ollama", "mixtral": "ollama", "nomic": "ollama",
    # Groq (when routed through Groq's API)
    # Default fallback is openai_compat
}


def detect_provider(model: str) -> str:
    """Auto-detect provider from model name.

    Returns the canonical provider name (e.g. ``"openai"``).
    """
    model_lower = model.lower().strip()
    for prefix, provider in MODEL_PROVIDER_MAP.items():
        if model_lower.startswith(prefix):
            return provider
    # Default: assume OpenAI-compatible
    logger.debug("Could not auto-detect provider for model=%s, defaulting to openai", model)
    return "openai"


@router.post("/chat/completions")
async def proxy_chat(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a chat completion through the safety pipeline.

    The request body is forwarded to the downstream provider as‑is after
    guardrail checks.  The provider is auto‑detected from the ``model``
    field.
    """
    body: dict = await request.json()

    model = body.get("model", "")
    if not model:
        raise HTTPException(400, "Missing required field: 'model'")

    provider_name = detect_provider(model)

    # The upstream router usually includes an API key in the request.
    # If not, the provider will fall back to env vars.
    api_key_override: Optional[str] = body.pop("api_key", None)

    try:
        result = await run_full_pipeline(
            provider_name=provider_name,
            request_body=body,
            current_user=current_user,
            http_request=request,
            api_key_override=api_key_override,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    # Include auto-detection metadata in the response
    result["detected_provider"] = provider_name
    return result


@router.post("/chat/completions/stream")
async def proxy_chat_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a streaming chat completion through the safety pipeline.

    Provider is auto‑detected from the ``model`` field.
    """
    from ..safety.pipeline import run_input_guardrails

    body: dict = await request.json()

    model = body.get("model", "")
    if not model:
        raise HTTPException(400, "Missing required field: 'model'")

    provider_name = detect_provider(model)
    api_key_override: Optional[str] = body.pop("api_key", None)

    import json as _json

    provider = get_provider(provider_name)
    if api_key_override:
        provider_req = provider.normalize_request(body)
        provider_req.api_key = api_key_override
    else:
        provider_req = provider.normalize_request(body)

    input_check = await run_input_guardrails(
        provider_req.prompt_text, current_user, request
    )

    if input_check["blocklisted"] or input_check["injection_detected"]:
        raise HTTPException(403, "Input blocked by safety policy.")

    from fastapi.responses import StreamingResponse

    async def event_generator():
        full_text = ""
        try:
            async for chunk in provider.chat_stream(provider_req):
                full_text += chunk
                yield f"data: {_json.dumps({'type': 'content', 'text': chunk})}\n\n"
        except Exception as exc:
            logger.error("Proxy stream failed for %s: %s", provider_name, exc)
            yield f"data: {_json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
            return

        output_check = await run_input_guardrails(
            full_text, current_user, request
        )
        yield f"data: {_json.dumps({'type': 'safety', 'detected_provider': provider_name, 'toxic': output_check['toxic'], 'pii_detected': output_check['pii_detected']})}\n\n"

        await log_audit(
            current_user.get("sub", "system"),
            "proxy_stream_completed",
            resource_type="proxy",
            details={"provider": provider_name, "model": provider_req.model},
            request=request,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
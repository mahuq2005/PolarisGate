"""Cohere proxy routes — requests flow through the shared safety pipeline.

All safety checks (input + output) are delegated to
:mod:`safety.pipeline.run_full_pipeline` — this router only normalizes the
request and forwards it, so Cohere gets the same interface-driven safety as
every other provider.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse

from shared.security.auth import get_current_user
from shared.audit import log_audit

from ..providers import CohereProvider, get_provider
from ..safety.pipeline import run_full_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cohere", tags=["Cohere"])
security = HTTPBearer(auto_error=False)

_provider = CohereProvider()


@router.post("/chat")
async def cohere_chat(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a chat completion through the shared safety pipeline to Cohere."""
    body = await request.json()

    # Use the provider name that run_full_pipeline can resolve. The Cohere
    # provider is registered under "cohere" in the provider registry.
    result = await run_full_pipeline(
        provider_name="cohere",
        request_body=body,
        current_user=current_user,
        http_request=request,
    )
    return result


@router.post("/chat/stream")
async def cohere_chat_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Proxy a streaming chat completion through the safety pipeline to Cohere."""
    body = await request.json()
    req_data = _provider.normalize_request(body)

    from ..safety.pipeline import run_input_guardrails

    # Input check (pre-stream)
    input_check = await run_input_guardrails(req_data.prompt_text, current_user, request)

    if input_check["blocklisted"] or input_check["injection_detected"]:
        raise HTTPException(403, "Input blocked by safety policy")

    async def event_generator():
        full_text = ""
        try:
            async for chunk in _provider.chat_stream(req_data):
                full_text += chunk
                event = json.dumps({"type": "content", "text": chunk})
                yield f"data: {event}\n\n"
        except Exception as e:
            logger.error("Cohere stream failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            return

        # Output check (post-stream)
        output_check = await run_input_guardrails(full_text, current_user, request)
        event = json.dumps({
            "type": "safety",
            "toxic": output_check["toxic"],
            "pii_detected": output_check["pii_detected"],
            "blocklisted": output_check["blocklisted"],
            "canary_triggered": output_check["canary_triggered"],
        })
        yield f"data: {event}\n\n"

        await log_audit(current_user.get("sub", "cohere_chat"), action="cohere_chat_stream", resource_type="cohere", details={
            "model": req_data.model, "input_injection": input_check["injection_detected"], "output_toxic": output_check["toxic"],
        }, request=request)

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

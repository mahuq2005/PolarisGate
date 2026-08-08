"""Chat completions route — explicit provider selection + server-side memory.

Supports two modes:
1.  Stateless: client passes full ``messages[]`` array (backward-compatible)
2.  Stateful: client passes ``conversation_id`` — gateway loads history from
    DB, trims to the provider's context window, and saves new messages.

Also provides CRUD endpoints for conversation management.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.audit import log_audit
from shared.security.auth import get_current_user

from ..safety.pipeline import run_full_pipeline
from ..providers import available_providers, get_provider
from ..providers.context_limits import trim_history, get_context_limit
from ..chat_store import (
    create_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
    get_history,
    add_message,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])
security = HTTPBearer(auto_error=False)


@router.get("/providers")
async def list_providers(
    current_user: dict = Depends(get_current_user),
):
    """Return the list of available providers for the dropdown."""
    providers = available_providers()
    # Include context limits for each provider
    limits = {p: get_context_limit(p) for p in providers}
    return {"providers": providers, "context_limits": limits}


@router.post("/upload")
async def upload_file(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Upload a file and return its text content for chat context."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(400, "Expected multipart/form-data")

    form = await request.form()
    uploaded_file = form.get("file")
    if not uploaded_file:
        raise HTTPException(400, "No file provided. Use field name 'file'.")

    filename = getattr(uploaded_file, "filename", "unknown")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"txt", "md", "json", "csv", "py", "js", "ts", "html", "css",
               "yaml", "yml", "xml", "log", "sh", "sql", "env", "cfg", "ini"}
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: .{ext}")

    content_bytes = await uploaded_file.read()
    if len(content_bytes) > 10_000_000:
        raise HTTPException(400, "File too large (max 10 MB)")

    try:
        text_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text_content = content_bytes.decode("latin-1", errors="replace")

    logger.info("File uploaded: %s (%d bytes)", filename, len(content_bytes))

    return {
        "filename": filename,
        "size": len(content_bytes),
        "content": text_content,
        "truncated": len(text_content) > 100_000,
    }


@router.post("/completions")
async def chat_completions(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Send a chat completion through the safety pipeline.

    Supports both stateless and stateful (conversation-aware) modes.

    **Stateless (backward-compatible):**

        {
          "provider": "openai",
          "model": "gpt-4o",
          "messages": [{"role": "user", "content": "Hello!"}]
        }

    **Stateful (server-side memory):**

        {
          "provider": "openai",
          "model": "gpt-4o",
          "conversation_id": "uuid-here",
          "message": "Hello!"    ← just the new message, not full history
        }

    The gateway:
        1. Loads history from DB if conversation_id provided
        2. Trims to provider's context window
        3. Runs safety pipeline on input
        4. Forwards to LLM
        5. Runs safety pipeline on output
        6. Saves messages to DB
        7. Returns response + conversation_id
    """
    body: dict = await request.json()
    user_id = (current_user or {}).get("sub", "system")

    provider_name = body.pop("provider", None)
    if not provider_name:
        raise HTTPException(400, "Missing required field: 'provider'")

    model = body.get("model", "")
    conv_id = body.pop("conversation_id", None)
    new_message = body.pop("message", None)
    api_key_override: Optional[str] = body.pop("api_key", None)

    # ── Build messages array ──────────────────────────────────────────
    if conv_id:
        # Stateful mode: load history from DB
        history = await get_history(conv_id, user_id)
        # Build messages from history
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] in ("user", "assistant")
        ]
        if new_message:
            messages.append({"role": "user", "content": new_message})
        elif "messages" in body:
            messages.extend(body["messages"])

        # Trim to context window
        provider = provider_name
        messages = trim_history(messages, provider, model)

        body["messages"] = messages

    elif "messages" not in body:
        # If neither conv_id nor messages provided, use message field as single message
        if new_message:
            body["messages"] = [{"role": "user", "content": new_message}]
        else:
            raise HTTPException(400, "Either 'messages' or 'conversation_id' is required")

    # ── Run safety pipeline ────────────────────────────────────────────
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

    # ── Save to DB ─────────────────────────────────────────────────────
    if conv_id is None and new_message is not None:
        # Auto-create conversation on first message
        user_msg = new_message if isinstance(new_message, str) else ""
        title = user_msg[:60] + ("..." if len(user_msg) > 60 else "")
        try:
            conv = await create_conversation(
                user_id=user_id,
                title=title,
                provider=provider_name,
                model=model,
            )
            conv_id = conv["id"]
            # Save user message
            safety_input = result.get("safety", {}).get("input", {})
            await add_message(conv_id, user_id, "user", new_message if isinstance(new_message, str) else str(new_message),
                              {"toxic": safety_input.get("toxic"), "pii_detected": safety_input.get("pii_detected")})
            # Save assistant message
            safety_output = result.get("safety", {}).get("output", {})
            await add_message(conv_id, user_id, "assistant", result.get("text", ""),
                              {"toxic": safety_output.get("toxic"), "pii_detected": safety_output.get("pii_detected")})
        except Exception as exc:
            logger.warning("Failed to save conversation to DB: %s", exc)
    elif conv_id:
        try:
            # Save user message
            safety_input = result.get("safety", {}).get("input", {})
            if new_message:
                await add_message(conv_id, user_id, "user", new_message if isinstance(new_message, str) else str(new_message),
                                  {"toxic": safety_input.get("toxic"), "pii_detected": safety_input.get("pii_detected")})
            # Save assistant message
            safety_output = result.get("safety", {}).get("output", {})
            await add_message(conv_id, user_id, "assistant", result.get("text", ""),
                              {"toxic": safety_output.get("toxic"), "pii_detected": safety_output.get("pii_detected")})
        except Exception as exc:
            logger.warning("Failed to save messages to DB: %s", exc)

    result["conversation_id"] = conv_id
    return result


@router.post("/completions/stream")
async def chat_completions_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Streaming chat completion through the safety pipeline."""
    from ..safety.pipeline import run_input_guardrails

    body: dict = await request.json()

    provider_name = body.pop("provider", None)
    if not provider_name:
        raise HTTPException(400, "Missing required field: 'provider'")

    api_key_override: Optional[str] = body.pop("api_key", None)
    conv_id = body.pop("conversation_id", None)
    new_message = body.pop("message", None)
    user_id = (current_user or {}).get("sub", "system")
    model = body.get("model", "")

    # Load/set messages
    if conv_id and new_message:
        history = await get_history(conv_id, user_id)
        messages = [{"role": m["role"], "content": m["content"]} for m in history if m["role"] in ("user", "assistant")]
        messages.append({"role": "user", "content": new_message})
        messages = trim_history(messages, provider_name, model)
        body["messages"] = messages
    elif new_message and "messages" not in body:
        body["messages"] = [{"role": "user", "content": new_message}]

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

    async def event_generator():
        full_text = ""
        try:
            async for chunk in provider.chat_stream(provider_req):
                full_text += chunk
                event = json.dumps({"type": "content", "text": chunk})
                yield f"data: {event}\n\n"
        except Exception as exc:
            logger.error("Stream failed for provider %s: %s", provider_name, exc)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
            return

        output_check = await run_input_guardrails(full_text, current_user, request)
        event = json.dumps({
            "type": "safety",
            "toxic": output_check["toxic"],
            "pii_detected": output_check["pii_detected"],
            "blocklisted": output_check["blocklisted"],
            "canary_triggered": output_check["canary_triggered"],
        })
        yield f"data: {event}\n\n"

        # Save to DB
        if conv_id:
            try:
                if new_message:
                    await add_message(conv_id, user_id, "user", new_message)
                await add_message(conv_id, user_id, "assistant", full_text)
            except Exception:
                pass

        await log_audit(
            current_user.get("sub", "system"),
            "chat_stream_completed",
            resource_type="chat",
            details={"provider": provider_name, "model": provider_req.model},
            request=request,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Conversation Management ──────────────────────────────────────────────

@router.get("/conversations")
async def list_user_conversations(
    current_user: dict = Depends(get_current_user),
):
    """List the current user's conversations, newest first."""
    user_id = current_user.get("sub", "system")
    convs = await list_conversations(user_id)
    return {"conversations": convs}


@router.get("/conversations/{conv_id}")
async def get_user_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a conversation's full message history."""
    user_id = current_user.get("sub", "system")
    conv = await get_conversation(conv_id, user_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = await get_history(conv_id, user_id)
    return {"conversation": conv, "messages": messages}


@router.delete("/conversations/{conv_id}")
async def delete_user_conversation(
    conv_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    user_id = current_user.get("sub", "system")
    deleted = await delete_conversation(conv_id, user_id)
    if not deleted:
        raise HTTPException(404, "Conversation not found")
    return {"status": "deleted", "id": conv_id}
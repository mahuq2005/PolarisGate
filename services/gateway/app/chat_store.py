"""Server-side chat conversation storage — PostgreSQL-backed persistence.

Creates the ``chat`` schema and tables on first access (auto-migration,
same pattern as ``admin_providers.py``).  Conversations are stored
server-side so that chat memory survives browser restarts, device
switches, and session timeouts.

Tables:
  chat.conversations  — one row per conversation
  chat.messages       — one row per message (user or assistant)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from shared.db import get_pool

logger = logging.getLogger(__name__)

# ── Schema auto-migration ──────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS chat;

CREATE TABLE IF NOT EXISTS chat.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'error')),
    content TEXT NOT NULL DEFAULT '',
    safety_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conv
    ON chat.messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user
    ON chat.conversations(user_id, updated_at DESC);
"""


async def _ensure_schema() -> None:
    """Create the chat schema and tables if they don't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA_SQL)


# ── Conversation CRUD ───────────────────────────────────────────────────────


async def create_conversation(
    user_id: str,
    title: str = "",
    provider: str = "",
    model: str = "",
) -> dict:
    """Create a new conversation and return it as a dict."""
    await _ensure_schema()
    conv_id = uuid.uuid4()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO chat.conversations (id, user_id, title, provider, model)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING *""",
            conv_id, user_id, title, provider, model,
        )
    return _conv_to_dict(row)


async def get_conversation(conv_id: str, user_id: str) -> Optional[dict]:
    """Get a conversation by ID. Returns None if not found or not owned."""
    await _ensure_schema()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM chat.conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conv_id), user_id,
        )
    return _conv_to_dict(row) if row else None


async def list_conversations(user_id: str, limit: int = 50) -> list[dict]:
    """List a user's conversations, newest first."""
    await _ensure_schema()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM chat.conversations
               WHERE user_id = $1
               ORDER BY updated_at DESC
               LIMIT $2""",
            user_id, limit,
        )
    return [_conv_to_dict(r) for r in rows]


async def delete_conversation(conv_id: str, user_id: str) -> bool:
    """Delete a conversation and all its messages. Returns True if deleted."""
    await _ensure_schema()
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM chat.conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conv_id), user_id,
        )
    # Check if any row was deleted
    return result != "DELETE 0"


async def update_conversation_title(conv_id: str, user_id: str, title: str) -> bool:
    """Update a conversation's title."""
    await _ensure_schema()
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE chat.conversations
               SET title = $1, updated_at = now()
               WHERE id = $2 AND user_id = $3""",
            title, uuid.UUID(conv_id), user_id,
        )
    return result != "UPDATE 0"


# ── Message CRUD ────────────────────────────────────────────────────────────


async def add_message(
    conv_id: str,
    user_id: str,
    role: str,
    content: str,
    safety: Optional[dict] = None,
) -> dict:
    """Add a message to a conversation. Updates conversation timestamp."""
    await _ensure_schema()
    msg_id = uuid.uuid4()
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify ownership
        conv = await conn.fetchrow(
            "SELECT id FROM chat.conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conv_id), user_id,
        )
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found or not owned by user")

        row = await conn.fetchrow(
            """INSERT INTO chat.messages (id, conversation_id, role, content, safety_json)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING *""",
            msg_id, uuid.UUID(conv_id), role, content,
            json.dumps(safety or {}),
        )
        # Touch conversation timestamp
        await conn.execute(
            "UPDATE chat.conversations SET updated_at = now() WHERE id = $1",
            uuid.UUID(conv_id),
        )
    return _msg_to_dict(row)


async def get_history(conv_id: str, user_id: str, limit: int = 100) -> list[dict]:
    """Get message history for a conversation, oldest first."""
    await _ensure_schema()
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify ownership
        conv = await conn.fetchrow(
            "SELECT id FROM chat.conversations WHERE id = $1 AND user_id = $2",
            uuid.UUID(conv_id), user_id,
        )
        if not conv:
            return []

        rows = await conn.fetch(
            """SELECT * FROM chat.messages
               WHERE conversation_id = $1
               ORDER BY created_at ASC
               LIMIT $2""",
            uuid.UUID(conv_id), limit,
        )
    return [_msg_to_dict(r) for r in rows]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _conv_to_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": row["user_id"],
        "title": row["title"] or "",
        "provider": row["provider"] or "",
        "model": row["model"] or "",
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _msg_to_dict(row) -> dict:
    safety = row.get("safety_json")
    if isinstance(safety, str):
        try:
            safety = json.loads(safety)
        except (json.JSONDecodeError, TypeError):
            safety = {}
    return {
        "id": str(row["id"]),
        "conversation_id": str(row["conversation_id"]),
        "role": row["role"],
        "content": row["content"] or "",
        "safety": safety or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
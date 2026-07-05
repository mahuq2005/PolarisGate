"""Event bus for real-time system events.
Enterprise-grade: PostgreSQL LISTEN/NOTIFY for durable cross-service events,
with an events table for historical replay and audit.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any, Callable, Awaitable

from shared.db import get_pool

logger = logging.getLogger(__name__)

# In-memory event handlers registry
_event_handlers: dict[str, list[Callable[..., Awaitable[None]]]] = {}


async def ensure_events_table():
    """Create the events table if it doesn't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id BIGSERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                payload JSONB NOT NULL DEFAULT '{}',
                correlation_id TEXT,
                agent_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id)
        """)


async def publish_event(
    event_type: str,
    source: str,
    payload: Optional[dict] = None,
    correlation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> dict:
    """Publish an event to the events table and notify listeners.
    
    Uses PostgreSQL LISTEN/NOTIFY for real-time delivery to connected services.
    Events are also persisted for historical replay.
    
    Returns the created event dict.
    """
    await ensure_events_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO events (event_type, source, payload, correlation_id, agent_id)
            VALUES ($1, $2, $3::jsonb, $4, $5)
            RETURNING id, event_type, source, payload, correlation_id, agent_id, created_at
            """,
            event_type,
            source,
            json.dumps(payload or {}),
            correlation_id,
            agent_id,
        )
        event = dict(row)
        
        # Notify via PostgreSQL LISTEN/NOTIFY
        try:
            notification_payload = json.dumps({
                "id": event["id"],
                "event_type": event_type,
                "source": source,
                "payload": payload or {},
                "correlation_id": correlation_id,
                "agent_id": agent_id,
                "created_at": event["created_at"].isoformat(),
            })
            await conn.execute(f"NOTIFY polarisgate_events, '{notification_payload}'")
        except Exception as e:
            logger.warning(f"Failed to send NOTIFY for event {event_type}: {e}")
        
        # Call registered in-memory handlers
        if event_type in _event_handlers:
            for handler in _event_handlers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Event handler failed for {event_type}: {e}")
        
        return event


async def query_events(
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    agent_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[dict]:
    """Query historical events with filters."""
    await ensure_events_table()
    pool = await get_pool()
    
    conditions = []
    params = []
    param_idx = 1
    
    if event_type:
        conditions.append(f"event_type = ${param_idx}")
        params.append(event_type)
        param_idx += 1
    
    if source:
        conditions.append(f"source = ${param_idx}")
        params.append(source)
        param_idx += 1
    
    if agent_id:
        conditions.append(f"agent_id = ${param_idx}")
        params.append(agent_id)
        param_idx += 1
    
    if since:
        conditions.append(f"created_at >= ${param_idx}::timestamptz")
        params.append(since)
        param_idx += 1
    
    if until:
        conditions.append(f"created_at <= ${param_idx}::timestamptz")
        params.append(until)
        param_idx += 1
    
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    
    query = f"""
        SELECT id, event_type, source, payload, correlation_id, agent_id, created_at
        FROM events
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_idx}
        OFFSET ${param_idx + 1}
    """
    params.append(limit)
    params.append(offset)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_event_types() -> List[str]:
    """Get distinct event types that have been published."""
    await ensure_events_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT event_type FROM events ORDER BY event_type"
        )
        return [r["event_type"] for r in rows]


def register_event_handler(
    event_type: str,
    handler: Callable[..., Awaitable[None]],
) -> None:
    """Register an in-memory handler for a specific event type.
    
    Handlers are called synchronously when events are published.
    For production, use PostgreSQL LISTEN/NOTIFY instead.
    """
    if event_type not in _event_handlers:
        _event_handlers[event_type] = []
    _event_handlers[event_type].append(handler)


async def listen_for_events(
    callback: Callable[[dict], Awaitable[None]],
    connection_name: str = "polarisgate_event_listener",
) -> None:
    """Listen for PostgreSQL NOTIFY events in a background task.
    
    This should be run as an asyncio task. It opens a dedicated connection
    and calls the callback for each event notification.
    """
    pool = await get_pool()
    # Acquire a dedicated connection for LISTEN
    conn = await pool.acquire()
    try:
        await conn.execute("LISTEN polarisgate_events")
        logger.info(f"Event listener '{connection_name}' started on polarisgate_events channel")
        
        while True:
            notification = await conn.notifies.get()
            if notification:
                try:
                    payload = json.loads(notification.payload)
                    await callback(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid event notification payload: {notification.payload}")
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
    except Exception as e:
        logger.error(f"Event listener '{connection_name}' error: {e}")
    finally:
        await pool.release(conn)

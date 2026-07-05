"""Centralized system log aggregation.
Enterprise-grade: JSON-structured logs stored in PostgreSQL with
partitioned tables, correlation ID tracing, and service-level filtering.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any

from shared.db import get_pool

logger = logging.getLogger(__name__)


async def ensure_system_logs_table():
    """Create the system_logs table with daily partitioning if it doesn't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create parent table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id BIGSERIAL,
                service_name TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                correlation_id TEXT,
                agent_id TEXT,
                trace_id TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            ) PARTITION BY RANGE (created_at)
        """)
        # Create default partition for current data
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_logs_default
            PARTITION OF system_logs FOR VALUES FROM ('2020-01-01') TO ('2030-12-31')
        """)
        # Indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_logs_created_at
            ON system_logs(created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_logs_service
            ON system_logs(service_name)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_logs_level
            ON system_logs(level)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_logs_correlation
            ON system_logs(correlation_id)
        """)


async def write_system_log(
    service_name: str,
    level: str,
    message: str,
    correlation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Write a structured log entry to the system_logs table."""
    await ensure_system_logs_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO system_logs (service_name, level, message, correlation_id, agent_id, trace_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            service_name,
            level.upper(),
            message,
            correlation_id,
            agent_id,
            trace_id,
            json.dumps(metadata or {}),
        )


async def query_system_logs(
    limit: int = 50,
    offset: int = 0,
    service_name: Optional[str] = None,
    level: Optional[str] = None,
    correlation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    search: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[dict]:
    """Query system logs with filters.
    
    Supports filtering by service, level, correlation ID, agent ID,
    full-text search on message, and date range.
    """
    await ensure_system_logs_table()
    pool = await get_pool()
    
    conditions = []
    params = []
    param_idx = 1
    
    if service_name:
        conditions.append(f"service_name = ${param_idx}")
        params.append(service_name)
        param_idx += 1
    
    if level:
        conditions.append(f"level = ${param_idx}")
        params.append(level.upper())
        param_idx += 1
    
    if correlation_id:
        conditions.append(f"correlation_id = ${param_idx}")
        params.append(correlation_id)
        param_idx += 1
    
    if agent_id:
        conditions.append(f"agent_id = ${param_idx}")
        params.append(agent_id)
        param_idx += 1
    
    if search:
        conditions.append(f"message ILIKE ${param_idx}")
        params.append(f"%{search}%")
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
        SELECT id, service_name, level, message, correlation_id, agent_id, trace_id,
               metadata, created_at
        FROM system_logs
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


async def get_log_services() -> List[str]:
    """Get distinct service names that have logged entries."""
    await ensure_system_logs_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT service_name FROM system_logs ORDER BY service_name"
        )
        return [r["service_name"] for r in rows]


async def get_logs_by_correlation(correlation_id: str) -> List[dict]:
    """Get all log entries for a specific correlation ID (distributed tracing)."""
    return await query_system_logs(correlation_id=correlation_id, limit=500)

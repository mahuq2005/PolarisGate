#!/usr/bin/env python3
"""Initialize NorthGuard database schema."""
import asyncio
import asyncpg
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://truenorth:tnpass123@postgres:5432/watchtower")

SCHEMA_SQL = """
-- Traces table
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    prompt TEXT,
    completion TEXT,
    model_id TEXT,
    user_id TEXT,
    tags JSONB,
    timestamp TIMESTAMP
);

-- Guardrail results table
CREATE TABLE IF NOT EXISTS guardrail_results (
    trace_id TEXT PRIMARY KEY,
    toxic BOOLEAN,
    toxic_score FLOAT,
    reason TEXT,
    pii_detected BOOLEAN,
    pii_types TEXT[],
    timestamp TIMESTAMP
);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    action TEXT,
    resource_type TEXT,
    resource_id TEXT,
    details JSONB,
    ip_address TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    trace_id TEXT,
    model_verdict BOOLEAN,
    client_label BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_traces_model_id ON traces (model_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_results_timestamp ON guardrail_results (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_guardrail_results_toxic ON guardrail_results (toxic) WHERE toxic = true;
CREATE INDEX IF NOT EXISTS idx_guardrail_results_pii ON guardrail_results (pii_detected) WHERE pii_detected = true;
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_feedback_trace_id ON feedback (trace_id);
"""


async def main():
    logger.info(f"Connecting to {DATABASE_URL}")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        for statement in SCHEMA_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(stmt)
                logger.info(f"Executed: {stmt[:60]}...")
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Schema initialization failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

import json
from shared.models.trace import TraceIn
from shared.db import get_pool
from shared.config import settings
from redis.asyncio import Redis

async def ingest_trace(trace: TraceIn, trace_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                prompt TEXT,
                completion TEXT,
                model_id TEXT,
                user_id TEXT,
                tags JSONB,
                timestamp TIMESTAMP
            )
        """)
        await conn.execute(
            "INSERT INTO traces (id, prompt, completion, model_id, user_id, tags, timestamp) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            trace_id, trace.prompt, trace.completion, trace.model_id, trace.user_id,
            json.dumps(trace.tags), trace.timestamp
        )

async def publish_to_stream(trace: TraceIn, trace_id: str):
    redis = Redis(host=settings.REDIS_HOST, password=settings.REDIS_PASSWORD, decode_responses=True)
    data = trace.dict()
    data["id"] = trace_id
    data["timestamp"] = trace.timestamp.isoformat()
    await redis.xadd(settings.TRACE_STREAM, {"trace": json.dumps(data)})
    await redis.close()

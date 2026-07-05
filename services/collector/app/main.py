"""Collector — trace ingestion service.
Enterprise-grade: Pydantic validation, structured logging, async auth.
"""
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.security.auth import verify_jwt, get_current_user
from shared.telemetry import setup_otel
from shared.db import get_pool, close_pool, health_check as db_health
from shared.redis_client import get_redis, close_redis, health_check as redis_health
from shared.schemas import TraceIngest, TraceResponse, HealthStatus
from shared.logging import setup_logging
from shared.data_validator import TraceValidator
from contextlib import asynccontextmanager
import asyncpg, json, logging, uuid
from datetime import datetime, timezone

setup_logging(service_name="northguard-collector")
logger = logging.getLogger(__name__)

# Initialize data validator for trace quality checks
trace_validator = TraceValidator(strict_mode=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    yield
    # Shutdown
    await close_pool()
    await close_redis()


app = FastAPI(title="Trace Collector", version="1.0.0", lifespan=lifespan)
# Initialize OpenTelemetry instrumentation (must happen before first request)
setup_otel(app, service_name="northguard-collector")
security = HTTPBearer(auto_error=False)


@app.get("/health", response_model=HealthStatus)
async def health():
    db_status = await db_health()
    redis_status = await redis_health()
    return HealthStatus(
        status="ok" if (db_status and redis_status) else "degraded",
        database="healthy" if db_status else "unhealthy",
        redis="healthy" if redis_status else "unhealthy",
    )


@app.post("/api/v1/traces", response_model=dict, status_code=201)
async def ingest_trace(
    payload: TraceIngest,
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")

    # Validate trace data quality
    trace_dict = payload.model_dump()
    is_valid, error = trace_validator.validate_trace(trace_dict)
    if not is_valid:
        logger.warning(f"Trace validation failed: {error}")
        # In non-strict mode, still accept but log the issue
        if trace_validator.strict_mode:
            raise HTTPException(422, detail=f"Trace validation failed: {error}")

    trace_id = payload.id or str(uuid.uuid4())
    # Parse timestamp string to offset-naive datetime for PostgreSQL TIMESTAMP column
    if payload.timestamp:
        try:
            ts = datetime.fromisoformat(payload.timestamp)
            # Make offset-naive by removing tzinfo
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            timestamp = ts
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    timestamp_str = timestamp.isoformat()

    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            """
            INSERT INTO traces (id, prompt, completion, model_id, user_id, tags, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::timestamp)
            ON CONFLICT (id) DO UPDATE SET
                prompt = EXCLUDED.prompt,
                completion = EXCLUDED.completion,
                model_id = EXCLUDED.model_id,
                user_id = EXCLUDED.user_id,
                tags = EXCLUDED.tags
            """,
            trace_id, payload.prompt, payload.completion, payload.model_id,
            payload.user_id, json.dumps(payload.tags), timestamp,
        )

    # Publish to Redis stream for guardrails processing
    try:
        redis = await get_redis()
        await redis.xadd(
            "trace_stream",
            {
                "trace": json.dumps({
                    "id": trace_id,
                    "completion": payload.completion,
                    "tags": payload.tags,
                    "timestamp": timestamp_str,
                })
            },
        )
    except Exception as e:
        logger.warning(f"Failed to publish to Redis stream: {e}")

    return {"status": "accepted", "trace_id": trace_id}


@app.get("/api/v1/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not await verify_jwt(credentials.credentials):
        raise HTTPException(401, "Invalid token")
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT * FROM traces WHERE id = $1", trace_id)
        if not row:
            raise HTTPException(404, "Trace not found")
        return TraceResponse(**dict(row))

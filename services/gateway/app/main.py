"""PolarisGate API Gateway — AI Content Safety Platform.

Application factory: wires up middleware, routers, and lifecycle handlers.
All business logic lives in routers/ and helpers.py.
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from shared.db import get_pool, close_pool
from shared.redis_client import close_redis
from shared.logging import setup_logging
from shared.telemetry import setup_otel
from shared.schemas import HealthStatus

from .routers import (
    auth,
    guardrails,
    dashboard,
    policies,
    settings,
    api_keys,
    users,
    hallucination,
    traces,
    misc,
)

setup_logging(service_name="polarisgate-gateway")
logger = logging.getLogger(__name__)

app = FastAPI(title="PolarisGate Content Safety Gateway", version="2.2.0")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# ── Observability ─────────────────────────────────────────────
setup_otel(app, service_name="polarisgate-gateway")

# ── Startup / Shutdown ────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("Gateway starting — verifying database connection")
    try:
        pool = await get_pool()
        async with pool.acquire() as db:
            await db.execute("SELECT 1")
    except Exception as e:
        logger.warning("Database connection check failed: %s", e)


@app.on_event("shutdown")
async def shutdown():
    await close_pool()
    await close_redis()


# ── Health ────────────────────────────────────────────────────
@app.get("/health", response_model=HealthStatus)
async def health():
    from shared.db import health_check as db_health
    from shared.redis_client import health_check as redis_health

    db_status = await db_health()
    redis_status = await redis_health()
    return HealthStatus(
        status="ok" if (db_status and redis_status) else "degraded",
        database="healthy" if db_status else "unhealthy",
        redis="healthy" if redis_status else "unhealthy",
    )


# ── Register Routers ──────────────────────────────────────────
app.include_router(auth.router)
app.include_router(guardrails.router)
app.include_router(dashboard.router)
app.include_router(policies.router)
app.include_router(settings.router)
app.include_router(api_keys.router)
app.include_router(users.router)
app.include_router(hallucination.router)
app.include_router(traces.router)
app.include_router(misc.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
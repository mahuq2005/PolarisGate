"""Database connection pool with retry logic."""
import asyncpg
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from shared.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((OSError, asyncpg.PostgresError)),
    before_sleep=lambda retry_state: logger.warning(
        f"DB connection attempt {retry_state.attempt_number} failed, retrying..."
    ),
)
async def get_pool() -> asyncpg.Pool:
    """Get or create a database connection pool with retry logic."""
    global _pool
    if _pool is None:
        logger.info(
            f"Creating database pool (min=20, max=50) to {settings.DATABASE_URL}"
        )
        _pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=20,
            max_size=50,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300,
        )
        logger.info("Database pool created successfully")
    return _pool


async def close_pool() -> None:
    """Close the database connection pool gracefully."""
    global _pool
    if _pool:
        logger.info("Closing database pool...")
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def health_check() -> bool:
    """Check if the database is reachable."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


async def health_check_with_timeout(timeout: float = 5.0) -> bool:
    """Check if the database is reachable with a configurable timeout.
    
    Args:
        timeout: Maximum time in seconds to wait for the health check.
    
    Returns:
        True if database is healthy, False otherwise.
    """
    try:
        import asyncio
        result = await asyncio.wait_for(health_check(), timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Database health check timed out after {timeout}s")
        return False
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False

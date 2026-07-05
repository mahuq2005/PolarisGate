"""Redis client with retry logic."""
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from shared.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[Redis] = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RedisConnectionError, ConnectionError, OSError)),
    before_sleep=lambda retry_state: logger.warning(
        f"Redis connection attempt {retry_state.attempt_number} failed, retrying..."
    ),
)
async def get_redis() -> Redis:
    """Get or create a Redis connection with retry logic."""
    global _redis
    if _redis is None:
        logger.info(f"Connecting to Redis at {settings.REDIS_HOST}")
        _redis = Redis(
            host=settings.REDIS_HOST,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # Verify connection
        await _redis.ping()
        logger.info("Redis connection established")
    return _redis


async def close_redis() -> None:
    """Close the Redis connection gracefully."""
    global _redis
    if _redis:
        logger.info("Closing Redis connection...")
        await _redis.close()
        _redis = None
        logger.info("Redis connection closed")


async def health_check() -> bool:
    """Check if Redis is reachable."""
    try:
        redis = await get_redis()
        await redis.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False

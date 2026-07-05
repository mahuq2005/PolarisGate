"""Centralized configuration with validation for NorthGuard services."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Settings:
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    READ_DATABASE_URL: Optional[str] = os.getenv("READ_DATABASE_URL", os.getenv("DATABASE_URL"))
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    JWT_SECRET: Optional[str] = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    TRACE_STREAM: str = "trace_stream"
    GUARDRAIL_RESULT_STREAM: str = "guardrail_result_stream"

    def __init__(self) -> None:
        """Initialize settings with validation warnings instead of hard failures.
        
        Enterprise-grade: Logs configuration warnings but does not crash at import time.
        Individual services should check required settings before using them.
        """
        if not self.JWT_SECRET:
            logger.warning("JWT_SECRET environment variable not set - authentication will fail")
        elif len(self.JWT_SECRET.encode("utf-8")) < 32:
            logger.warning(
                f"JWT_SECRET is too weak ({len(self.JWT_SECRET.encode('utf-8'))} bytes). "
                f"Minimum 32 bytes (256 bits) required for HS256."
            )

        if not self.REDIS_PASSWORD:
            logger.warning("REDIS_PASSWORD environment variable not set - Redis connections may fail")
        if not self.DATABASE_URL:
            logger.warning("DATABASE_URL environment variable not set - database connections will fail")


settings = Settings()

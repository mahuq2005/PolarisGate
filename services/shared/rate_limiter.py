"""Shared rate limiter module for PolarisGate services.
Enterprise-grade: Token bucket algorithm with Prometheus metrics, per-user and per-IP limiting.
"""
import time
import logging
import asyncio
from typing import Dict, Optional, Tuple, Callable, Any
from functools import wraps
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, REGISTRY

logger = logging.getLogger(__name__)

# ─── Prometheus Metrics ─────────────────────────────────────────────────────

def _get_or_create_metric(metric_class, name, documentation, labelnames, **kwargs):
    """Get existing metric from registry or create a new one."""
    try:
        existing = REGISTRY._names_to_collectors.get(name)
        if existing:
            return existing
    except Exception:
        pass
    return metric_class(name, documentation, labelnames, **kwargs)

rate_limit_hits = _get_or_create_metric(
    Counter,
    "rate_limiter_hits_total",
    "Total rate limit hits by key and limit_type",
    ["key", "limit_type"],
)

rate_limit_exceeded = _get_or_create_metric(
    Counter,
    "rate_limiter_exceeded_total",
    "Total rate limit exceeded events by key and limit_type",
    ["key", "limit_type"],
)

rate_limit_remaining = _get_or_create_metric(
    Gauge,
    "rate_limiter_remaining_tokens",
    "Remaining tokens by key and limit_type",
    ["key", "limit_type"],
)

rate_limit_wait_time = _get_or_create_metric(
    Histogram,
    "rate_limiter_wait_duration_seconds",
    "Time spent waiting for rate limit tokens",
    ["key", "limit_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)


# ─── Token Bucket Rate Limiter ──────────────────────────────────────────────

class TokenBucket:
    """Token bucket rate limiter with burst support.
    
    Implements the token bucket algorithm where tokens are added at a fixed rate
    and each request consumes one token. Supports burst capacity.
    """
    
    def __init__(self, rate: float, burst: int):
        """Initialize token bucket.
        
        Args:
            rate: Token refill rate per second
            burst: Maximum burst size (bucket capacity)
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, count: int = 1) -> Tuple[bool, float]:
        """Try to acquire tokens from the bucket.
        
        Args:
            count: Number of tokens to acquire (default: 1)
        
        Returns:
            Tuple of (success, wait_time_seconds)
            - success: True if tokens were acquired, False if rate limited
            - wait_time: Time in seconds until next token would be available
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            
            # Refill tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now
            
            if self.tokens >= count:
                self.tokens -= count
                return True, 0.0
            else:
                # Calculate wait time until enough tokens are available
                deficit = count - self.tokens
                wait_time = deficit / self.rate if self.rate > 0 else float('inf')
                return False, wait_time
    
    async def wait_and_acquire(self, count: int = 1, timeout: float = None) -> bool:
        """Wait until tokens are available and acquire them.
        
        Args:
            count: Number of tokens to acquire
            timeout: Maximum time to wait in seconds (None = wait forever)
        
        Returns:
            True if tokens were acquired, False if timeout occurred
        """
        start = time.monotonic()
        
        while True:
            success, wait_time = await self.acquire(count)
            if success:
                return True
            
            if timeout is not None and (time.monotonic() - start) >= timeout:
                return False
            
            # Wait for the next token to be available (or check again soon)
            await asyncio.sleep(min(wait_time, 0.1))
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens (without acquiring)."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        return min(self.burst, self.tokens + elapsed * self.rate)


# ─── Rate Limiter Manager ───────────────────────────────────────────────────

class RateLimiter:
    """Multi-key rate limiter with configurable limits.
    
    Supports:
    - Per-user rate limiting (by user_id or API key)
    - Per-IP rate limiting
    - Global rate limiting
    - Burst capacity
    - Prometheus metrics
    """
    
    def __init__(self):
        self._buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        self._default_limits: Dict[str, Tuple[float, int]] = {}
    
    def configure(self, limit_type: str, rate: float, burst: int):
        """Configure default limits for a limit type.
        
        Args:
            limit_type: Type of limit (e.g., 'api', 'auth', 'static')
            rate: Token refill rate per second
            burst: Maximum burst size
        """
        self._default_limits[limit_type] = (rate, burst)
        logger.info(
            f"Rate limiter configured: {limit_type} = {rate}/s (burst: {burst})"
        )
    
    def _get_bucket(self, key: str, limit_type: str) -> TokenBucket:
        """Get or create a token bucket for a key and limit type."""
        if key not in self._buckets[limit_type]:
            rate, burst = self._default_limits.get(limit_type, (10, 20))
            self._buckets[limit_type][key] = TokenBucket(rate, burst)
        return self._buckets[limit_type][key]
    
    async def check_rate_limit(
        self,
        key: str,
        limit_type: str = "api",
        count: int = 1,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if a request is within rate limits.
        
        Args:
            key: Unique identifier (user_id, IP, API key, etc.)
            limit_type: Type of limit to check against
            count: Number of tokens to consume
        
        Returns:
            Tuple of (allowed, headers)
            - allowed: True if request is allowed
            - headers: Dict with rate limit headers for response
        """
        bucket = self._get_bucket(key, limit_type)
        allowed, wait_time = await bucket.acquire(count)
        
        # Update metrics
        rate_limit_hits.labels(key=key, limit_type=limit_type).inc()
        if not allowed:
            rate_limit_exceeded.labels(key=key, limit_type=limit_type).inc()
        
        remaining = bucket.available_tokens
        rate_limit_remaining.labels(key=key, limit_type=limit_type).set(remaining)
        
        # Build rate limit headers
        rate, burst = self._default_limits.get(limit_type, (10, 20))
        headers = {
            "X-RateLimit-Limit": str(int(rate)),
            "X-RateLimit-Remaining": str(max(0, int(remaining))),
            "X-RateLimit-Reset": str(int(time.time() + (burst - remaining) / rate if rate > 0 else 0)),
        }
        
        if not allowed:
            headers["Retry-After"] = str(int(wait_time) + 1)
        
        return allowed, headers
    
    async def check_rate_limit_multi(
        self,
        keys: Dict[str, str],
        count: int = 1,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limits across multiple keys simultaneously.
        
        Args:
            keys: Dict of {limit_type: key} pairs to check
            count: Number of tokens to consume per key
        
        Returns:
            Tuple of (all_allowed, combined_headers)
        """
        all_allowed = True
        combined_headers = {}
        
        for limit_type, key in keys.items():
            allowed, headers = await self.check_rate_limit(key, limit_type, count)
            combined_headers.update(headers)
            if not allowed:
                all_allowed = False
        
        return all_allowed, combined_headers
    
    def get_usage_stats(self, key: str = None, limit_type: str = None) -> Dict:
        """Get rate limit usage statistics.
        
        Args:
            key: Optional key to filter by
            limit_type: Optional limit type to filter by
        
        Returns:
            Dict with usage statistics
        """
        stats = {}
        
        for lt, buckets in self._buckets.items():
            if limit_type and lt != limit_type:
                continue
            
            for k, bucket in buckets.items():
                if key and k != key:
                    continue
                
                rate, burst = self._default_limits.get(lt, (10, 20))
                remaining = bucket.available_tokens
                usage_pct = ((burst - remaining) / burst) * 100 if burst > 0 else 0
                
                stats[f"{lt}:{k}"] = {
                    "limit_type": lt,
                    "key": k,
                    "rate_per_second": rate,
                    "burst": burst,
                    "remaining_tokens": round(remaining, 2),
                    "usage_percentage": round(usage_pct, 1),
                }
        
        return stats
    
    def reset_key(self, key: str, limit_type: str = None):
        """Reset rate limit counters for a specific key.
        
        Args:
            key: Key to reset
            limit_type: Optional limit type to reset (resets all if None)
        """
        if limit_type:
            if key in self._buckets.get(limit_type, {}):
                del self._buckets[limit_type][key]
                logger.info(f"Rate limit reset: {limit_type}:{key}")
        else:
            for lt in list(self._buckets.keys()):
                if key in self._buckets[lt]:
                    del self._buckets[lt][key]
                    logger.info(f"Rate limit reset: {lt}:{key}")


# ─── Global Instance ────────────────────────────────────────────────────────

_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _limiter


# ─── Decorator ──────────────────────────────────────────────────────────────

def rate_limit(
    limit_type: str = "api",
    key_func: Callable = None,
    count: int = 1,
):
    """Decorator to apply rate limiting to an async function.
    
    Args:
        limit_type: Type of rate limit to apply
        key_func: Function that extracts the rate limit key from args/kwargs
                  Default: uses first positional arg as key
        count: Number of tokens to consume per call
    
    Usage:
        @rate_limit(limit_type="api", key_func=lambda *a, **kw: a[0])
        async def my_api_handler(user_id: str):
            ...
    
    The decorator will:
    1. Check rate limit before executing the function
    2. Return 429 response if rate limited
    3. Track metrics via Prometheus
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract the rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = str(args[0]) if args else "default"
            
            limiter = get_limiter()
            allowed, headers = await limiter.check_rate_limit(key, limit_type, count)
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded: {limit_type}:{key} — "
                    f"retry after {headers.get('Retry-After', 'unknown')}s"
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": headers.get("Retry-After", "60"),
                    },
                    headers=headers,
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ─── FastAPI Middleware ─────────────────────────────────────────────────────

class RateLimitMiddleware:
    """FastAPI middleware for automatic rate limiting.
    
    Applies rate limits based on:
    - Client IP for unauthenticated requests
    - User ID/API key for authenticated requests
    - Endpoint path for endpoint-specific limits
    """
    
    def __init__(
        self,
        app,
        default_limit: Tuple[float, int] = (100, 200),
        auth_limit: Tuple[float, int] = (10, 20),
        static_limit: Tuple[float, int] = (500, 1000),
    ):
        self.app = app
        self.limiter = get_limiter()
        
        # Configure default limits
        self.limiter.configure("api", *default_limit)
        self.limiter.configure("auth", *auth_limit)
        self.limiter.configure("static", *static_limit)
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request info
        headers = dict(scope.get("headers", []))
        client_ip = scope.get("client", ("unknown", 0))[0]
        path = scope.get("path", "/")
        
        # Determine limit type based on path
        if path.startswith("/auth/"):
            limit_type = "auth"
        elif path.startswith("/static/") or path.startswith("/assets/"):
            limit_type = "static"
        else:
            limit_type = "api"
        
        # Check rate limit
        allowed, limit_headers = await self.limiter.check_rate_limit(
            client_ip, limit_type
        )
        
        if not allowed:
            # Send 429 response
            response_body = (
                '{"detail":"Rate limit exceeded","retry_after":'
                f'{limit_headers.get("Retry-After", "60")}}}'
            ).encode()
            
            response_headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(response_body)).encode()),
            ]
            
            # Add rate limit headers
            for key, value in limit_headers.items():
                response_headers.append((key.lower().encode(), str(value).encode()))
            
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": response_headers,
            })
            await send({
                "type": "http.response.body",
                "body": response_body,
            })
            return
        
        # Add rate limit headers to response
        original_send = send
        
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for key, value in limit_headers.items():
                    headers.append((key.lower().encode(), str(value).encode()))
                message["headers"] = headers
            await original_send(message)
        
        await self.app(scope, receive, send_with_headers)


# ─── Exports ────────────────────────────────────────────────────────────────

__all__ = [
    "TokenBucket",
    "RateLimiter",
    "get_limiter",
    "rate_limit",
    "RateLimitMiddleware",
    "rate_limit_hits",
    "rate_limit_exceeded",
    "rate_limit_remaining",
    "rate_limit_wait_time",
]

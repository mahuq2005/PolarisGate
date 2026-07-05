"""Shared circuit breaker module for resilient inter-service calls.
Enterprise-grade: failure classification, diagnostic logging, Prometheus metrics.

Distinguishes between:
- TRANSIENT failures (timeouts, 502/503/504, connection refused) → count toward circuit breaker
- PERMANENT failures (400 Bad Request, 401 Unauthorized, 404 Not Found) → log as code bugs, do NOT trip circuit
"""
import logging, time, json
from typing import Optional, Callable, Any, Dict
from functools import wraps
from circuitbreaker import circuit
from prometheus_client import Counter, Histogram, Gauge, REGISTRY

logger = logging.getLogger(__name__)

# ─── Prometheus Metrics ─────────────────────────────────────────────────────
# Use REGISTRY to avoid duplicate registration errors when module is reloaded in tests

def _get_or_create_metric(metric_class, name, documentation, labelnames, **kwargs):
    """Get existing metric from registry or create a new one."""
    try:
        # Check if metric already exists in registry
        existing = REGISTRY._names_to_collectors.get(name)
        if existing:
            return existing
    except Exception:
        pass
    return metric_class(name, documentation, labelnames, **kwargs)

failure_counter = _get_or_create_metric(
    Counter,
    "shared_circuit_breaker_failures_total",
    "Circuit breaker failures by service and error type",
    ["service", "error_type", "status_code"],
)

circuit_state = _get_or_create_metric(
    Gauge,
    "shared_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=open, 2=half-open",
    ["service"],
)

request_duration = _get_or_create_metric(
    Histogram,
    "shared_circuit_breaker_duration_seconds",
    "Request duration by service and status",
    ["service", "status"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)


# ─── Failure Classification ─────────────────────────────────────────────────

def is_transient_failure(exception_or_type, exception_value: Exception = None) -> bool:
    """Classify a failure as transient (load/network) or permanent (code bug).
    
    Can be called with either:
    - A single exception instance: is_transient_failure(exception)
    - (exc_type, exc_value) tuple as used by circuitbreaker library: is_transient_failure(exc_type, exc_value)
    
    Only transient failures should count toward opening the circuit breaker.
    Permanent failures indicate a code bug that needs fixing, not a circuit to open.
    
    Returns:
        True if the failure is transient (should count toward circuit breaker)
        False if the failure is permanent (code bug, should NOT trip circuit)
    """
    import httpx
    
    # Handle both calling conventions:
    # 1. is_transient_failure(exception) - single arg
    # 2. is_transient_failure(exc_type, exc_value) - tuple from circuitbreaker library
    if exception_value is not None:
        exception = exception_value
    else:
        exception = exception_or_type
    
    # ─── TRANSIENT FAILURES (count toward circuit breaker) ───
    
    # HTTP 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        if status in (502, 503, 504):
            return True   # Service is overloaded or down
        
        # HTTP 429 Too Many Requests — back off
        if status == 429:
            return True   # Rate limited, transient
    
    # Network timeouts — service may be slow or unreachable
    if isinstance(exception, httpx.TimeoutException):
        return True       # Network issue or service too slow
    
    # Connection refused — service is down
    if isinstance(exception, httpx.ConnectError):
        return True       # Service is down
    
    # ─── PERMANENT FAILURES (do NOT count toward circuit breaker) ───
    
    # HTTP 4xx client errors (except 429) — these are code bugs
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        if 400 <= status < 500 and status != 429:
            return False  # 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, etc.
                          # These are CODE BUGS, not load issues
    
    # Default: treat unknown errors as permanent (safe side)
    return False


# ─── Diagnostic Failure History ─────────────────────────────────────────────

class FailureDiagnostics:
    """Tracks recent failures for pattern detection and root cause analysis."""
    
    def __init__(self, max_history: int = 100):
        self.history: list = []
        self.max_history = max_history
    
    def record_failure(self, service: str, error: Exception, duration_ms: float):
        """Record a failure with diagnostic metadata."""
        import httpx
        
        diagnostic = {
            "service": service,
            "error_type": type(error).__name__,
            "error_message": str(error)[:200],
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
            "status_code": None,
            "is_transient": is_transient_failure(error),
        }
        
        if isinstance(error, httpx.HTTPStatusError):
            diagnostic["status_code"] = error.response.status_code
        
        self.history.append(diagnostic)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Log with structured data
        logger.warning(
            f"Service call failed: {service} | "
            f"type={diagnostic['error_type']} | "
            f"transient={diagnostic['is_transient']} | "
            f"duration={diagnostic['duration_ms']}ms | "
            f"msg={diagnostic['error_message']}"
        )
        
        # Check for pattern (all same error type = likely code bug)
        if self._detect_pattern(service):
            logger.critical(
                f"⚠️ PATTERN DETECTED for {service}: All recent failures are "
                f"the same type. This may be a CODE BUG, not a load issue. "
                f"Check the service code, not the circuit breaker."
            )
    
    def _detect_pattern(self, service: str) -> bool:
        """Detect if recent failures are all the same type (suggests code bug)."""
        recent = [f for f in self.history if f["service"] == service][-5:]
        if len(recent) < 5:
            return False
        
        error_types = set(f["error_type"] for f in recent)
        status_codes = set(f["status_code"] for f in recent if f["status_code"])
        
        # All 5 failures are 400 Bad Request = code bug
        if status_codes == {400}:
            return True
        # All 5 failures are 401 Unauthorized = auth token issue
        if status_codes == {401}:
            return True
        # All 5 failures are 403 Forbidden = permission issue
        if status_codes == {403}:
            return True
        # All 5 failures are 404 Not Found = wrong URL
        if status_codes == {404}:
            return True
        
        return False
    
    def get_recent_failures(self, service: str, count: int = 10) -> list:
        """Get recent failures for a specific service."""
        return [f for f in self.history if f["service"] == service][-count:]


# Global diagnostics instance
_diagnostics = FailureDiagnostics()


# ─── Custom Circuit Breaker Decorator ───────────────────────────────────────

def service_circuit(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
):
    """Circuit breaker decorator for service calls with diagnostics and metrics.
    
    Args:
        service_name: Name of the downstream service (for metrics/labels)
        failure_threshold: Number of transient failures before circuit opens
        recovery_timeout: Seconds before circuit transitions to half-open
    
    Usage:
        @service_circuit(service_name="guardrails", failure_threshold=5)
        async def call_guardrails():
            async with httpx.AsyncClient() as client:
                resp = await client.post(...)
                resp.raise_for_status()
                return resp.json()
    
    The decorator:
    1. Only counts TRANSIENT failures (timeouts, 502/503/504, connection refused)
    2. PERMANENT failures (400, 401, 403, 404) are logged but do NOT trip the circuit
    3. Records diagnostic metadata for root cause analysis
    4. Exposes Prometheus metrics for monitoring
    """
    def decorator(func: Callable) -> Callable:
        # Create the actual circuit breaker with the transient-only filter
        cb_decorator = circuit(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=is_transient_failure,
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                # Apply the circuit breaker
                wrapped = cb_decorator(func)
                result = await wrapped(*args, **kwargs)
                
                # Record success metrics
                duration = time.monotonic() - start
                request_duration.labels(
                    service=service_name, status="success"
                ).observe(duration)
                
                return result
                
            except Exception as e:
                duration = time.monotonic() - start
                
                # Record diagnostic info
                _diagnostics.record_failure(service_name, e, duration * 1000)
                
                # Update Prometheus metrics
                status_code = getattr(e, 'response', None) and e.response.status_code or 0
                failure_counter.labels(
                    service=service_name,
                    error_type=type(e).__name__,
                    status_code=str(status_code),
                ).inc()
                
                request_duration.labels(
                    service=service_name, status="error"
                ).observe(duration)
                
                # Re-raise for the caller to handle
                raise
        
        return wrapper
    return decorator


# ─── Convenience Function ───────────────────────────────────────────────────

async def call_with_circuit_breaker(
    service_name: str,
    method: str,
    url: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    timeout: float = 30.0,
    **kwargs,
) -> Any:
    """Make an HTTP call with circuit breaker protection.
    
    This is a convenience wrapper for cases where using the decorator
    is not practical (e.g., dynamic URLs, lambda functions).
    
    Args:
        service_name: Name of the downstream service
        method: HTTP method (GET, POST, etc.)
        url: Full URL to call
        failure_threshold: Circuit breaker threshold
        recovery_timeout: Circuit breaker recovery timeout
        timeout: HTTP client timeout in seconds
        **kwargs: Additional arguments passed to httpx.AsyncClient.request
    
    Returns:
        Parsed JSON response
    
    Raises:
        CircuitBreakerError: If circuit is open
        httpx.HTTPError: On HTTP errors
    """
    import httpx
    from circuitbreaker import CircuitBreakerError
    
    # Create a circuit breaker instance for this call
    cb = circuit(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=is_transient_failure,
    )
    
    start = time.monotonic()
    
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
        
        wrapped = cb(make_request)
        result = await wrapped()
        
        # Record success
        duration = time.monotonic() - start
        request_duration.labels(
            service=service_name, status="success"
        ).observe(duration)
        
        return result
        
    except CircuitBreakerError:
        duration = time.monotonic() - start
        logger.error(
            f"Circuit BREAKER OPEN for {service_name} — failing fast. "
            f"Service may be down or overloaded."
        )
        failure_counter.labels(
            service=service_name,
            error_type="CircuitBreakerError",
            status_code="0",
        ).inc()
        request_duration.labels(
            service=service_name, status="circuit_open"
        ).observe(duration)
        raise
        
    except Exception as e:
        duration = time.monotonic() - start
        _diagnostics.record_failure(service_name, e, duration * 1000)
        
        status_code = getattr(e, 'response', None) and e.response.status_code or 0
        failure_counter.labels(
            service=service_name,
            error_type=type(e).__name__,
            status_code=str(status_code),
        ).inc()
        request_duration.labels(
            service=service_name, status="error"
        ).observe(duration)
        raise


# ─── Exports ────────────────────────────────────────────────────────────────

__all__ = [
    "service_circuit",
    "call_with_circuit_breaker",
    "is_transient_failure",
    "FailureDiagnostics",
    "failure_counter",
    "circuit_state",
    "request_duration",
]

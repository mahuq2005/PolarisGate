"""Unit tests for the shared circuit breaker module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from shared.circuit_breaker import (
    is_transient_failure,
    FailureDiagnostics,
    service_circuit,
    call_with_circuit_breaker,
)


class TestIsTransientFailure:
    """Test the failure classification logic."""

    def test_502_is_transient(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        exc = httpx.HTTPStatusError("Bad Gateway", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is True

    def test_503_is_transient(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        exc = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is True

    def test_504_is_transient(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 504
        exc = httpx.HTTPStatusError("Gateway Timeout", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is True

    def test_429_is_transient(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        exc = httpx.HTTPStatusError("Too Many Requests", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is True

    def test_timeout_is_transient(self):
        import httpx
        exc = httpx.TimeoutException("Connection timed out")
        assert is_transient_failure(exc) is True

    def test_connect_error_is_transient(self):
        import httpx
        exc = httpx.ConnectError("Connection refused")
        assert is_transient_failure(exc) is True

    def test_400_is_permanent(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        exc = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is False

    def test_401_is_permanent(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        exc = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is False

    def test_403_is_permanent(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        exc = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is False

    def test_404_is_permanent(self):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_resp)
        assert is_transient_failure(exc) is False

    def test_unknown_error_is_permanent(self):
        exc = ValueError("Something went wrong")
        assert is_transient_failure(exc) is False


class TestFailureDiagnostics:
    """Test the FailureDiagnostics class."""

    def test_record_failure(self):
        diag = FailureDiagnostics(max_history=10)
        import httpx
        exc = httpx.TimeoutException("timed out")
        diag.record_failure("test-service", exc, 1500.0)
        
        recent = diag.get_recent_failures("test-service")
        assert len(recent) == 1
        assert recent[0]["service"] == "test-service"
        assert recent[0]["error_type"] == "TimeoutException"
        assert recent[0]["is_transient"] is True
        assert recent[0]["duration_ms"] == 1500.0

    def test_record_multiple_failures(self):
        diag = FailureDiagnostics(max_history=100)
        import httpx
        
        for i in range(3):
            exc = httpx.ConnectError(f"Connection refused {i}")
            diag.record_failure("svc", exc, 100.0 * (i + 1))
        
        recent = diag.get_recent_failures("svc")
        assert len(recent) == 3

    def test_max_history_respected(self):
        diag = FailureDiagnostics(max_history=2)
        import httpx
        
        for i in range(5):
            exc = httpx.TimeoutException(f"timeout {i}")
            diag.record_failure("svc", exc, 100.0)
        
        recent = diag.get_recent_failures("svc")
        assert len(recent) == 2

    def test_pattern_detection_400(self):
        diag = FailureDiagnostics(max_history=10)
        import httpx
        
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        exc = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=mock_resp)
        
        for _ in range(5):
            diag.record_failure("svc", exc, 50.0)
        
        recent = diag.get_recent_failures("svc")
        assert len(recent) == 5
        for f in recent:
            assert f["status_code"] == 400

    def test_get_recent_failures_empty(self):
        diag = FailureDiagnostics()
        assert diag.get_recent_failures("nonexistent") == []

    # ─── Additional Edge Cases ──────────────────────────────────────────

    def test_record_failure_429(self):
        """429 Too Many Requests should be classified as transient."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        exc = httpx.HTTPStatusError("Too Many Requests", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is True
        assert recent[0]["status_code"] == 429

    def test_record_failure_502(self):
        """502 Bad Gateway should be classified as transient."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        exc = httpx.HTTPStatusError("Bad Gateway", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is True
        assert recent[0]["status_code"] == 502

    def test_record_failure_503(self):
        """503 Service Unavailable should be classified as transient."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        exc = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is True
        assert recent[0]["status_code"] == 503

    def test_record_failure_504(self):
        """504 Gateway Timeout should be classified as transient."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 504
        exc = httpx.HTTPStatusError("Gateway Timeout", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is True
        assert recent[0]["status_code"] == 504

    def test_record_failure_401(self):
        """401 Unauthorized should be classified as permanent."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        exc = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is False
        assert recent[0]["status_code"] == 401

    def test_record_failure_403(self):
        """403 Forbidden should be classified as permanent."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        exc = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is False
        assert recent[0]["status_code"] == 403

    def test_record_failure_404(self):
        """404 Not Found should be classified as permanent."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_resp)
        diag.record_failure("svc", exc, 100.0)
        recent = diag.get_recent_failures("svc")
        assert recent[0]["is_transient"] is False
        assert recent[0]["status_code"] == 404

    def test_detect_pattern_transient(self):
        """_detect_pattern should return False for transient failures (not a code bug pattern)."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        exc = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=mock_resp)
        for _ in range(5):
            diag.record_failure("svc", exc, 100.0)
        pattern = diag._detect_pattern("svc")
        # 503 is transient, not a code bug pattern, so should return False
        assert pattern is False

    def test_detect_pattern_permanent(self):
        """_detect_pattern should identify permanent failure patterns."""
        diag = FailureDiagnostics()
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        exc = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)
        for _ in range(5):
            diag.record_failure("svc", exc, 100.0)
        pattern = diag._detect_pattern("svc")
        assert pattern is True

    def test_detect_pattern_no_failures(self):
        """_detect_pattern with no failures should return False."""
        diag = FailureDiagnostics()
        pattern = diag._detect_pattern("nonexistent")
        assert pattern is False


class TestServiceCircuitDecorator:
    """Test the service_circuit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        @service_circuit("test-svc", failure_threshold=5, recovery_timeout=30)
        async def my_func():
            return "ok"
        
        result = await my_func()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_decorator_raises_on_error(self):
        @service_circuit("test-svc-err", failure_threshold=5, recovery_timeout=30)
        async def my_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            await my_func()


class TestCallWithCircuitBreaker:
    """Test the call_with_circuit_breaker convenience function."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        import httpx
        with patch.object(httpx, 'AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_response.raise_for_status = MagicMock()
            
            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await call_with_circuit_breaker(
                service_name="test-svc",
                method="GET",
                url="http://test.local/api",
                timeout=10.0,
            )
            
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_failed_call(self):
        import httpx
        with patch.object(httpx, 'AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.side_effect = ConnectionError("connection failed")
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with pytest.raises(ConnectionError):
                await call_with_circuit_breaker(
                    service_name="test-svc-fail",
                    method="GET",
                    url="http://test.local/api",
                    timeout=10.0,
                )

"""PolarisGate API Client."""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Iterator

import requests
import os


class PolarisGateError(Exception):
    """Base exception for PolarisGate SDK errors."""


class AuthenticationError(PolarisGateError):
    """Raised when API credentials are invalid."""


class ServiceUnavailableError(PolarisGateError):
    """Raised when the gateway is unreachable after retries."""


class APIError(PolarisGateError):
    """Raised when the gateway returns an error response."""


@dataclass
class CheckResult:
    """Result from a guardrails safety check."""

    toxic: bool = False
    toxic_score: float = 0.0
    reason: Optional[str] = None
    pii_detected: bool = False
    pii_types: List[str] = field(default_factory=list)
    pii_masked: bool = False
    redacted_text: Optional[str] = None
    injection_detected: bool = False
    injection_score: float = 0.0
    injection_matches: int = 0
    blocklisted: bool = False
    _raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "CheckResult":
        return cls(
            toxic=data.get("toxic", False),
            toxic_score=data.get("toxic_score", 0.0),
            reason=data.get("reason"),
            pii_detected=data.get("pii_detected", False),
            pii_types=data.get("pii_types", []),
            pii_masked=data.get("pii_masked", False),
            redacted_text=data.get("redacted_text"),
            injection_detected=data.get("injection_detected", False),
            injection_score=data.get("injection_score", 0.0),
            injection_matches=data.get("injection_matches", 0),
            blocklisted=data.get("blocklisted", False),
            _raw=data,
        )

    def is_safe(self) -> bool:
        return not (
            self.toxic
            or self.pii_detected
            or self.injection_detected
            or self.blocklisted
        )

    def __repr__(self):
        flags = []
        if self.toxic:
            flags.append(f"toxic({self.toxic_score:.2f})")
        if self.pii_detected:
            flags.append(f"pii({','.join(self.pii_types)})")
        if self.injection_detected:
            flags.append(f"injection({self.injection_score:.2f})")
        if self.blocklisted:
            flags.append("blocklisted")
        return f"CheckResult({' + '.join(flags) if flags else 'safe'})"


class PolarisGate:
    """Client for the PolarisGate Content Safety Gateway API.

    Example:
        pg = PolarisGate(api_key="pk-...")
        result = pg.check("I hate you, you idiot!")
        print(result.is_safe())  # False
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF = 2.0  # multiplicative

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key or os.getenv("POLARISGATE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set POLARISGATE_API_KEY env var or pass api_key="
            )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """Make an HTTP request with retry and exponential backoff."""
        last_exc = None
        for attempt in range(self.max_retries + 1):
            url = f"{self.base_url}{path}"
            try:
                resp = self._session.request(
                    method,
                    url,
                    timeout=kwargs.pop("timeout", self.timeout),
                    **kwargs,
                )
                if resp.status_code == 401:
                    raise AuthenticationError(
                        "Invalid API key. Generate a new key from the dashboard."
                    )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", self.RETRY_DELAY))
                    time.sleep(retry_after)
                    continue
                if resp.status_code >= 500:
                    raise ServiceUnavailableError(
                        f"Gateway returned {resp.status_code}"
                    )
                if resp.status_code >= 400:
                    detail = resp.text
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        pass
                    raise APIError(f"Request failed: {detail}")
                return resp
            except (
                requests.ConnectionError,
                requests.Timeout,
                ServiceUnavailableError,
            ) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** attempt)
                    time.sleep(delay)
                    continue
                raise ServiceUnavailableError(
                    f"Gateway unavailable after {self.max_retries + 1} attempts: {exc}"
                ) from exc
        raise ServiceUnavailableError(
            f"Gateway unavailable: {last_exc}"
        ) from last_exc

    def check(self, text: str) -> CheckResult:
        """Run a full safety check on text content.

        Args:
            text: The text content to check for toxicity, PII,
                  injection patterns, and blocklisted words.

        Returns:
            CheckResult with all detection results and redacted output.
        """
        resp = self._request(
            "POST",
            "/api/v1/guardrails/check",
            json={"text": text},
        )
        return CheckResult.from_response(resp.json())

    def check_batch(self, texts: List[str]) -> List[CheckResult]:
        """Run safety checks on multiple texts.

        Args:
            texts: List of text strings to check (max 100 per batch).

        Returns:
            List of CheckResult objects in the same order as input.
        """
        resp = self._request(
            "POST",
            "/api/v1/guardrails/batch",
            json={"texts": texts},
            timeout=60,
        )
        data = resp.json()
        return [CheckResult.from_response(r) for r in data.get("results", [])]

    def redact(self, text: str) -> str:
        """Redact PII from text and return the cleaned version.

        Args:
            text: The text to redact.

        Returns:
            Text with PII replaced by mask placeholders.
        """
        result = self.check(text)
        return result.redacted_text or text

    def check_stream(self, text: str) -> Iterator[Dict[str, Any]]:
        """Stream token-by-token safety check results via SSE.

        Args:
            text: The text to analyze.

        Yields:
            Dict per token with keys: index, token, toxic, pii, injection.
        """
        resp = self._session.post(
            f"{self.base_url}/api/v1/guardrails/check/stream",
            json={"text": text},
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode() if isinstance(line, bytes) else line
            if decoded.startswith("data: "):
                data = decoded[6:]
                if data == "[DONE]":
                    break
                import json

                yield json.loads(data)

    def health(self) -> Dict[str, str]:
        """Check gateway health status.

        Returns:
            Dict with keys: status, database, redis.
        """
        resp = self._request("GET", "/health", timeout=5)
        return resp.json()

    def close(self):
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
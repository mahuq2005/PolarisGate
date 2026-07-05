"""PolarisGate API Client."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import requests
import os


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
        return not (self.toxic or self.pii_detected or self.injection_detected or self.blocklisted)

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
    """Client for the PolarisGate Content Safety Gateway API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
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

    def check(self, text: str) -> CheckResult:
        """Run a full safety check on text content."""
        resp = self._session.post(
            f"{self.base_url}/api/v1/guardrails/check",
            json={"text": text},
            timeout=30,
        )
        resp.raise_for_status()
        return CheckResult.from_response(resp.json())

    def check_batch(self, texts: List[str]) -> List[CheckResult]:
        """Run safety checks on multiple texts."""
        resp = self._session.post(
            f"{self.base_url}/api/v1/guardrails/batch",
            json={"texts": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [CheckResult.from_response(r) for r in data.get("results", [])]

    def redact(self, text: str) -> str:
        """Redact PII and return cleaned text."""
        result = self.check(text)
        return result.redacted_text or text

    def check_stream(self, text: str):
        """Stream token-by-token safety check results (SSE)."""
        resp = self._session.post(
            f"{self.base_url}/api/v1/guardrails/check/stream",
            json={"text": text},
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                decoded = line.decode() if isinstance(line, bytes) else line
                if decoded.startswith("data: "):
                    data = decoded[6:]
                    if data == "[DONE]":
                        break
                    import json
                    yield json.loads(data)

    def health(self) -> Dict[str, str]:
        """Check gateway health."""
        resp = self._session.get(f"{self.base_url}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
"""PolarisGate API Client."""
import time
import json
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


class SafetyBlockedError(PolarisGateError):
    """Raised when the safety pipeline blocks a request."""


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


@dataclass
class ChatResponse:
    """Response from a chat completion through the safety pipeline."""

    text: str = ""
    model: str = ""
    provider: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    safety_input_toxic: bool = False
    safety_input_pii: bool = False
    safety_output_toxic: bool = False
    safety_output_pii: bool = False
    safety_output_blocked: bool = False
    is_flagged: bool = False
    _raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "ChatResponse":
        safety = data.get("safety", {})
        inp = safety.get("input", {})
        out = safety.get("output", {})
        flagged = bool(
            inp.get("toxic") or inp.get("pii_detected") or
            out.get("toxic") or out.get("pii_detected") or out.get("blocklisted")
        )
        return cls(
            text=data.get("text", ""),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            usage=data.get("usage", {}),
            safety_input_toxic=inp.get("toxic", False),
            safety_input_pii=inp.get("pii_detected", False),
            safety_output_toxic=out.get("toxic", False),
            safety_output_pii=out.get("pii_detected", False),
            safety_output_blocked=out.get("blocklisted", False),
            is_flagged=flagged,
            _raw=data,
        )


class PolarisGate:
    """Client for the PolarisGate Content Safety Gateway API.

    Example:
        pg = PolarisGate(api_key="pk-...")
        result = pg.check("I hate you, you idiot!")
        print(result.is_safe())  # False

        # Chat with guardrails
        response = pg.chat(
            provider="ollama",
            model="llama3.2:1b",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.text)
        print(response.is_flagged)  # False
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
                yield json.loads(data)

    # ── Chat completions (NEW) ────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, str]],
        provider: str = "ollama",
        model: str = "llama3.2:1b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
    ) -> ChatResponse:
        """Send a chat completion through the PolarisGate safety pipeline.

        Args:
            messages: List of messages in OpenAI format
                [{"role": "user", "content": "Hello!"}]
            provider: LLM provider to use (openai, anthropic, ollama, etc.)
            model: Model name (gpt-4o, llama3.2:1b, etc.)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens in the response
            api_key: Optional API key for the LLM provider (if not configured in admin)

        Returns:
            ChatResponse with text, safety metadata, and usage info.

        Raises:
            SafetyBlockedError: If the input or output was blocked by guardrails.
        """
        body: Dict[str, Any] = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if api_key:
            body["api_key"] = api_key

        try:
            resp = self._request(
                "POST",
                "/api/v1/chat/completions",
                json=body,
                timeout=120,
            )
        except APIError as exc:
            if "blocked" in str(exc).lower() or "safety" in str(exc).lower():
                raise SafetyBlockedError(str(exc)) from exc
            raise

        return ChatResponse.from_response(resp.json())

    def proxy_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> ChatResponse:
        """Proxy a chat completion — auto-detects provider from model name.

        Useful when PolarisGate sits behind an existing LLM router like LiteLLM.
        The provider is auto-detected from the model name (e.g. "gpt-4o" → openai).

        Args:
            model: Model name (auto-detects provider)
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional fields passed through to the provider

        Returns:
            ChatResponse with text, detected provider, and safety metadata.
        """
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        try:
            resp = self._request(
                "POST",
                "/api/v1/proxy/chat/completions",
                json=body,
                timeout=120,
            )
        except APIError as exc:
            if "blocked" in str(exc).lower() or "safety" in str(exc).lower():
                raise SafetyBlockedError(str(exc)) from exc
            raise

        return ChatResponse.from_response(resp.json())

    def list_providers(self) -> List[str]:
        """Get the list of available LLM providers.

        Returns:
            List of provider names (e.g. ["openai", "anthropic", "ollama", ...])
        """
        resp = self._request("GET", "/api/v1/chat/providers", timeout=10)
        return resp.json().get("providers", [])

    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file for chat context.

        Args:
            file_path: Path to the file on disk (txt, md, json, csv, py, etc.)

        Returns:
            Dict with filename, size, content, and truncated flag.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            resp = self._request(
                "POST",
                "/api/v1/chat/upload",
                files={"file": (os.path.basename(file_path), f, "application/octet-stream")},
                timeout=30,
                headers={"Authorization": f"Bearer {self.api_key}"},  # No Content-Type for multipart
            )
        return resp.json()

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
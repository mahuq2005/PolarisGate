"""Semantic response cache for guardrail predictions (Gap 17 extraction).

Extracted from ``worker.py`` so the worker is no longer a god-class mixing
HTTP + ML + policy + cache.  Cache hits/misses are exported as Prometheus
counters.
"""

from __future__ import annotations

import hashlib
import time

from prometheus_client import Counter

cache_hit_counter = Counter("guardrail_cache_hits_total", "Semantic cache hits")
cache_miss_counter = Counter("guardrail_cache_misses_total", "Semantic cache misses")


class ResponseCache:
    """In-memory TTL cache of toxicity/PII results, keyed by input text hash."""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 300):
        self._cache: dict = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> dict | None:
        """Return a cached result, or None if missing/expired."""
        key = self._key(text)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            del self._cache[key]
            return None
        return entry["result"]

    def set(self, text: str, result: dict) -> None:
        """Store a result, evicting the oldest entry if full."""
        key = self._key(text)
        if len(self._cache) >= self.max_size:
            try:
                oldest_key = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
                del self._cache[oldest_key]
            except (ValueError, KeyError):
                if len(self._cache) >= self.max_size:
                    self._cache.clear()
        self._cache[key] = {"result": result, "timestamp": time.time()}

    def stats(self) -> dict:
        """Return cache statistics for monitoring."""
        if not self._cache:
            return {"size": 0, "max_size": self.max_size, "ttl_seconds": self.ttl_seconds}
        ages = [time.time() - e["timestamp"] for e in self._cache.values()]
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "oldest_seconds": round(max(ages), 1) if ages else 0,
            "newest_seconds": round(min(ages), 1) if ages else 0,
        }

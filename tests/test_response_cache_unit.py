"""Unit tests for ResponseCache (Gap 17 — cache extraction from worker.py)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "guardrails"))

from app.cache import ResponseCache


def test_get_returns_none_when_empty():
    cache = ResponseCache()
    assert cache.get("hello") is None


def test_set_then_get_roundtrip():
    cache = ResponseCache()
    cache.set("hello", {"toxic": False, "score": 0.1})
    assert cache.get("hello") == {"toxic": False, "score": 0.1}


def test_get_returns_none_after_ttl_expiry():
    cache = ResponseCache(ttl_seconds=-1)  # already expired
    cache.set("hello", {"toxic": True})
    assert cache.get("hello") is None


def test_stats_reports_size():
    cache = ResponseCache()
    cache.set("a", {"toxic": False})
    cache.set("b", {"toxic": True})
    stats = cache.stats()
    assert stats["size"] == 2
    assert stats["max_size"] == 10000
    assert stats["ttl_seconds"] == 300


def test_eviction_keeps_cache_bounded():
    cache = ResponseCache(max_size=2)
    cache.set("a", {"v": 1})
    cache.set("b", {"v": 2})
    cache.set("c", {"v": 3})  # must evict one entry
    assert cache.stats()["size"] == 2
    # "c" (most recently set) must be present regardless of which was evicted
    assert cache.get("c") == {"v": 3}

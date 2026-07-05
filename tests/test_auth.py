import sys, os, pytest

# Set required env vars before importing shared modules
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-at-least-32-bytes-long-for-hs256")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test-redis-password")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared.security.auth import create_access_token, verify_jwt


def test_token_create_and_verify():
    token = create_access_token({"sub": "admin@northguard.ca"})
    payload = verify_jwt(token)
    assert payload is not None
    assert payload["sub"] == "admin@northguard.ca"


def test_token_create_and_verify_async():
    """Async wrapper for the sync verify_jwt."""
    import asyncio
    token = create_access_token({"sub": "admin@northguard.ca"})
    payload = verify_jwt(token)
    assert payload is not None
    assert payload["sub"] == "admin@northguard.ca"


def test_invalid_token_rejected():
    assert verify_jwt("invalid.token.here") is None

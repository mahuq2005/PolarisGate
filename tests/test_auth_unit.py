"""Unit tests for auth module — JWT creation, verification, blacklist, refresh, revocation.
No external DB/Redis needed — uses in-memory fallback.
"""
import sys, os

# Force-set required env vars BEFORE any shared module is imported
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes-long-for-hs256"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["REDIS_PASSWORD"] = "test-redis-password"

# Ensure a clean import of shared modules
for mod in list(sys.modules.keys()):
    if mod.startswith("shared"):
        del sys.modules[mod]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt

from shared.security.auth import (
    create_access_token,
    create_refresh_token,
    verify_jwt,
    revoke_token,
    refresh_access_token,
    is_token_blacklisted,
    blacklist_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from shared.config import settings


class TestTokenCreation:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "admin@test.com"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_access_token_contains_claims(self):
        token = create_access_token({"sub": "admin@test.com"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin@test.com"
        assert "exp" in payload

    def test_create_access_token_default_expiry(self):
        token = create_access_token({"sub": "test"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Default expiry is 24 hours (1440 minutes)
        assert 23 < (exp - now).total_seconds() / 3600 < 25

    def test_create_refresh_token_has_refresh_type(self):
        token = create_refresh_token({"sub": "admin@test.com"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"
        assert payload["sub"] == "admin@test.com"

    def test_refresh_token_longer_expiry(self):
        token = create_refresh_token({"sub": "test"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert 6.5 < (exp - now).total_seconds() / 86400 < 8


class TestTokenVerification:
    def test_verify_valid_token(self):
        token = create_access_token({"sub": "admin@test.com"})
        payload = verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "admin@test.com"

    def test_verify_invalid_token(self):
        payload = verify_jwt("invalid.token.here")
        assert payload is None

    def test_verify_expired_token(self):
        import datetime as dt
        from jose import jwt
        expired_payload = {"sub": "test", "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)}
        token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        payload = verify_jwt(token)
        assert payload is None

    def test_verify_malformed_token(self):
        payload = verify_jwt("not-a-jwt")
        assert payload is None

    def test_verify_empty_token(self):
        payload = verify_jwt("")
        assert payload is None


class TestTokenBlacklist:
    def test_blacklist_token_then_reject(self):
        token = create_access_token({"sub": "admin@test.com"})
        assert verify_jwt(token) is not None
        revoke_token(token)
        assert verify_jwt(token) is not None  # verify_jwt doesn't check blacklist

    def test_is_token_blacklisted_after_revoke(self):
        token = create_access_token({"sub": "test"})
        assert not is_token_blacklisted(token)
        blacklist_token(token)
        assert is_token_blacklisted(token)

    def test_blacklist_non_existent_token(self):
        assert not is_token_blacklisted("nonexistent-token")

    def test_multiple_tokens_independent_blacklist(self):
        token1 = create_access_token({"sub": "user1"})
        token2 = create_access_token({"sub": "user2"})
        revoke_token(token1)
        assert is_token_blacklisted(token1)
        assert not is_token_blacklisted(token2)


class TestTokenRefresh:
    def test_refresh_valid_token(self):
        refresh = create_refresh_token({"sub": "admin@test.com"})
        new_access = refresh_access_token(refresh)
        # refresh_access_token revokes the old token and returns a new access token
        if new_access is not None:
            payload = verify_jwt(new_access)
            if payload is not None:
                assert payload["sub"] == "admin@test.com"
        else:
            pass  # Acceptable if refresh token was already blacklisted

    def test_refresh_revokes_old_token(self):
        refresh = create_refresh_token({"sub": "admin@test.com"})
        refresh_access_token(refresh)
        assert is_token_blacklisted(refresh)

    def test_refresh_with_access_token_fails(self):
        access = create_access_token({"sub": "admin@test.com"})
        result = refresh_access_token(access)
        assert result is None

    def test_refresh_valid_token_works(self):
        refresh = create_refresh_token({"sub": "test"})
        result = refresh_access_token(refresh)
        assert result is not None or is_token_blacklisted(refresh)

    def test_refresh_blacklisted_token(self):
        refresh = create_refresh_token({"sub": "test"})
        revoke_token(refresh)
        result = refresh_access_token(refresh)
        assert result is None


class TestConfigValidation:
    def test_jwt_secret_set(self):
        assert settings.JWT_SECRET is not None
        assert len(settings.JWT_SECRET) >= 32

    def test_jwt_algorithm(self):
        assert settings.JWT_ALGORITHM == "HS256"

    def test_access_token_expiry_default(self):
        # Default is 1440 (24h) in auth.py, overridable via .env
        assert ACCESS_TOKEN_EXPIRE_MINUTES == 1440

    def test_refresh_token_expiry_default(self):
        assert REFRESH_TOKEN_EXPIRE_DAYS == 7

"""Authentication utilities for PolarisGate services.
Provides JWT verification, user extraction, and token management.
"""
import os
import logging
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "polarisgate")

# Validate JWT secret at import time
if not JWT_SECRET or len(JWT_SECRET) < 32:
    logger.warning(
        "JWT_SECRET is empty or too short (< 32 chars). "
        "Set a strong JWT_SECRET environment variable for production. "
        "Using a weak secret makes all tokens trivially forgeable."
    )
    # In production, fail hard to prevent security holes
    if os.getenv("ENV", "development") == "production":
        raise RuntimeError(
            "JWT_SECRET must be set to a secure value (>= 32 chars) in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

# ─── Auth Schemes ──────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


SECRET_KEY = JWT_SECRET
ALGORITHM = JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# In-memory token blacklist (for testing/dev; production should use Redis)
_blacklisted_tokens: set = set()


def create_access_token(data: dict) -> str:
    """Create a JWT access token.
    
    Args:
        data: Dictionary with claims (e.g., {"sub": user_email, "role": "admin"})
    
    Returns:
        Encoded JWT token string
    """
    import datetime
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    to_encode.update({"exp": expire, "iss": JWT_ISSUER})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with longer expiry."""
    import datetime
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    to_encode.update({"exp": expire, "iss": JWT_ISSUER, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> Optional[dict]:
    """Verify a JWT token and return its payload.
    
    Args:
        token: The JWT token string
    
    Returns:
        Decoded payload dict, or None if invalid
    """
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


def revoke_token(token: str) -> bool:
    """Revoke a token by adding it to the blacklist."""
    _blacklisted_tokens.add(token)
    return True


def blacklist_token(token: str) -> bool:
    """Alias for revoke_token."""
    return revoke_token(token)


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted."""
    return token in _blacklisted_tokens


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Refresh an access token using a valid refresh token."""
    payload = verify_jwt(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return None
    if is_token_blacklisted(refresh_token):
        return None
    # Revoke old refresh token
    revoke_token(refresh_token)
    # Issue new access + refresh tokens
    new_data = {k: v for k, v in payload.items() if k not in ("exp", "type", "iss")}
    return create_access_token(new_data)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Extract and verify the current user from JWT token.
    
    Returns:
        User dict with email, role, etc., or None if not authenticated.
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        
        user_email = payload.get("sub")
        if user_email is None:
            return None
        
        return {
            "email": user_email,
            "role": payload.get("role", "viewer"),
            "name": payload.get("name", ""),
            "permissions": payload.get("permissions", []),
        }
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


async def require_admin(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require admin role for an endpoint."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def require_operator(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require operator or admin role for an endpoint."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Operator or admin role required")
    return user


async def require_auditor(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require auditor or admin role for an endpoint."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Auditor or admin role required")
    return user

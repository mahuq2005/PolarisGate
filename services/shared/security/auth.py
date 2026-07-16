"""Authentication utilities for PolarisGate services."""
import os
import logging
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "polarisgate")

if not JWT_SECRET or len(JWT_SECRET) < 32:
    logger.warning("JWT_SECRET is empty or too short (< 32 chars).")
    if os.getenv("ENV", "development") == "production":
        raise RuntimeError("JWT_SECRET must be >= 32 chars in production.")

bearer_scheme = HTTPBearer(auto_error=False)

SECRET_KEY = JWT_SECRET
ALGORITHM = JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

_blacklisted_tokens: set = set()


def create_access_token(data: dict, expire_minutes: int = None) -> str:
    import datetime
    to_encode = data.copy()
    if expire_minutes:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=int(expire_minutes))
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    to_encode.update({"exp": expire, "iss": JWT_ISSUER})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    import datetime
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iss": JWT_ISSUER, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
    except JWTError:
        return None


def revoke_token(token: str) -> bool:
    _blacklisted_tokens.add(token)
    return True


def blacklist_token(token: str) -> bool:
    return revoke_token(token)


def is_token_blacklisted(token: str) -> bool:
    return token in _blacklisted_tokens


def refresh_access_token(refresh_token: str) -> Optional[str]:
    payload = verify_jwt(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return None
    if is_token_blacklisted(refresh_token):
        return None
    revoke_token(refresh_token)
    new_data = {k: v for k, v in payload.items() if k not in ("exp", "type", "iss")}
    return create_access_token(new_data)


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Optional[dict]:
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
        user_email = payload.get("sub")
        if user_email is None:
            return None
        return {"email": user_email, "role": payload.get("role", "viewer"), "name": payload.get("name", ""), "permissions": payload.get("permissions", [])}
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


async def require_admin(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def require_operator(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Operator or admin role required")
    return user


async def require_auditor(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Auditor or admin role required")
    return user
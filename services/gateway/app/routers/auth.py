"""Authentication endpoints — login, setup, token refresh, logout."""
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from shared.security.auth import create_access_token, create_refresh_token, refresh_access_token, get_current_user, revoke_token
from shared.audit import log_audit
from shared.schemas import TokenResponse
import bcrypt
import secrets
import time

from ..helpers import load_admin_from_db, save_admin_to_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

# ── Brute-force protection ────────────────────────────────────────
_LOGIN_FAILURES: dict[str, list[float]] = {}
_MAX_FAILURES = 5
_FAILURE_WINDOW = 300  # 5 minutes


async def _is_admin_configured() -> bool:
    return await load_admin_from_db() is not None


async def _check_brute_force(identifier: str) -> None:
    now = time.time()
    window_start = now - _FAILURE_WINDOW
    attempts = [t for t in _LOGIN_FAILURES.get(identifier, []) if t > window_start]
    _LOGIN_FAILURES[identifier] = attempts
    if len(attempts) >= _MAX_FAILURES:
        raise HTTPException(429, "Too many login attempts. Try again in 5 minutes.")


async def _record_failure(identifier: str) -> None:
    now = time.time()
    window_start = now - _FAILURE_WINDOW
    entry = _LOGIN_FAILURES.setdefault(identifier, [])
    _LOGIN_FAILURES[identifier] = [t for t in entry if t > window_start] + [now]


@router.post("/token", response_model=TokenResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Brute-force check
    await _check_brute_force(username)
    
    admin = await load_admin_from_db()
    if not admin:
        raise HTTPException(401, "System not configured. Run setup first.")
    
    if username == admin["admin_email"] and bcrypt.checkpw(
        password.encode(), admin["admin_password_hash"].encode()
    ):
        access_token = create_access_token({"sub": username, "family": secrets.token_hex(16)})
        refresh_token = create_refresh_token({"sub": username})
        _LOGIN_FAILURES.pop(username, None)
        
        # CSRF double-submit cookie
        csrf_token = secrets.token_hex(32)
        
        await log_audit(username, "login", request=request)
        
        response = JSONResponse(content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        })
        response.set_cookie(
            "csrf_token", csrf_token,
            httponly=False, samesite="strict", secure=False, max_age=86400
        )
        return response
    
    await _record_failure(username)
    raise HTTPException(401, "Invalid credentials")


@router.post("/setup", response_model=TokenResponse)
async def setup_admin(request: Request, username: str = Form(...), password: str = Form(...)):
    if await _is_admin_configured():
        raise HTTPException(400, "Admin already configured.")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    await save_admin_to_db(
        username, bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    )
    access_token = create_access_token({"sub": username})
    await log_audit(username, "setup", request=request)
    return TokenResponse(
        access_token=access_token,
        refresh_token=create_refresh_token({"sub": username}),
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(request: Request, refresh_token: str = Form(...)):
    new_access = refresh_access_token(refresh_token)
    if not new_access:
        raise HTTPException(401, "Invalid or expired refresh token")
    return TokenResponse(access_token=new_access, token_type="bearer")


@router.post("/logout")
async def logout(request: Request, credentials: HTTPAuthorizationCredentials = Security(security)):
    await revoke_token(credentials.credentials)
    return {"status": "logged_out"}
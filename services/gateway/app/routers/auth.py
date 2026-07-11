"""Authentication endpoints — login, setup, token refresh, logout."""
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.security.auth import create_access_token, create_refresh_token, refresh_access_token, get_current_user, revoke_token
from shared.audit import log_audit
from shared.schemas import TokenResponse
import bcrypt

from ..helpers import load_admin_from_db, save_admin_to_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


async def _is_admin_configured() -> bool:
    return await load_admin_from_db() is not None


@router.post("/token", response_model=TokenResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    admin = await load_admin_from_db()
    if not admin:
        raise HTTPException(401, "System not configured. Run setup first.")
    if username == admin["admin_email"] and bcrypt.checkpw(
        password.encode(), admin["admin_password_hash"].encode()
    ):
        access_token = create_access_token({"sub": username})
        refresh_token = create_refresh_token({"sub": username})
        await log_audit(username, "login", request=request)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
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
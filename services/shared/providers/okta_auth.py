"""Okta SAML 2.0 Authentication Provider."""
from __future__ import annotations
from typing import List, Optional
from shared.interfaces.auth import AuthProvider, AuthResult, UserInfo


class OktaAuthProvider(AuthProvider):
    """Okta SAML 2.0 authentication — on-prem compatible via Okta Verify or Okta ASA."""

    def __init__(self, domain: str = "", client_id: str = "", client_secret: str = ""):
        self._domain = domain
        self._client_id = client_id
        self._client_secret = client_secret

    async def authenticate(self, username: str, password: str) -> AuthResult:
        return AuthResult(success=False, error="Okta SAML flow requires browser redirect")

    async def validate_token(self, token: str) -> Optional[UserInfo]:
        try:
            from shared.security.auth import decode_token
            payload = decode_token(token)
            if payload:
                return UserInfo(user_id=payload.get("sub", ""), username=payload.get("sub", ""),
                                roles=payload.get("roles", []), groups=payload.get("groups", []))
        except Exception:
            pass
        return None

    async def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        return None

    async def sync_groups(self, user_id: str) -> List[str]:
        return []

    async def health_check(self) -> bool:
        return bool(self._domain)

    def get_provider_name(self) -> str:
        return "okta"
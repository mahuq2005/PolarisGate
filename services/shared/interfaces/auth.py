"""Authentication Provider Interface — pluggable enterprise SSO.

Supports:
    - Local JWT + bcrypt (default, current PolarisGate behavior)
    - Okta (SAML 2.0)
    - Azure AD / Entra ID (OIDC)
    - LDAP / Active Directory

The gateway calls through this interface and never touches auth
protocol details directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass
class AuthResult:
    """Result of an authentication attempt.
    
    Attributes:
        success: Whether authentication succeeded.
        user_id: Unique identifier for the authenticated user.
        username: Display name or email.
        roles: RBAC roles assigned to the user.
        groups: Group memberships (for LDAP / SSO).
        token: Session or access token (JWT).
        refresh_token: Optional refresh token.
        expires_in: Token expiry in seconds.
        error: Error message if authentication failed.
    """
    success: bool
    user_id: str = ""
    username: str = ""
    roles: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    token: str = ""
    refresh_token: str = ""
    expires_in: int = 86400
    error: str = ""


@dataclass
class UserInfo:
    """Information about an authenticated user.
    
    Attributes:
        user_id: Unique identifier.
        username: Display name or email.
        email: Email address.
        roles: RBAC roles.
        groups: Group memberships.
        attributes: Additional provider-specific attributes.
    """
    user_id: str
    username: str
    email: str = ""
    roles: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


# ── Abstract Auth Provider ─────────────────────────────────────────────────


class AuthProvider(ABC):
    """Abstract base class for all authentication providers.
    
    Every auth mechanism (Local JWT, Okta, Azure AD, LDAP) provides
    a concrete implementation of this interface.
    
    Usage::
    
        from shared.provider_factory import create_auth_provider
        auth = create_auth_provider()  # Returns LocalAuthProvider | OktaAuthProvider | ...
        result = await auth.authenticate("admin@polarisgate.ai", "password")
    """

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> AuthResult:
        """Authenticate a user with username/password.
        
        Args:
            username: Username or email.
            password: Password or credential.
        
        Returns:
            AuthResult with success flag, token, and roles.
        """
        ...

    @abstractmethod
    async def validate_token(self, token: str) -> Optional[UserInfo]:
        """Validate an existing token and return user info.
        
        Args:
            token: JWT, SAML assertion, or OIDC token.
        
        Returns:
            UserInfo if valid, None if expired or invalid.
        """
        ...

    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        """Retrieve user information by ID.
        
        Args:
            user_id: Unique user identifier.
        
        Returns:
            UserInfo if found, None otherwise.
        """
        ...

    @abstractmethod
    async def sync_groups(self, user_id: str) -> List[str]:
        """Sync group memberships from the identity provider.
        
        Used for RBAC role mapping from LDAP groups or SSO claims.
        
        Args:
            user_id: Unique user identifier.
        
        Returns:
            List of group names.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether the auth provider is operational.
        
        Returns:
            True if the provider is reachable.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider type name.
        
        Returns:
            'local', 'okta', 'azure_ad', or 'ldap'.
        """
        ...


# ── Provider configuration helper ──────────────────────────────────────────


@dataclass
class AuthProviderConfig:
    """Configuration for an auth provider instance.
    
    Attributes:
        provider_type: 'local', 'okta', 'azure_ad', or 'ldap'.
        jwt_secret: Secret key for JWT signing (local provider).
        jwt_expiry_hours: JWT access token expiry in hours.
        okta_domain: Okta domain (e.g. 'acme.okta.com').
        okta_client_id: Okta SAML client ID.
        okta_client_secret: Okta SAML client secret.
        azure_tenant_id: Azure AD tenant ID.
        azure_client_id: Azure AD application client ID.
        azure_client_secret: Azure AD client secret.
        ldap_server: LDAP server URI.
        ldap_base_dn: LDAP base DN for user search.
        ldap_bind_dn: LDAP bind DN template.
        ldap_group_dn: LDAP group search base DN.
    """
    provider_type: str = "local"
    jwt_secret: str = ""
    jwt_expiry_hours: int = 24
    
    # Okta
    okta_domain: str = ""
    okta_client_id: str = ""
    okta_client_secret: str = ""
    
    # Azure AD
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    
    # LDAP
    ldap_server: str = ""
    ldap_base_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_group_dn: str = ""
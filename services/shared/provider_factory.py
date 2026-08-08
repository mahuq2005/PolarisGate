"""Provider Factory — centralized provider creation from environment variables.

Reads SAFETY_PROVIDER, AUTH_PROVIDER, LLM_PROVIDER, INFRA_PROVIDER from env
and returns the correct implementation. The core gateway calls this factory
and never knows which provider it's using.

Usage::

    from shared.provider_factory import create_safety_provider, create_auth_provider
    safety = create_safety_provider()
    auth = create_auth_provider()
    result = await safety.detect_toxicity("hello world")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from shared.interfaces.safety import SafetyProvider, SafetyProviderConfig
from shared.interfaces.llm import LLMProvider
from shared.interfaces.auth import AuthProvider, AuthProviderConfig
from shared.interfaces.infra import InfraProvider, InfraProviderConfig

logger = logging.getLogger(__name__)

# ── Safety Provider ─────────────────────────────────────────────────────────


def create_safety_provider(config: Optional[SafetyProviderConfig] = None) -> SafetyProvider:
    """Create a safety provider based on environment configuration.

    Reads ``SAFETY_PROVIDER`` environment variable:
        - ``local`` (default) → LocalSafetyProvider (BERT, regex, NLI)
        - ``aws`` → AWSSafetyProvider (Comprehend, Bedrock) — future
        - ``azure`` → AzureSafetyProvider (AI Content Safety) — future
        - ``gcp`` → GCPSafetyProvider (Cloud DLP, Vertex AI) — future

    Args:
        config: Optional SafetyProviderConfig override.

    Returns:
        SafetyProvider implementation.
    """
    provider_type = os.getenv("SAFETY_PROVIDER", "local").lower().strip()

    if config is None:
        config = SafetyProviderConfig(
            provider_type=provider_type,
            region=os.getenv("AWS_REGION", ""),
            endpoint=os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT", ""),
            api_key=os.getenv("AZURE_CONTENT_SAFETY_KEY", ""),
            project_id=os.getenv("GCP_PROJECT_ID", ""),
            models_dir=os.getenv("POLARISGATE_MODELS_DIR", ""),
        )

    if provider_type == "aws":
        # Future: AWSSafetyProvider
        logger.warning("AWS safety provider not yet implemented, falling back to local")
        from shared.providers.local_safety import LocalSafetyProvider
        return LocalSafetyProvider(models_dir=config.models_dir)

    elif provider_type == "azure":
        # Future: AzureSafetyProvider
        logger.warning("Azure safety provider not yet implemented, falling back to local")
        from shared.providers.local_safety import LocalSafetyProvider
        return LocalSafetyProvider(models_dir=config.models_dir)

    elif provider_type == "gcp":
        # Future: GCPSafetyProvider
        logger.warning("GCP safety provider not yet implemented, falling back to local")
        from shared.providers.local_safety import LocalSafetyProvider
        return LocalSafetyProvider(models_dir=config.models_dir)

    else:  # "local" (default)
        from shared.providers.local_safety import LocalSafetyProvider
        logger.info("Using LocalSafetyProvider (BERT + regex + NLI)")
        return LocalSafetyProvider(models_dir=config.models_dir)


# ── Auth Provider ───────────────────────────────────────────────────────────


def create_auth_provider(config: Optional[AuthProviderConfig] = None) -> AuthProvider:
    """Create an auth provider based on environment configuration.

    Reads ``AUTH_PROVIDER`` environment variable:
        - ``local_jwt`` (default) → LocalAuthProvider (JWT + bcrypt)
        - ``okta`` → OktaAuthProvider (SAML 2.0) — future
        - ``azure_ad`` → AzureADAuthProvider (OIDC) — future
        - ``ldap`` → LDAPAuthProvider — future

    Args:
        config: Optional AuthProviderConfig override.

    Returns:
        AuthProvider implementation.
    """
    provider_type = os.getenv("AUTH_PROVIDER", "local_jwt").lower().strip()

    if config is None:
        config = AuthProviderConfig(
            provider_type=provider_type,
            jwt_secret=os.getenv("JWT_SECRET", ""),
            jwt_expiry_hours=int(os.getenv("JWT_EXPIRY_HOURS", "24")),
            okta_domain=os.getenv("OKTA_DOMAIN", ""),
            okta_client_id=os.getenv("OKTA_CLIENT_ID", ""),
            okta_client_secret=os.getenv("OKTA_CLIENT_SECRET", ""),
            azure_tenant_id=os.getenv("AZURE_TENANT_ID", ""),
            azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
            azure_client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
            ldap_server=os.getenv("LDAP_SERVER", ""),
            ldap_base_dn=os.getenv("LDAP_BASE_DN", ""),
            ldap_bind_dn=os.getenv("LDAP_BIND_DN", ""),
            ldap_group_dn=os.getenv("LDAP_GROUP_DN", ""),
        )

    if provider_type == "okta":
        logger.warning("Okta auth provider not yet implemented, falling back to local")
        from shared.providers.local_auth import LocalAuthProvider
        return LocalAuthProvider(jwt_secret=config.jwt_secret, jwt_expiry_hours=config.jwt_expiry_hours)

    elif provider_type == "azure_ad":
        logger.warning("Azure AD auth provider not yet implemented, falling back to local")
        from shared.providers.local_auth import LocalAuthProvider
        return LocalAuthProvider(jwt_secret=config.jwt_secret, jwt_expiry_hours=config.jwt_expiry_hours)

    elif provider_type == "ldap":
        logger.warning("LDAP auth provider not yet implemented, falling back to local")
        from shared.providers.local_auth import LocalAuthProvider
        return LocalAuthProvider(jwt_secret=config.jwt_secret, jwt_expiry_hours=config.jwt_expiry_hours)

    else:  # "local_jwt" (default)
        from shared.providers.local_auth import LocalAuthProvider
        logger.info("Using LocalAuthProvider (JWT + bcrypt)")
        return LocalAuthProvider(jwt_secret=config.jwt_secret, jwt_expiry_hours=config.jwt_expiry_hours)


# ── Infra Provider ──────────────────────────────────────────────────────────


def create_infra_provider(config: Optional[InfraProviderConfig] = None) -> InfraProvider:
    """Create an infrastructure provider based on environment configuration.

    Reads ``INFRA_PROVIDER`` environment variable:
        - ``local`` (default) → LocalInfraProvider (Docker Compose / K8s)
        - ``aws`` → AWSInfraProvider (ECS Fargate) — future
        - ``azure`` → AzureInfraProvider (Container Apps) — future
        - ``gcp`` → GCPInfraProvider (Cloud Run) — future

    Args:
        config: Optional InfraProviderConfig override.

    Returns:
        InfraProvider implementation.
    """
    provider_type = os.getenv("INFRA_PROVIDER", "local").lower().strip()

    if config is None:
        config = InfraProviderConfig(
            provider_type=provider_type,
            docker_compose_path=os.getenv("DOCKER_COMPOSE_PATH", "docker-compose.yml"),
            kubeconfig_path=os.getenv("KUBECONFIG", ""),
            helm_release_name=os.getenv("HELM_RELEASE_NAME", "polarisgate"),
            helm_chart_path=os.getenv("HELM_CHART_PATH", "k8s/helm/polarisgate"),
            aws_region=os.getenv("AWS_REGION", ""),
            aws_ecs_cluster=os.getenv("AWS_ECS_CLUSTER", ""),
            azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
            gcp_project=os.getenv("GCP_PROJECT", ""),
        )

    if provider_type in ("aws", "azure", "gcp"):
        logger.warning(f"{provider_type} infra provider not yet implemented, falling back to local")
        from shared.providers.local_infra import LocalInfraProvider
        return LocalInfraProvider(compose_path=config.docker_compose_path)

    else:  # "local" (default)
        from shared.providers.local_infra import LocalInfraProvider
        logger.info("Using LocalInfraProvider (Docker Compose / K8s)")
        return LocalInfraProvider(compose_path=config.docker_compose_path)


# ── Convenience: Create all providers at once ───────────────────────────────


def create_all_providers() -> dict:
    """Create all providers for the current environment.

    Returns a dict with keys 'safety', 'auth', 'infra'.
    """
    return {
        "safety": create_safety_provider(),
        "auth": create_auth_provider(),
        "infra": create_infra_provider(),
    }
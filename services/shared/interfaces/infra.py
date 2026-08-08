"""Infrastructure Provider Interface — deployment and operations abstraction.

Supports:
    - Docker Compose (local / on-prem)
    - Kubernetes (vanilla, OpenShift, Rancher)
    - AWS ECS Fargate / EKS
    - Azure Container Apps / AKS
    - GCP Cloud Run / GKE
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass
class DeployResult:
    """Result of a deployment operation.
    
    Attributes:
        success: Whether deployment succeeded.
        service_count: Number of services deployed.
        endpoints: Service endpoint URLs.
        errors: List of error messages (if any).
    """
    success: bool
    service_count: int = 0
    endpoints: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class HealthStatus:
    """Health status of the platform.
    
    Attributes:
        status: 'ok', 'degraded', or 'unhealthy'.
        services: Per-service health status.
        uptime_seconds: Platform uptime in seconds.
        version: PolarisGate version string.
    """
    status: str = "ok"
    services: Dict[str, str] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    version: str = ""


# ── Abstract Infra Provider ────────────────────────────────────────────────


class InfraProvider(ABC):
    """Abstract base class for all infrastructure providers.
    
    Every deployment target (Docker Compose, K8s, ECS, Container Apps, Cloud Run)
    provides a concrete implementation of this interface.
    
    Usage::
    
        from shared.provider_factory import create_infra_provider
        infra = create_infra_provider()  # Returns LocalInfraProvider | AWSInfraProvider | ...
        result = await infra.deploy(config)
    """

    @abstractmethod
    async def deploy(self, config: Dict[str, Any]) -> DeployResult:
        """Deploy PolarisGate to the target infrastructure.
        
        Args:
            config: Deployment configuration (from polarisgate.enterprise.yaml).
        
        Returns:
            DeployResult with success flag and endpoint URLs.
        """
        ...

    @abstractmethod
    async def scale(self, service: str, replicas: int) -> bool:
        """Scale a service to the specified number of replicas.
        
        Args:
            service: Service name to scale.
            replicas: Target replica count.
        
        Returns:
            True if scaling succeeded.
        """
        ...

    @abstractmethod
    async def backup(self, destination: str) -> bool:
        """Create a backup of all platform data.
        
        Args:
            destination: Backup destination path / URI.
        
        Returns:
            True if backup succeeded.
        """
        ...

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check the health of all platform services.
        
        Returns:
            HealthStatus with per-service health.
        """
        ...

    @abstractmethod
    def get_infra_type(self) -> str:
        """Return the infrastructure type.
        
        Returns:
            'local', 'k8s', 'aws', 'azure', or 'gcp'.
        """
        ...


# ── Provider configuration helper ──────────────────────────────────────────


@dataclass
class InfraProviderConfig:
    """Configuration for an infrastructure provider.
    
    Attributes:
        provider_type: 'local', 'k8s', 'aws', 'azure', or 'gcp'.
        docker_compose_path: Path to docker-compose.yml.
        kubeconfig_path: Path to kubeconfig file.
        helm_release_name: Helm release name.
        helm_chart_path: Path to Helm chart directory.
        aws_region: AWS region.
        aws_ecs_cluster: ECS cluster name.
        azure_resource_group: Azure resource group.
        gcp_project: GCP project ID.
    """
    provider_type: str = "local"
    docker_compose_path: str = "docker-compose.yml"
    kubeconfig_path: str = ""
    helm_release_name: str = "polarisgate"
    helm_chart_path: str = "k8s/helm/polarisgate"
    aws_region: str = ""
    aws_ecs_cluster: str = ""
    azure_resource_group: str = ""
    gcp_project: str = ""
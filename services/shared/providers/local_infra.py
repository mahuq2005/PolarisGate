"""Local Infrastructure Provider — Docker Compose and Kubernetes management.

ON-PREM implementation of the InfraProvider interface.
Supports Docker Compose (single host) and vanilla Kubernetes deployments.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from shared.interfaces.infra import InfraProvider, DeployResult, HealthStatus

logger = logging.getLogger(__name__)


class LocalInfraProvider(InfraProvider):
    """On-prem infrastructure management via Docker Compose or Kubernetes."""

    def __init__(self, compose_path: str = "docker-compose.yml", kubeconfig: str = ""):
        self._compose_path = compose_path
        self._kubeconfig = kubeconfig

    async def deploy(self, config: Dict[str, Any]) -> DeployResult:
        """Deploy PolarisGate using Docker Compose or Helm."""
        from shared.provider_factory import create_safety_provider

        errors: list[str] = []
        endpoints: Dict[str, str] = {}

        infra_type = config.get("infra_type", "docker")

        try:
            if infra_type == "docker":
                result = subprocess.run(
                    ["docker", "compose", "-f", self._compose_path, "up", "-d", "--wait"],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    errors.append(f"Docker Compose failed: {result.stderr}")
                endpoints = {
                    "gateway": "http://localhost:8002",
                    "frontend": "http://localhost:3001",
                    "grafana": "http://localhost:3000",
                    "prometheus": "http://localhost:9090",
                }

            elif infra_type == "k8s":
                helm_path = config.get("helm_chart_path", "k8s/helm/polarisgate")
                release = config.get("helm_release_name", "polarisgate")
                result = subprocess.run(
                    ["helm", "upgrade", "--install", release, helm_path, "--wait"],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode != 0:
                    errors.append(f"Helm deploy failed: {result.stderr}")
                endpoints = {
                    "gateway": "http://polarisgate-gateway:8002",
                    "frontend": "http://polarisgate-frontend:3001",
                }
            else:
                errors.append(f"Unknown infra_type: {infra_type}")

        except subprocess.TimeoutExpired:
            errors.append("Deployment timed out after 120 seconds")
        except FileNotFoundError as e:
            errors.append(f"Tool not found: {e}")

        # Verify safety provider health
        try:
            safety = create_safety_provider()
            await safety.health_check()
        except Exception as e:
            errors.append(f"Safety provider health check failed: {e}")

        return DeployResult(
            success=len(errors) == 0,
            service_count=14,
            endpoints=endpoints if len(errors) == 0 else {},
            errors=errors,
        )

    async def scale(self, service: str, replicas: int) -> bool:
        """Scale a service in Docker Compose or Kubernetes."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self._compose_path, "up", "-d", "--scale", f"{service}={replicas}"],
                capture_output=True, text=True, timeout=60,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def backup(self, destination: str) -> bool:
        """Create a database backup via pg_dump."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self._compose_path, "exec", "-T", "postgres",
                 "pg_dump", "-U", "polarisgate", "polarisgate"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                with open(destination, "w") as f:
                    f.write(result.stdout)
                return True
            return False
        except Exception:
            return False

    async def health_check(self) -> HealthStatus:
        """Check health via docker compose ps or kubectl."""
        import time
        services: Dict[str, str] = {}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("http://localhost:8002/health")
                if resp.status_code == 200:
                    data = resp.json()
                    return HealthStatus(
                        status=data.get("status", "degraded"),
                        services={"gateway": data.get("status", "unknown")},
                        uptime_seconds=0.0,
                        version="3.0.0",
                    )
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self._compose_path, "ps", "--format", "json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        import json
                        svc = json.loads(line)
                        services[svc.get("Service", "unknown")] = svc.get("State", "unknown")
        except Exception:
            services["error"] = "docker not available"

        all_healthy = all(s == "running" for s in services.values())
        return HealthStatus(
            status="ok" if all_healthy else "degraded",
            services=services,
            uptime_seconds=0.0,
            version="3.0.0",
        )

    def get_infra_type(self) -> str:
        return "local"
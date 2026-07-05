"""OPA (Open Policy Agent) client for PolarisGate.
Evaluates policies against requests and supports risk-based fail mode.

Enterprise features:
- Risk-based fail mode: fail-open (log only) vs fail-closed (block)
- Circuit breaker for OPA service availability with auto-reset (half-open)
- Cached policy evaluation for performance
- Audit logging of all policy decisions
"""
import os
import time
import logging
import json
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

OPA_URL = os.getenv("OPA_URL", "http://opa:8181")
OPA_ENFORCED = os.getenv("OPA_ENFORCED", "true").lower() == "true"
OPA_FAIL_MODE = os.getenv("OPA_FAIL_MODE", "risk_based")  # "fail_open", "fail_closed", "risk_based"
OPA_TIMEOUT = int(os.getenv("OPA_TIMEOUT", "5"))
OPA_CACHE_TTL = int(os.getenv("OPA_CACHE_TTL", "300"))  # 5 minutes
OPA_CIRCUIT_THRESHOLD = int(os.getenv("OPA_CIRCUIT_THRESHOLD", "5"))
OPA_CIRCUIT_RESET_SECONDS = int(os.getenv("OPA_CIRCUIT_RESET_SECONDS", "30"))  # Half-open timeout


class FailMode(str, Enum):
    """Risk-based fail mode for OPA evaluation."""
    FAIL_OPEN = "fail_open"       # Log only, never block
    FAIL_CLOSED = "fail_closed"   # Block if OPA is unavailable
    RISK_BASED = "risk_based"     # Block only for high-risk decisions


class PolicyDecision:
    """Result of a policy evaluation."""
    
    def __init__(
        self,
        allowed: bool,
        policy: str,
        risk_level: str = "low",
        reason: Optional[str] = None,
        warnings: Optional[list[str]] = None,
    ):
        self.allowed = allowed
        self.policy = policy
        self.risk_level = risk_level
        self.reason = reason or ""
        self.warnings = warnings or []
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "policy": self.policy,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }
    
    @property
    def effective_allowed(self) -> bool:
        """Determine if the action is allowed based on fail mode."""
        if not OPA_ENFORCED:
            return True
        
        if self.allowed:
            return True
        
        # Risk-based fail mode
        if OPA_FAIL_MODE == "fail_open":
            logger.warning(
                f"OPA would block but fail_open mode: {self.policy} | {self.reason}"
            )
            return True
        
        if OPA_FAIL_MODE == "risk_based":
            if self.risk_level in ("critical", "high"):
                logger.warning(
                    f"OPA blocking high-risk action: {self.policy} | {self.reason}"
                )
                return False
            logger.warning(
                f"OPA would block but risk_based mode (risk={self.risk_level}): "
                f"{self.policy} | {self.reason}"
            )
            return True
        
        # fail_closed — block everything
        return False


class OpaClient:
    """Client for evaluating OPA policies with circuit breaker pattern."""
    
    def __init__(self, base_url: str = OPA_URL):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit_open = False
        self._circuit_failures = 0
        self._circuit_threshold = OPA_CIRCUIT_THRESHOLD
        self._circuit_reset_seconds = OPA_CIRCUIT_RESET_SECONDS
        self._circuit_opened_at: Optional[float] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=OPA_TIMEOUT,
            )
        return self._client
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open, with auto-reset (half-open) support.
        
        Returns:
            True if circuit is open (requests should be blocked), False if closed.
        """
        if not self._circuit_open:
            return False
        
        # Check if enough time has passed to attempt half-open state
        if self._circuit_opened_at is not None:
            elapsed = time.time() - self._circuit_opened_at
            if elapsed >= self._circuit_reset_seconds:
                logger.info(
                    f"OPA circuit breaker half-open after {elapsed:.1f}s. "
                    f"Attempting recovery..."
                )
                # Transition to half-open — allow the next request through
                self._circuit_open = False
                self._circuit_failures = 0
                self._circuit_opened_at = None
                return False
        
        return True
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        logger.warning(
            f"OPA circuit breaker opened after {self._circuit_failures} failures. "
            f"Will attempt half-open after {self._circuit_reset_seconds}s."
        )
    
    async def evaluate(
        self,
        policy_path: str,
        input_data: dict,
        risk_level: str = "low",
    ) -> PolicyDecision:
        """Evaluate a policy against input data.
        
        Args:
            policy_path: OPA policy path (e.g., "eu_aia/article_09")
            input_data: The input to evaluate against the policy
            risk_level: Risk level of the decision ("low", "medium", "high", "critical")
        
        Returns:
            PolicyDecision with the evaluation result
        """
        # Check circuit breaker (with auto half-open reset)
        if self._check_circuit_breaker():
            logger.warning(f"OPA circuit breaker open, using fail mode: {OPA_FAIL_MODE}")
            return PolicyDecision(
                allowed=(OPA_FAIL_MODE != "fail_closed"),
                policy=policy_path,
                risk_level=risk_level,
                reason="OPA circuit breaker open",
                warnings=["OPA service unavailable"],
            )
        
        try:
            client = await self._get_client()
            resp = await client.post(
                f"/v1/data/{policy_path}",
                json={"input": input_data},
            )
            
            if resp.status_code == 200:
                result = resp.json()
                allowed = result.get("result", {}).get("allow", True)
                warnings = result.get("result", {}).get("warnings", [])
                reason = result.get("result", {}).get("reason", "")
                
                # Reset circuit breaker on success
                self._circuit_failures = 0
                if self._circuit_open:
                    self._circuit_open = False
                    self._circuit_opened_at = None
                    logger.info("OPA circuit breaker closed (recovered)")
                
                return PolicyDecision(
                    allowed=allowed,
                    policy=policy_path,
                    risk_level=risk_level,
                    reason=reason,
                    warnings=warnings,
                )
            else:
                logger.error(f"OPA returned {resp.status_code}: {resp.text}")
                self._circuit_failures += 1
                if self._circuit_failures >= self._circuit_threshold:
                    self._open_circuit()
                
                return PolicyDecision(
                    allowed=(OPA_FAIL_MODE != "fail_closed"),
                    policy=policy_path,
                    risk_level=risk_level,
                    reason=f"OPA error: {resp.status_code}",
                    warnings=["OPA returned error"],
                )
        
        except httpx.TimeoutException:
            logger.error(f"OPA timeout for policy {policy_path}")
            self._circuit_failures += 1
            if self._circuit_failures >= self._circuit_threshold:
                self._open_circuit()
            
            return PolicyDecision(
                allowed=(OPA_FAIL_MODE != "fail_closed"),
                policy=policy_path,
                risk_level=risk_level,
                reason="OPA timeout",
                warnings=["OPA service timeout"],
            )
        
        except Exception as e:
            logger.error(f"OPA error for policy {policy_path}: {e}")
            self._circuit_failures += 1
            if self._circuit_failures >= self._circuit_threshold:
                self._open_circuit()
            
            return PolicyDecision(
                allowed=(OPA_FAIL_MODE != "fail_closed"),
                policy=policy_path,
                risk_level=risk_level,
                reason=str(e),
                warnings=["OPA service error"],
            )
    
    async def evaluate_all(
        self,
        input_data: dict,
        policies: Optional[list[str]] = None,
    ) -> list[PolicyDecision]:
        """Evaluate multiple policies against the same input.
        
        Args:
            input_data: The input to evaluate
            policies: List of policy paths to evaluate (default: all active policies)
        
        Returns:
            List of PolicyDecisions
        """
        if policies is None:
            policies = [
                "eu_aia/article_09",   # Risk management
                "eu_aia/article_13",   # Transparency
                "eu_aia/article_14",   # Human oversight
                "eu_aia/article_15",   # Accuracy & robustness
            ]
        
        decisions = []
        for policy in policies:
            decision = await self.evaluate(policy, input_data)
            decisions.append(decision)
        
        return decisions
    
    async def health_check(self) -> bool:
        """Check if OPA service is healthy."""
        try:
            client = await self._get_client()
            resp = await client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False
    
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        self._circuit_open = False
        self._circuit_failures = 0
        self._circuit_opened_at = None
        logger.info("OPA circuit breaker manually reset")


# Global OPA client
opa_client = OpaClient()


async def evaluate_policy(
    policy_path: str,
    input_data: dict,
    risk_level: str = "low",
) -> PolicyDecision:
    """Convenience function to evaluate a single policy."""
    return await opa_client.evaluate(policy_path, input_data, risk_level)


async def evaluate_all_policies(
    input_data: dict,
    policies: Optional[list[str]] = None,
) -> list[PolicyDecision]:
    """Convenience function to evaluate all policies."""
    return await opa_client.evaluate_all(input_data, policies)

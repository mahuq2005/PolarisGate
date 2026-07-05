"""Inference cost tracking for NorthGuard.
Enterprise-grade: Token counting, inference cost estimation, GPU utilization
monitoring, and carbon footprint tracking.

All metrics are exposed via Prometheus for dashboard visibility.
"""
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Cost per 1K tokens (USD) — approximate rates
COST_PER_1K_TOKENS = {
    "llama3.2:1b": 0.0002,
    "llama3.2:3b": 0.0006,
    "tinyllama": 0.0001,
    "bert": 0.00005,
}

# Carbon intensity (gCO2e per kWh) — default for average grid
DEFAULT_CARBON_INTENSITY = 400  # gCO2e/kWh

# GPU power consumption (watts) by model
GPU_POWER_WATTS = {
    "llama3.2:1b": 50,
    "llama3.2:3b": 75,
    "tinyllama": 30,
    "bert": 20,
}


class CostTracker:
    """Tracks inference costs, token usage, and carbon footprint.

    Thread-safe design with Prometheus metric exposure.
    """

    def __init__(self):
        self._total_tokens: int = 0
        self._total_cost: float = 0.0
        self._total_inference_time: float = 0.0
        self._total_carbon_g: float = 0.0
        self._request_count: int = 0
        self._model_counts: Dict[str, int] = {}
        self._model_costs: Dict[str, float] = {}
        self._start_time: float = time.time()

    @property
    def uptime_hours(self) -> float:
        return (time.time() - self._start_time) / 3600

    def record_inference(
        self,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        inference_time_ms: float = 0.0,
        gpu_utilization: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Record an inference request and compute costs.

        Args:
            model_name: Name of the model used
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            inference_time_ms: Inference time in milliseconds
            gpu_utilization: GPU utilization percentage (0-100)

        Returns:
            Dict with cost breakdown including token counts, cost, carbon,
            and inference time
        """
        total_tokens = prompt_tokens + completion_tokens
        cost_per_1k = COST_PER_1K_TOKENS.get(model_name, 0.0001)
        cost = (total_tokens / 1000) * cost_per_1k

        # Carbon footprint estimation
        power_w = GPU_POWER_WATTS.get(model_name, 30)
        hours = inference_time_ms / (1000 * 3600)
        energy_kwh = power_w * hours / 1000
        carbon_g = energy_kwh * DEFAULT_CARBON_INTENSITY

        # Update totals
        self._total_tokens += total_tokens
        self._total_cost += cost
        self._total_inference_time += inference_time_ms
        self._total_carbon_g += carbon_g
        self._request_count += 1
        self._model_counts[model_name] = self._model_counts.get(model_name, 0) + 1
        self._model_costs[model_name] = self._model_costs.get(model_name, 0.0) + cost

        return {
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
            "carbon_g": round(carbon_g, 6),
            "inference_time_ms": round(inference_time_ms, 2),
            "gpu_utilization": gpu_utilization,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all tracked costs and usage.

        Returns:
            Dict with total cost, token usage, request count, and per-model breakdown
        """
        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 6),
            "total_inference_time_ms": round(self._total_inference_time, 2),
            "total_carbon_g": round(self._total_carbon_g, 4),
            "uptime_hours": round(self.uptime_hours, 2),
            "avg_cost_per_request": round(
                self._total_cost / max(self._request_count, 1), 6
            ),
            "avg_tokens_per_request": round(
                self._total_tokens / max(self._request_count, 1), 1
            ),
            "models": {
                model: {
                    "requests": count,
                    "total_cost": round(self._model_costs.get(model, 0.0), 4),
                }
                for model, count in self._model_counts.items()
            },
        }

    def get_prometheus_metrics(self) -> Dict[str, float]:
        """Get metrics suitable for Prometheus exposition.

        Returns:
            Dict of metric names to values
        """
        return {
            "northguard_inference_total_cost": round(self._total_cost, 6),
            "northguard_inference_total_tokens": self._total_tokens,
            "northguard_inference_total_requests": self._request_count,
            "northguard_inference_total_carbon_g": round(self._total_carbon_g, 4),
            "northguard_inference_avg_cost_per_request": round(
                self._total_cost / max(self._request_count, 1), 8
            ),
        }


# ─── Cost Optimization Tiering ───────────────────────────────────────────────

# Tier definitions with cost limits and model restrictions
COST_TIERS = {
    "free": {
        "max_daily_cost": 0.01,       # $0.01 per day
        "max_monthly_cost": 0.10,     # $0.10 per month
        "allowed_models": ["tinyllama", "bert"],
        "max_tokens_per_request": 500,
        "rate_limit_rpm": 10,         # requests per minute
        "description": "Free tier - basic models only",
    },
    "standard": {
        "max_daily_cost": 0.10,       # $0.10 per day
        "max_monthly_cost": 2.00,     # $2.00 per month
        "allowed_models": ["tinyllama", "bert", "llama3.2:1b"],
        "max_tokens_per_request": 2000,
        "rate_limit_rpm": 60,
        "description": "Standard tier - small models",
    },
    "premium": {
        "max_daily_cost": 1.00,       # $1.00 per day
        "max_monthly_cost": 20.00,    # $20.00 per month
        "allowed_models": ["llama3.2:1b", "llama3.2:3b", "tinyllama", "bert"],
        "max_tokens_per_request": 8000,
        "rate_limit_rpm": 300,
        "description": "Premium tier - all models",
    },
    "enterprise": {
        "max_daily_cost": float("inf"),
        "max_monthly_cost": float("inf"),
        "allowed_models": None,       # All models allowed
        "max_tokens_per_request": 32000,
        "rate_limit_rpm": 1000,
        "description": "Enterprise tier - unlimited",
    },
}

DEFAULT_TIER = "standard"


class CostOptimizer:
    """Cost optimization manager with tier-based controls.

    Enforces per-tier cost limits, model restrictions, and rate limiting.
    Integrates with CostTracker for real-time cost monitoring.
    """

    def __init__(self, tracker: Optional[CostTracker] = None):
        self._tracker = tracker or get_cost_tracker()
        self._user_tiers: Dict[str, str] = {}
        self._daily_spend: Dict[str, float] = {}
        self._monthly_spend: Dict[str, float] = {}
        self._request_counts: Dict[str, List[float]] = {}
        self._last_reset_day: Optional[str] = None
        self._last_reset_month: Optional[str] = None

    def set_user_tier(self, user_id: str, tier: str) -> None:
        """Set the cost tier for a user.

        Args:
            user_id: Unique user identifier
            tier: Tier name ('free', 'standard', 'premium', 'enterprise')

        Raises:
            ValueError: If tier is invalid
        """
        if tier not in COST_TIERS:
            raise ValueError(f"Invalid tier: {tier}. Valid tiers: {list(COST_TIERS.keys())}")
        self._user_tiers[user_id] = tier
        self._reset_if_needed()

    def get_user_tier(self, user_id: str) -> str:
        """Get the cost tier for a user.

        Args:
            user_id: Unique user identifier

        Returns:
            Tier name (defaults to DEFAULT_TIER)
        """
        return self._user_tiers.get(user_id, DEFAULT_TIER)

    def can_use_model(self, user_id: str, model_name: str) -> bool:
        """Check if a user can use a specific model based on their tier.

        Args:
            user_id: Unique user identifier
            model_name: Name of the model

        Returns:
            True if the model is allowed for the user's tier
        """
        tier = self.get_user_tier(user_id)
        config = COST_TIERS[tier]
        if config["allowed_models"] is None:
            return True  # Enterprise: all models allowed
        return model_name in config["allowed_models"]

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if a user has exceeded their rate limit.

        Args:
            user_id: Unique user identifier

        Returns:
            True if request is allowed, False if rate limited
        """
        tier = self.get_user_tier(user_id)
        rpm = COST_TIERS[tier]["rate_limit_rpm"]
        now = time.time()

        if user_id not in self._request_counts:
            self._request_counts[user_id] = []

        # Remove requests older than 1 minute
        self._request_counts[user_id] = [
            t for t in self._request_counts[user_id]
            if now - t < 60
        ]

        if len(self._request_counts[user_id]) >= rpm:
            return False

        self._request_counts[user_id].append(now)
        return True

    def check_daily_budget(self, user_id: str, estimated_cost: float = 0.0) -> bool:
        """Check if a user has exceeded their daily budget.

        Args:
            user_id: Unique user identifier
            estimated_cost: Estimated cost of the new request

        Returns:
            True if within budget, False if exceeded
        """
        self._reset_if_needed()
        tier = self.get_user_tier(user_id)
        max_daily = COST_TIERS[tier]["max_daily_cost"]
        current = self._daily_spend.get(user_id, 0.0)
        return (current + estimated_cost) <= max_daily

    def check_monthly_budget(self, user_id: str, estimated_cost: float = 0.0) -> bool:
        """Check if a user has exceeded their monthly budget.

        Args:
            user_id: Unique user identifier
            estimated_cost: Estimated cost of the new request

        Returns:
            True if within budget, False if exceeded
        """
        self._reset_if_needed()
        tier = self.get_user_tier(user_id)
        max_monthly = COST_TIERS[tier]["max_monthly_cost"]
        current = self._monthly_spend.get(user_id, 0.0)
        return (current + estimated_cost) <= max_monthly

    def record_spend(self, user_id: str, cost: float) -> None:
        """Record a cost against a user's budget.

        Args:
            user_id: Unique user identifier
            cost: Cost in USD
        """
        self._reset_if_needed()
        self._daily_spend[user_id] = self._daily_spend.get(user_id, 0.0) + cost
        self._monthly_spend[user_id] = self._monthly_spend.get(user_id, 0.0) + cost

    def _reset_if_needed(self) -> None:
        """Reset daily/monthly counters if a new day/month has started."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        this_month = datetime.now(timezone.utc).strftime("%Y-%m")

        if today != self._last_reset_day:
            self._daily_spend.clear()
            self._last_reset_day = today

        if this_month != self._last_reset_month:
            self._monthly_spend.clear()
            self._last_reset_month = this_month

    def get_tier_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a summary of the user's tier status and spending.

        Args:
            user_id: Unique user identifier

        Returns:
            Dict with tier info, current spend, and limits
        """
        tier = self.get_user_tier(user_id)
        config = COST_TIERS[tier]
        return {
            "user_id": user_id,
            "tier": tier,
            "tier_description": config["description"],
            "daily_spend": round(self._daily_spend.get(user_id, 0.0), 6),
            "daily_limit": config["max_daily_cost"],
            "monthly_spend": round(self._monthly_spend.get(user_id, 0.0), 6),
            "monthly_limit": config["max_monthly_cost"],
            "allowed_models": config["allowed_models"],
            "rate_limit_rpm": config["rate_limit_rpm"],
        }

    def recommend_model(self, user_id: str, required_quality: str = "standard") -> str:
        """Recommend the most cost-effective model for a user.

        Args:
            user_id: Unique user identifier
            required_quality: 'basic', 'standard', or 'high'

        Returns:
            Recommended model name
        """
        tier = self.get_user_tier(user_id)
        config = COST_TIERS[tier]
        allowed = config["allowed_models"]

        if allowed is None:
            allowed = list(COST_PER_1K_TOKENS.keys())

        if required_quality == "basic":
            # Cheapest available
            return min(allowed, key=lambda m: COST_PER_1K_TOKENS.get(m, 0.0001))
        elif required_quality == "high":
            # Most capable (most expensive) available
            return max(allowed, key=lambda m: COST_PER_1K_TOKENS.get(m, 0.0001))
        else:
            # Mid-range
            sorted_models = sorted(allowed, key=lambda m: COST_PER_1K_TOKENS.get(m, 0.0001))
            return sorted_models[len(sorted_models) // 2]


# Module-level singletons
_tracker: Optional[CostTracker] = None
_optimizer: Optional[CostOptimizer] = None


def get_cost_tracker() -> CostTracker:
    """Get or create the global CostTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


def get_cost_optimizer() -> CostOptimizer:
    """Get or create the global CostOptimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = CostOptimizer()
    return _optimizer


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a rough approximation: ~4 characters per token for English text.

    Args:
        text: Input text string

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Rough approximation: ~4 chars per token
    return max(1, len(text) // 4)

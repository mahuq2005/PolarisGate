"""Policy Engine — evaluates tool calls against deny list, role, and user overrides."""
from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
import yaml
import os

logger = logging.getLogger(__name__)

_POLICIES: Optional[Dict[str, Any]] = None


def _load_policies() -> Dict[str, Any]:
    global _POLICIES
    if _POLICIES is not None:
        return _POLICIES
    path = os.path.join(os.path.dirname(__file__), "..", "..", "policies", "tool_access_policies.yaml")
    try:
        with open(path) as f:
            _POLICIES = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load tool access policies: %s", e)
        _POLICIES = {"global_deny_list": {"categories": [], "custom_rules": []}, "roles": {}, "users": {}, "contexts": {}}
    return _POLICIES


def evaluate_tool_call(
    user_email: str,
    user_role: str,
    context: str,
    tool_name: str,
    target_resource: str = "",
) -> Dict[str, Any]:
    """Evaluate whether a tool call should be allowed, blocked, or require approval.

    Evaluation order (first match wins):
    1. Global Deny List — pattern match → BLOCK
    2. Context Restrictions — exceeds limits? → BLOCK
    3. User-Specific Overrides — explicit allow or deny
    4. Role-Based Policy — inherited permissions
    5. Default — BLOCK (least privilege)

    Returns: {"effect": "allow"|"deny"|"require_approval", "reason": "...", "layer": "..."}
    """
    policies = _load_policies()

    # 1. Global Deny List (supports both flat list and category-based format)
    deny_config = policies.get("global_deny_list", [])
    
    # Handle category-based format (new)
    if isinstance(deny_config, dict):
        categories = deny_config.get("categories", [])
        for cat in categories:
            if not cat.get("enabled", True):
                continue
            pattern = cat.get("patterns", "")
            if pattern and re.search(pattern, tool_name, re.IGNORECASE):
                return {
                    "effect": "deny",
                    "reason": cat.get("description", f"Tool matches deny category: {cat.get('name', '')}"),
                    "layer": "deny_list",
                    "risk": cat.get("risk", "HIGH"),
                    "category": cat.get("name", ""),
                }
        # Handle custom rules
        custom_rules = deny_config.get("custom_rules", [])
        for rule in custom_rules:
            pattern = rule.get("pattern", "")
            if pattern and re.search(pattern, tool_name, re.IGNORECASE):
                return {
                    "effect": "deny",
                    "reason": rule.get("description", f"Tool matches custom deny rule: {pattern}"),
                    "layer": "deny_list",
                    "risk": rule.get("risk", "HIGH"),
                    "category": "Custom Rule",
                }
    # Handle flat list format (legacy)
    else:
        for entry in deny_config:
            pattern = entry.get("pattern", "")
            if pattern and re.search(pattern, tool_name, re.IGNORECASE):
                return {
                    "effect": "deny",
                    "reason": entry.get("reason", f"Tool matches global deny pattern: {pattern}"),
                    "layer": "deny_list",
                    "risk": entry.get("risk", "HIGH"),
                }

    # 2. Context Restrictions
    contexts = policies.get("contexts", {})
    ctx_rules = contexts.get(context, {})
    max_tools = ctx_rules.get("max_tools_per_response", 999)
    require_confirm = ctx_rules.get("require_confirmation_for", [])
    for pattern in require_confirm:
        if re.search(pattern, tool_name, re.IGNORECASE):
            return {
                "effect": "require_approval",
                "reason": f"Tool requires confirmation in {context} context",
                "layer": "context",
            }

    # 3. User-Specific Overrides
    users = policies.get("users", {})
    user_overrides = users.get(user_email, {}).get("overrides", [])
    for override in user_overrides:
        tool_pat = override.get("tool", "")
        target_pat = override.get("target", "")
        if re.search(tool_pat, tool_name, re.IGNORECASE):
            if target_pat and not re.search(target_pat, target_resource, re.IGNORECASE):
                continue  # Target doesn't match
            permission = override.get("permission", "allow")
            return {
                "effect": permission,
                "reason": override.get("reason", f"User override: {permission}"),
                "layer": "user",
            }

    # 4. Role-Based Policy
    user_role_config = users.get(user_email, {}).get("role") or user_role
    roles_config = policies.get("roles", {})
    role_policy = roles_config.get(user_role_config) or roles_config.get("intern")

    # Check explicit role allows
    for allow_pat in role_policy.get("tools_allow", []):
        if re.search(allow_pat, tool_name, re.IGNORECASE):
            return {"effect": "allow", "reason": f"Role policy allows (role: {user_role_config})", "layer": "role"}

    # Check inherited role
    inherits = role_policy.get("inherits")
    if inherits:
        parent_role = roles_config.get(inherits, {})
        for allow_pat in parent_role.get("tools_allow", []):
            if re.search(allow_pat, tool_name, re.IGNORECASE):
                return {"effect": "allow", "reason": f"Inherited from role: {inherits}", "layer": "role"}

    # Check explicit role denies
    for deny_pat in role_policy.get("tools_deny", []):
        if re.search(deny_pat, tool_name, re.IGNORECASE):
            return {"effect": "deny", "reason": f"Role policy denies (role: {user_role_config})", "layer": "role"}

    # Check require_approval_for
    for approve_pat in role_policy.get("require_approval_for", []):
        if re.search(approve_pat, tool_name, re.IGNORECASE):
            return {
                "effect": "require_approval",
                "reason": f"Role {user_role_config} requires approval for {tool_name}",
                "layer": "role",
            }

    # 5. Default — BLOCK
    return {
        "effect": "deny",
        "reason": "No policy allows this tool call (least privilege default)",
        "layer": "default",
    }


def get_all_policies() -> Dict[str, Any]:
    """Return all loaded policies for the API."""
    return _load_policies()


def get_user_effective_policy(user_email: str, user_role: str) -> Dict[str, Any]:
    """Get computed effective policy for a user."""
    policies = _load_policies()
    roles_config = policies.get("roles", {})
    role_policy = roles_config.get(user_role, roles_config.get("intern", {}))

    allows = list(role_policy.get("tools_allow", []))
    inherits = role_policy.get("inherits")
    if inherits:
        parent = roles_config.get(inherits, {})
        allows.extend(parent.get("tools_allow", []))

    return {
        "user_email": user_email,
        "role": user_role,
        "inherits": inherits,
        "allows": allows,
        "denies": list(role_policy.get("tools_deny", [])),
        "require_approval_for": list(role_policy.get("require_approval_for", [])),
        "scope": role_policy.get("scope", "internal_only"),
        "user_overrides": policies.get("users", {}).get(user_email, {}).get("overrides", []),
    }
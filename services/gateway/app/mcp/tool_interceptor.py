"""Tool Interceptor — inspects tool_calls from LLM responses and enforces policies."""
from __future__ import annotations
import re
import json
import logging
from typing import Dict, Any, Optional
from .policy_engine import evaluate_tool_call

logger = logging.getLogger(__name__)


async def intercept_tool_call(
    user_email: str,
    user_role: str,
    context: str,
    tool_call: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate a single tool call against the access policy.

    Args:
        user_email: Authenticated user's email
        user_role: User's role (intern, senior_developer, admin, auditor)
        context: Usage context (chat_ui, api_key, hosted_agent)
        tool_call: The tool_call dict from LLM response {id, type, function: {name, arguments}}

    Returns:
        Dict with evaluation result: {allowed, reason, tool_name, ...}
    """
    func = tool_call.get("function", {})
    tool_name = func.get("name", "unknown")
    arguments = func.get("arguments", "{}")

    # Parse arguments to inspect target
    target = ""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        # Extract common target patterns
        target = args.get("path") or args.get("url") or args.get("to") or args.get("command") or ""
    except (json.JSONDecodeError, TypeError):
        target = str(arguments)[:200]

    result = evaluate_tool_call(user_email, user_role, context, tool_name, target)

    # Log the decision
    logger.info(
        "Tool call: user=%s role=%s tool=%s target=%s → %s (%s)",
        user_email, user_role, tool_name, target[:100],
        result["effect"], result["layer"],
    )

    return {
        "allowed": result["effect"] == "allow",
        "requires_approval": result["effect"] == "require_approval",
        "blocked": result["effect"] == "deny",
        "tool_name": tool_name,
        "target": target[:200],
        "reason": result["reason"],
        "policy_layer": result["layer"],
        "risk": result.get("risk", "NONE"),
    }


async def intercept_tool_calls(
    user_email: str,
    user_role: str,
    context: str,
    tool_calls: list,
) -> list:
    """Evaluate all tool calls from an LLM response.

    Returns filtered list: only allowed tool calls, with blocked ones replaced by error responses.
    """
    allowed = []
    blocked = []
    approval_needed = []

    for tc in tool_calls:
        result = await intercept_tool_call(user_email, user_role, context, tc)
        if result["allowed"]:
            allowed.append(tc)
        elif result["requires_approval"]:
            approval_needed.append({"tool_call": tc, "evaluation": result})
        else:
            blocked.append({"tool_call": tc, "evaluation": result})

    return {
        "allowed_tool_calls": allowed,
        "blocked_tool_calls": blocked,
        "approval_required": approval_needed,
        "total": len(tool_calls),
        "allowed": len(allowed),
        "blocked": len(blocked),
        "pending_approval": len(approval_needed),
    }
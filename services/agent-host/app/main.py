"""Agent Lifecycle API — create, start, stop, delete agents."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from shared.security.auth import get_current_user
from shared.feature_flags import is_enabled, FeatureFlag
from .connectors import get_agent_registry

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])
_registry = get_agent_registry()


@router.get("")
async def list_agents(current_user: dict = Depends(get_current_user)):
    if not is_enabled(FeatureFlag.AGENT_HOSTING):
        return {"agents": [], "status": "disabled"}
    return {"agents": _registry.list_all()}


@router.post("")
async def create_agent(body: dict, current_user: dict = Depends(get_current_user)):
    if not is_enabled(FeatureFlag.AGENT_HOSTING):
        raise HTTPException(400, "Agent hosting is disabled")
    return _registry.create(
        name=body.get("name", "Untitled"),
        framework=body.get("framework", "langchain"),
        provider=body.get("provider", "openai"),
        model=body.get("model", "gpt-4o"),
        system_prompt=body.get("system_prompt", ""),
        safety_enabled=body.get("safety_enabled", True),
    )


@router.post("/{agent_id}/start")
async def start_agent(agent_id: int, current_user: dict = Depends(get_current_user)):
    if not _registry.start(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"status": "started", "id": agent_id}


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: int, current_user: dict = Depends(get_current_user)):
    if not _registry.stop(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"status": "stopped", "id": agent_id}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, current_user: dict = Depends(get_current_user)):
    if not _registry.delete(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"status": "deleted", "id": agent_id}


@router.post("/mcp")
async def register_mcp(body: dict, current_user: dict = Depends(get_current_user)):
    return _registry.register_mcp(
        name=body.get("name", ""),
        endpoint=body.get("endpoint", ""),
        auth_token=body.get("auth_token", ""),
    )


@router.get("/mcp")
async def list_mcp(current_user: dict = Depends(get_current_user)):
    return {"mcp_servers": _registry.list_mcp()}


@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    if not is_enabled(FeatureFlag.AGENT_HOSTING):
        return {"status": "disabled"}
    agents = _registry.list_all()
    return {"status": "active", "agents_running": sum(1 for a in agents if a["status"] == "running"), "mcp_servers": len(_registry.list_mcp())}

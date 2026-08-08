"""Agent Host Connectors — LangChain and CrewAI adapter stubs."""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class LangChainConnector:
    def __init__(self, name: str, provider: str, model: str, system_prompt: str = "", safety_enabled: bool = True):
        self.name = name
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.safety_enabled = safety_enabled
        self.running = False

    async def start(self) -> bool:
        self.running = True
        return True

    async def stop(self) -> bool:
        self.running = False
        return True

    def status(self) -> str:
        return "running" if self.running else "stopped"


class CrewAIAdapter:
    def __init__(self, name: str, crew_config: dict = None):
        self.name = name
        self.config = crew_config or {}
        self.running = False

    async def start(self) -> bool:
        self.running = True
        return True

    async def stop(self) -> bool:
        self.running = False
        return True

    def status(self) -> str:
        return "running" if self.running else "stopped"


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._mcp_servers: List[Dict] = []
        self._next_id = 1

    def create(self, name: str, framework: str, provider: str, model: str, system_prompt: str = "", safety_enabled: bool = True) -> dict:
        if framework == "crewai":
            agent = CrewAIAdapter(name)
        else:
            agent = LangChainConnector(name, provider, model, system_prompt, safety_enabled)
        agent_id = self._next_id
        self._next_id += 1
        self._agents[agent_id] = agent
        return {"id": agent_id, "name": name, "framework": framework, "status": agent.status()}

    def get(self, agent_id: int) -> Optional[Any]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[dict]:
        return [{"id": aid, "name": a.name, "framework": type(a).__name__.replace("Connector", "").replace("Adapter", "").lower(),
                 "status": a.status()} for aid, a in self._agents.items()]

    def delete(self, agent_id: int) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def start(self, agent_id: int) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        import asyncio
        asyncio.create_task(agent.start())
        return True

    def stop(self, agent_id: int) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        import asyncio
        asyncio.create_task(agent.stop())
        return True

    def register_mcp(self, name: str, endpoint: str, auth_token: str = "") -> dict:
        srv = {"id": len(self._mcp_servers) + 1, "name": name, "endpoint": endpoint, "auth_token": auth_token}
        self._mcp_servers.append(srv)
        return srv

    def list_mcp(self) -> List[dict]:
        return self._mcp_servers


_registry = AgentRegistry()

def get_agent_registry() -> AgentRegistry:
    return _registry

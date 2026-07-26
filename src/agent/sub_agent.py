#!/usr/bin/env python3
"""Gestionnaire de sous-agents avec APIs dediees."""
import json, uuid, threading, time
from typing import Optional, Dict, List
from .core import NemesisAgent
from src.providers import PROVIDER_REGISTRY
from src.tools.definitions import get_tool_definitions
from src.tools.executor import ToolExecutor
from src.prompts import get_sub_agent_prompt


class SubAgent:
    def __init__(self, agent_id, task, role, provider, tool_defs, tool_exec, timeout=300):
        self.id = agent_id
        self.task = task
        self.role = role
        self.status = "PENDING"
        self.result = None
        self.error = None
        self.provider = provider
        self.timeout = timeout
        self.agent = NemesisAgent(provider, get_sub_agent_prompt(), tool_defs, tool_exec)
        self._thread = None

    def run(self):
        self.status = "RUNNING"
        try:
            result = self.agent.chat(self.task)
            self.result = result
            self.status = "SUCCESS"
        except Exception as e:
            self.error = str(e)
            self.status = "FAILED"

    def start(self):
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def cancel(self):
        self.status = "CANCELLED"


class SubAgentManager:
    def __init__(self, workspace: str = "./workspace", debug: bool = False):
        self.sub_agents: Dict[str, SubAgent] = {}
        self.workspace = workspace
        self.debug = debug
        self.available_apis: List[dict] = []
        self.default_provider = None
        self.default_tool_defs = get_tool_definitions()
        self.default_tool_exec = ToolExecutor(workspace=workspace)

    def configure_api(self, name: str, provider_type: str, api_key: str,
                      base_url: str = "", model: str = "") -> bool:
        self.available_apis.append({
            "name": name, "provider": provider_type,
            "api_key": api_key, "base_url": base_url, "model": model
        })
        return True

    def set_default_provider(self, provider):
        self.default_provider = provider

    def set_default_tools(self, tool_defs, tool_exec):
        self.default_tool_defs = tool_defs or get_tool_definitions()
        if tool_exec:
            self.default_tool_exec = tool_exec

    def spawn(self, task: str, role: str = "coder", api_name: str = None) -> str:
        agent_id = str(uuid.uuid4())[:8]
        provider = self._get_provider(api_name)
        if not provider:
            agent_id = "error_" + agent_id
            sub = SubAgent(agent_id, task, role, None, [], None, timeout=5)
            self.sub_agents[agent_id] = sub
            sub.status = "FAILED"
            sub.error = "Provider non configure pour le sous-agent"
            return agent_id
        tool_defs = self.default_tool_defs
        tool_exec = self.default_tool_exec
        sub = SubAgent(agent_id, task, role, provider, tool_defs, tool_exec, timeout=300)
        self.sub_agents[agent_id] = sub
        sub.start()
        return agent_id

    def get_status(self, agent_id: str) -> dict:
        sub = self.sub_agents.get(agent_id)
        if not sub:
            return {"error": "Agent non trouve"}
        return {"id": sub.id, "task": sub.task, "role": sub.role, "status": sub.status}

    def get_result(self, agent_id: str) -> dict:
        sub = self.sub_agents.get(agent_id)
        if not sub:
            return {"error": "Agent non trouve"}
        return {"id": sub.id, "status": sub.status, "result": sub.result, "error": sub.error}

    def list_agents(self) -> list:
        return [
            {"id": s.id, "role": s.role, "status": s.status, "task": s.task[:80]}
            for s in self.sub_agents.values()
        ]

    def cancel(self, agent_id: str) -> bool:
        sub = self.sub_agents.get(agent_id)
        if sub:
            sub.cancel()
            return True
        return False

    def cleanup(self):
        done = [
            k for k, v in self.sub_agents.items()
            if v.status in ("SUCCESS", "FAILED", "CANCELLED")
        ]
        for k in done:
            del self.sub_agents[k]

    def _get_provider(self, api_name: str = None):
        if api_name and self.available_apis:
            for api in self.available_apis:
                if api["name"] == api_name:
                    cls = PROVIDER_REGISTRY.get(api["provider"])
                    if cls:
                        return cls(
                            api_key=api["api_key"],
                            base_url=api.get("base_url", ""),
                            model=api.get("model", ""),
                        )
        return self.default_provider

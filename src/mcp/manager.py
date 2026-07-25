#!/usr/bin/env python3
"""Gestionnaire de serveurs MCP."""
from typing import Dict, Any, List
from .client import MCPClient


class MCPManager:
    def __init__(self):
        self.servers: Dict[str, MCPClient] = {}
        self._tool_map: Dict[str, tuple] = {}

    def add_server(self, name: str, command: str, args: list = None, env: dict = None) -> bool:
        try:
            client = MCPClient(command, args or [], env)
            client.initialize()
            self.servers[name] = client
            self._rebuild_tool_map()
            return True
        except Exception:
            return False

    def remove_server(self, name: str) -> bool:
        if name in self.servers:
            self.servers[name].close()
            del self.servers[name]
            self._rebuild_tool_map()
            return True
        return False

    def list_servers(self) -> list:
        return list(self.servers.keys())

    def get_all_tools(self) -> list:
        self._rebuild_tool_map()
        tools = []
        for prefixed, (srv, orig) in self._tool_map.items():
            client = self.servers.get(srv)
            if not client:
                continue
            for t in client.list_tools():
                if t.get("name") == orig:
                    tool = {
                        "type": "function",
                        "function": {
                            "name": f"mcp__{orig}",
                            "description": f"[MCP:{srv}] {t.get('description', '')}",
                            "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                        }
                    }
                    tools.append(tool)
                    break
        return tools

    def call_tool(self, prefixed_name: str, arguments: dict) -> dict:
        real_name = prefixed_name.replace("mcp__", "", 1)
        for srv_name, client in self.servers.items():
            for t in client.list_tools():
                if t.get("name") == real_name:
                    return client.call_tool(real_name, arguments)
        return {"content": [{"type": "text", "text": f"Outil MCP non trouvé: {real_name}"}], "isError": True}

    def _rebuild_tool_map(self):
        self._tool_map = {}
        for srv_name, client in self.servers.items():
            try:
                for t in client.list_tools():
                    name = t.get("name", "")
                    if name:
                        self._tool_map[f"{srv_name}__{name}"] = (srv_name, name)
            except Exception:
                pass

    def close_all(self):
        for c in self.servers.values():
            c.close()
        self.servers.clear()

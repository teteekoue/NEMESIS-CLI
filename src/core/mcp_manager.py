import subprocess
import sys
import json
import yaml
from pathlib import Path

class MCPManager:
    def __init__(self, config_file="mcp_config.yaml"):
        self.config_file = Path(config_file)
        self.servers = self._load_config()

    def _load_config(self):
        if not self.config_file.exists():
            return {}
        with open(self.config_file, "r") as f:
            return yaml.safe_load(f) or {}

    def _save_config(self):
        with open(self.config_file, "w") as f:
            yaml.dump(self.servers, f)

    def add_server(self, name, command):
        """Ajoute et enregistre un serveur MCP."""
        self.servers[name] = {"command": command}
        self._save_config()
        return True, f"Serveur MCP '{name}' ajouté."

    def remove_server(self, name):
        """Supprime un serveur MCP enregistré."""
        if name in self.servers:
            del self.servers[name]
            self._save_config()
            return True, f"Serveur MCP '{name}' supprimé."
        return False, f"Serveur '{name}' non trouvé."

    def list_servers(self):
        return self.servers

    def get_client(self, name):
        """Retourne un client configuré pour le serveur avec ses variables d'environnement."""
        if name not in self.servers:
            return None
        from src.core.mcp_client import SimpleMCPClient
        server_cfg = self.servers[name]
        cmd = server_cfg["command"].split()
        env = server_cfg.get("env", {})
        return SimpleMCPClient(cmd[0], cmd[1:], env=env)

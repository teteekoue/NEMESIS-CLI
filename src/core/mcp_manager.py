import subprocess
import sys
from pathlib import Path
from rich.console import Console

console = Console()

class MCPManager:
    # Registre des connecteurs pré-configurés
    CONNECTORS = {
        "colab": {
            "name": "Google Colab",
            "cmd": [sys.executable, "-c", "print('Colab MCP: Not implemented locally')"],
            "desc": "Accès aux notebooks et GPU Colab"
        },
        "filesystem": {
            "name": "Local Filesystem",
            "cmd": [sys.executable, "src/core/mcp_server.py"],
            "desc": "Accès sécurisé au dossier ./workspace"
        }
    }

    def __init__(self):
        self.active_servers = {} # name -> process

    def list_connectors(self):
        return self.CONNECTORS

    def start_connector(self, key):
        """Lance un connecteur pré-configuré."""
        if key not in self.CONNECTORS:
            return False, "Connecteur inconnu"
            
        config = self.CONNECTORS[key]
        try:
            # Lancement du processus
            proc = subprocess.Popen(
                config["cmd"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.active_servers[key] = proc
            return True, f"Serveur '{config['name']}' lancé (PID: {proc.pid})"
        except Exception as e:
            return False, str(e)

    def stop_server(self, key):
        if key in self.active_servers:
            self.active_servers[key].terminate()
            del self.active_servers[key]
            return True
        return False

    def list_active(self):
        return list(self.active_servers.keys())

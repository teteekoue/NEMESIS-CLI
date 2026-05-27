import subprocess
import json
import uuid
import threading
import queue
from typing import Dict, Any, Optional

class SimpleMCPClient:
    """Client MCP léger sans dépendances lourdes, utilise stdio."""
    
    def __init__(self, command: str, args: List[str]):
        self.process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.response_queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._read_output, daemon=True)
        self.thread.start()

    def _read_output(self):
        while self.running:
            line = self.process.stdout.readline()
            if not line: break
            try:
                data = json.loads(line)
                self.response_queue.put(data)
            except json.JSONDecodeError:
                pass

    def send_request(self, method: str, params: Dict[str, Any] = None):
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Attente bloquante simple pour la réponse
        return self.response_queue.get(timeout=10)

    def list_tools(self):
        return self.send_request("tools/list")

    def call_tool(self, name: str, arguments: Dict[str, Any]):
        return self.send_request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.running = False
        self.process.terminate()

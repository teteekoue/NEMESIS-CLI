#!/usr/bin/env python3
"""Client MCP (Model Context Protocol) via stdio JSON-RPC."""
import json, uuid, threading, queue, subprocess, os
from typing import Dict, Any, Optional, List


class MCPClient:
    def __init__(self, command: str, args: list, env: dict = None, timeout: int = 30):
        full_env = os.environ.copy()
        if env: full_env.update(env)
        self.process = subprocess.Popen(
            [command] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=full_env
        )
        self._queue = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self.timeout = timeout

    def _read_loop(self):
        while self._running:
            line = self.process.stdout.readline()
            if not line: break
            try:
                data = json.loads(line)
                self._queue.put(data)
            except: pass

    def _send(self, method: str, params: dict = None) -> dict:
        req = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}
        self.process.stdin.write(json.dumps(req) + "
")
        self.process.stdin.flush()
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                msg = self._queue.get(timeout=2)
                if msg.get("id") == req["id"]: return msg
            except queue.Empty: pass
        return {"error": "Timeout MCP"}

    def initialize(self) -> dict:
        r = self._send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                            "clientInfo": {"name": "nemesis-cli", "version": "3.0.0"}})
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "
")
        self.process.stdin.flush()
        return r

    def list_tools(self) -> list:
        r = self._send("tools/list")
        if "result" in r and "tools" in r["result"]: return r["result"]["tools"]
        return []

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self._send("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self._running = False
        try: self.process.terminate()
        except: pass
        try: self._thread.join(timeout=5)
        except: pass

import time

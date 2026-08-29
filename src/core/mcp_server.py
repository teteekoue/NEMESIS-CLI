#!/usr/bin/env python3
"""Minimal example MCP server (newline JSON-RPC). Prefer mcp_calculator.py for real use."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional


def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")
    if req_id is None and method and str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "nemesis-example", "version": "1.0.0"},
            },
        )
    if method == "tools/list":
        return _ok(
            req_id,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo back a message",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                        },
                    }
                ]
            },
        )
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "echo":
            msg = args.get("message", "")
            return _ok(req_id, {"content": [{"type": "text", "text": str(msg)}]})
        return _err(req_id, -32602, f"Unknown tool: {name}")
    return _err(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(req, dict):
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

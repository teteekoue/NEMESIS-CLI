#!/usr/bin/env python3
"""Minimal MCP calculator server (newline-delimited JSON-RPC over stdio)."""

from __future__ import annotations

import json
import math
import sys
from typing import Any, Dict, Optional


TOOLS = [
    {
        "name": "calculate",
        "description": "Perform a basic math operation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "add | subtract | multiply | divide | power | sqrt",
                    "enum": ["add", "subtract", "multiply", "divide", "power", "sqrt"],
                },
                "a": {"type": "number", "description": "First operand"},
                "b": {
                    "type": "number",
                    "description": "Second operand (not required for sqrt)",
                },
            },
            "required": ["operation", "a"],
        },
    }
]


def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _calculate(args: Dict[str, Any]) -> Dict[str, Any]:
    op = str(args.get("operation", "")).strip().lower()
    try:
        a = float(args.get("a", 0))
    except (TypeError, ValueError):
        return {"error": "Invalid number for 'a'"}
    try:
        b = float(args.get("b", 0)) if "b" in args and args.get("b") is not None else 0.0
    except (TypeError, ValueError):
        return {"error": "Invalid number for 'b'"}

    try:
        if op == "add":
            result = a + b
        elif op == "subtract":
            result = a - b
        elif op == "multiply":
            result = a * b
        elif op == "divide":
            if b == 0:
                return {"error": "Division by zero"}
            result = a / b
        elif op == "power":
            result = a ** b
        elif op == "sqrt":
            if a < 0:
                return {"error": "Square root of negative number"}
            result = math.sqrt(a)
        else:
            return {"error": f"Unknown operation: {op}"}
    except Exception as e:
        return {"error": str(e)}

    text = f"Result of {op}({a}" + (f", {b}" if op != "sqrt" else "") + f") = {result}"
    return {"content": [{"type": "text", "text": text}]}


def handle(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC request. Returns None for notifications (no id)."""
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    # Notifications have no id — no response
    if req_id is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "nemesis-calculator", "version": "1.1.0"},
            },
        )

    if method == "ping":
        return _ok(req_id, {})

    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name") if isinstance(params, dict) else None
        arguments = (params.get("arguments") or {}) if isinstance(params, dict) else {}
        if name != "calculate":
            return _err(req_id, -32602, f"Unknown tool: {name}")
        result = _calculate(arguments if isinstance(arguments, dict) else {})
        if "error" in result:
            return _err(req_id, -32000, str(result["error"]))
        return _ok(req_id, result)

    if method in ("resources/list", "prompts/list"):
        key = "resources" if method.startswith("resources") else "prompts"
        return _ok(req_id, {key: []})

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
            request = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON decode error: {e}\n")
            sys.stderr.flush()
            continue
        if not isinstance(request, dict):
            continue
        try:
            response = handle(request)
        except Exception as e:
            response = _err(request.get("id"), -32603, f"Internal error: {e}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

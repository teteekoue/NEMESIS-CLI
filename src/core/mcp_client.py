"""Lightweight MCP client over stdio (JSON-RPC, newline or Content-Length framing)."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class SimpleMCPClient:
    """MCP client without heavy dependencies.

    Supports:
    - Newline-delimited JSON-RPC (preferred by NEMESIS demo servers)
    - Content-Length framed messages (standard MCP / LSP style)
    """

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        cwd: Optional[str] = None,
    ):
        self.timeout = float(timeout)
        self._initialized = False
        self._pending: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._stderr_lines: List[str] = []
        self.running = False

        full_env = os.environ.copy()
        if env:
            full_env.update({str(k): str(v) for k, v in env.items()})

        cmd = [command] + list(args or [])
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=full_env,
                cwd=cwd,
                bufsize=1,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"MCP command not found: {command}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to start MCP server '{command}': {e}") from e

        self.running = True
        self._reader = threading.Thread(target=self._read_loop, name="mcp-stdout", daemon=True)
        self._stderr_thread = threading.Thread(target=self._drain_stderr, name="mcp-stderr", daemon=True)
        self._reader.start()
        self._stderr_thread.start()

    # ── IO helpers ──────────────────────────────────────────────

    def _drain_stderr(self) -> None:
        try:
            while self.running and self.process.stderr:
                line = self.process.stderr.readline()
                if not line:
                    break
                line = line.rstrip("\n")
                if line:
                    with self._lock:
                        self._stderr_lines.append(line)
                        if len(self._stderr_lines) > 200:
                            self._stderr_lines = self._stderr_lines[-100:]
        except Exception:
            pass

    def stderr_tail(self, n: int = 20) -> str:
        with self._lock:
            return "\n".join(self._stderr_lines[-n:])

    def _dispatch(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        msg_id = data.get("id")
        if msg_id is None:
            return  # notification / event
        key = str(msg_id)
        with self._lock:
            q = self._pending.get(key)
        if q is not None:
            try:
                q.put(data)
            except Exception:
                pass

    def _read_loop(self) -> None:
        """Read stdout: either Content-Length frames or newline JSON."""
        stdout = self.process.stdout
        if stdout is None:
            return
        while self.running:
            try:
                # Peek-ish: read a line; if Content-Length, read body by size
                line = stdout.readline()
            except Exception:
                break
            if not line:
                break
            stripped = line.strip()
            if not stripped:
                continue

            lower = stripped.lower()
            if lower.startswith("content-length:"):
                try:
                    length = int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    continue
                # Consume remaining headers until blank line
                while True:
                    hdr = stdout.readline()
                    if hdr is None or hdr == "" or hdr.strip() == "":
                        break
                try:
                    body = stdout.read(length)
                except Exception:
                    continue
                if not body:
                    continue
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    continue
                self._dispatch(data)
                continue

            # Newline-delimited JSON
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            self._dispatch(data)

    # ── RPC ─────────────────────────────────────────────────────

    def _alive(self) -> bool:
        return self.process.poll() is None

    def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self._alive():
            code = self.process.returncode
            tail = self.stderr_tail()
            extra = f"\nstderr:\n{tail}" if tail else ""
            raise RuntimeError(f"MCP process exited with code {code}{extra}")

        req_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params if params is not None else {},
        }
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[req_id] = q

        try:
            assert self.process.stdin is not None
            payload = json.dumps(request, ensure_ascii=False) + "\n"
            self.process.stdin.write(payload)
            self.process.stdin.flush()
        except Exception as e:
            with self._lock:
                self._pending.pop(req_id, None)
            raise RuntimeError(f"Failed to write to MCP process: {e}") from e

        try:
            response = q.get(timeout=timeout if timeout is not None else self.timeout)
        except queue.Empty:
            with self._lock:
                self._pending.pop(req_id, None)
            tail = self.stderr_tail()
            extra = f" stderr={tail[:300]!r}" if tail else ""
            raise TimeoutError(
                f"MCP request '{method}' timed out after {timeout or self.timeout}s.{extra}"
            )
        finally:
            with self._lock:
                self._pending.pop(req_id, None)

        if "error" in response and response["error"]:
            err = response["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise RuntimeError(f"MCP error on '{method}': {msg}")
        return response

    def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        note = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params is not None else {},
        }
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(json.dumps(note, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except Exception:
            pass

    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            return {"already": True}
        # Give the process a brief moment to start
        deadline = time.time() + 2.0
        while time.time() < deadline and not self._alive():
            time.sleep(0.05)
        response = self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nemesis-cli", "version": "2.1.0"},
            },
        )
        self.send_notification("notifications/initialized", {})
        self._initialized = True
        return response

    def list_tools(self) -> Any:
        if not self._initialized:
            self.initialize()
        response = self.send_request("tools/list")
        result = response.get("result", response)
        if isinstance(result, dict) and "tools" in result:
            return result["tools"]
        return result

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        if not self._initialized:
            self.initialize()
        response = self.send_request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return response.get("result", response)

    def close(self) -> None:
        self.running = False
        try:
            if self.process.poll() is None:
                try:
                    if self.process.stdin:
                        self.process.stdin.close()
                except Exception:
                    pass
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    try:
                        self.process.wait(timeout=1)
                    except Exception:
                        pass
        except Exception:
            pass

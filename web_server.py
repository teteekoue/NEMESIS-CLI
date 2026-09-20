#!/usr/bin/env python3
"""NEMESIS Web — a small, dependency-light web shell around the CLI engine.

The browser is only a presentation layer.  Provider calls, action parsing,
workspace tools, risk classification and the approval workflow are shared with
NEMESIS-CLI through ``ToolBridge`` and ``ActionParser``.

Run locally with::

    python web_server.py --host 0.0.0.0 --port 8000

The server deliberately uses the Python standard library so the web UI can be
started before the optional CLI dependencies are installed.  When the normal
requirements are available, selecting Live mode uses the configured NEMAPI
provider unchanged.
"""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import queue
import re
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, unquote, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from action_parser import ActionParser
from providers import create_provider
from src.core.paths import INSTALL_DIR, DEFAULT_WORKSPACE, USER_CONFIG_DIR, resolve_workspace
from src.core.tool_bridge import ToolBridge


WEB_DIR = Path(__file__).resolve().parent / "web"
WEB_SETTINGS_PATH = USER_CONFIG_DIR / "web_settings.json"
MAX_HISTORY = 500
MAX_OUTPUT = 1_000_000


def _json_default(value: Any) -> Any:
    """JSON fallback for dataclasses and small result objects."""
    if hasattr(value, "__dict__"):
        return value.__dict__
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _safe_json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))
    except Exception:
        return str(value)


def _load_yaml_fallback(path: Path) -> dict:
    """Read the small config shape used by NEMESIS without requiring PyYAML.

    PyYAML remains supported when installed.  This fallback is intentionally
    conservative: it understands nested mappings, quoted scalar values and
    integer/boolean scalars, which is enough for the shipped config file.
    """
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    if not path.exists():
        return {}

    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return root

    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        key = key.strip().strip("'\"")
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not value:
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        if value.startswith("[") or value.startswith("{"):
            try:
                parent[key] = json.loads(value.replace("'", '"'))
                continue
            except Exception:
                pass
        value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif value.lower() in {"true", "false"}:
            value = value.lower() == "true"
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        parent[key] = value
    return root


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _default_config() -> dict:
    """Load user config first, then the checked-in defaults."""
    candidates = [USER_CONFIG_DIR / "config.yaml", INSTALL_DIR / "config.yaml"]
    for candidate in candidates:
        data = _load_yaml_fallback(candidate)
        if data:
            break
    else:
        data = {}
    provider = data.get("provider") if isinstance(data.get("provider"), dict) else {}
    security = data.get("security") if isinstance(data.get("security"), dict) else {}
    nemapi = data.get("nemapi") if isinstance(data.get("nemapi"), dict) else {}
    config = {
        "provider": {
            "type": provider.get("type", "nemapi"),
            "model": provider.get("model", "qwen-chat"),
        },
        "nemapi": {
            "host": nemapi.get("host", provider.get("host", "127.0.0.1")),
            "port": nemapi.get("port", provider.get("port", 8090)),
        },
        "security": {
            "workspace": security.get("workspace", str(DEFAULT_WORKSPACE)),
        },
    }
    return config


def _load_settings() -> dict:
    settings = _read_json(WEB_SETTINGS_PATH, {})
    return settings if isinstance(settings, dict) else {}


def _display_path(path: Path) -> str:
    try:
        return str(path).replace(str(Path.home()), "~", 1)
    except Exception:
        return str(path)


def _truncate(text: Any, limit: int = MAX_OUTPUT) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n\n[output truncated at {limit:,} characters]"


def _result_to_dict(result: Any) -> dict:
    if isinstance(result, dict):
        data = dict(result)
    elif hasattr(result, "__dict__"):
        data = dict(result.__dict__)
    else:
        data = {"success": True, "stdout": str(result)}
    for key in ("stdout", "output", "error", "content"):
        if key in data and data[key] is not None and not isinstance(data[key], (dict, list)):
            data[key] = _truncate(data[key])
    if "success" not in data:
        data["success"] = not bool(data.get("error"))
    return _safe_json(data)


def _extract_tool_calls(result: dict, parsed: dict) -> list[dict]:
    """Merge native OpenAI-style calls into ActionParser output like the CLI."""
    actions = list(parsed.get("actions") or [])
    native_calls = result.get("tool_calls") or []
    for native_call in native_calls:
        if isinstance(native_call, dict):
            actions.append({
                "type": native_call.get("type", ""),
                "content": native_call.get("content", {}),
            })
    if not native_calls:
        native_call = result.get("tool_call")
        if isinstance(native_call, dict):
            actions.append({
                "type": native_call.get("type", ""),
                "content": native_call.get("content", {}),
            })
    # ActionParser keeps a singular alias for older callers.
    if actions and not parsed.get("action"):
        parsed["action"] = actions[0]
    parsed["actions"] = actions
    return actions


def _tool_summary(name: str, params: dict) -> str:
    params = params if isinstance(params, dict) else {}
    if name in {"read_file", "read"}:
        return f"Read {params.get('path') or params.get('paths') or 'file'}"
    if name in {"write_file", "write"}:
        return f"Write {params.get('file_path') or params.get('path') or 'file'}"
    if name in {"edit", "search_replace", "replace", "apply_patch"}:
        return f"Edit {params.get('file_path') or params.get('path') or 'workspace'}"
    if name == "bash":
        return f"Run {params.get('command') or 'command'}"
    if name in {"grep", "glob", "list_dir"}:
        return f"Inspect {params.get('path') or params.get('pattern') or 'workspace'}"
    if name.startswith("web_"):
        return f"{name.replace('_', ' ').title()} {params.get('query') or params.get('url') or ''}".strip()
    return name.replace("_", " ").title()


class DemoProvider:
    """Offline preview provider.

    It intentionally returns the same JSON tool grammar as the configured
    provider.  This lets a fresh clone demonstrate approvals and real tool
    execution even when NEMAPI is not running; Live mode never uses it.
    """

    model = "nemesis-web-demo"
    host = "demo"
    port = None

    def __init__(self) -> None:
        self._conversation: list[dict] = []

    def test_connection(self) -> bool:
        return True

    def list_models(self) -> list[dict]:
        return [{"id": self.model, "owned_by": "NEMESIS", "display_name": "Local preview"}]

    def reset_conversation(self) -> None:
        self._conversation = []

    def conversation_count(self) -> int:
        return len(self._conversation)

    def get_conversation(self) -> list[dict]:
        return list(self._conversation)

    def send_message(self, message: str, role: str = "user") -> dict:
        self._conversation.append({"role": role, "content": message})
        if role == "system":
            return {"success": True, "response": "Demo workspace initialized."}
        if role == "tool_result":
            self._conversation.append({"role": "assistant", "content": ""})
            return {
                "success": True,
                "response": "J'ai reçu le résultat de l'outil. En mode aperçu, le cycle est terminé — passez en Live pour déléguer l'analyse au modèle NEMAPI.",
            }

        text = (message or "").strip()
        low = text.lower()
        if low.startswith("/"):
            command = low.split()[0]
            if command in {"/help", "/commands"}:
                return {"success": True, "response": "Commandes web disponibles : `/help`, `/status`, `/tools`, `/clear`."}
            if command == "/status":
                return {"success": True, "response": "Mode aperçu local actif. Les outils NEMESIS restent disponibles dans le workspace."}
            if command == "/tools":
                return {"success": True, "response": "Ouvrez le panneau Outils pour parcourir le registre partagé de NEMESIS."}

        if any(word in low for word in ("écrire", "ecrire", "crée", "cree", "write", "fichier")) and any(
            word in low for word in ("crée", "cree", "écrire", "ecrire", "write", "note")
        ):
            return {
                "success": True,
                "response": "Je peux créer un fichier de démonstration dans le workspace. Cette action modifie le disque et demande votre approbation.",
                "tool_calls": [{
                    "type": "write_file",
                    "content": {
                        "file_path": "demo-note.md",
                        "content": "# Note NEMESIS\n\nCréée depuis l'interface web.\n",
                    },
                }],
            }
        if any(word in low for word in ("lire", "read", "ouvre", "contenu")):
            match = re.search(r"(?:lire|read|ouvre|ouvrir)\s+[`\"']?([^ `\"']+)", text, re.I)
            path = match.group(1) if match else "README.md"
            return {
                "success": True,
                "response": f"Je lis `{path}` depuis le workspace.",
                "tool_calls": [{"type": "read_file", "content": {"path": path}}],
            }
        if any(word in low for word in ("commande", "bash", "terminal", "exécute", "execute", "run")):
            return {
                "success": True,
                "response": "Je lance une commande sûre de démonstration. Les commandes shell réelles restent soumises à l'autorisation.",
                "tool_calls": [{"type": "bash", "content": {"command": "printf 'NEMESIS web preview\n'; pwd"}}],
            }
        if any(word in low for word in ("liste", "explore", "explorer", "fichiers", "dossier", "directory")):
            return {
                "success": True,
                "response": "J'inspecte la racine du workspace.",
                "tool_calls": [{"type": "list_dir", "content": {"path": ".", "depth": 2}}],
            }
        if any(word in low for word in ("cherche", "recherche", "grep", "search")):
            return {
                "success": True,
                "response": "Je recherche les occurrences de `TODO` dans le workspace.",
                "tool_calls": [{"type": "grep", "content": {"pattern": "TODO", "path": "."}}],
            }
        return {
            "success": True,
            "response": (
                "Le mode aperçu est prêt. Essayez « liste les fichiers », « lis README.md », "
                "« exécute une commande » ou « crée une note » pour voir le cycle agent → outil → résultat."
            ),
        }


@dataclass
class Approval:
    approval_id: str
    job_id: str
    tool: str
    params: dict
    risk: str
    created_at: float = field(default_factory=time.time)
    decision: Optional[str] = None
    event: threading.Event = field(default_factory=threading.Event)


@dataclass
class Job:
    job_id: str
    message: str
    started_at: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)
    done: bool = False
    error: Optional[str] = None


class WebSession:
    """One browser workspace/session and its event stream."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.subscribers: set[queue.Queue] = set()
        self.history: list[dict] = []
        self.approvals: dict[str, Approval] = {}
        self.jobs: dict[str, Job] = {}
        self.authorized_tools: set[str] = set()
        self.active_job_id: Optional[str] = None
        self.mode = "demo"
        self.config = _default_config()
        self.settings = _load_settings()
        self.send_system_prompt = bool(self.settings.get("send_system_prompt", True))
        self.connection_checked = False
        self.connection_ok: Optional[bool] = None
        self.connection_error = ""
        self.provider: Any = None
        self.executor: ToolBridge
        self.parser: ActionParser
        self._build_engine("demo")

    @property
    def workspace(self) -> Path:
        return Path(self.config.get("security", {}).get("workspace", DEFAULT_WORKSPACE)).expanduser().resolve()

    def _build_engine(self, mode: str) -> None:
        self.mode = mode
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.executor = ToolBridge(str(self.workspace))
        self.parser = ActionParser(extra_valid_tools=set(self.executor.registry._tools.keys()))
        self.connection_checked = False
        self.connection_ok = True if mode == "demo" else None
        self.connection_error = ""
        if mode == "demo":
            self.provider = DemoProvider()
            return
        try:
            self.provider = create_provider(self.config)
        except Exception as exc:
            self.provider = None
            self.connection_error = str(exc)

    def _record(self, item: dict) -> None:
        with self.lock:
            self.history.append({"id": uuid.uuid4().hex[:10], "ts": time.time(), **_safe_json(item)})
            if len(self.history) > MAX_HISTORY:
                del self.history[:-MAX_HISTORY]

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            self.subscribers.discard(q)

    def emit(self, event: str, payload: Optional[dict] = None) -> None:
        message = {"event": event, "data": _safe_json(payload or {}), "ts": time.time()}
        with self.lock:
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(message)
            except queue.Full:
                pass

    def state(self) -> dict:
        with self.lock:
            active = self.jobs.get(self.active_job_id) if self.active_job_id else None
            pending = [
                {
                    "approval_id": approval.approval_id,
                    "job_id": approval.job_id,
                    "tool": approval.tool,
                    "params": approval.params,
                    "risk": approval.risk,
                    "created_at": approval.created_at,
                }
                for approval in self.approvals.values()
                if approval.decision is None
            ]
            model = getattr(self.provider, "model", self.config.get("provider", {}).get("model", ""))
            return {
                "session_id": SESSION_ID,
                "mode": self.mode,
                "busy": bool(active and not active.done),
                "active_job_id": self.active_job_id,
                "workspace": str(self.workspace),
                "workspace_display": _display_path(self.workspace),
                "provider": self.config.get("provider", {}).get("type", "nemapi").upper() if self.mode == "live" else "DEMO",
                "model": model,
                "endpoint": self._endpoint(),
                "connection": "connected" if self.connection_ok is True else "offline" if self.connection_ok is False else "not_tested",
                "connection_error": self.connection_error,
                "send_system_prompt": self.send_system_prompt,
                "history": list(self.history),
                "pending_approvals": pending,
                "authorized_tools": sorted(self.authorized_tools),
            }

    def _endpoint(self) -> str:
        if self.mode != "live":
            return "local preview"
        nemapi = self.config.get("nemapi", {})
        return f"{nemapi.get('host', '127.0.0.1')}:{nemapi.get('port', 8090)}"

    def update_settings(self, data: dict) -> dict:
        with self.lock:
            requested_mode = str(data.get("mode", self.mode)).lower()
            if requested_mode not in {"demo", "live"}:
                requested_mode = self.mode
            provider = self.config.setdefault("provider", {})
            nemapi = self.config.setdefault("nemapi", {})
            security = self.config.setdefault("security", {})
            if data.get("host"):
                nemapi["host"] = str(data["host"]).strip()
            if data.get("port"):
                try:
                    nemapi["port"] = int(data["port"])
                except (TypeError, ValueError):
                    pass
            if data.get("model") is not None:
                provider["model"] = str(data["model"]).strip() or "qwen-chat"
            if data.get("workspace"):
                security["workspace"] = str(Path(str(data["workspace"])).expanduser())
            if "send_system_prompt" in data:
                self.send_system_prompt = bool(data["send_system_prompt"])
            self.settings.update({
                "mode": requested_mode,
                "send_system_prompt": self.send_system_prompt,
            })
            _save_json(WEB_SETTINGS_PATH, self.settings)
            self._build_engine(requested_mode)
        if requested_mode == "live":
            self.check_connection()
        self.emit("state", self.state())
        return self.state()

    def check_connection(self) -> bool:
        if self.mode == "demo":
            self.connection_checked = True
            self.connection_ok = True
            return True
        if not self.provider:
            self.connection_checked = True
            self.connection_ok = False
            return False
        try:
            self.connection_ok = bool(self.provider.test_connection())
            self.connection_error = "" if self.connection_ok else "NEMAPI ne répond pas sur cet endpoint."
        except Exception as exc:
            self.connection_ok = False
            self.connection_error = str(exc)
        self.connection_checked = True
        return bool(self.connection_ok)

    def reset(self) -> dict:
        with self.lock:
            if self.active_job_id and self.active_job_id in self.jobs:
                self.jobs[self.active_job_id].cancel.set()
            self.history.clear()
            self.approvals.clear()
            self.authorized_tools.clear()
            mode = self.mode
            self._build_engine(mode)
            self.active_job_id = None
        self.emit("reset", {})
        self.emit("state", self.state())
        return self.state()

    def submit(self, message: str) -> tuple[str, Optional[str]]:
        text = (message or "").strip()
        if not text:
            raise ValueError("Le message est vide.")
        with self.lock:
            if self.active_job_id:
                running = self.jobs.get(self.active_job_id)
                if running and not running.done:
                    raise RuntimeError("Une tâche est déjà en cours. Arrêtez-la avant d'envoyer un nouveau message.")
            job_id = uuid.uuid4().hex[:12]
            job = Job(job_id=job_id, message=text)
            self.jobs[job_id] = job
            self.active_job_id = job_id
            self._record({"kind": "user", "text": text, "job_id": job_id})
        self.emit("user", {"job_id": job_id, "text": text})
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True, name=f"nemesis-web-{job_id}")
        thread.start()
        return job_id, None

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.done:
                return False
            job.cancel.set()
            for approval in self.approvals.values():
                if approval.job_id == job_id and approval.decision is None:
                    approval.decision = "deny"
                    approval.event.set()
        self.emit("cancel_requested", {"job_id": job_id})
        return True

    def decide(self, approval_id: str, decision: str) -> bool:
        decision = (decision or "").lower()
        if decision in {"approve", "yes", "y"}:
            decision = "once"
        elif decision in {"always", "allow_all", "a"}:
            decision = "always"
        else:
            decision = "deny"
        with self.lock:
            approval = self.approvals.get(approval_id)
            if not approval or approval.decision is not None:
                return False
            approval.decision = decision
            if decision == "always":
                self.authorized_tools.add(approval.tool)
            approval.event.set()
        self.emit("approval_decision", {"approval_id": approval_id, "decision": decision, "tool": approval.tool})
        return True

    def _wait_for_approval(self, job: Job, tool: str, params: dict, risk: str) -> bool:
        if risk == "read" or tool in self.authorized_tools:
            return True
        approval = Approval(
            approval_id=uuid.uuid4().hex[:12],
            job_id=job.job_id,
            tool=tool,
            params=params if isinstance(params, dict) else {},
            risk=risk,
        )
        with self.lock:
            self.approvals[approval.approval_id] = approval
        self._record({
            "kind": "approval",
            "approval_id": approval.approval_id,
            "job_id": job.job_id,
            "tool": tool,
            "params": approval.params,
            "risk": risk,
            "status": "pending",
        })
        self.emit("approval_required", {
            "approval_id": approval.approval_id,
            "job_id": job.job_id,
            "tool": tool,
            "params": approval.params,
            "risk": risk,
            "summary": _tool_summary(tool, approval.params),
        })
        approval.event.wait(timeout=300)
        with self.lock:
            decision = approval.decision or "deny"
            if decision == "deny" and not approval.event.is_set():
                approval.decision = "deny"
        return decision in {"once", "always"} and not job.cancel.is_set()

    def _run_job(self, job: Job) -> None:
        started = time.time()
        tool_count = 0
        try:
            if self.mode == "live" and not self.check_connection():
                raise RuntimeError(self.connection_error or "Provider indisponible.")
            if job.cancel.is_set():
                return
            if self.send_system_prompt and getattr(self.provider, "_web_prompt_sent", False) is not True:
                prompt = self.executor.get_system_prompt()
                result = self.provider.send_message(prompt, role="system")
                if not result.get("success", False):
                    raise RuntimeError(result.get("error", "Initialisation du prompt système impossible."))
                try:
                    self.provider._web_prompt_sent = True
                except Exception:
                    pass

            current_input = job.message
            current_role = "user"
            last_response_hash = None
            max_iterations = 50
            for iteration in range(1, max_iterations + 1):
                if job.cancel.is_set():
                    self.emit("cancelled", {"job_id": job.job_id})
                    return
                result = self.provider.send_message(current_input, role=current_role)
                if not result.get("success", False):
                    raise RuntimeError(result.get("error", "Réponse provider invalide."))
                raw = str(result.get("response", "") or "")
                parsed = self.parser.parse(raw)
                actions = _extract_tool_calls(result, parsed)
                response_hash = hash(raw.strip())
                if response_hash == last_response_hash and iteration > 1:
                    actions = []
                last_response_hash = response_hash
                text = parsed.get("text", "") or ""
                if text and not str(text).startswith("FEEDBACK:"):
                    self._record({"kind": "assistant", "text": str(text), "job_id": job.job_id, "iteration": iteration})
                    self.emit("assistant", {"job_id": job.job_id, "text": str(text), "iteration": iteration})
                if not actions:
                    self.emit("done", {
                        "job_id": job.job_id,
                        "elapsed": round(time.time() - started, 2),
                        "tool_count": tool_count,
                    })
                    return

                feedback: list[str] = []
                for action in actions:
                    if job.cancel.is_set():
                        self.emit("cancelled", {"job_id": job.job_id})
                        return
                    tool = str(action.get("type", ""))
                    params = action.get("content", {})
                    params = params if isinstance(params, dict) else {}
                    risk = self.executor.risk_for(tool, params)
                    allowed = self._wait_for_approval(job, tool, params, risk)
                    if not allowed:
                        self.emit("tool_result", {
                            "job_id": job.job_id,
                            "tool": tool,
                            "params": params,
                            "success": False,
                            "output": "Exécution refusée par l'utilisateur.",
                            "denied": True,
                        })
                        feedback.append(f"Tool: {tool}\nSuccess: false\nOutput:\n[EXECUTION REFUSEE PAR L'UTILISATEUR]")
                        continue
                    tool_count += 1
                    self.emit("tool_start", {
                        "job_id": job.job_id,
                        "tool": tool,
                        "params": params,
                        "risk": risk,
                        "summary": _tool_summary(tool, params),
                    })
                    final: dict = {}
                    for update in self.executor.execute_tool(tool, params):
                        if job.cancel.is_set():
                            break
                        final = _result_to_dict(update)
                        if update.get("needs_input"):
                            self.emit("tool_input", {
                                "job_id": job.job_id,
                                "tool": tool,
                                "context": update.get("input_context", "La commande attend une entrée."),
                            })
                            # Browser input forwarding is intentionally not
                            # implicit; do not leave a PTY blocked forever.
                            final = {"success": False, "stdout": "Commande interactive : utilisez un terminal local pour cette action."}
                            break
                        if tool != "bash" or "success" in update:
                            break
                    if not final:
                        final = {"success": False, "stdout": "Aucun résultat retourné par l'outil."}
                    output = final.get("output") or final.get("stdout") or final.get("error") or ""
                    self._record({
                        "kind": "tool",
                        "job_id": job.job_id,
                        "tool": tool,
                        "params": params,
                        "risk": risk,
                        "success": bool(final.get("success", False)),
                        "output": _truncate(output),
                    })
                    self.emit("tool_result", {
                        "job_id": job.job_id,
                        "tool": tool,
                        "params": params,
                        "risk": risk,
                        "success": bool(final.get("success", False)),
                        "output": _truncate(output),
                        "result": final,
                    })
                    feedback.append(self._feedback(tool, final))
                current_input = "FEEDBACK:\n" + "\n\n".join(feedback)
                current_role = "tool_result"
            raise RuntimeError(f"Limite de {max_iterations} itérations d'outils atteinte.")
        except Exception as exc:
            job.error = str(exc)
            self._record({"kind": "error", "job_id": job.job_id, "text": str(exc)})
            self.emit("error", {"job_id": job.job_id, "message": str(exc)})
        finally:
            with self.lock:
                job.done = True
                if self.active_job_id == job.job_id:
                    self.active_job_id = None
            self.emit("state", self.state())

    @staticmethod
    def _feedback(tool: str, result: dict) -> str:
        output = result.get("stdout") or result.get("output") or result.get("error") or "[no output]"
        return f"FEEDBACK:\nTool: {tool}\nSuccess: {bool(result.get('success', False))}\nOutput:\n{_truncate(output)}"


SESSION_ID = uuid.uuid4().hex[:16]
SESSION = WebSession()


class NemesisHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "NEMESIS-Web/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("NEMESIS_WEB_ACCESS_LOG", "") in {"1", "true", "yes"}:
            super().log_message(fmt, *args)

    def _headers(self, content_type: str = "application/json; charset=utf-8", length: Optional[int] = None) -> None:
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self._headers(length=len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8_000_000:
                raise ValueError("Request trop volumineuse.")
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Objet JSON attendu.")
            return data
        except Exception as exc:
            raise ValueError(f"JSON invalide: {exc}") from exc

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._headers(length=0)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/index.html"}:
                return self._serve_static("index.html")
            if path.startswith("/assets/"):
                return self._serve_static(path.removeprefix("/assets/"))
            if path == "/api/health":
                return self._send_json({
                    "ok": True,
                    "service": "NEMESIS Web",
                    "version": "1.0",
                    "mode": SESSION.mode,
                    "connection": SESSION.state()["connection"],
                    "workspace": SESSION.state()["workspace_display"],
                })
            if path == "/api/state":
                return self._send_json(SESSION.state())
            if path == "/api/events":
                return self._stream_events()
            if path == "/api/models":
                if SESSION.mode == "live" and SESSION.provider:
                    models = SESSION.provider.list_models()
                else:
                    models = DemoProvider().list_models()
                return self._send_json({"models": _safe_json(models), "selected": getattr(SESSION.provider, "model", "")})
            if path == "/api/tools":
                return self._send_json({"tools": self._tool_definitions()})
            if path == "/api/skills":
                return self._send_json({"skills": self._skills()})
            if path == "/api/agents":
                return self._send_json({"agents": self._agents()})
            if path == "/api/todos":
                return self._send_json({"items": self._todos()})
            if path == "/api/workspace/tree":
                query = parse_qs(parsed.query)
                return self._send_json(self._workspace_tree(query.get("path", ["."])[0]))
            if path == "/api/workspace/file":
                query = parse_qs(parsed.query)
                return self._send_json(self._workspace_file(query.get("path", [""])[0]))
            return self._send_error_json("Route introuvable.", 404)
        except Exception as exc:
            if os.environ.get("NEMESIS_WEB_DEBUG"):
                traceback.print_exc()
            return self._send_error_json(str(exc), 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/chat":
                body = self._body()
                job_id, _ = SESSION.submit(str(body.get("message", "")))
                return self._send_json({"accepted": True, "job_id": job_id}, 202)
            if path == "/api/reset":
                return self._send_json(SESSION.reset())
            if path == "/api/settings":
                return self._send_json(SESSION.update_settings(self._body()))
            if path.startswith("/api/approvals/"):
                approval_id = path.rsplit("/", 1)[-1]
                body = self._body()
                ok = SESSION.decide(approval_id, str(body.get("decision", "deny")))
                return self._send_json({"ok": ok}, 200 if ok else 404)
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path.split("/")[3]
                return self._send_json({"ok": SESSION.cancel(job_id)})
            if path == "/api/check-connection":
                return self._send_json({"ok": SESSION.check_connection(), **SESSION.state()})
            return self._send_error_json("Route introuvable.", 404)
        except (ValueError, RuntimeError) as exc:
            return self._send_error_json(str(exc), 409 if isinstance(exc, RuntimeError) else 400)
        except Exception as exc:
            if os.environ.get("NEMESIS_WEB_DEBUG"):
                traceback.print_exc()
            return self._send_error_json(str(exc), 500)

    def _serve_static(self, relative: str) -> None:
        relative = unquote(relative).replace("\\", "/")
        candidate = (WEB_DIR / relative).resolve()
        if WEB_DIR not in candidate.parents and candidate != WEB_DIR:
            return self._send_error_json("Fichier invalide.", 403)
        if not candidate.is_file():
            return self._send_error_json("Fichier introuvable.", 404)
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        if candidate.suffix in {".js", ".css", ".html"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self._headers(content_type=content_type, length=len(content))
        self.end_headers()
        self.wfile.write(content)

    def _stream_events(self) -> None:
        subscriber = SESSION.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    message = subscriber.get(timeout=20)
                    event = message.get("event", "message")
                    data = json.dumps(message.get("data", {}), ensure_ascii=False, default=_json_default)
                    payload = f"event: {event}\ndata: {data}\n\n".encode("utf-8")
                except queue.Empty:
                    payload = b": ping\n\n"
                self.wfile.write(payload)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            SESSION.unsubscribe(subscriber)

    @staticmethod
    def _tool_definitions() -> list[dict]:
        definitions = []
        for name, registration in SESSION.executor.registry:
            definition = registration.definition
            definitions.append({
                "name": name,
                "description": definition.description,
                "kind": definition.kind.value,
                "namespace": definition.namespace.value,
                "risk": SESSION.executor.registry.risk_for(name),
                "schema": definition.params_schema,
            })
        return definitions

    @staticmethod
    def _skills() -> list[dict]:
        root = INSTALL_DIR / "tools_library"
        skills = []
        if not root.is_dir():
            return skills
        for skill_file in sorted(root.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8", errors="replace")
            front = re.search(r"^---\s*(.*?)\s*---", text, re.S | re.M)
            meta = {}
            if front:
                for line in front.group(1).splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meta[key.strip()] = value.strip().strip("'\"")
            skills.append({
                "name": meta.get("name", skill_file.parent.name),
                "description": meta.get("description", ""),
                "version": meta.get("version", "1.0"),
            })
        return skills

    @staticmethod
    def _agents() -> list[dict]:
        candidates = [USER_CONFIG_DIR / "agents.json", INSTALL_DIR / "agents.json"]
        for path in candidates:
            data = _read_json(path, None)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [{"name": key, **(value if isinstance(value, dict) else {})} for key, value in data.items()]
        return []

    @staticmethod
    def _todos() -> list[dict]:
        store = SESSION.workspace / ".nemesis-todos.json"
        data = _read_json(store, [])
        return data if isinstance(data, list) else []

    @staticmethod
    def _workspace_path(raw: str) -> Path:
        raw = (raw or ".").strip()
        candidate = Path(raw).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (SESSION.workspace / candidate).resolve()
        if resolved != SESSION.workspace and SESSION.workspace not in resolved.parents:
            raise ValueError("Le chemin doit rester dans le workspace.")
        return resolved

    def _workspace_tree(self, raw: str) -> dict:
        root = self._workspace_path(raw)
        if not root.exists():
            return {"path": raw, "name": root.name, "type": "directory", "children": []}
        if not root.is_dir():
            return {"path": str(root.relative_to(SESSION.workspace)), "name": root.name, "type": "file"}

        def walk(directory: Path, depth: int) -> list[dict]:
            if depth > 3:
                return []
            children = []
            try:
                entries = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            except OSError:
                return children
            for entry in entries:
                if entry.name in {".git", "__pycache__", ".venv", "venv", "node_modules"}:
                    continue
                rel = str(entry.relative_to(SESSION.workspace))
                if entry.is_dir():
                    children.append({"name": entry.name, "path": rel, "type": "directory", "children": walk(entry, depth + 1)})
                else:
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    children.append({"name": entry.name, "path": rel, "type": "file", "size": size})
            return children

        return {"path": str(root.relative_to(SESSION.workspace)) if root != SESSION.workspace else ".", "name": root.name, "type": "directory", "children": walk(root, 0)}

    def _workspace_file(self, raw: str) -> dict:
        path = self._workspace_path(raw)
        if not path.exists() or not path.is_file():
            raise ValueError("Fichier introuvable.")
        size = path.stat().st_size
        if size > 1_000_000:
            raise ValueError("Fichier trop volumineux pour l'aperçu web.")
        data = path.read_bytes()
        if b"\0" in data:
            return {"path": raw, "name": path.name, "binary": True, "size": size}
        text = data.decode("utf-8", errors="replace")
        return {"path": str(path.relative_to(SESSION.workspace)), "name": path.name, "content": text, "size": size, "language": path.suffix.lstrip(".") or "text"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur web NEMESIS")
    parser.add_argument("--host", default=os.environ.get("NEMESIS_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    if not WEB_DIR.is_dir():
        raise SystemExit(f"Répertoire web introuvable: {WEB_DIR}")
    httpd = ThreadingHTTPServer((args.host, args.port), NemesisHTTPRequestHandler)
    httpd.daemon_threads = True
    print(f"NEMESIS Web listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

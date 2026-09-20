"""Gestion des sessions web NEMESIS.

Chaque session possède sa propre instance du moteur (`NemesisApp`), un thread
de travail qui consomme les messages utilisateur, un journal d'événements
(rejoué à la reconnexion) et des abonnés temps réel (WebSockets).
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from web.engine import (
    EventConsole,
    InteractiveCommandError,
    WebNemesisApp,
    _current_sink,
    install_shared_console,
)

# Verrou global : les commandes slash utilisent un état module (`_active_app`).
_SLASH_LOCK = threading.Lock()

MAX_EVENTS = 5000


def _sessions_dir() -> Path:
    from src.core.paths import USER_CONFIG_DIR

    d = USER_CONFIG_DIR / "web_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Session:
    def __init__(
        self,
        manager: "SessionManager",
        title: str = "Nouvelle conversation",
        access_mode: str = "ask",
        send_system_prompt: bool = True,
        session_id: Optional[str] = None,
    ):
        self.id = session_id or uuid.uuid4().hex[:12]
        self.manager = manager
        self.title = title
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.access_mode = access_mode  # ask | full | readonly
        self.send_system_prompt = send_system_prompt
        self.events: List[Dict[str, Any]] = []
        self._seq = 0
        self._subscribers: List[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._inbox: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self._pending_inputs: Dict[str, Dict[str, Any]] = {}
        self._closed = False
        self.busy = False
        self.pending_request: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.stats = {
            "turns": 0,
            "llm_iterations": 0,
            "tool_calls": 0,
            "tool_failures": 0,
            "llm_time": 0.0,
            "elapsed_total": 0.0,
        }
        self.app = None
        self._thread = threading.Thread(target=self._run, name=f"nemesis-web-{self.id}", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------
    def emit(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            event = dict(event)
            event.setdefault("ts", time.time())
            event["seq"] = self._seq
            self.events.append(event)
            if len(self.events) > MAX_EVENTS:
                self.events = self.events[-MAX_EVENTS:]
            self.updated_at = event["ts"]
            subs = list(self._subscribers)
            if event.get("type") in ("auth_request", "input_request"):
                self.pending_request = event
            elif event.get("type") == "input_resolved":
                self.pending_request = None
        loop = self.manager.loop
        if loop is not None:
            for q in subs:
                try:
                    loop.call_soon_threadsafe(q.put_nowait, event)
                except RuntimeError:
                    pass
        self.manager.schedule_save(self)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # ------------------------------------------------------------------
    # Entrées utilisateur bloquantes (autorisation, stdin des commandes…)
    # ------------------------------------------------------------------
    def wait_for_input(self, request_id: str) -> Optional[str]:
        ev = threading.Event()
        slot = {"event": ev, "value": None}
        self._pending_inputs[request_id] = slot
        ev.wait()
        self._pending_inputs.pop(request_id, None)
        return slot["value"]

    def resolve_input(self, request_id: str, value: Optional[str]) -> bool:
        slot = self._pending_inputs.get(request_id)
        if not slot:
            return False
        slot["value"] = value
        slot["event"].set()
        return True

    def cancel_pending_inputs(self) -> None:
        for rid in list(self._pending_inputs.keys()):
            self.resolve_input(rid, None)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def send(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if self.title == "Nouvelle conversation" and not text.startswith("/"):
            self.title = text[:60] + ("…" if len(text) > 60 else "")
            self.emit({"type": "meta", "title": self.title})
        self._inbox.put({"kind": "message", "text": text})

    def interrupt(self) -> None:
        if self.app is not None:
            self.app._interrupted = True
        self.cancel_pending_inputs()
        self.emit({"type": "system", "level": "warning", "text": "Interruption demandée…"})

    def set_access_mode(self, mode: str) -> None:
        if mode in ("ask", "full", "readonly"):
            self.access_mode = mode
            self.emit({"type": "meta", "access_mode": mode})

    def set_model(self, model: str) -> None:
        if self.app and self.app.client:
            self.app.client.model = model
            self.emit({"type": "meta", "model": model})

    def close(self) -> None:
        self._closed = True
        self.cancel_pending_inputs()
        self._inbox.put(None)

    def snapshot(self) -> Dict[str, Any]:
        client = getattr(self.app, "client", None)
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_mode": self.access_mode,
            "send_system_prompt": self.send_system_prompt,
            "busy": self.busy,
            "pending_request": self.pending_request,
            "error": self.error,
            "stats": dict(self.stats),
            "model": getattr(client, "model", None),
            "connected": getattr(self.app, "_conn_ok", None),
            "authorized_tools": sorted(getattr(self.app, "_authorized_tools", set()) or []),
            "message_count": sum(1 for e in self.events if e.get("type") == "user"),
        }

    # ------------------------------------------------------------------
    # Thread de travail
    # ------------------------------------------------------------------
    def _run(self) -> None:
        token = _current_sink.set(self.emit)
        try:
            self._bootstrap()
            while not self._closed:
                item = self._inbox.get()
                if item is None:
                    break
                self.busy = True
                self.emit({"type": "busy", "busy": True})
                try:
                    self._handle(item)
                except SystemExit:
                    self.emit({"type": "system", "text": "Session terminée (/exit)."})
                    break
                except KeyboardInterrupt:
                    self.emit({"type": "system", "level": "warning", "text": "Tâche interrompue."})
                except Exception as exc:  # noqa: BLE001
                    self.emit({
                        "type": "error",
                        "message": f"{type(exc).__name__}: {exc}",
                        "trace": traceback.format_exc(),
                    })
                finally:
                    self.busy = False
                    self.emit({"type": "busy", "busy": False})
        finally:
            _current_sink.reset(token)

    def _bootstrap(self) -> None:
        import src.core.default_commands as dc
        from providers import create_provider
        from tools import create_executor_from_config
        from action_parser import ActionParser

        install_shared_console()
        app = WebNemesisApp.build(self, self.emit)
        self.app = app
        app.session_start = time.time()
        app._load_config()
        try:
            app.client = create_provider(app.config)
        except Exception as exc:  # noqa: BLE001
            self.error = f"Provider indisponible : {exc}"
            self.emit({"type": "error", "message": self.error})

        app.executor = create_executor_from_config(app.config, bridge=app.client)
        if hasattr(app.executor, "registry") and app.executor.registry:
            app.parser = ActionParser(extra_valid_tools=set(app.executor.registry._tools.keys()))

        from src.core.agent_manager import get_scheduler

        get_scheduler().set_executor(app.executor)
        dc.reload_agents_with_executor(app.executor)

        # Choix « prompt système » de la CLI, pris depuis les options de session.
        app._send_system_prompt = bool(self.send_system_prompt)
        app._prompt_sent = not self.send_system_prompt
        app._conn_ok = None

        client = app.client
        self.emit({
            "type": "ready",
            "provider": app.config.get("provider", {}).get("type", "nemapi").upper(),
            "model": getattr(client, "model", ""),
            "target": getattr(client, "base_url", "—") if client else "—",
            "workspace": app.config.get("security", {}).get("workspace", ""),
            "send_system_prompt": self.send_system_prompt,
        })

    def _handle(self, item: Dict[str, Any]) -> None:
        from src.core.commands import registry
        import src.core.default_commands as dc

        app = self.app
        text = item["text"]
        if app is None:
            self.emit({"type": "error", "message": "Moteur non initialisé."})
            return

        if text.startswith("/"):
            parts = text[1:].split()
            self.emit({"type": "user", "text": text, "command": True})
            with _SLASH_LOCK:
                dc.set_active_app(app)
                if not parts:
                    app._show_commands()
                    return
                cmd_name = parts[0].lower()
                cmd = registry.get_command(cmd_name)
                if not cmd:
                    self.emit({
                        "type": "error",
                        "message": f"Commande inconnue : /{cmd_name} — utilisez /help.",
                    })
                    return
                try:
                    res = cmd.handler(parts[1:])
                except InteractiveCommandError as exc:
                    self.emit({"type": "system", "level": "warning", "text": str(exc)})
                    return
                if isinstance(res, str) and res.startswith("PROMPT_INTERNAL:"):
                    app._process_cycle(res.replace("PROMPT_INTERNAL:", "").strip())
            return

        if app.client is None:
            self.emit({
                "type": "error",
                "message": "Aucun provider actif. Configurez NEMAPI dans les paramètres.",
            })
            return
        with _SLASH_LOCK:
            dc.set_active_app(app)
        app._process_cycle(text)
        self.emit({"type": "meta", "connected": app._conn_ok, "model": getattr(app.client, "model", None)})


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._save_lock = threading.Lock()
        self._dirty: set = set()
        self._saver = threading.Thread(target=self._save_loop, daemon=True)
        self._saver.start()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def create(self, **kwargs) -> Session:
        s = Session(self, **kwargs)
        self.sessions[s.id] = s
        return s

    def get(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def list(self) -> List[Dict[str, Any]]:
        live = [s.snapshot() for s in self.sessions.values()]
        archived = self._list_archived({s.id for s in self.sessions.values()})
        return sorted(live + archived, key=lambda s: s["updated_at"], reverse=True)

    def delete(self, session_id: str) -> bool:
        s = self.sessions.pop(session_id, None)
        if s:
            s.close()
        path = _sessions_dir() / f"{session_id}.json"
        if path.exists():
            path.unlink()
        return s is not None or True

    # -- persistance ------------------------------------------------------
    def schedule_save(self, session: Session) -> None:
        with self._save_lock:
            self._dirty.add(session.id)

    def _save_loop(self) -> None:
        while True:
            time.sleep(2.0)
            with self._save_lock:
                ids = list(self._dirty)
                self._dirty.clear()
            for sid in ids:
                s = self.sessions.get(sid)
                if s:
                    try:
                        self._save(s)
                    except Exception:
                        pass

    def _save(self, s: Session) -> None:
        payload = {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "access_mode": s.access_mode,
            "stats": s.stats,
            "events": [e for e in s.events if e.get("type") not in ("busy", "thinking")],
        }
        path = _sessions_dir() / f"{s.id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _list_archived(self, exclude: set) -> List[Dict[str, Any]]:
        out = []
        for p in _sessions_dir().glob("*.json"):
            if p.stem in exclude:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append({
                "id": data.get("id", p.stem),
                "title": data.get("title", p.stem),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
                "access_mode": data.get("access_mode", "ask"),
                "busy": False,
                "archived": True,
                "stats": data.get("stats", {}),
                "message_count": sum(1 for e in data.get("events", []) if e.get("type") == "user"),
            })
        return out

    def load_archived(self, session_id: str) -> Optional[Dict[str, Any]]:
        p = _sessions_dir() / f"{session_id}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None


manager = SessionManager()

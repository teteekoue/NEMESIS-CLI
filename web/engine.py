"""NEMESIS Web engine — réutilise le moteur CLI (NemesisApp) en remplaçant
l'affichage terminal par un flux d'événements structurés.

Rien de la logique interne n'est dupliqué : `_process_cycle`,
`_ask_for_authorization`, le parseur, l'exécuteur d'outils, le registre de
commandes slash… sont ceux d'`agent.py`. Seules les surfaces d'E/S
(`Console`, `Composer`) sont remplacées par des adaptateurs qui émettent des
événements JSON consommés par l'interface web.
"""

from __future__ import annotations

import contextvars
import io
import os
import queue
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

from src.ui.theme import NEMESIS_THEME

EventSink = Callable[[Dict[str, Any]], None]

# Session courante pour le thread de travail (utilisée par la console partagée
# des commandes slash, cf. `install_shared_console`).
_current_sink: contextvars.ContextVar[Optional[EventSink]] = contextvars.ContextVar(
    "nemesis_web_sink", default=None
)


class InteractiveCommandError(RuntimeError):
    """Levée quand une commande slash tente de lire sur stdin."""


# ---------------------------------------------------------------------------
# Console → événements HTML
# ---------------------------------------------------------------------------

_HTML_FORMAT = '<pre class="rich">{code}</pre>'


class EventConsole(Console):
    """Console Rich dont chaque `print` est exporté en HTML puis émis."""

    def __init__(self, sink: Optional[EventSink] = None, **kwargs):
        kwargs.setdefault("theme", NEMESIS_THEME)
        super().__init__(
            file=io.StringIO(),
            record=True,
            width=kwargs.pop("width", 110),
            force_terminal=True,
            color_system="truecolor",
            highlight=False,
            **kwargs,
        )
        self._sink = sink

    # -- résolution du destinataire -------------------------------------
    def _resolve_sink(self) -> Optional[EventSink]:
        return self._sink or _current_sink.get()

    def _flush_event(self):
        sink = self._resolve_sink()
        text = self.export_text(clear=False)
        html = self.export_html(clear=True, inline_styles=True, code_format=_HTML_FORMAT)
        # vider le tampon StringIO pour ne pas croître indéfiniment
        try:
            self.file.seek(0)
            self.file.truncate(0)
        except Exception:
            pass
        if not text.strip():
            return
        if sink:
            sink({"type": "system", "html": html, "text": text})

    # -- surcharges -------------------------------------------------------
    def print(self, *args, **kwargs):  # noqa: A003 - API Rich
        super().print(*args, **kwargs)
        self._flush_event()

    def log(self, *args, **kwargs):
        super().log(*args, **kwargs)
        self._flush_event()

    def clear(self, home: bool = True):
        sink = self._resolve_sink()
        if sink:
            sink({"type": "clear"})

    def input(self, prompt: str = "", *args, **kwargs):  # noqa: A003
        raise InteractiveCommandError(
            "Cette commande est interactive dans le terminal. "
            "Utilisez le panneau Paramètres de l'interface web."
        )

    def status(self, *args, **kwargs):
        # Contexte neutre : pas d'animation dans le navigateur
        import contextlib

        return contextlib.nullcontext()


def install_shared_console() -> None:
    """Remplace la console module de `default_commands` par une EventConsole
    contextuelle afin que les commandes slash s'affichent dans le navigateur."""
    import src.core.default_commands as dc

    if not isinstance(dc.console, EventConsole):
        dc.console = EventConsole(sink=None)


# ---------------------------------------------------------------------------
# Composer → événements structurés + entrées bloquantes
# ---------------------------------------------------------------------------


class WebComposer:
    """Remplace `src.ui.composer.Composer` : même interface, sortie web."""

    DEFAULT_TITLE = "input"
    AUTH_TITLE = "authorization  [y / n / a]"

    def __init__(self, sink: EventSink, session):
        self._sink = sink
        self._session = session
        self.console = EventConsole(sink=sink)
        self._pending_auth: Optional[Dict[str, Any]] = None
        self._call_counter = 0
        self._open_calls: List[str] = []

    # -- helpers --------------------------------------------------------
    def _emit(self, ev: Dict[str, Any]):
        self._sink(ev)

    # -- messages ---------------------------------------------------------
    def display_user_message(self, text: str):
        self._emit({"type": "user", "text": text})

    def display_ai_message(self, text: str):
        self._emit({"type": "assistant", "text": text})

    def display_welcome(self, **kwargs):
        self._emit({"type": "welcome", **kwargs})

    # -- outils -----------------------------------------------------------
    def display_tool_start(self, tool_name: str, params: dict):
        self._call_counter += 1
        call_id = f"c{self._call_counter}"
        self._open_calls.append(call_id)
        risk = "medium"
        app = self._session.app
        try:
            if app and app.executor and hasattr(app.executor, "risk_for"):
                risk = app.executor.risk_for(tool_name, params)
        except Exception:
            pass
        self._emit({
            "type": "tool_start",
            "call_id": call_id,
            "tool": tool_name,
            "params": _jsonable(params),
            "risk": risk,
        })

    def display_tool_result(self, result: dict, tool_name: str = ""):
        call_id = self._open_calls.pop() if self._open_calls else None
        if hasattr(result, "success"):
            success = bool(result.success)
            output = getattr(result, "output", "") or ""
            payload: Dict[str, Any] = {}
        else:
            result = result if isinstance(result, dict) else {}
            success = bool(result.get("success", False))
            output = result.get("output") or result.get("stdout") or result.get("error") or ""
            payload = {
                k: _jsonable(v)
                for k, v in result.items()
                if k in ("edits", "message", "output_id", "exit_code", "task_id", "error", "items")
            }
        self._session.stats["tool_calls"] += 1
        if not success:
            self._session.stats["tool_failures"] += 1
        self._emit({
            "type": "tool_result",
            "call_id": call_id,
            "tool": tool_name,
            "success": success,
            "output": str(output),
            **payload,
        })

    def display_tool_error(self, error: str):
        self._emit({"type": "error", "message": str(error)})

    def display_todo(self, items):
        self._emit({"type": "todo", "items": _jsonable(items)})

    def display_task_summary(self, elapsed: float, tool_count: int = 0):
        self._session.stats["turns"] += 1
        self._session.stats["llm_iterations"] += max(1, tool_count + 1)
        self._session.stats["elapsed_total"] += float(elapsed)
        self._emit({"type": "summary", "elapsed": float(elapsed), "tool_count": int(tool_count)})

    def display_thinking(self, message: str = "thinking..."):
        """Générateur compatible avec `next(anim)` / `anim.close()`."""
        self._emit({"type": "thinking", "active": True, "message": message})
        started = time.time()
        try:
            yield
        finally:
            self._session.stats["llm_time"] += time.time() - started
            self._emit({"type": "thinking", "active": False, "message": message})

    def display_auth(self, tool_name: str, params: dict):
        self._pending_auth = {"tool": tool_name, "params": _jsonable(params)}

    def live_terminal(self, title: str = "bash"):
        import contextlib

        return contextlib.nullcontext()

    # -- entrées bloquantes -------------------------------------------------
    def prompt_input(self, title: Optional[str] = None, placeholder: str = "") -> Optional[str]:
        """Bloque le thread de travail jusqu'à réponse de l'utilisateur web."""
        request_id = uuid.uuid4().hex[:10]
        if title == self.AUTH_TITLE and self._pending_auth:
            info = self._pending_auth
            self._pending_auth = None
            risk = "medium"
            app = self._session.app
            try:
                if app and app.executor and hasattr(app.executor, "risk_for"):
                    risk = app.executor.risk_for(info["tool"], info["params"])
            except Exception:
                pass
            self._emit({
                "type": "auth_request",
                "request_id": request_id,
                "tool": info["tool"],
                "params": info["params"],
                "risk": risk,
            })
        else:
            self._emit({
                "type": "input_request",
                "request_id": request_id,
                "title": title or self.DEFAULT_TITLE,
                "placeholder": placeholder,
            })
        value = self._session.wait_for_input(request_id)
        self._emit({"type": "input_resolved", "request_id": request_id, "value": value})
        if value is None:
            raise KeyboardInterrupt
        return value


def _jsonable(value: Any) -> Any:
    """Convertit récursivement en structures JSON-sérialisables."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        try:
            return _jsonable(vars(value))
        except Exception:
            pass
    return str(value)


# ---------------------------------------------------------------------------
# Application NEMESIS pilotée par le web
# ---------------------------------------------------------------------------


class WebNemesisApp:
    """Fabrique et configure une instance `NemesisApp` branchée sur le web."""

    @staticmethod
    def build(session, sink: EventSink, debug: bool = False):
        from agent import NemesisApp

        app = NemesisApp(debug=debug)
        app.console = EventConsole(sink=sink)
        app._console = app.console
        app.composer = WebComposer(sink, session)

        # Mode "accès complet" : court-circuite la demande d'autorisation.
        original_ask = app._ask_for_authorization

        def ask(tool_name, action_content, risk="medium"):
            if session.access_mode == "full":
                return True
            if session.access_mode == "readonly" and risk != "read":
                sink({
                    "type": "system",
                    "level": "warning",
                    "text": f"Outil '{tool_name}' bloqué (mode lecture seule).",
                })
                return False
            return original_ask(tool_name, action_content, risk)

        app._ask_for_authorization = ask
        return app

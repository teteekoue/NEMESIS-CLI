"""NEMESIS Web — serveur FastAPI.

Lancement : `python -m web.server` (ou `nemesis-web`).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Le moteur CLI est importé depuis la racine du dépôt.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from web.sessions import manager  # noqa: E402

STATIC_DIR = Path(__file__).parent / "static"

from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    manager.attach_loop(asyncio.get_running_loop())
    yield
    for s in list(manager.sessions.values()):
        s.close()


app = FastAPI(title="NEMESIS Web", version="1.0.0", docs_url="/api/docs", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------


class NewSession(BaseModel):
    title: Optional[str] = None
    access_mode: str = "ask"
    send_system_prompt: bool = True


class Message(BaseModel):
    text: str


class Respond(BaseModel):
    request_id: str
    value: Optional[str] = None


class AccessMode(BaseModel):
    mode: str


class ModelChoice(BaseModel):
    model: str


class ConfigUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    model: Optional[str] = None
    workspace: Optional[str] = None
    timeout: Optional[int] = None


class MCPServer(BaseModel):
    name: str
    command: str
    description: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config() -> Dict[str, Any]:
    """Charge la config utilisateur via la même logique que la CLI."""
    from agent import NemesisApp

    tmp = NemesisApp.__new__(NemesisApp)
    from src.core.paths import config_path, mcp_config_path, ensure_user_dirs

    ensure_user_dirs()
    tmp.config_path = config_path()
    tmp.mcp_config_path = mcp_config_path()
    tmp.config = None
    tmp._load_config()
    return tmp.config


def _save_config(config: Dict[str, Any]) -> None:
    from agent import NemesisApp
    from src.core.paths import config_path

    tmp = NemesisApp.__new__(NemesisApp)
    tmp.config_path = config_path()
    tmp.config = config
    tmp._save_config()


def _provider(config: Optional[Dict[str, Any]] = None):
    from providers import create_provider

    return create_provider(config or _load_config())


def _session_or_404(session_id: str):
    s = manager.get(session_id)
    if not s:
        raise HTTPException(404, "Session introuvable")
    return s


def _workspace() -> Path:
    from src.core.paths import resolve_workspace

    return resolve_workspace(_load_config())


def _safe_ws_path(rel: str) -> Path:
    ws = _workspace()
    target = (ws / rel).resolve() if rel else ws
    if target != ws and ws not in target.parents:
        raise HTTPException(400, "Chemin hors du workspace")
    return target


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "sessions": len(manager.sessions)}


# ---------------------------------------------------------------------------
# État global / configuration
# ---------------------------------------------------------------------------


@app.get("/api/state")
async def state():
    config = _load_config()
    from src.core.commands import registry
    import src.core.default_commands  # noqa: F401
    from src.core.paths import USER_CONFIG_DIR, INSTALL_DIR

    nem = config.get("nemapi", {})
    return {
        "provider": config.get("provider", {}),
        "nemapi": {"host": nem.get("host", "127.0.0.1"), "port": nem.get("port", 8090)},
        "workspace": config.get("security", {}).get("workspace", ""),
        "config_dir": str(USER_CONFIG_DIR),
        "install_dir": str(INSTALL_DIR),
        "commands": [
            {"name": c.name, "description": c.description, "usage": c.usage}
            for c in registry.list_commands()
        ],
        "access_modes": [
            {"id": "ask", "label": "Demander", "desc": "Confirmation avant chaque outil sensible (y / n / a)"},
            {"id": "full", "label": "Accès complet", "desc": "Exécute tous les outils sans confirmation"},
            {"id": "readonly", "label": "Lecture seule", "desc": "Seuls les outils de lecture sont autorisés"},
        ],
    }


@app.get("/api/config")
async def get_config():
    return _load_config()


@app.put("/api/config")
async def put_config(update: ConfigUpdate):
    config = _load_config()
    nem = config.setdefault("nemapi", {})
    if update.host:
        host = update.host.strip()
        if "://" in host:
            from urllib.parse import urlparse

            parsed = urlparse(host)
            host = parsed.hostname or host
            if parsed.port and not update.port:
                update.port = parsed.port
        nem["host"] = host
        nem.pop("url", None)
    if update.port:
        nem["port"] = int(update.port)
    if update.model:
        config.setdefault("provider", {})["model"] = update.model
        nem["model"] = update.model
    if update.timeout:
        config.setdefault("provider", {})["timeout"] = int(update.timeout)
    if update.workspace:
        config.setdefault("security", {})["workspace"] = str(Path(update.workspace).expanduser())
    _save_config(config)
    # Reconfigurer les sessions actives à chaud (comme /config dans la CLI)
    for s in manager.sessions.values():
        if s.app is not None:
            try:
                ok, msg = s.app.reconfigure_provider(config)
                s.emit({"type": "system", "level": "info" if ok else "warning", "text": f"Configuration : {msg}"})
            except Exception as exc:  # noqa: BLE001
                s.emit({"type": "error", "message": f"Reconfiguration échouée : {exc}"})
    return {"ok": True, "config": config}


@app.post("/api/config/test")
async def test_config():
    try:
        p = _provider()
        ok = await asyncio.to_thread(p.test_connection)
        return {"ok": bool(ok), "target": p.base_url, "model": p.model}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.get("/api/models")
async def list_models():
    try:
        p = _provider()
        models = await asyncio.to_thread(p.list_models)
        return {"models": models, "current": p.model}
    except Exception as exc:  # noqa: BLE001
        return {"models": [], "current": None, "error": str(exc)}


@app.get("/api/tools")
async def list_tools():
    from src.core.agent_tools import create_registry

    reg = create_registry(str(_workspace()))
    out = []
    for name, r in reg:
        out.append({
            "name": name,
            "kind": r.definition.kind.value,
            "risk": r.risk,
            "description": (r.definition.description or "").strip().split("\n")[0][:200],
            "params": list((r.definition.params_schema or {}).get("properties", {}).keys()),
        })
    return {"tools": sorted(out, key=lambda t: t["name"])}


@app.get("/api/system-prompt", response_class=PlainTextResponse)
async def system_prompt():
    from src.core.agent_tools import create_registry, build_system_prompt

    return build_system_prompt(create_registry(str(_workspace())))


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": manager.list()}


@app.post("/api/sessions")
async def create_session(body: NewSession):
    s = manager.create(
        title=body.title or "Nouvelle conversation",
        access_mode=body.access_mode,
        send_system_prompt=body.send_system_prompt,
    )
    return s.snapshot()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, since: int = 0):
    s = manager.get(session_id)
    if s:
        snap = s.snapshot()
        snap["events"] = [e for e in s.events if e["seq"] > since]
        return snap
    archived = manager.load_archived(session_id)
    if not archived:
        raise HTTPException(404, "Session introuvable")
    archived["archived"] = True
    archived["busy"] = False
    return archived


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    manager.delete(session_id)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/message")
async def send_message(session_id: str, body: Message):
    s = _session_or_404(session_id)
    s.send(body.text)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/respond")
async def respond(session_id: str, body: Respond):
    s = _session_or_404(session_id)
    ok = s.resolve_input(body.request_id, body.value)
    if not ok:
        raise HTTPException(409, "Aucune demande en attente avec cet identifiant")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/interrupt")
async def interrupt(session_id: str):
    _session_or_404(session_id).interrupt()
    return {"ok": True}


@app.post("/api/sessions/{session_id}/access")
async def access(session_id: str, body: AccessMode):
    s = _session_or_404(session_id)
    s.set_access_mode(body.mode)
    return {"ok": True, "access_mode": s.access_mode}


@app.post("/api/sessions/{session_id}/model")
async def session_model(session_id: str, body: ModelChoice):
    s = _session_or_404(session_id)
    s.set_model(body.model)
    config = _load_config()
    config.setdefault("provider", {})["model"] = body.model
    config.setdefault("nemapi", {})["model"] = body.model
    _save_config(config)
    return {"ok": True}


@app.get("/api/sessions/{session_id}/outputs")
async def session_outputs(session_id: str):
    s = _session_or_404(session_id)
    outs = getattr(s.app, "_hidden_outputs", {}) or {}
    return {
        "outputs": [
            {"id": k, "command": v.get("command"), "success": v.get("success"), "size": len(v.get("output", ""))}
            for k, v in sorted(outs.items())
        ]
    }


@app.get("/api/sessions/{session_id}/outputs/{output_id}", response_class=PlainTextResponse)
async def session_output(session_id: str, output_id: int):
    s = _session_or_404(session_id)
    outs = getattr(s.app, "_hidden_outputs", {}) or {}
    if output_id not in outs:
        raise HTTPException(404, "Sortie introuvable")
    return outs[output_id].get("output", "")


@app.get("/api/sessions/{session_id}/history")
async def session_history(session_id: str):
    s = _session_or_404(session_id)
    client = getattr(s.app, "client", None)
    return {"conversation": client.get_conversation() if client else []}


@app.websocket("/ws/sessions/{session_id}")
async def ws_session(ws: WebSocket, session_id: str):
    await ws.accept()
    s = manager.get(session_id)
    if not s:
        await ws.send_text(json.dumps({"type": "error", "message": "Session introuvable"}))
        await ws.close()
        return
    since = 0
    try:
        since = int(ws.query_params.get("since", "0"))
    except ValueError:
        pass
    q = s.subscribe()
    try:
        # rejouer l'historique manquant
        for ev in list(s.events):
            if ev["seq"] > since:
                await ws.send_text(json.dumps(ev, ensure_ascii=False))
        await ws.send_text(json.dumps({"type": "snapshot", **s.snapshot()}, ensure_ascii=False))

        async def reader():
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = msg.get("type")
                if kind == "message":
                    s.send(msg.get("text", ""))
                elif kind == "respond":
                    s.resolve_input(msg.get("request_id", ""), msg.get("value"))
                elif kind == "interrupt":
                    s.interrupt()
                elif kind == "access":
                    s.set_access_mode(msg.get("mode", "ask"))
                elif kind == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

        async def writer():
            while True:
                ev = await q.get()
                await ws.send_text(json.dumps(ev, ensure_ascii=False))

        tasks = [asyncio.create_task(reader()), asyncio.create_task(writer())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            # Récupérer l'exception (déconnexion normale) pour éviter le bruit de log
            t.exception()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        s.unsubscribe(q)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "build"}


@app.get("/api/workspace/tree")
async def workspace_tree(path: str = ""):
    target = _safe_ws_path(path)
    if not target.exists():
        raise HTTPException(404, "Dossier introuvable")
    ws = _workspace()
    entries = []
    try:
        for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if p.name in _IGNORED_DIRS:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append({
                "name": p.name,
                "path": str(p.relative_to(ws)),
                "dir": p.is_dir(),
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
    except PermissionError:
        raise HTTPException(403, "Accès refusé")
    return {"root": str(ws), "path": str(target.relative_to(ws)) if target != ws else "", "entries": entries}


@app.get("/api/workspace/file")
async def workspace_file(path: str):
    target = _safe_ws_path(path)
    if not target.is_file():
        raise HTTPException(404, "Fichier introuvable")
    if target.stat().st_size > 2_000_000:
        raise HTTPException(413, "Fichier trop volumineux")
    try:
        content = target.read_text(encoding="utf-8")
        binary = False
    except UnicodeDecodeError:
        content = ""
        binary = True
    return {"path": path, "content": content, "binary": binary, "size": target.stat().st_size}


@app.get("/api/todo")
async def todo():
    from src.core.tools.todo import _load

    return {"items": _load(str(_workspace()))}


@app.get("/api/git")
async def git_info():
    import subprocess

    ws = _workspace()

    def run(args):
        try:
            return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return ""

    if not (ws / ".git").exists():
        return {"repo": False}
    return {
        "repo": True,
        "branch": run(["rev-parse", "--abbrev-ref", "HEAD"]).strip(),
        "status": run(["status", "--porcelain"]),
        "log": run(["log", "--oneline", "-n", "10"]),
    }


# ---------------------------------------------------------------------------
# MCP / Skills / Agents (mêmes managers que la CLI)
# ---------------------------------------------------------------------------


@app.get("/api/mcp")
async def mcp_list():
    import src.core.default_commands as dc

    dc.mcp_mgr.reload()
    return {"servers": dc.mcp_mgr.list_servers()}


@app.post("/api/mcp")
async def mcp_add(body: MCPServer):
    import src.core.default_commands as dc

    ok, msg = dc.mcp_mgr.add_server(body.name, body.command, description=body.description)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@app.delete("/api/mcp/{name}")
async def mcp_remove(name: str):
    import src.core.default_commands as dc

    ok, msg = dc.mcp_mgr.remove_server(name)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@app.post("/api/mcp/{name}/test")
async def mcp_test(name: str):
    import src.core.default_commands as dc

    ok, msg = await asyncio.to_thread(dc.mcp_mgr.test_server, name)
    return {"ok": ok, "message": msg}


@app.get("/api/skills")
async def skills():
    import src.core.default_commands as dc

    return {"skills": dc.skill_mgr.list_installed()}


@app.get("/api/agents")
async def agents():
    from src.core.agent_manager import get_scheduler

    sched = get_scheduler()
    try:
        return {"agents": sched.list_agents(), "tasks": sched.get_task_status()}
    except Exception as exc:  # noqa: BLE001
        return {"agents": [], "tasks": {}, "error": str(exc)}


# Static assets (après les routes API)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="NEMESIS Web UI")
    parser.add_argument("--host", default=os.environ.get("NEMESIS_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NEMESIS_WEB_PORT", "3080")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("web.server:app", host=args.host, port=args.port, reload=args.reload, log_level="info")


if __name__ == "__main__":
    main()

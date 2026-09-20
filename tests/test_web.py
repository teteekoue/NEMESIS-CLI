"""Tests de l'interface web (API + moteur événementiel), sans serveur NEMAPI réel."""

import json
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    cfg = tmp_path_factory.mktemp("cfg")
    ws = tmp_path_factory.mktemp("ws")
    os.environ["NEMESIS_CONFIG_DIR"] = str(cfg)
    os.environ["NEMESIS_WORKSPACE"] = str(ws)
    # `src.core.paths` peut déjà être importé par d'autres tests : forcer les chemins.
    import src.core.paths as paths

    paths.USER_CONFIG_DIR = cfg
    paths.DEFAULT_WORKSPACE = ws
    # mock NEMAPI sur un port libre
    from web.mock_nemapi import Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (cfg / "config.yaml").write_text(
        f"provider:\n  type: nemapi\n  model: mock-agent\nnemapi:\n  host: 127.0.0.1\n  port: {port}\nsecurity:\n  workspace: {ws}\n"
    )
    yield {"cfg": cfg, "ws": ws, "port": port}
    srv.shutdown()


@pytest.fixture(scope="module")
def client(env):
    from web.server import app

    with TestClient(app) as c:
        yield c


def _drain(client, sid, since=0, until=None, timeout=20, on_event=None):
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/sessions/{sid}", params={"since": since}).json()
        for e in r["events"]:
            since = e["seq"]
            events.append(e)
            if on_event:
                on_event(e)
            if until and until(e):
                return events, since
        time.sleep(0.2)
    return events, since


def test_state_and_tools(client):
    st = client.get("/api/state").json()
    assert any(c["name"] == "help" for c in st["commands"])
    assert {m["id"] for m in st["access_modes"]} == {"ask", "full", "readonly"}
    tools = client.get("/api/tools").json()["tools"]
    names = {t["name"] for t in tools}
    assert {"bash", "read_file", "write_file", "edit", "todo"} <= names
    assert client.get("/api/system-prompt").text.startswith("You are NEMESIS")


def test_models_and_connection(client, env):
    r = client.post("/api/config/test").json()
    assert r["ok"] is True
    models = client.get("/api/models").json()["models"]
    assert any(m["id"] == "mock-agent" for m in models)


def test_full_cycle_with_authorization(client, env):
    s = client.post("/api/sessions", json={"access_mode": "ask", "send_system_prompt": True}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    client.post(f"/api/sessions/{sid}/message", json={"text": "Écris un script hello.py et exécute-le"})

    def approve(e):
        if e["type"] == "auth_request":
            client.post(f"/api/sessions/{sid}/respond", json={"request_id": e["request_id"], "value": "y"})

    events, _ = _drain(client, sid, until=lambda e: e["type"] == "summary", on_event=approve)
    types = [e["type"] for e in events]
    assert "auth_request" in types
    assert types.count("tool_start") == 3
    results = [e for e in events if e["type"] == "tool_result"]
    assert all(r["success"] for r in results), [(r["tool"], r["output"], r.get("error")) for r in results]
    assert (env["ws"] / "hello.py").exists()
    bash = [r for r in results if r["tool"] == "bash"][0]
    assert "Bonjour" in bash["output"]
    assert bash["output_id"] == 1
    outs = client.get(f"/api/sessions/{sid}/outputs").json()["outputs"]
    assert outs[0]["command"] == "python3 hello.py"
    assert "Bonjour" in client.get(f"/api/sessions/{sid}/outputs/1").text
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["stats"]["tool_calls"] == 3
    assert snap["title"].startswith("Écris un script")


def test_denial_is_fed_back(client, env):
    s = client.post("/api/sessions", json={"access_mode": "ask"}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    client.post(f"/api/sessions/{sid}/message", json={"text": "supprime le dossier danger"})

    seen = {}

    def deny(e):
        if e["type"] == "auth_request":
            seen["risk"] = e["risk"]
            client.post(f"/api/sessions/{sid}/respond", json={"request_id": e["request_id"], "value": "n"})

    events, _ = _drain(client, sid, until=lambda e: e["type"] == "summary", on_event=deny)
    assert seen["risk"] == "high"  # rm -rf → high via ToolBridge.risk_for
    assert not any(e["type"] == "tool_start" for e in events)
    last = [e for e in events if e["type"] == "assistant"][-1]["text"]
    assert "refusé" in last


def test_full_access_skips_prompt(client, env):
    s = client.post("/api/sessions", json={"access_mode": "full"}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    client.post(f"/api/sessions/{sid}/message", json={"text": "Explore le workspace"})
    events, _ = _drain(client, sid, until=lambda e: e["type"] == "summary")
    assert not any(e["type"] == "auth_request" for e in events)
    assert [e["tool"] for e in events if e["type"] == "tool_start"] == ["list_dir", "bash", "grep"]


def test_readonly_blocks_writes(client, env):
    s = client.post("/api/sessions", json={"access_mode": "readonly"}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    client.post(f"/api/sessions/{sid}/message", json={"text": "Écris un script hello.py"})
    events, _ = _drain(client, sid, until=lambda e: e["type"] == "summary")
    assert not any(e["type"] == "tool_start" for e in events)
    assert any("lecture seule" in (e.get("text") or "") for e in events if e["type"] == "system")


def test_slash_commands_render_html(client, env):
    s = client.post("/api/sessions", json={}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    client.post(f"/api/sessions/{sid}/message", json={"text": "/status"})
    events, since = _drain(client, sid, until=lambda e: e["type"] == "busy" and not e["busy"])
    sys_events = [e for e in events if e["type"] == "system"]
    assert sys_events and "<pre" in sys_events[0]["html"]
    assert "Etat de la session" in sys_events[0]["text"]
    client.post(f"/api/sessions/{sid}/message", json={"text": "/nope"})
    events, _ = _drain(client, sid, since=since, until=lambda e: e["type"] == "error")
    assert "Commande inconnue" in events[-1]["message"]


def test_workspace_endpoints(client, env):
    tree = client.get("/api/workspace/tree").json()
    assert any(e["name"] == "hello.py" for e in tree["entries"])
    f = client.get("/api/workspace/file", params={"path": "hello.py"}).json()
    assert "date" in f["content"]
    assert client.get("/api/workspace/file", params={"path": "../../etc/passwd"}).status_code == 400
    todo = client.get("/api/todo").json()["items"]
    assert len(todo) >= 2


def test_websocket_replay_and_respond(client, env):
    s = client.post("/api/sessions", json={"access_mode": "ask"}).json()
    sid = s["id"]
    _drain(client, sid, until=lambda e: e["type"] == "ready")
    with client.websocket_connect(f"/ws/sessions/{sid}") as ws:
        first = json.loads(ws.receive_text())
        assert first["type"] == "ready"
        snap = json.loads(ws.receive_text())
        assert snap["type"] == "snapshot"
        ws.send_text(json.dumps({"type": "message", "text": "Écris un script hello"}))
        done = False
        while not done:
            ev = json.loads(ws.receive_text())
            if ev["type"] == "auth_request":
                ws.send_text(json.dumps({"type": "respond", "request_id": ev["request_id"], "value": "a"}))
            if ev["type"] == "summary":
                done = True
    snap = client.get(f"/api/sessions/{sid}").json()
    assert "todo" in snap["authorized_tools"] or snap["stats"]["tool_calls"] >= 1


def test_sessions_list_and_delete(client):
    lst = client.get("/api/sessions").json()["sessions"]
    assert lst
    sid = lst[0]["id"]
    assert client.delete(f"/api/sessions/{sid}").json()["ok"]
    assert sid not in {s["id"] for s in client.get("/api/sessions").json()["sessions"]}

#!/usr/bin/env python3
"""NEMESIS Web UI - Serveur Flask (API + WebSocket)"""
import sys, os, json, subprocess, signal, time, threading, re, pty
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_sock import Sock

sys.path.insert(0, str(Path(__file__).parent.parent))
from bridge_client import create_client_from_config
from tools import ActionExecutor

app = Flask(__name__, static_folder='dist', static_url_path='')
sock = Sock(app)

PROJECT_ROOT = Path(__file__).parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"
LOGS_DIR = PROJECT_ROOT / "web" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

executor = None
bridge = None
config = {}
active_connections = []
bridge_lock = threading.Lock()
initialized = False
pending_action = None

def broadcast(data):
    msg = json.dumps(data)
    dead = []
    for ws in active_connections[:]:
        try:
            ws.send(msg)
        except:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)

def parse_ai_response(resp):
    parsed = {"text": resp, "action": None}
    code_blocks = []
    def save_block(m):
        code_blocks.append(m.group(0))
        return f"___CB{len(code_blocks)-1}___"
    cleaned = re.sub(r'```.*?```', save_block, resp, flags=re.S)
    last_end = cleaned.rfind('</ACTION>')
    if last_end != -1:
        before = cleaned[:last_end]
        last_start = before.rfind('<ACTION')
        if last_start != -1:
            action_clean = cleaned[last_start:last_end + len('</ACTION>')]
            action_full = action_clean
            for i, block in enumerate(code_blocks):
                action_full = action_full.replace(f"___CB{i}___", block)
            type_match = re.match(r'<ACTION\s+type="([\w-]+)">', action_full, re.I)
            if type_match:
                action_type = type_match.group(1).lower()
                prefix_len = len(type_match.group(0))
                action_content = action_full[prefix_len:len(action_full) - len('</ACTION>')].strip()
                parsed["action"] = {"type": action_type, "content": action_content}
    clean_text = re.sub(r'<ACTION.*?>.*?</ACTION>', '', resp, flags=re.S | re.I)
    parsed["text"] = clean_text.strip()
    return parsed

def safe_send(msg):
    with bridge_lock:
        return bridge.send_message(msg)

def send_bridge(msg):
    try:
        return safe_send(msg)
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_and_feedback(act_type, act_content):
    final_res = {}
    block_id = None

    if act_type == "bash":
        p = act_content.split("|", 1)
        mode = p[0].strip().lower() if len(p) > 1 else "synchrone"
        cmd = p[1].strip() if len(p) > 1 else p[0].strip()
        is_async = (mode == "asynchrone")
        block_id = ("async-" if is_async else "sync-") + str(int(time.time() * 1000))
        broadcast({"type": "log_block_create", "block_id": block_id, "block_type": "async" if is_async else "sync", "label": "Bash " + mode.upper()})

        if is_async:
            # ASYNCHRONE : lancer le processus, thread pour streamer les logs
            log_path = WORKSPACE / f"proc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            proc = subprocess.Popen(f"{cmd} > '{log_path}' 2>&1", shell=True, executable="/bin/bash", preexec_fn=os.setsid, cwd=WORKSPACE)
            executor.processes[proc.pid] = {"cmd": cmd, "log": str(log_path), "start": datetime.now().isoformat()}
            broadcast({"type": "log_block_update", "block_id": block_id, "pid": proc.pid})
            final_res = {"success": True, "stdout": f"PID {proc.pid} lance en arriere-plan."}

            def stream_async_log():
                last_pos = 0
                while True:
                    try:
                        os.kill(proc.pid, 0)
                    except OSError:
                        break
                    try:
                        with open(log_path, "r") as lf:
                            lf.seek(last_pos)
                            new = lf.read()
                            if new:
                                for line in new.splitlines(True):
                                    broadcast({"type": "log_line", "block_id": block_id, "line": line})
                                last_pos = lf.tell()
                    except:
                        pass
                    time.sleep(0.5)
                broadcast({"type": "log_block_done", "block_id": block_id})
            t = threading.Thread(target=stream_async_log)
            t.daemon = True
            t.start()
        else:
            # SYNCHRONE : streamer les logs en direct, puis fermer
            try:
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, executable="/bin/bash", cwd=WORKSPACE)
                full_output = []
                for line in iter(process.stdout.readline, ''):
                    if line:
                        full_output.append(line)
                        broadcast({"type": "log_line", "block_id": block_id, "line": line})
                process.wait()
                final_res = {"success": process.returncode == 0, "stdout": "".join(full_output)}
            except Exception as e:
                final_res = {"success": False, "stdout": str(e)}
            broadcast({"type": "log_block_done", "block_id": block_id})
    else:
        try:
            for update in executor.execute_action(act_type, act_content):
                if "partial" in update:
                    broadcast({"type": "log_line", "block_id": "sync-bash", "line": update["line"]})
                else:
                    final_res = update
        except Exception as e:
            final_res = {"success": False, "stdout": str(e)}

    success = final_res.get("success", False)
    output = final_res.get("stdout", "")
    broadcast({"type": "action_result", "success": success, "output": output})
    return success, output

def feedback_loop(initial_text):
    current = initial_text
    iteration = 0
    while current and iteration < 30:
        iteration += 1
        parsed = parse_ai_response(current)
        if parsed.get("text"):
            broadcast({"type": "ai_text", "content": parsed["text"]})
        if parsed.get("action"):
            act = parsed["action"]
            broadcast({"type": "action_start", "action_type": act["type"], "content": act["content"]})
            success, output = execute_and_feedback(act["type"], act["content"])
            fb = f"FEEDBACK:\nAction: {act['type']}\nSucces: {success}\nOutput:\n{output}"
            fb_result = send_bridge(fb)
            if fb_result.get("success"):
                current = fb_result.get("response", "")
            else:
                current = None
        else:
            current = None
    broadcast({"type": "ai_done"})

@app.route('/')
def index():
    return send_from_directory('dist', 'index.html')

@app.route('/setup')
def setup():
    return send_from_directory('dist', 'index.html')

@app.route('/api/config')
def api_config():
    return jsonify({"bridge": config.get("bridge", None) if config else None, "initialized": initialized})

@app.route('/api/init', methods=['POST'])
def api_init():
    global executor, bridge, config, initialized
    data = request.get_json()
    config = {"bridge": {"host": data.get("host", "192.168.1.71"), "port": int(data.get("port", 8080))}, "security": {"workspace": str(data.get("workspace", "./workspace"))}}
    bridge = create_client_from_config(config)
    executor = ActionExecutor(workspace=config["security"]["workspace"], bridge=bridge)
    bridge_ok = bridge.test_connection()
    if not bridge_ok:
        initialized = False
        return jsonify({"success": False, "error": "Bridge injoignable"})
    if data.get("send_prompt", True):
        prompt_path = PROJECT_ROOT / "prompt_system.txt"
        if prompt_path.exists():
            with open(prompt_path) as f:
                prompt = f.read()
            result = send_bridge(prompt)
            initialized = True
            if result.get("success"):
                return jsonify({"success": True, "message": "NEMESIS pret", "bridge_online": True, "prompt_sent": True, "ai_response": result.get("response", "")})
    initialized = True
    return jsonify({"success": True, "message": "NEMESIS pret", "bridge_online": bridge_ok})

@app.route('/api/ask', methods=['POST'])
def api_ask():
    global initialized
    if not bridge or not executor:
        return jsonify({"success": False, "error": "NEMESIS non initialise"})
    if not initialized:
        return jsonify({"success": False, "error": "Initialisation en cours..."})
    data = request.get_json()
    message = data.get("message", "")
    auto_approve = data.get("auto_approve", False)
    def process():
        result = send_bridge(message)
        if not result.get("success"):
            broadcast({"type": "bridge_status", "online": False})
            broadcast({"type": "ai_done"})
            return
        broadcast({"type": "bridge_status", "online": True})
        parsed = parse_ai_response(result.get("response", ""))
        if parsed.get("text"):
            broadcast({"type": "ai_text", "content": parsed["text"]})
        if parsed.get("action"):
            if auto_approve:
                feedback_loop(result.get("response", ""))
            else:
                global pending_action
                pending_action = parsed["action"]
                broadcast({"type": "action_pending", "action_type": parsed["action"]["type"], "content": parsed["action"]["content"][:300]})
        else:
            broadcast({"type": "ai_done"})
    t = threading.Thread(target=process)
    t.daemon = True
    t.start()
    return jsonify({"success": True, "message": "Processing"})

@app.route('/api/approve', methods=['POST'])
def api_approve():
    global pending_action
    data = request.get_json()
    choice = data.get("choice", "y")
    if choice == "n":
        act = pending_action
        pending_action = None
        if act:
            fb = f"FEEDBACK:\nAction: {act['type']}\nSucces: False\nOutput: Action refusee par l'utilisateur"
            result = send_bridge(fb)
            if result.get("success"):
                parsed = parse_ai_response(result.get("response", ""))
                if parsed.get("text"):
                    broadcast({"type": "ai_text", "content": parsed["text"]})
        broadcast({"type": "ai_done"})
        return jsonify({"success": True})
    if choice == "a":
        pending_action = None
        broadcast({"type": "auto_approve_enabled"})
        return jsonify({"success": True})
    act = pending_action
    pending_action = None
    if act:
        def process():
            broadcast({"type": "action_start", "action_type": act["type"], "content": act["content"]})
            success, output = execute_and_feedback(act["type"], act["content"])
            fb = f"FEEDBACK:\nAction: {act['type']}\nSucces: {success}\nOutput:\n{output}"
            result = send_bridge(fb)
            if result.get("success"):
                parsed = parse_ai_response(result.get("response", ""))
                if parsed.get("text"):
                    broadcast({"type": "ai_text", "content": parsed["text"]})
            broadcast({"type": "ai_done"})
        t = threading.Thread(target=process)
        t.daemon = True
        t.start()
    return jsonify({"success": True})

@app.route('/api/kill_process', methods=['POST'])
def api_kill_process():
    data = request.get_json()
    pid = data.get("pid")
    if pid:
        try:
            os.killpg(int(pid), signal.SIGTERM)
            return jsonify({"success": True})
        except:
            pass
    return jsonify({"success": False})

@sock.route('/api/terminal/ws')
def terminal_ws(ws):
    master_fd = None
    pid = None
    try:
        master_fd, slave_fd = pty.openpty()
        pid = os.fork()
        if pid == 0:
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.execve("/bin/bash", ["/bin/bash"], os.environ.copy())
            os._exit(1)
        os.close(slave_fd)
        import fcntl
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        while True:
            try:
                data = ws.receive(timeout=0.05)
                if data:
                    msg = json.loads(data)
                    if msg.get("type") == "input":
                        os.write(master_fd, msg["data"].encode())
            except:
                pass
            try:
                output = os.read(master_fd, 4096)
                if output:
                    ws.send(json.dumps({"type": "output", "data": output.decode("utf-8", errors="replace")}))
            except:
                pass
    except:
        pass
    finally:
        if pid:
            try: os.kill(pid, signal.SIGTERM)
            except: pass
        if master_fd:
            try: os.close(master_fd)
            except: pass

@app.route('/api/workspace/list')
def api_workspace_list():
    files = []
    if WORKSPACE.exists():
        for f in WORKSPACE.iterdir():
            files.append({"name": f.name, "is_dir": f.is_dir(), "path": f.name})
    return jsonify({"files": sorted(files, key=lambda x: (not x["is_dir"], x["name"]))})

@app.route('/api/workspace/read')
def api_workspace_read():
    path = request.args.get("path", "")
    fp = WORKSPACE / path
    if not fp.exists():
        return jsonify({"success": False, "error": "Fichier introuvable"})
    if fp.is_dir():
        items = []
        for f in fp.iterdir():
            items.append({"name": f.name, "is_dir": f.is_dir(), "path": str(f.relative_to(WORKSPACE))})
        return jsonify({"success": True, "is_dir": True, "files": sorted(items, key=lambda x: (not x["is_dir"], x["name"]))})
    try:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return jsonify({"success": True, "content": content, "is_dir": False})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/workspace/save', methods=['POST'])
def api_workspace_save():
    data = request.get_json()
    path = data.get("path", "")
    content = data.get("content", "")
    fp = WORKSPACE / path
    fp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"success": True, "message": "Fichier sauvegarde"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@sock.route('/api/ws')
def ws_route(ws):
    active_connections.append(ws)
    try:
        while True:
            data = ws.receive()
            if data:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    ws.send(json.dumps({"type": "pong"}))
    except:
        pass
    finally:
        if ws in active_connections:
            active_connections.remove(ws)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"NEMESIS Web UI - http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

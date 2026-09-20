"""Mock NEMAPI — serveur de démonstration pour tester l'interface web sans LLM.

Expose la même surface que NEMAPI (``/status``, ``/v1/models``,
``/v1/chat/completions``) et rejoue un scénario scripté : appels d'outils
JSON, puis synthèse lorsque le résultat d'outil revient.

Lancement : ``python -m web.mock_nemapi --port 8090``
Ce serveur n'est PAS une IA : il sert uniquement à valider l'interface.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = [
    {"id": "mock-agent", "owned_by": "mock", "display_name": "Mock Agent (démo)"},
    {"id": "qwen-chat", "owned_by": "mock", "display_name": "Qwen Chat (mock)"},
    {"id": "gemini-chat", "owned_by": "mock", "display_name": "Gemini Chat (mock)"},
]

# état par "session" (le mock est mono-conversation, comme NEMAPI côté serveur)
_STATE = {"step": 0, "scenario": None}


def _tool(tool, **params):
    return "```json\n" + json.dumps({"tool": tool, "parameters": params}, ensure_ascii=False) + "\n```"


def _plan(user_msg: str):
    m = user_msg.lower()
    if "script" in m or "hello" in m:
        return [
            "Je vais créer le script puis l'exécuter.\n\n"
            + _tool("todo", action="add", items=["Créer hello.py", "Exécuter le script"]),
            _tool("write_file", file_path="hello.py",
                  content="from datetime import date\nprint('Bonjour depuis NEMESIS —', date.today().isoformat())\n"),
            "Fichier écrit. Exécution :\n\n" + _tool("bash", command="python3 hello.py", description="Exécuter hello.py"),
            "FINAL:Le script `hello.py` a été créé et exécuté avec succès. Il affiche la date du jour.\n\n"
            "```python\nfrom datetime import date\nprint('Bonjour depuis NEMESIS —', date.today().isoformat())\n```",
        ]
    if "git" in m or "plan" in m:
        return [
            "Je consulte l'état git du workspace.\n\n" + _tool("git", action="status"),
            _tool("todo", action="add", items=["Relire les fichiers modifiés", "Écrire les tests manquants", "Préparer le commit"]),
            "FINAL:Voici le plan de travail proposé (voir le panneau **Todo**) :\n\n1. Relire les fichiers modifiés\n2. Écrire les tests manquants\n3. Préparer le commit",
        ]
    if "supprime" in m or "rm " in m or "danger" in m:
        return [
            "Attention, cette opération est destructive — je demande confirmation.\n\n"
            + _tool("bash", command="rm -rf /tmp/nemesis-demo-dir", description="Supprimer le dossier de démo"),
            "FINAL:Opération terminée (ou refusée selon votre choix).",
        ]
    # défaut : exploration
    return [
        "Je commence par explorer le workspace.\n\n"
        + "```json\n" + json.dumps([
            {"tool": "list_dir", "parameters": {"path": ".", "depth": 2}},
            {"tool": "bash", "parameters": {"command": "uname -a && python3 --version", "description": "Infos système"}},
        ]) + "\n```",
        _tool("grep", pattern="TODO|FIXME", path=".", case_insensitive=True),
        "FINAL:## Résumé du workspace\n\nJ'ai listé le contenu du dossier, vérifié l'environnement système et recherché les marqueurs `TODO`/`FIXME`.\n\n"
        "- Le workspace est prêt pour travailler.\n- Aucune action destructive n'a été effectuée.\n\n"
        "> Ceci est une réponse du **mock NEMAPI** : branchez un vrai serveur NEMAPI dans ⚙ Paramètres pour utiliser un modèle réel.",
    ]


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # silence
        return

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/status"):
            return self._json(200, {"status": "ok", "mock": True})
        if self.path.startswith("/v1/models"):
            return self._json(200, {"object": "list", "data": MODELS})
        return self._json(200, {"name": "mock-nemapi"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        msgs = payload.get("messages") or []
        content = str(msgs[-1].get("content", "")) if msgs else ""
        role = msgs[-1].get("role", "user") if msgs else "user"
        model = payload.get("model", "mock-agent")

        if role == "system" or content.startswith("[SYSTEM INSTRUCTIONS]"):
            reply = "Prompt système reçu. Prêt."
        elif content.startswith("[TOOL RESULT]") or content.startswith("FEEDBACK:"):
            plan = _STATE["scenario"] or []
            _STATE["step"] += 1
            if _STATE["step"] < len(plan):
                reply = plan[_STATE["step"]]
            else:
                reply = "Terminé."
            if "REFUSEE" in content or "refus" in content.lower():
                reply = "FINAL:Vous avez refusé l'exécution — j'arrête ici, rien n'a été modifié."
        else:
            plan = _plan(content)
            _STATE["scenario"] = plan
            _STATE["step"] = 0
            reply = plan[0]

        if reply.startswith("FINAL:"):
            reply = reply[len("FINAL:"):]
        time.sleep(0.6)  # simuler la latence
        return self._json(200, {
            "id": f"mock-{int(time.time()*1000)}",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(content) // 4, "completion_tokens": len(reply) // 4},
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()
    print(f"Mock NEMAPI sur http://{a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

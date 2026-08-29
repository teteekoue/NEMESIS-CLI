#!/usr/bin/env python3
"""Provider nemapi-bridge — API OpenAI-compatible via NEMAPI Bridge (Firefox).

Le contexte de conversation est géré côté navigateur / proxy NEMAPI :
on n'envoie que le message courant (comme le bridge Android), pas l'historique.
"""

import json
import time
from typing import Dict, Any, List

from providers.base import BaseProvider


class NemapiBridgeProvider(BaseProvider):
    """Provider pour NEMAPI Bridge (proxy Python + extension Firefox).

    Endpoint principal : POST /v1/chat/completions (stream=false).
    Config : section nemapi_bridge {host, port} ou provider {host, port}.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8080
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import requests as req

        self.req = req
        nb_cfg = config.get("nemapi_bridge", {})
        # Priorité : section nemapi_bridge > provider.host/port > défauts
        self.host = (
            nb_cfg.get("host")
            or self.provider_config.get("host")
            or self.DEFAULT_HOST
        )
        self.port = int(
            nb_cfg.get("port")
            or self.provider_config.get("port")
            or self.DEFAULT_PORT
        )
        self.base_url = f"http://{self.host}:{self.port}"
        self.model = self.provider_config.get("model", self.DEFAULT_MODEL)
        self.timeout = int(self.provider_config.get("timeout", 180))
        self.max_retries = 3
        self.retry_delay = 3
        self._conversation: List[Dict[str, str]] = []

    def test_connection(self) -> bool:
        """Teste /status puis fallback sur la racine."""
        try:
            resp = self.req.get(f"{self.base_url}/status", timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        try:
            self.req.head(f"{self.base_url}/", timeout=5)
            return True
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """Liste les modèles exposés par /v1/models."""
        try:
            resp = self.req.get(f"{self.base_url}/v1/models", timeout=10)
            if resp.status_code != 200:
                return self._default_models()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                mid = m.get("id")
                if mid:
                    models.append({
                        "id": mid,
                        "owned_by": m.get("owned_by", "nemapi-bridge"),
                    })
            return models or self._default_models()
        except Exception:
            return self._default_models()

    def _default_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "deepseek-chat", "owned_by": "nemapi-bridge"},
            {"id": "nemapi-local", "owned_by": "nemapi-bridge"},
        ]

    def send_message(self, message: str, role: str = "user") -> Dict[str, Any]:
        """Envoie uniquement le message courant au format OpenAI.
        Le contexte est géré côté API/Bridge, pas ici.
        """
        if role == "tool_result":
            send_content = (
                "[TOOL RESULT]\n"
                f"{message}"
            )
            send_role = "user"
        else:
            send_role = role
            send_content = message

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                payload = {
                    "model": self.model,
                    "messages": [{"role": send_role, "content": send_content}],
                    "stream": False,
                }
                resp = self.req.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )

                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
                    return {"success": False, "error": last_error}

                data = resp.json()
                reply = self._extract_reply(data)

                # Pas d'historique local inutile — on se comporte comme un bridge stateless
                return {"success": True, "response": reply}

            except self.req.exceptions.Timeout:
                last_error = f"Timeout apres {self.timeout}s"
            except self.req.exceptions.ConnectionError as e:
                last_error = f"Connexion refusee: {e}"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        return {
            "success": False,
            "error": f"Echec apres {self.max_retries} tentatives: {last_error}",
        }

    def _extract_reply(self, data: Dict[str, Any]) -> str:
        """Extrait le texte assistant, y compris tool_calls sérialisés."""
        choices = data.get("choices") or []
        if not choices:
            if isinstance(data.get("response"), str):
                return data["response"]
            if isinstance(data.get("content"), str):
                return data["content"]
            return json.dumps(data, ensure_ascii=False)

        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        # Si NEMAPI a déjà parsé des tool_calls OpenAI, on les reformate
        # en bloc ```json pour le parseur de l'agent.
        if tool_calls:
            parts = []
            if content and str(content).strip():
                parts.append(str(content).strip())
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}
                if name:
                    tool_obj = {"tool": name, "parameters": args}
                    parts.append(
                        "```json\n"
                        + json.dumps(tool_obj, ensure_ascii=False, indent=2)
                        + "\n```"
                    )
            return "\n\n".join(parts) if parts else content

        if content:
            return str(content)

        # Fallback delta / text
        for key in ("text", "response", "result"):
            if key in choice and choice[key]:
                return str(choice[key])
        return ""

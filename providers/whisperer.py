"""Provider Whisperer - proxy local llm-whisperer (API OpenAI-compatible).
Utilise des requetes HTTP directes (requests) sans dependance au SDK openai.
"""

import json
import re
from typing import Dict, Any

from providers.base import BaseProvider


class WhispererProvider(BaseProvider):
    """Provider pour llm-whisperer, proxy local compatible OpenAI."""

    DEFAULT_BASE_URL = "http://localhost:9777/v1"
    DEFAULT_MODEL = "deepseek"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import requests as req
        self.req = req
        self.base_url = self.provider_config.get("base_url", self.DEFAULT_BASE_URL)
        self.model = self.provider_config.get("model", self.DEFAULT_MODEL)
        self.api_key = self.provider_config.get("api_key", "sk-dummy-key")
        self._conversation = []
        self._system_prompt_sent = False

    def test_connection(self) -> bool:
        """Teste la connexion au proxy whisperer via l'endpoint /health."""
        try:
            health_url = self.base_url.replace("/v1", "") + "/health"
            resp = self.req.get(health_url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self):
        """Whisperer n'expose pas la liste des modeles via l'API.
        Retourne les providers courants supportes par llm-whisperer.
        """
        return [
            {"id": "deepseek", "owned_by": "DeepSeek"},
            {"id": "qwen", "owned_by": "Qwen"},
            {"id": "chatgpt", "owned_by": "OpenAI"},
            {"id": "claude", "owned_by": "Anthropic"},
        ]

    def send_message(self, message: str) -> Dict[str, Any]:
        """Envoie un message au proxy whisperer (format OpenAI-compatible)."""
        try:
            if not self._system_prompt_sent and self._is_system_prompt(message):
                self._conversation.append({"role": "system", "content": message})
                self._system_prompt_sent = True
                return {"success": True, "response": "Systeme initialise. Pret a t'assister."}

            self._conversation.append({"role": "user", "content": message})

            if len(self._conversation) > 51:
                system_msgs = [m for m in self._conversation if m["role"] == "system"]
                rest = [m for m in self._conversation if m["role"] != "system"]
                self._conversation = system_msgs + rest[-50:]

            payload = {
                "model": self.model,
                "messages": self._conversation,
                "max_tokens": 4096,
                "temperature": 0.7,
            }

            resp = self.req.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120,
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}

            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not reply and "message" in data:
                reply = data["message"].get("content", "")

            self._conversation.append({"role": "assistant", "content": reply})
            return {"success": True, "response": reply}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _is_system_prompt(self, message: str) -> bool:
        """Detecte si le message est le prompt systeme initial."""
        return (
            message.startswith("# ")
            and "NEMESIS" in message
            and len(message) > 500
        ) or (
            "LOI 1" in message and "LOI 2" in message
        )

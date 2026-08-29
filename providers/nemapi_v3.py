#!/usr/bin/env python3
"""Provider nemapi-v3 — API OpenAI-compatible via NEMAPI v3 (proxy Python).

Le contexte de conversation est géré côté navigateur / proxy NEMAPI v3 :
on n'envoie que le message courant (comme le bridge Android), pas l'historique.

Ce provider est optimisé pour NEMAPI v3 qui a une architecture simplifiée :
- 4 modèles standard : deepseek-chat, qwen-chat, claude-chat, gemini-chat
- Pas de contexte incrémental
- Auto-configuration des onglets fournisseurs
"""

import json
import time
from typing import Dict, Any, List

from providers.base import BaseProvider


class NemapiV3Provider(BaseProvider):
    """Provider pour NEMAPI v3 (proxy Python + extension Firefox).

    Endpoint principal : POST /v1/chat/completions (stream=false).
    Config : section nemapi_v3 {host, port, model} ou provider {host, port, model}.
    
    Modèles disponibles : deepseek-chat, qwen-chat, claude-chat, gemini-chat
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8080
    DEFAULT_MODEL = "qwen-chat"  # Modèle par défaut
    
    # Liste des 4 modèles standard de NEMAPI v3
    AVAILABLE_MODELS = [
        "deepseek-chat",
        "qwen-chat", 
        "claude-chat",
        "gemini-chat"
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import requests as req

        self.req = req
        nv3_cfg = config.get("nemapi_v3", {})
        # Priorité : section nemapi_v3 > provider.host/port/model > défauts
        self.host = (
            nv3_cfg.get("host")
            or self.provider_config.get("host")
            or self.DEFAULT_HOST
        )
        self.port = int(
            nv3_cfg.get("port")
            or self.provider_config.get("port")
            or self.DEFAULT_PORT
        )
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Configuration du modèle - peut être spécifié ou choisi parmi les 4 disponibles
        self.model = (
            nv3_cfg.get("model")
            or self.provider_config.get("model")
            or self.DEFAULT_MODEL
        )
        
        # Vérifier que le modèle est valide
        if self.model not in self.AVAILABLE_MODELS:
            # Si le modèle n'est pas dans la liste, utiliser le modèle par défaut
            self.model = self.DEFAULT_MODEL
        
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
        """Liste les 4 modèles standard de NEMAPI v3."""
        models = []
        for model_id in self.AVAILABLE_MODELS:
            models.append({
                "id": model_id,
                "owned_by": "nemapi-v3",
                "display_name": model_id.replace("-", " ").title()
            })
        return models

    def send_message(self, message: str, role: str = "user") -> Dict[str, Any]:
        """Envoie uniquement le message courant au format OpenAI.
        Le contexte est géré côté API/Bridge, pas ici.
        
        NEMAPI v3 ne gère pas le contexte incrémental, donc on envoie
        uniquement le message courant sans historique.
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

                text = resp.text
                
                # D'abord, essayer de parser comme JSON normal (non-streaming)
                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and 'choices' in data:
                        reply = self._extract_reply(data)
                        return {"success": True, "response": reply}
                except json.JSONDecodeError:
                    pass
                
                # Si ce n'est pas du JSON normal, vérifier si c'est du streaming SSE
                if "data: {" in text or "data:{" in text:
                    full_content = ""
                    for line in text.split('\n'):
                        line = line.strip()
                        if line.startswith('data: '):
                            chunk_data = line[6:]
                        elif line.startswith('data:'):
                            chunk_data = line[5:]
                        else:
                            continue
                            
                        if chunk_data == '[DONE]':
                            continue
                        try:
                            chunk = json.loads(chunk_data)
                            if 'choices' in chunk and chunk['choices']:
                                delta = chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    full_content += content
                        except json.JSONDecodeError:
                            continue
                    
                    if full_content:
                        return {"success": True, "response": full_content}
                
                # Si aucun contenu n'a été extrait, retourner une erreur
                return {"success": False, "error": f"Aucun contenu extrait de la réponse: {text[:200]}"}

                # Pas d'historique local inutile — on se comporte comme un bridge stateless
                return {"success": True, "response": reply}

            except self.req.exceptions.Timeout:
                last_error = f"Timeout après {self.timeout}s"
            except self.req.exceptions.ConnectionError as e:
                last_error = f"Connexion refusée: {e}"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        return {
            "success": False,
            "error": f"Échec après {self.max_retries} tentatives: {last_error}",
        }

    def _extract_reply(self, data: Any) -> str:
        """Extrait le texte assistant, y compris tool_calls sérialisés."""
        if not isinstance(data, dict):
            # Si data n'est pas un dict, c'est probablement une réponse non-structurée
            return str(data)
        
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

    def set_model(self, model: str) -> bool:
        """Change le modèle utilisé."""
        if model in self.AVAILABLE_MODELS:
            self.model = model
            return True
        return False

    def get_available_models(self) -> List[str]:
        """Retourne la liste des modèles disponibles."""
        return list(self.AVAILABLE_MODELS)

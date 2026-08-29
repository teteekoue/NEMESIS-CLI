"""Providers OpenAI-compatibles : Groq, Nvidia NIM, Fireworks, Cohere, Together AI.
Tous utilisent le SDK openai avec des base_url et models differents.
Supporte le function calling natif quand des outils sont fournis via send_message_with_tools()."""

from typing import Dict, Any, List, Optional
import json
import re

from providers.base import BaseProvider

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAICompatibleProvider(BaseProvider):
    """Provider generique pour toute API compatible OpenAI."""

    DEFAULT_BASE_URL: str = ""
    DEFAULT_MODEL: str = ""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "Le package 'openai' est requis. Installez-le avec: pip install openai"
            )

        self.api_key = self.provider_config.get("api_key", "")
        self.base_url = self.provider_config.get("base_url", self.DEFAULT_BASE_URL)
        self.model = self.provider_config.get("model", self.DEFAULT_MODEL)
        self.temperature = float(self.provider_config.get("temperature", 0.7))
        self.max_tokens = int(self.provider_config.get("max_tokens", 4096))

        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self._conversation = []
        self._system_prompt_sent = False
        self._tools_cache: Optional[List[dict]] = None

        if not self.api_key:
            raise ValueError(
                f"Cle API manquante pour le provider '{self.provider_config.get('type')}'. "
                "Ajoutez 'api_key' dans la section 'provider' de config.yaml."
            )

    def test_connection(self) -> bool:
        """Teste la connexion en listant les modeles disponibles."""
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """Liste les modeles disponibles via l'API."""
        try:
            response = self._client.models.list()
            models = []
            for m in response.data:
                model_id = m.id
                if model_id:
                    models.append({
                        "id": model_id,
                        "owned_by": getattr(m, "owned_by", "unknown"),
                    })
            models.sort(key=lambda x: x["id"])
            return models
        except Exception:
            return []

    def reset_conversation(self):
        """Efface l'historique de conversation."""
        self._conversation = []
        self._system_prompt_sent = False
        self._tools_cache = None

    def set_tools(self, tools: List[dict]):
        """Configure les outils disponibles pour le function calling."""
        self._tools_cache = tools

    def send_message(self, message: str) -> Dict[str, Any]:
        """Envoie un message via l'API OpenAI-compatible avec conservation du contexte."""
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

            kwargs = dict(
                model=self.model,
                messages=self._conversation,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if self._tools_cache:
                kwargs["tools"] = self._tools_cache
                kwargs["tool_choice"] = "auto"

            response = self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                return self._handle_tool_call_response(choice)

            reply = choice.message.content or ""
            self._conversation.append({"role": "assistant", "content": reply})

            return {"success": True, "response": reply}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_tool_call_response(self, choice) -> Dict[str, Any]:
        """Convertit les tool_calls natifs en format compatible avec l'agent existant."""
        message = choice.message
        self._conversation.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        })

        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        try:
            params = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            params = {}

        return {
            "success": True,
            "response": message.content or "",
            "tool_call": {"type": tool_name, "content": params},
            "tool_call_id": tool_call.id,
        }

    def send_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> Dict[str, Any]:
        """Envoie le resultat d'un outil au LLM."""
        try:
            self._conversation.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })

            kwargs = dict(
                model=self.model,
                messages=self._conversation,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            if self._tools_cache:
                kwargs["tools"] = self._tools_cache
                kwargs["tool_choice"] = "auto"

            response = self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                return self._handle_tool_call_response(choice)

            reply = choice.message.content or ""
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


class GroqProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "llama-3.1-8b-instant"


class NvidiaNimProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"


class XaiProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-beta"


class OpenRouterProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openai/gpt-4o"


class OllamaProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "llama3.1"


class FireworksProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"
    DEFAULT_MODEL = "accounts/fireworks/models/llama-v3p1-8b-instruct"


class CohereProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.cohere.com/v1"
    DEFAULT_MODEL = "command-r-plus"


def list_models_for_provider(provider_type: str, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Helper: cree un provider temporaire, liste ses modeles, et le detruit."""
    config = {"provider": {"type": provider_type, "api_key": api_key}}
    if base_url:
        config["provider"]["base_url"] = base_url

    try:
        from providers import create_provider
        provider = create_provider(config)
        models = provider.list_models()
        model_ids = [m["id"] for m in models]
        return {"success": True, "models": model_ids, "count": len(model_ids)}
    except Exception as e:
        return {"success": False, "error": str(e)}

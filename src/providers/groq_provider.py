"""Provider Groq avec function calling natif."""
import httpx
from .base import BaseProvider, ProviderResponse


class GroqProvider(BaseProvider):
    def __init__(self, **kwargs):
        kwargs.setdefault("base_url", "https://api.groq.com/openai/v1")
        kwargs.setdefault("model", "llama-3.3-70b-versatile")
        super().__init__(**kwargs)

    def chat(self, messages: list, tools: list = None) -> ProviderResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = self._convert_tools_to_native(tools)
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return ProviderResponse(content=f"Erreur Groq: {e}", finish_reason="error")

        choice = data.get("choices", [{}])[0].get("message", {})
        content = choice.get("content") or ""
        raw_tool_calls = choice.get("tool_calls") or []
        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": func.get("arguments", "{}")
            })
        usage_data = data.get("usage", {})
        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0)
            },
            raw=data,
            finish_reason=choice.get("finish_reason", "stop")
        )

    def list_models(self) -> list:
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]

    def test_connection(self) -> bool:
        try:
            return len(self.list_models()) > 0
        except Exception:
            return False

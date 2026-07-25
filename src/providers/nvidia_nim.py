"""Provider NVIDIA NIM (format OpenAI-compatible)."""
import httpx
from .base import BaseProvider, ProviderResponse


class NVIDIANIMProvider(BaseProvider):
    def __init__(self, **kwargs):
        kwargs.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
        kwargs.setdefault("model", "meta/llama-3.1-70b-instruct")
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
            return ProviderResponse(content=f"Erreur NVIDIA NIM: {e}", finish_reason="error")

        choice = data.get("choices", [{}])[0].get("message", {})
        content = choice.get("content") or ""
        raw_tc = choice.get("tool_calls") or []
        tool_calls = [{"id": t["id"], "name": t["function"]["name"], "arguments": t["function"]["arguments"]} for t in raw_tc]
        u = data.get("usage", {})
        return ProviderResponse(
            content=content, tool_calls=tool_calls,
            usage={"prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0), "total_tokens": u.get("total_tokens", 0)},
            raw=data, finish_reason=choice.get("finish_reason", "stop")
        )

    def list_models(self) -> list:
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                resp.raise_for_status()
                return [m["id"] for m in resp.json().get("data", [])]
        except Exception:
            return ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-405b-instruct", "mistralai/mixtral-8x22b-instruct-v0.1"]

    def test_connection(self) -> bool:
        try:
            return len(self.list_models()) > 0
        except Exception:
            return False

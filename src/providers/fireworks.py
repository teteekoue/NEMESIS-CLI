"""Provider Fireworks AI (OpenAI-compatible)."""
import httpx
from .base import BaseProvider, ProviderResponse

class FireworksProvider(BaseProvider):
    def __init__(self, **kw):
        kw.setdefault("base_url", "https://api.fireworks.ai/inference/v1")
        kw.setdefault("model", "accounts/fireworks/models/llama-v3p1-70b-instruct")
        super().__init__(**kw)

    def chat(self, messages, tools=None):
        payload = {"model": self.model, "messages": messages, "max_tokens": self.max_tokens, "temperature": self.temperature}
        if tools: payload["tools"] = tools
        try:
            with httpx.Client(timeout=120.0) as c:
                r = c.post(f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
                r.raise_for_status(); data = r.json()
        except Exception as e:
            return ProviderResponse(content=f"Erreur Fireworks: {e}", finish_reason="error")
        ch = data.get("choices", [{}])[0].get("message", {})
        tc = [{"id": t["id"], "name": t["function"]["name"], "arguments": t["function"]["arguments"]} for t in (ch.get("tool_calls") or [])]
        u = data.get("usage", {})
        return ProviderResponse(content=ch.get("content") or "", tool_calls=tc,
            usage={"prompt_tokens": u.get("prompt_tokens",0), "completion_tokens": u.get("completion_tokens",0), "total_tokens": u.get("total_tokens",0)},
            raw=data, finish_reason=ch.get("finish_reason", "stop"))

    def list_models(self):
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                r.raise_for_status(); return [m["id"] for m in r.json().get("data", [])]
        except: return [self.model]

    def test_connection(self):
        try: return len(self.list_models()) > 0
        except: return False

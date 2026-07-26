"""Provider Cohere (format v2 avec tool calling)."""
import json, httpx
from .base import BaseProvider, ProviderResponse

class CohereProvider(BaseProvider):
    def __init__(self, **kw):
        kw.setdefault("base_url", "https://api.cohere.com/v2")
        kw.setdefault("model", "command-r-plus")
        super().__init__(**kw)

    def chat(self, messages, tools=None):
        payload = {"model": self.model, "messages": messages, "max_tokens": self.max_tokens, "temperature": self.temperature}
        if tools:
            payload["tools"] = self._convert_tools_to_native(tools)
        try:
            with httpx.Client(timeout=120.0) as c:
                r = c.post(f"{self.base_url}/chat",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
                r.raise_for_status(); data = r.json()
        except Exception as e:
            return ProviderResponse(content=f"Erreur Cohere: {e}", finish_reason="error")
        msg = data.get("message", {})
        content = ""
        for block in (msg.get("content") or []):
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")
        tc_raw = msg.get("tool_calls") or []
        tc = []
        for t in tc_raw:
            args = t.get("arguments", t.get("input", {}))
            if isinstance(args, dict):
                args = json.dumps(args)
            tc.append({
                "id": t.get("id", t.get("tool_call_id", "")),
                "name": t.get("name", t.get("function", {}).get("name", "")),
                "arguments": args
            })
        u = data.get("usage", {})
        return ProviderResponse(content=content, tool_calls=tc,
            usage={"prompt_tokens": u.get("input_tokens",0), "completion_tokens": u.get("output_tokens",0), "total_tokens": u.get("input_tokens",0)+u.get("output_tokens",0)},
            raw=data, finish_reason=msg.get("finish_reason", "stop"))

    def _convert_tools_to_native(self, tools):
        if not tools:
            return None
        result = []
        for t in tools:
            func = t.get("function", t)
            result.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameter_definitions": func.get("parameters", {}).get("properties", {})
            })
        return result

    def list_models(self):
        return ["command-r-plus", "command-r", "command-r-08-2024", "command-light"]

    def test_connection(self):
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(f"{self.base_url}/chat", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5})
                return r.status_code < 500
        except: return False

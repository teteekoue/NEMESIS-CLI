"""Provider API Bridge - Reverse engineered, extraction JSON du texte."""
import re, json, time
import httpx
from .base import BaseProvider, ProviderResponse

class APIBridgeProvider(BaseProvider):
    def __init__(self, **kw):
        kw.setdefault("base_url", "http://192.168.1.67:8080")
        kw.setdefault("model", "bridge-default")
        kw.setdefault("api_key", "")
        super().__init__(**kw)
        self.max_retries = 3
        self.poll_interval = 3
        self.max_polls = 200

    def chat(self, messages, tools=None):
        last_msg = messages[-1]["content"] if messages else ""
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=30.0) as c:
                    r = c.get(f"{self.base_url}/ask", params={"q": last_msg})
                    job_id = r.text.strip()
                if not job_id or len(job_id) < 3:
                    if attempt < self.max_retries: time.sleep(5); continue
                    return ProviderResponse(content="Job ID invalide", finish_reason="error")
                for _ in range(self.max_polls):
                    with httpx.Client(timeout=10.0) as c:
                        r = c.get(f"{self.base_url}/result?id={job_id}")
                    result = r.text.strip()
                    if result == "STILL_WORKING": time.sleep(self.poll_interval); continue
                    if result == "Job introuvable": continue
                    return self._parse_bridge_response(result)
                return ProviderResponse(content="Timeout apres 10 min", finish_reason="error")
            except Exception as e:
                if attempt == self.max_retries:
                    return ProviderResponse(content=f"Erreur Bridge: {e}", finish_reason="error")
                time.sleep(5)
        return ProviderResponse(content="Echec Bridge", finish_reason="error")

    def _parse_bridge_response(self, text):
        tool_calls = []
        content = text
        # Chercher des tool calls JSON dans la réponse
        patterns = [
            r'```json\s*(\{[^`]*?"tool_calls"\s*:\s*\[[^\]]*\][^`]*?\})\s*```',
            r'```json\s*(\{"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\})\s*```',
            r'(\{"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\})',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                    if "tool_calls" in parsed:
                        for tc in parsed["tool_calls"]:
                            tool_calls.append({"id": tc.get("id", "bridge_0"), "name": tc.get("name", ""), "arguments": json.dumps(tc.get("arguments", {}))})
                        content = text[:m.start()] + text[m.end():]
                    elif "name" in parsed:
                        tool_calls.append({"id": "bridge_0", "name": parsed["name"], "arguments": json.dumps(parsed.get("arguments", {}))})
                        content = text[:m.start()] + text[m.end():]
                except json.JSONDecodeError: pass
        return ProviderResponse(content=content.strip(), tool_calls=tool_calls, finish_reason="stop")

    def list_models(self): return ["bridge-default"]
    def test_connection(self):
        try:
            with httpx.Client(timeout=10.0) as c: c.head(self.base_url); return True
        except: return False

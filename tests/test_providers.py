import pytest
import os, sys, json, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.base import ProviderResponse, BaseProvider
from src.providers.groq_provider import GroqProvider
from src.providers.nvidia_nim import NVIDIANIMProvider
from src.providers.openrouter import OpenRouterProvider
from src.providers.fireworks import FireworksProvider
from src.providers.cohere_provider import CohereProvider
from src.providers.custom_openai import CustomOpenAIProvider
from src.providers.api_bridge import APIBridgeProvider
from src.providers import PROVIDER_REGISTRY


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class TestBaseProvider:
    def test_provider_response_defaults(self):
        resp = ProviderResponse()
        assert resp.content == ""
        assert resp.tool_calls == []
        assert resp.finish_reason == "stop"
        assert resp.usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_provider_initialization(self):
        class TestProvider(BaseProvider):
            def chat(self, messages, tools=None):
                return ProviderResponse(content="test")
            def list_models(self):
                return ["test-model"]
            def test_connection(self):
                return True

        prov = TestProvider(api_key="key123", base_url="http://test/", model="test-model")
        assert prov.api_key == "key123"
        assert prov.base_url == "http://test"
        assert prov.model == "test-model"
        assert prov.max_tokens == 8192
        assert prov.temperature == 0.7
        assert prov.validate_config()

    def test_validate_config_no_api_key(self):
        class TestProvider(BaseProvider):
            def chat(self, messages, tools=None):
                return ProviderResponse()
            def list_models(self):
                return []
            def test_connection(self):
                return False

        prov = TestProvider(api_key="")
        assert not prov.validate_config()

    def test_convert_tools_to_native(self):
        class TestProvider(BaseProvider):
            def chat(self, m, t=None):
                return ProviderResponse()
            def list_models(self):
                return []
            def test_connection(self):
                return False

        prov = TestProvider()
        tools = [{"type": "function", "function": {"name": "test"}}]
        assert prov._convert_tools_to_native(tools) == tools
        assert prov._convert_tools_to_native(None) is None


class TestGroqProvider:
    def test_default_config(self):
        prov = GroqProvider(api_key="test")
        assert "groq.com" in prov.base_url
        assert "llama" in prov.model.lower()

    def test_chat_error_handling(self, monkeypatch):
        def mock_post(*args, **kwargs):
            raise Exception("Network error")

        monkeypatch.setattr("httpx.Client.post", mock_post)
        prov = GroqProvider(api_key="test")
        resp = prov.chat([{"role": "user", "content": "hello"}])
        assert "Erreur" in resp.content
        assert resp.finish_reason == "error"

    def test_chat_success(self, monkeypatch):
        def mock_post(self, *args, **kwargs):
            return MockResponse(200, {
                "choices": [{
                    "message": {
                        "content": "Hello!",
                        "role": "assistant"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            })

        monkeypatch.setattr("httpx.Client.post", mock_post)
        prov = GroqProvider(api_key="test")
        resp = prov.chat([{"role": "user", "content": "hello"}])
        assert resp.content == "Hello!"
        assert resp.finish_reason == "stop"
        assert resp.usage["total_tokens"] == 15


class TestCohereProvider:
    def test_default_config(self):
        prov = CohereProvider(api_key="test")
        assert "cohere.com" in prov.base_url
        assert "command" in prov.model

    def test_tool_conversion(self):
        prov = CohereProvider(api_key="test")
        tools = [{
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"]
                }
            }
        }]
        result = prov._convert_tools_to_native(tools)
        assert len(result) == 1
        assert result[0]["name"] == "bash"
        assert result[0]["description"] == "Execute command"
        assert "parameter_definitions" in result[0]


class TestOpenRouterProvider:
    def test_default_config(self):
        prov = OpenRouterProvider(api_key="test")
        assert "openrouter.ai" in prov.base_url
        assert "llama" in prov.model.lower()


class TestNVIDIANIMProvider:
    def test_default_config(self):
        prov = NVIDIANIMProvider(api_key="test")
        assert "nvidia.com" in prov.base_url
        assert "llama" in prov.model.lower()


class TestFireworksProvider:
    def test_default_config(self):
        prov = FireworksProvider(api_key="test")
        assert "fireworks.ai" in prov.base_url


class TestCustomOpenAIProvider:
    def test_default_config(self):
        prov = CustomOpenAIProvider()
        assert prov.model == "gpt-3.5-turbo"


class TestProviderRegistry:
    def test_all_providers_registered(self):
        expected = {"groq", "nvidia_nim", "openrouter", "fireworks", "cohere", "api_bridge", "custom_openai"}
        assert set(PROVIDER_REGISTRY.keys()) == expected

    def test_providers_are_classes(self):
        for name, cls in PROVIDER_REGISTRY.items():
            assert issubclass(cls, BaseProvider), f"{name} is not a BaseProvider"

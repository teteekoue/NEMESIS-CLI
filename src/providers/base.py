"""Provider de base abstrait et réponse standardisée."""
from dataclasses import dataclass, field
from typing import Any, List
from abc import ABC, abstractmethod

@dataclass
class ProviderResponse:
    content: str = ""
    tool_calls: List[dict] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    raw: Any = None
    finish_reason: str = "stop"

class BaseProvider(ABC):
    def __init__(self, api_key: str = "", base_url: str = "", model: str = "",
                 max_tokens: int = 8192, temperature: float = 0.7):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    def chat(self, messages: list, tools: list = None) -> ProviderResponse: pass

    @abstractmethod
    def list_models(self) -> list: pass

    @abstractmethod
    def test_connection(self) -> bool: pass

    def validate_config(self) -> bool:
        if not self.api_key and self.__class__.__name__ != "APIBridgeProvider":
            return False
        return True

    def _convert_tools_to_native(self, tools: list) -> list:
        return tools if tools else None

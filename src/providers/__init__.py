from .base import BaseProvider, ProviderResponse
from .groq_provider import GroqProvider
from .nvidia_nim import NVIDIANIMProvider
from .openrouter import OpenRouterProvider
from .fireworks import FireworksProvider
from .cohere_provider import CohereProvider
from .api_bridge import APIBridgeProvider
from .custom_openai import CustomOpenAIProvider

PROVIDER_REGISTRY = {
    "groq": GroqProvider, "nvidia_nim": NVIDIANIMProvider,
    "openrouter": OpenRouterProvider, "fireworks": FireworksProvider,
    "cohere": CohereProvider, "api_bridge": APIBridgeProvider,
    "custom_openai": CustomOpenAIProvider,
}

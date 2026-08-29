#!/usr/bin/env python3
"""Fabrique de providers pour NEMESIS CLI."""

from typing import Dict, Any
from providers.base import BaseProvider
from providers.bridge import BridgeProvider
from providers.nemapi_bridge import NemapiBridgeProvider
from providers.nemapi_v3 import NemapiV3Provider
from providers.openai_compatible import (
    GroqProvider,
    NvidiaNimProvider,
    XaiProvider,
    OpenRouterProvider,
    OllamaProvider,
    FireworksProvider,
    CohereProvider,
)
from providers.whisperer import WhispererProvider

PROVIDER_MAP = {
    "bridge": BridgeProvider,
    "nemapi_bridge": NemapiBridgeProvider,
    "nemapi-v3": NemapiV3Provider,
    "groq": GroqProvider,
    "nvidia": NvidiaNimProvider,
    "nvidia_nim": NvidiaNimProvider,
    "xai": XaiProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
    "fireworks": FireworksProvider,
    "cohere": CohereProvider,
    "whisperer": WhispererProvider,
}


def create_provider(config: Dict[str, Any]) -> BaseProvider:
    """Cree le provider approprie selon la configuration."""
    provider_config = config.get("provider", {})
    provider_type = provider_config.get("type", "bridge")

    provider_cls = PROVIDER_MAP.get(provider_type)
    if provider_cls is None:
        available = ", ".join(PROVIDER_MAP.keys())
        raise ValueError(
            f"Provider inconnu: '{provider_type}'. Disponibles: {available}"
        )

    if provider_type in ("bridge", "nemapi_bridge", "nemapi-v3"):
        return provider_cls(config)

    if provider_type == "whisperer":
        api_key = provider_config.get("api_key", "sk-dummy-key")
        if not provider_config.get("api_key"):
            provider_config["api_key"] = api_key
        return provider_cls(config)

    api_key = provider_config.get("api_key", "")
    if not api_key:
        raise ValueError(
            f"Cle API manquante pour '{provider_type}'. Utilisez /provider pour configurer."
        )

    return provider_cls(config)


def list_providers() -> list:
    """Liste les providers disponibles."""
    return list(PROVIDER_MAP.keys())

#!/usr/bin/env python3
"""Fabrique de providers pour NEMESIS CLI."""

from typing import Dict, Any
from providers.base import BaseProvider
from providers.nemapi_v3 import NemapiV3Provider

PROVIDER_MAP = {
    "nemapi": NemapiV3Provider,
}


def create_provider(config: Dict[str, Any]) -> BaseProvider:
    """Cree le provider approprie selon la configuration."""
    provider_config = config.get("provider", {})
    provider_type = provider_config.get("type", "nemapi")

    provider_cls = PROVIDER_MAP.get(provider_type)
    if provider_cls is None:
        available = ", ".join(PROVIDER_MAP.keys())
        raise ValueError(
            f"Provider inconnu: '{provider_type}'. Disponibles: {available}"
        )

    if provider_type in PROVIDER_MAP:
        return provider_cls(config)
    raise ValueError(f"Provider non supporte: {provider_type}")


def list_providers() -> list:
    """Liste les providers disponibles."""
    return list(PROVIDER_MAP.keys())

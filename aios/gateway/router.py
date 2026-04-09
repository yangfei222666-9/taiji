"""
Provider router — selects upstream provider based on model name + fallback chain.
"""
from __future__ import annotations

import logging
from typing import Optional

from .config import GatewayConfig, ProviderConfig

log = logging.getLogger("gateway.router")

# Model prefix → provider name mapping
_MODEL_PREFIX_MAP = {
    "qwen": "ollama",
    "llama": "ollama",
    "mistral": "ollama",
    "gemma": "ollama",
    "phi": "ollama",
    "deepseek": "deepseek",
    "claude": "anthropic",
    "gpt": "openai",
}


class ProviderRouter:
    def __init__(self, config: GatewayConfig):
        self._config = config
        self._providers = {p.name: p for p in config.providers if p.enabled}
        self._degraded: set[str] = set()

    def select(self, model: str) -> Optional[ProviderConfig]:
        """Select provider for the given model. Returns None if no provider available."""
        # 1. Try exact model match
        for p in self._config.providers:
            if p.enabled and model in p.models and p.name not in self._degraded:
                return p

        # 2. Try prefix match
        model_lower = model.lower()
        for prefix, provider_name in _MODEL_PREFIX_MAP.items():
            if model_lower.startswith(prefix):
                p = self._providers.get(provider_name)
                if p and p.name not in self._degraded:
                    return p

        # 3. Fallback: try providers in priority order
        available = sorted(
            [p for p in self._config.providers if p.enabled and p.name not in self._degraded],
            key=lambda p: p.priority,
        )
        if available:
            log.info(f"No exact match for model={model}, falling back to {available[0].name}")
            return available[0]

        # 4. Last resort: try degraded providers
        all_enabled = sorted(
            [p for p in self._config.providers if p.enabled],
            key=lambda p: p.priority,
        )
        if all_enabled:
            log.warning(f"All providers degraded, trying {all_enabled[0].name} anyway")
            return all_enabled[0]

        return None

    def mark_degraded(self, provider_name: str):
        self._degraded.add(provider_name)
        log.warning(f"Provider {provider_name} marked degraded")

    def mark_healthy(self, provider_name: str):
        self._degraded.discard(provider_name)

    def list_models(self) -> list[str]:
        models = []
        for p in self._config.providers:
            if p.enabled:
                models.extend(p.models)
        return models

"""
Gateway configuration — env vars + optional JSON config.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


GATEWAY_DIR = Path(__file__).resolve().parent
CONFIG_DIR = GATEWAY_DIR / "config"
DATA_DIR = GATEWAY_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str = ""
    priority: int = 0
    enabled: bool = True
    timeout_s: int = 120
    models: List[str] = field(default_factory=list)

    @property
    def api_key(self) -> str:
        if not self.api_key_env:
            return ""
        return os.getenv(self.api_key_env, "")


@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 9200
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])
    default_provider: str = "ollama"
    default_model: str = "qwen2.5:3b"
    upstream_timeout_s: int = 120
    max_body_bytes: int = 256 * 1024  # 256KB
    enable_streaming: bool = True
    providers: List[ProviderConfig] = field(default_factory=list)

    def __post_init__(self):
        if not self.providers:
            self.providers = _default_providers()


def _default_providers() -> List[ProviderConfig]:
    providers = [
        ProviderConfig(
            name="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            priority=0,
            models=["qwen2.5:3b", "qwen2.5:7b", "llama3.2:3b"],
        ),
        ProviderConfig(
            name="deepseek",
            base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            priority=10,
            enabled=bool(os.getenv("DEEPSEEK_API_KEY")),
            models=["deepseek-chat", "deepseek-coder"],
        ),
        ProviderConfig(
            name="anthropic",
            base_url="https://api.anthropic.com",
            api_key_env="ANTHROPIC_API_KEY",
            priority=20,
            enabled=bool(os.getenv("ANTHROPIC_API_KEY")),
            models=["claude-sonnet-4-6", "claude-haiku-4-5"],
        ),
    ]
    # Timeout test provider — only enabled when explicitly requested
    if os.getenv("TAIJIOS_GATEWAY_ENABLE_TIMEOUT_PROVIDER", "").lower() in ("1", "true", "yes"):
        providers.append(ProviderConfig(
            name="timeout-test",
            base_url="http://10.255.255.1",  # non-routable IP, causes real TCP timeout
            priority=99,
            enabled=True,
            timeout_s=3,
            models=["timeout-test-model"],
        ))
    return providers


def load_config() -> GatewayConfig:
    """Load config from env vars, with optional JSON override."""
    cfg = GatewayConfig(
        host=os.getenv("TAIJIOS_GATEWAY_HOST", "127.0.0.1"),
        port=int(os.getenv("TAIJIOS_GATEWAY_PORT", "9200")),
        default_provider=os.getenv("TAIJIOS_GATEWAY_DEFAULT_PROVIDER", "ollama"),
        default_model=os.getenv("TAIJIOS_GATEWAY_DEFAULT_MODEL", "qwen2.5:3b"),
    )

    # Optional JSON config override
    config_path = CONFIG_DIR / "gateway.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
            if "cors_origins" in overrides:
                cfg.cors_origins = overrides["cors_origins"]
            if "providers" in overrides:
                cfg.providers = [ProviderConfig(**p) for p in overrides["providers"]]
        except Exception:
            pass

    return cfg

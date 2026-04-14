"""
TaijiOS 统一配置 — 所有配置收敛到这一个文件

优先级：环境变量 > .env 文件 > 默认值
用法：
    from settings import cfg
    print(cfg.api_model)
    print(cfg.data_dir)
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field

APP_DIR = Path(__file__).parent

# 加载 .env（如果 python-dotenv 可用）
try:
    from dotenv import load_dotenv
    load_dotenv(APP_DIR.parent / ".env")
    load_dotenv(APP_DIR / ".env", override=True)
except ImportError:
    pass


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    raw = os.getenv(key, "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return default


def _detect_api_key() -> str:
    """按优先级检测 API Key"""
    for key in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "CLAUDE_API_KEY",
                "DASHSCOPE_API_KEY", "QWEN_API_KEY"]:
        val = os.getenv(key, "")
        if val:
            return val
    # fallback: 从本地 model_config.json 读取
    cfg_path = APP_DIR / "data" / "model_config.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return data.get("api_key", "")
        except Exception:
            pass
    return ""


def _detect_provider(api_key: str) -> str:
    """根据已有环境变量推断 provider"""
    explicit = os.getenv("API_PROVIDER", "")
    if explicit:
        return explicit
    if os.getenv("DEEPSEEK_API_KEY"):
        return "DeepSeek"
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI"
    if os.getenv("CLAUDE_API_KEY"):
        return "Anthropic"
    if os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY"):
        return "Qwen"
    return "DeepSeek"


@dataclass(frozen=True)
class TaijiOSSettings:
    """TaijiOS 全局配置（只读，启动时确定）"""

    # ── AI 模型 ──
    api_key: str = field(default_factory=_detect_api_key)
    api_provider: str = ""  # 延迟计算，见 __post_init__
    api_base_url: str = field(default_factory=lambda: _env("API_BASE_URL", "https://api.deepseek.com"))
    api_model: str = field(default_factory=lambda: _env("API_MODEL", "deepseek-chat"))

    # ── Telegram ──
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN") or _env("TAIJI_TELEGRAM_BOT_TOKEN"))

    # ── 飞书 ──
    feishu_app_id: str = field(default_factory=lambda: _env("FEISHU_APP_ID"))
    feishu_app_secret: str = field(default_factory=lambda: _env("FEISHU_APP_SECRET"))
    feishu_port: int = field(default_factory=lambda: _env_int("FEISHU_BOT_PORT", 9090))

    # ── 路径 ──
    app_dir: Path = APP_DIR
    data_dir: Path = field(default_factory=lambda: APP_DIR / "data")
    evolution_dir: Path = field(default_factory=lambda: APP_DIR / "data" / "evolution")
    users_dir: Path = field(default_factory=lambda: APP_DIR / "data" / "bot_users")

    def __post_init__(self):
        # frozen=True 下用 object.__setattr__ 设置计算字段
        if not self.api_provider:
            object.__setattr__(self, "api_provider", _detect_provider(self.api_key))

        # 确保目录存在
        for d in [self.data_dir, self.evolution_dir, self.users_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def model_config(self) -> dict:
        """兼容旧代码的 MODEL_CONFIG dict"""
        return {
            "provider": self.api_provider,
            "base_url": self.api_base_url,
            "model": self.api_model,
            "api_key": self.api_key,
        }

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_token)

    @property
    def has_feishu(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    def summary(self) -> str:
        lines = [
            f"Provider: {self.api_provider} ({self.api_model})",
            f"API Key:  {'***' + self.api_key[-4:] if len(self.api_key) > 4 else '(未设置)'}",
            f"Telegram: {'已配置' if self.has_telegram else '未配置'}",
            f"飞书:     {'已配置' if self.has_feishu else '未配置'}",
            f"数据目录: {self.data_dir}",
        ]
        return "\n".join(lines)


# 全局单例
cfg = TaijiOSSettings()

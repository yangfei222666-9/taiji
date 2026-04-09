"""
secret_manager.py - TaijiOS 统一密钥加载

所有模块通过此模块获取 secret，禁止直接 os.getenv 读取敏感值。

优先级：
  1. 环境变量（直接指定）
  2. *_env 字段指向的环境变量名（从 yaml 配置读取）
  3. 都没有 → 明确失败，不静默

缺失即失败：
  get_secret(name, required=True) 缺失时抛 SecretMissingError
  get_secret(name, required=False) 缺失时返回 ""
"""

import os
import sys
from pathlib import Path
from typing import Optional


class SecretMissingError(RuntimeError):
    """必填 secret 缺失"""
    pass


# ── 已知 secret 注册表 ────────────────────────────────────────────────
# 格式：name -> (env_var, description, required_in_prod)
_REGISTRY: dict[str, tuple[str, str, bool]] = {
    "telegram_bot_token": (
        "TAIJI_TELEGRAM_BOT_TOKEN",
        "Telegram Bot Token，用于告警推送",
        True,
    ),
    "telegram_chat_id": (
        "TAIJI_TELEGRAM_CHAT_ID",
        "Telegram Chat ID（prod），告警目标群",
        True,
    ),
    "telegram_chat_id_dev": (
        "TAIJI_DEV_TELEGRAM_CHAT_ID",
        "Telegram Chat ID（dev），dev 告警目标群",
        False,
    ),
    "telegram_chat_id_staging": (
        "TAIJI_STAGING_TELEGRAM_CHAT_ID",
        "Telegram Chat ID（staging），staging 告警目标群",
        False,
    ),
    "api_token": (
        "TAIJIOS_API_TOKEN",
        "TaijiOS API Token，用于任务提交鉴权",
        True,
    ),
    "openclaw_api_key": (
        "OPENCLAW_API_KEY",
        "OpenClaw / Anthropic API Key",
        True,
    ),
    "anthropic_api_key": (
        "ANTHROPIC_API_KEY",
        "Anthropic API Key（real_coder 等直接调用）",
        False,
    ),
}


def _current_env() -> str:
    return os.environ.get("TAIJI_ENV", "prod").strip().lower()


def get_secret(name: str, required: bool = True, env_override: Optional[str] = None) -> str:
    """
    获取 secret 值。

    Args:
        name: secret 注册名（见 _REGISTRY）
        required: True 时缺失抛 SecretMissingError
        env_override: 覆盖默认环境变量名

    Returns:
        secret 值，缺失且 required=False 时返回 ""
    """
    if name not in _REGISTRY and not env_override:
        raise KeyError(f"Unknown secret name: {name!r}. Register it in secret_manager._REGISTRY first.")

    entry = _REGISTRY.get(name)
    env_var = env_override or (entry[0] if entry else name.upper())

    value = os.environ.get(env_var, "").strip()
    if value:
        return value

    if required:
        taiji_env = _current_env()
        entry_required = entry[2] if entry else True
        # dev 环境对 required_in_prod=True 的 secret 降级为警告
        if taiji_env != "prod" and entry and not entry_required:
            return ""
        raise SecretMissingError(
            f"Required secret {name!r} is missing. "
            f"Set environment variable: {env_var}"
        )
    return ""


def get_telegram_bot_token(required: bool = True) -> str:
    """获取 Telegram Bot Token，兼容旧环境变量名"""
    # 优先级：TAIJI_ALERT_TELEGRAM_BOT_TOKEN > TAIJI_TELEGRAM_BOT_TOKEN > TG_BOT_TOKEN > TELEGRAM_BOT_TOKEN
    for env_var in (
        "TAIJI_ALERT_TELEGRAM_BOT_TOKEN",
        "TAIJI_TELEGRAM_BOT_TOKEN",
        "TG_BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN",
    ):
        val = os.environ.get(env_var, "").strip()
        if val:
            return val
    if required:
        raise SecretMissingError(
            "Telegram Bot Token missing. Set: TAIJI_TELEGRAM_BOT_TOKEN"
        )
    return ""


def get_telegram_chat_id(required: bool = True) -> str:
    """获取当前环境的 Telegram Chat ID"""
    taiji_env = _current_env()
    env_map = {
        "prod":    ("TAIJI_ALERT_TELEGRAM_CHAT_ID", "TAIJI_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID", "TG_CHAT_ID"),
        "staging": ("TAIJI_STAGING_TELEGRAM_CHAT_ID", "TAIJI_TELEGRAM_CHAT_ID", "TG_CHAT_ID"),
        "dev":     ("TAIJI_DEV_TELEGRAM_CHAT_ID", "TAIJI_TELEGRAM_CHAT_ID", "TG_CHAT_ID"),
    }
    for env_var in env_map.get(taiji_env, env_map["prod"]):
        val = os.environ.get(env_var, "").strip()
        if val:
            return val
    if required:
        raise SecretMissingError(
            f"Telegram Chat ID missing for env={taiji_env}. "
            f"Set: {env_map.get(taiji_env, env_map['prod'])[0]}"
        )
    return ""


def check_all(env: Optional[str] = None) -> dict:
    """
    检查所有注册 secret 的状态。
    返回 {"ok": bool, "missing": [...], "present": [...]}
    """
    taiji_env = env or _current_env()
    missing = []
    present = []

    for name, (env_var, desc, required_in_prod) in _REGISTRY.items():
        val = os.environ.get(env_var, "").strip()
        required = required_in_prod or taiji_env == "prod"
        if val:
            present.append({"name": name, "env_var": env_var, "status": "present"})
        elif required:
            missing.append({"name": name, "env_var": env_var, "desc": desc, "status": "missing_required"})
        else:
            missing.append({"name": name, "env_var": env_var, "desc": desc, "status": "missing_optional"})

    required_missing = [m for m in missing if m["status"] == "missing_required"]
    return {
        "ok": len(required_missing) == 0,
        "env": taiji_env,
        "present": present,
        "missing": missing,
        "required_missing_count": len(required_missing),
    }


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="TaijiOS Secret Manager")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="检查所有 secret 状态")
    sub.add_parser("list", help="列出所有注册 secret")

    p_get = sub.add_parser("get", help="获取指定 secret（仅用于调试）")
    p_get.add_argument("name")
    p_get.add_argument("--optional", action="store_true")

    args = parser.parse_args()

    if args.cmd == "check":
        result = check_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["ok"] else 1)

    elif args.cmd == "list":
        for name, (env_var, desc, req) in _REGISTRY.items():
            status = "✅" if os.environ.get(env_var, "").strip() else ("❌" if req else "⚠️ ")
            print(f"{status} {name:35s} {env_var:45s} {desc}")

    elif args.cmd == "get":
        try:
            val = get_secret(args.name, required=not args.optional)
            # 只打印前4位，保护 secret
            masked = val[:4] + "***" if len(val) > 4 else "***"
            print(f"[OK] {args.name} = {masked}")
        except SecretMissingError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()

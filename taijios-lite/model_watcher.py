#!/usr/bin/env python3
"""
TaijiOS 大模型新模型监控
定时轮询各家 API 的模型列表，发现新模型通过 Telegram 推送通知。

支持：OpenAI(中转) / DeepSeek / Gemini / Anthropic(网页)
用法：python model_watcher.py          # 单次检查
      python model_watcher.py --loop   # 每6小时循环检查
"""

import os
import sys
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime

os.environ["PYTHONUTF8"] = "1"
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("model_watcher")

# ── 配置 ──────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN", "")
                  or os.getenv("TAIJI_TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 已知模型存档路径
KNOWN_MODELS_FILE = Path(__file__).resolve().parent / "data" / "known_models.json"

CHECK_INTERVAL = 6 * 3600  # 6小时


# ── 各家 API 查询 ─────────────────────────────────────────────────────────────

def fetch_openai_models() -> list[str]:
    """查询 OpenAI / 中转站模型列表"""
    key = os.getenv("OPENAI_API_KEY", "")
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    if not key:
        return []
    try:
        r = requests.get(f"{base}/models",
                         headers={"Authorization": f"Bearer {key}"},
                         timeout=30)
        r.raise_for_status()
        data = r.json()
        models = [m["id"] for m in data.get("data", [])]
        return sorted(models)
    except Exception as e:
        logger.warning(f"OpenAI/中转 模型列表获取失败: {e}")
        return []


def fetch_deepseek_models() -> list[str]:
    """查询 DeepSeek 模型列表"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get("https://api.deepseek.com/models",
                         headers={"Authorization": f"Bearer {key}"},
                         timeout=30)
        r.raise_for_status()
        data = r.json()
        models = [m["id"] for m in data.get("data", [])]
        return sorted(models)
    except Exception as e:
        logger.warning(f"DeepSeek 模型列表获取失败: {e}")
        return []


def fetch_gemini_models() -> list[str]:
    """查询 Gemini 可用模型列表"""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            timeout=30)
        r.raise_for_status()
        data = r.json()
        models = [m["name"].replace("models/", "")
                  for m in data.get("models", [])]
        return sorted(models)
    except Exception as e:
        logger.warning(f"Gemini 模型列表获取失败: {e}")
        return []


def fetch_anthropic_models() -> list[str]:
    """查询 Anthropic 模型列表（需要 API key）"""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get("https://api.anthropic.com/v1/models",
                         headers={
                             "x-api-key": key,
                             "anthropic-version": "2023-06-01",
                         },
                         timeout=30)
        r.raise_for_status()
        data = r.json()
        models = [m["id"] for m in data.get("data", [])]
        return sorted(models)
    except Exception as e:
        logger.warning(f"Anthropic 模型列表获取失败: {e}")
        return []


# ── 核心逻辑 ──────────────────────────────────────────────────────────────────

PROVIDERS = {
    "OpenAI/中转": fetch_openai_models,
    "DeepSeek": fetch_deepseek_models,
    "Gemini": fetch_gemini_models,
    "Anthropic": fetch_anthropic_models,
}


def load_known() -> dict[str, list[str]]:
    """加载已知模型快照"""
    if KNOWN_MODELS_FILE.exists():
        return json.loads(KNOWN_MODELS_FILE.read_text(encoding="utf-8"))
    return {}


def save_known(known: dict[str, list[str]]):
    """保存模型快照"""
    KNOWN_MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_MODELS_FILE.write_text(
        json.dumps(known, ensure_ascii=False, indent=2),
        encoding="utf-8")


def send_telegram(message: str):
    """通过 Telegram 推送通知"""
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN 未配置，跳过推送")
        print(f"[通知] {message}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=15)
        logger.info("Telegram 通知已发送")
    except Exception as e:
        logger.warning(f"Telegram 发送失败: {e}")
        print(f"[通知] {message}")


def check_once() -> dict[str, list[str]]:
    """
    单次检查所有厂商，返回新增模型 {provider: [new_models]}
    """
    known = load_known()
    all_new = {}
    updated = False

    for provider, fetcher in PROVIDERS.items():
        logger.info(f"检查 {provider} ...")
        current = fetcher()
        if not current:
            continue

        prev = set(known.get(provider, []))
        new_models = [m for m in current if m not in prev]

        if new_models:
            all_new[provider] = new_models
            logger.info(f"  {provider} 新增 {len(new_models)} 个模型: {new_models}")

        # 更新快照（包含全量，方便下次对比）
        known[provider] = current
        updated = True

    if updated:
        save_known(known)

    return all_new


def format_notification(all_new: dict[str, list[str]]) -> str:
    """格式化推送消息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"🔔 *大模型新模型上线提醒*\n_{now}_\n"]

    for provider, models in all_new.items():
        lines.append(f"*{provider}* 新增 {len(models)} 个:")
        for m in models[:20]:  # 最多显示20个
            lines.append(f"  • `{m}`")
        if len(models) > 20:
            lines.append(f"  ... 等共 {len(models)} 个")
        lines.append("")

    lines.append("_TaijiOS Model Watcher_")
    return "\n".join(lines)


def run_check():
    """执行一次检查并推送"""
    all_new = check_once()

    if all_new:
        msg = format_notification(all_new)
        send_telegram(msg)
        total = sum(len(v) for v in all_new.values())
        logger.info(f"发现 {total} 个新模型，已推送通知")
    else:
        logger.info("无新模型")

    return all_new


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TaijiOS 大模型监控")
    parser.add_argument("--loop", action="store_true", help="循环模式，每6小时检查")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help="循环间隔秒数（默认6小时）")
    args = parser.parse_args()

    if args.loop:
        logger.info(f"启动循环监控，间隔 {args.interval // 3600}小时")
        while True:
            try:
                run_check()
            except Exception as e:
                logger.error(f"检查异常: {e}")
            time.sleep(args.interval)
    else:
        # 单次检查
        result = run_check()
        if not result:
            print("当前无新模型。首次运行已保存基线快照。")

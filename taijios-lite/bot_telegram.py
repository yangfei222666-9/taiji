#!/usr/bin/env python3
"""
TaijiOS Telegram Bot — 认知军师上飞机（async 版）

用法：
  1. 找 @BotFather 创建Bot，拿到 Token
  2. 配置环境变量或 .env 文件：
     TELEGRAM_BOT_TOKEN=你的Token
     DEEPSEEK_API_KEY=你的DeepSeek Key（或其他模型的Key）
  3. python bot_telegram.py

支持：
  - 私聊：每个用户独立会话 + 引擎
  - 群聊：@机器人名 或回复机器人消息触发
  - 命令：/start /status /help /kb
"""
import os
import sys
import json
import asyncio
import logging

os.environ["PYTHONUTF8"] = "1"
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("需要安装 aiohttp: pip install aiohttp")
    sys.exit(1)

APP_DIR = Path(__file__).parent
# 先加载 workspace 级别 .env（基础密钥），再加载本地 .env（可覆盖）
load_dotenv(APP_DIR.parent / ".env")
load_dotenv(APP_DIR / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("telegram")

# ── 配置 ────────────────────────────────────────────

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN", "")
                  or os.getenv("TAIJI_TELEGRAM_BOT_TOKEN", ""))
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("API_BASE_URL", "https://api.deepseek.com")
API_MODEL = os.getenv("API_MODEL", "deepseek-chat")
API_PROVIDER = os.getenv("API_PROVIDER", "DeepSeek")

if not TELEGRAM_TOKEN:
    print("错误：需要设置 TELEGRAM_BOT_TOKEN")
    print("  1. 找 @BotFather 创建Bot")
    print("  2. 在 .env 文件添加: TELEGRAM_BOT_TOKEN=你的Token")
    sys.exit(1)

if not API_KEY:
    # 尝试从本地配置读取
    config_path = APP_DIR / "data" / "model_config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            API_KEY = cfg.get("api_key", "")
            API_BASE = cfg.get("base_url", API_BASE)
            API_MODEL = cfg.get("model", API_MODEL)
            API_PROVIDER = cfg.get("provider", API_PROVIDER)
        except Exception:
            pass
    if not API_KEY:
        print("错误：需要设置 AI 模型的 API Key")
        print("  在 .env 文件添加: DEEPSEEK_API_KEY=你的Key")
        sys.exit(1)

MODEL_CONFIG = {
    "provider": API_PROVIDER,
    "base_url": API_BASE,
    "model": API_MODEL,
    "api_key": API_KEY,
}

# ── Telegram API (async) ────────────────────────────

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


async def tg_request(session: aiohttp.ClientSession, method: str, data: dict = None) -> dict:
    """Telegram Bot API 请求（非阻塞）"""
    url = f"{TG_API}/{method}"
    try:
        if data:
            async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                return await resp.json()
        else:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                return await resp.json()
    except Exception as e:
        logger.error(f"TG API 错误: {e}")
        return {}


async def send_message(session: aiohttp.ClientSession, chat_id: int, text: str, reply_to: int = None):
    """发送消息（自动分段，Telegram单条上限4096字符）"""
    MAX_LEN = 4000
    chunks = []
    while text:
        if len(text) <= MAX_LEN:
            chunks.append(text)
            break
        # 找最近的换行符分割
        cut = text[:MAX_LEN].rfind("\n")
        if cut < 100:
            cut = MAX_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip()

    for i, chunk in enumerate(chunks):
        data = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        }
        if reply_to and i == 0:
            data["reply_to_message_id"] = reply_to
        result = await tg_request(session, "sendMessage", data)
        # Markdown 解析失败时降级为纯文本
        if not result.get("ok"):
            data.pop("parse_mode", None)
            await tg_request(session, "sendMessage", data)


async def send_typing(session: aiohttp.ClientSession, chat_id: int):
    """显示"正在输入"状态"""
    await tg_request(session, "sendChatAction", {
        "chat_id": chat_id,
        "action": "typing",
    })


# ── 主循环 ────────────────────────────────────────────

async def main():
    from bot_core import TaijiBot

    bot = TaijiBot(MODEL_CONFIG)

    async with aiohttp.ClientSession() as session:
        bot_info = await tg_request(session, "getMe")
        bot_username = bot_info.get("result", {}).get("username", "TaijiOS")

        print("=" * 50)
        print(f"  TaijiOS Telegram Bot 已启动 (async)")
        print(f"  Bot: @{bot_username}")
        print(f"  模型: {API_PROVIDER} ({API_MODEL})")
        print(f"  知识库: {bot.knowledge.get_status()}")
        print("=" * 50)
        print("  等待消息...\n")

        offset = 0

        while True:
            try:
                # 长轮询获取更新（非阻塞）
                updates = await tg_request(session, "getUpdates", {
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": ["message"],
                })

                if not updates.get("ok"):
                    await asyncio.sleep(5)
                    continue

                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message")
                    if not msg or not msg.get("text"):
                        continue

                    chat_id = msg["chat"]["id"]
                    chat_type = msg["chat"]["type"]  # private / group / supergroup
                    user = msg.get("from", {})
                    user_id = str(user.get("id", chat_id))
                    user_name = (user.get("first_name", "") + " " +
                                user.get("last_name", "")).strip()
                    text = msg["text"].strip()
                    msg_id = msg.get("message_id")

                    # 群聊过滤：只响应 @Bot 或回复Bot的消息
                    if chat_type in ("group", "supergroup"):
                        is_mentioned = f"@{bot_username}" in text
                        is_reply_to_bot = (
                            msg.get("reply_to_message", {})
                            .get("from", {}).get("is_bot", False))
                        if not is_mentioned and not is_reply_to_bot:
                            continue
                        # 去掉 @mention
                        text = text.replace(f"@{bot_username}", "").strip()

                    if not text:
                        continue

                    logger.info(f"[{user_name}] {text[:50]}")

                    # 命令处理
                    if text == "/start":
                        greeting = bot.handle_greeting(user_id, user_name)
                        await send_message(session, chat_id, greeting, msg_id)
                        continue

                    if text in ("/status", "/状态"):
                        reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, "status")
                        await send_message(session, chat_id, reply, msg_id)
                        continue

                    if text in ("/help", "/帮助"):
                        reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, "help")
                        await send_message(session, chat_id, reply, msg_id)
                        continue

                    if text in ("/kb", "/知识库"):
                        reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, "kb")
                        await send_message(session, chat_id, reply, msg_id)
                        continue

                    if text in ("/profile", "/资料卡"):
                        reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, "资料卡")
                        await send_message(session, chat_id, reply, msg_id)
                        continue

                    if text in ("/reset", "/重置", "/重新开始"):
                        reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, "重置")
                        await send_message(session, chat_id, reply, msg_id)
                        continue

                    # 去掉命令前缀
                    if text.startswith("/"):
                        text = text.lstrip("/")

                    # 显示输入中（不阻塞）
                    await send_typing(session, chat_id)

                    # 处理消息（LLM 调用在线程池中执行，不阻塞事件循环）
                    reply = await asyncio.to_thread(bot.handle_message, user_id, user_name, text)
                    await send_message(session, chat_id, reply, msg_id)
                    logger.info(f"  → 回复 {len(reply)}字")

            except KeyboardInterrupt:
                print("\n退出")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主循环错误: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

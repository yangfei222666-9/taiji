#!/usr/bin/env python3
"""
TaijiOS 飞书Bot — 认知军师上飞书（WebSocket 长连接，无需公网IP）

用法：
  1. 去飞书开放平台(open.feishu.cn)创建企业自建应用
  2. 添加「机器人」能力
  3. 配置环境变量或 .env：
     FEISHU_APP_ID=你的App ID
     FEISHU_APP_SECRET=你的App Secret
     DEEPSEEK_API_KEY=你的DeepSeek Key
  4. python bot_feishu.py

支持：
  - 私聊：每个用户独立会话
  - 群聊：@机器人触发
  - 命令：资料卡 / status / help / kb
"""
import os
import sys
import json
import time
import logging
import threading
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
# 先加载 workspace 级别 .env（基础密钥），再加载本地 .env（可覆盖）
load_dotenv(APP_DIR.parent / ".env")
load_dotenv(APP_DIR / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("feishu")

# ── 配置 ────────────────────────────────────────────

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("API_BASE_URL", "https://api.deepseek.com")
API_MODEL = os.getenv("API_MODEL", "deepseek-chat")
API_PROVIDER = os.getenv("API_PROVIDER", "DeepSeek")

if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
    print("错误：需要设置飞书应用配置")
    print("  在 .env 文件添加:")
    print("    FEISHU_APP_ID=你的App ID")
    print("    FEISHU_APP_SECRET=你的App Secret")
    print("  去 open.feishu.cn 创建企业自建应用")
    sys.exit(1)

if not API_KEY:
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
        sys.exit(1)

MODEL_CONFIG = {
    "provider": API_PROVIDER,
    "base_url": API_BASE,
    "model": API_MODEL,
    "api_key": API_KEY,
}

# ── lark SDK ──────────────────────────────────────

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    ReplyMessageRequest, ReplyMessageRequestBody,
    CreateMessageRequest, CreateMessageRequestBody,
)


LARK_DOMAIN = os.getenv("LARK_DOMAIN", "")


def _detect_domain() -> str:
    """自动检测飞书/Lark域名（国内用 feishu.cn，国际用 larksuite.com）"""
    if LARK_DOMAIN:
        return LARK_DOMAIN
    import requests as req
    for domain in ["https://open.larksuite.com", "https://open.feishu.cn"]:
        try:
            resp = req.post(
                f"{domain}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
                timeout=5,
            )
            if resp.json().get("code") == 0:
                logger.info(f"检测到域名: {domain}")
                return domain
        except Exception:
            continue
    return "https://open.feishu.cn"


def _check_ws_available(domain: str) -> bool:
    """预检测 WebSocket 长连接是否可用"""
    import requests as req
    try:
        resp = req.post(
            f"{domain}/callback/ws/endpoint",
            headers={"locale": "zh"},
            json={"AppID": FEISHU_APP_ID, "AppSecret": FEISHU_APP_SECRET},
            timeout=10,
        )
        return resp.json().get("code", -1) == 0
    except Exception:
        return False


# 检测域名，创建客户端
_domain = _detect_domain()
logger.info(f"使用域名: {_domain}")

lark_client = lark.Client.builder() \
    .app_id(FEISHU_APP_ID) \
    .app_secret(FEISHU_APP_SECRET) \
    .domain(_domain) \
    .log_level(lark.LogLevel.WARNING) \
    .build()


def reply_message(message_id: str, text: str):
    """回复飞书消息"""
    content = json.dumps({"text": text}, ensure_ascii=False)
    req = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
                      .content(content)
                      .msg_type("text")
                      .build()) \
        .build()
    resp = lark_client.im.v1.message.reply(req)
    if not resp.success():
        logger.error(f"回复失败: code={resp.code} msg={resp.msg}")
    return resp


# ── 消息去重 ────────────────────────────────────────

_processed_msgs = set()
_processed_lock = threading.Lock()


def is_duplicate(msg_id: str) -> bool:
    with _processed_lock:
        if msg_id in _processed_msgs:
            return True
        _processed_msgs.add(msg_id)
        if len(_processed_msgs) > 1000:
            _processed_msgs.clear()
        return False


# ── WebSocket 事件处理 ──────────────────────────────

def on_message_receive(data: lark.im.v1.P2ImMessageReceiveV1):
    """收到飞书消息的回调"""
    try:
        event = data.event
        message = event.message
        sender = event.sender

        msg_id = message.message_id
        msg_type = message.message_type
        chat_type = message.chat_type  # p2p / group

        # 去重
        if is_duplicate(msg_id):
            return

        # 解析文本（支持 text 和 post 富文本）
        text = ""
        try:
            content = json.loads(message.content)
            if msg_type == "text":
                text = content.get("text", "").strip()
            elif msg_type == "post":
                # 富文本：遍历所有段落提取纯文本
                post = content.get("post", {})
                lang = post.get("zh_cn") or post.get("en_us") or next(iter(post.values()), {})
                for para in lang.get("content", []):
                    for node in para:
                        if node.get("tag") == "text":
                            text += node.get("text", "")
                text = text.strip()
            else:
                reply_message(msg_id, "目前只支持文字消息，直接打字就好。")
                return
        except Exception:
            text = ""

        if not text:
            return

        # 群聊去掉 @mention
        if message.mentions:
            for m in message.mentions:
                if hasattr(m, 'key') and m.key:
                    text = text.replace(m.key, "").strip()

        # 用户信息
        open_id = sender.sender_id.open_id or ""
        user_id = sender.sender_id.user_id or open_id
        user_name = ""

        logger.info(f"[{open_id[:8]}] {text[:50]}")

        # 异步处理（避免阻塞 WebSocket）
        def process_and_reply():
            try:
                resp = taiji_bot.handle_message(user_id, user_name, text)
                reply_message(msg_id, resp)
                logger.info(f"  → 回复 {len(resp)}字")
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                reply_message(msg_id, f"军师遇到问题了：{str(e)[:50]}")

        threading.Thread(target=process_and_reply, daemon=True).start()

    except Exception as e:
        logger.error(f"事件处理异常: {e}")


# ── 主入口 ────────────────────────────────────────────

taiji_bot = None


PORT = int(os.getenv("FEISHU_BOT_PORT", "9090"))


def start_webhook_mode():
    """Webhook 模式（需要公网IP或内网穿透）"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import requests as req

    class FeishuWebhookAPI:
        """用原生 requests 回复消息"""
        def __init__(self):
            self._token = ""
            self._token_expires = 0

        def get_token(self):
            if self._token and time.time() < self._token_expires - 60:
                return self._token
            resp = req.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") == 0:
                self._token = data["tenant_access_token"]
                self._token_expires = time.time() + data.get("expire", 7200)
            return self._token

        def reply_msg(self, message_id, text):
            content = json.dumps({"text": text}, ensure_ascii=False)
            req.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {self.get_token()}",
                         "Content-Type": "application/json; charset=utf-8"},
                json={"content": content, "msg_type": "text"},
                timeout=30,
            )

    api = FeishuWebhookAPI()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/webhook/event":
                self.send_response(404); self.end_headers(); return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except Exception:
                self.send_response(400); self.end_headers(); return

            # URL验证
            if "challenge" in data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"challenge": data["challenge"]}).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":0}')

            # 异步处理消息
            def handle():
                try:
                    evt = data.get("event", {})
                    msg = evt.get("message", {})
                    msg_id = msg.get("message_id", "")
                    if not msg_id or is_duplicate(msg_id):
                        return
                    msg_type = msg.get("message_type")
                    content = json.loads(msg.get("content", "{}"))
                    if msg_type == "text":
                        text = content.get("text", "").strip()
                    elif msg_type == "post":
                        text = ""
                        post = content.get("post", {})
                        lang = post.get("zh_cn") or post.get("en_us") or next(iter(post.values()), {})
                        for para in lang.get("content", []):
                            for node in para:
                                if node.get("tag") == "text":
                                    text += node.get("text", "")
                        text = text.strip()
                    else:
                        api.reply_msg(msg_id, "目前只支持文字消息。")
                        return
                    for m in msg.get("mentions", []):
                        if m.get("key"):
                            text = text.replace(m["key"], "").strip()
                    if not text:
                        return
                    sender = evt.get("sender", {}).get("sender_id", {})
                    user_id = sender.get("user_id", "") or sender.get("open_id", "")
                    logger.info(f"[webhook] {text[:50]}")
                    resp = taiji_bot.handle_message(user_id, "", text)
                    api.reply_msg(msg_id, resp)
                    logger.info(f"  → 回复 {len(resp)}字")
                except Exception as e:
                    logger.error(f"webhook处理失败: {e}")

            threading.Thread(target=handle, daemon=True).start()

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "bot": "TaijiOS Feishu"}).encode())
            else:
                self.send_response(404); self.end_headers()

        def log_message(self, fmt, *args):
            pass

    print(f"  [降级] Webhook 模式 — 端口 {PORT}")
    print(f"  把这个地址填到飞书事件订阅：")
    print(f"    http://你的公网IP:{PORT}/webhook/event")
    print(f"  没有公网IP？用 ngrok/frp 内网穿透\n")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def main():
    global taiji_bot
    from bot_core import TaijiBot

    taiji_bot = TaijiBot(MODEL_CONFIG)

    print("=" * 50)
    print(f"  TaijiOS 飞书Bot")
    print(f"  模型: {API_PROVIDER} ({API_MODEL})")
    print(f"  知识库: {taiji_bot.knowledge.get_status()}")
    print("=" * 50)

    # 预检测 WebSocket 长连接
    ws_ok = _check_ws_available(_domain)

    if ws_ok:
        print(f"  连接模式: WebSocket 长连接（无需公网IP）")
        print("  等待消息...\n")

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(on_message_receive) \
            .build()

        ws_client = lark.ws.Client(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
            auto_reconnect=True,
            domain=_domain,
        )
        ws_client.start()
    else:
        print(f"\n  WebSocket 长连接不可用")
        print("  要启用（推荐，无需公网IP）：")
        print("  1. 打开 open.feishu.cn → 你的应用")
        print("  2. 事件与回调 → 选择「使用长连接接收事件」")
        print("  3. 重启本程序\n")
        print("  正在使用 Webhook 模式...\n")
        start_webhook_mode()


if __name__ == "__main__":
    main()

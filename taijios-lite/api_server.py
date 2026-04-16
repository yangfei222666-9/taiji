#!/usr/bin/env python3
"""
TaijiOS Lite API Server — 前端接口 + HUD接口

预留接口，后续对接：
  1. Web前端（实时语音对话）
  2. 本地HUD（桌面悬浮窗/状态栏）
  3. 移动端（微信小程序/iOS App/Android App）

启动：python api_server.py
默认端口：8390

API列表：
  POST /api/chat          对话（支持流式）
  POST /api/voice         语音输入（base64音频）
  GET  /api/status        获取进化状态
  GET  /api/hexagram      获取当前卦象
  GET  /api/cognitive_map  获取认知地图
  GET  /api/contribution  获取积分信息
  GET  /api/ecosystem     获取生态制度+Agent网络状态
  POST /api/export        导出经验
  POST /api/import        导入经验
  GET  /api/hud           HUD状态数据（轻量级，给桌面悬浮窗用）
  WS   /ws/chat           WebSocket实时对话（语音流式）
"""

import json
import sys
import os
from pathlib import Path

# 复用主程序的配置
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

DATA_DIR = APP_DIR / "data"
EVOLUTION_DIR = DATA_DIR / "evolution"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
EVOLUTION_DIR.mkdir(exist_ok=True)


def create_app():
    """
    创建API应用。
    当前为接口定义，实际HTTP框架后续接入（Flask/FastAPI）。
    """
    from evolution.crystallizer import CrystallizationEngine
    from evolution.learner import ConversationLearner
    from evolution.hexagram import HexagramEngine
    from evolution.agi_core import CognitiveMap
    from evolution.experience_pool import ExperiencePool
    from evolution.premium import PremiumManager
    from evolution.contribution import ContributionSystem
    from evolution.ecosystem import EcosystemManager

    # 初始化引擎
    engines = {
        "crystallizer": CrystallizationEngine(str(EVOLUTION_DIR)),
        "learner": ConversationLearner(str(EVOLUTION_DIR)),
        "hexagram": HexagramEngine(str(EVOLUTION_DIR)),
        "cognitive_map": CognitiveMap(str(EVOLUTION_DIR)),
        "experience_pool": ExperiencePool(str(EVOLUTION_DIR)),
        "premium": PremiumManager(str(EVOLUTION_DIR)),
        "contribution": ContributionSystem(str(EVOLUTION_DIR)),
        "ecosystem": EcosystemManager(str(EVOLUTION_DIR)),
    }

    return engines


# ── API 路由定义（接口契约）──────────────────────────────────────────

def api_chat(engines: dict, message: str, user_id: str = "api_default",
             user_name: str = "", history: list = None,
             model_config: dict = None) -> dict:
    """
    POST /api/chat
    请求：{"message": "你好", "user_id": "u123", "history": [...]}
    响应：{"reply": "...", "hexagram": {...}, "points_earned": 1}
    """
    if history is None:
        history = []

    # ── AI 回复（TaijiBot 多模型路由）──
    bot = engines.get("bot")
    if bot:
        reply = bot.handle_message(user_id, user_name, message)
    else:
        reply = "[军师暂时不在线，请稍后再试]"

    # ── 更新卦象 ──
    user_msgs = [m["content"] for m in history if m["role"] == "user"]
    user_msgs.append(message)
    rate = engines["learner"].get_positive_rate()
    hex_result = engines["hexagram"].update_from_conversation(user_msgs, rate)

    # ── 更新认知地图 ──
    engines["cognitive_map"].extract_from_message(message, reply)

    # ── 积分 ──
    engines["contribution"].add_points("chat")

    return {
        "status": "ok",
        "reply": reply,
        "hexagram": hex_result,
        "cognitive_map_summary": engines["cognitive_map"].get_map_summary(),
        "points_earned": 1,
    }


def api_voice(engines: dict, audio_base64: str) -> dict:
    """
    POST /api/voice
    请求：{"audio": "base64编码的音频", "format": "wav"}
    响应：{"text": "识别出的文字", "reply": "AI回复"}

    语音识别可对接：
    - 阿里云ASR
    - Whisper本地
    - 浏览器Web Speech API（前端直接转文字传过来）
    """
    return {
        "status": "not_implemented",
        "message": "语音接口预留，需对接ASR服务",
        "supported_formats": ["wav", "mp3", "webm"],
        "recommended": "前端用Web Speech API转文字后调/api/chat",
    }


def api_status(engines: dict) -> dict:
    """
    GET /api/status
    响应：完整进化状态
    """
    return {
        "premium": engines["premium"].is_premium,
        "contribution": {
            "points": engines["contribution"].total_points,
            "level": engines["contribution"].level[0],
            "streak": engines["contribution"].data.get("streak", 0),
        },
        "hexagram": {
            "current": engines["hexagram"].current_hexagram,
            "lines": engines["hexagram"].current_lines,
            "prompt": engines["hexagram"].get_strategy_prompt(),
        },
        "cognitive_map": {
            "display": engines["cognitive_map"].get_display(),
            "summary": engines["cognitive_map"].get_map_summary(),
        },
        "crystals": len(engines["crystallizer"].get_active_rules()),
        "shared_rules": len(engines["experience_pool"].get_shared_rules()),
        "stats": engines["learner"].get_stats_display(),
    }


def api_hud(engines: dict) -> dict:
    """
    GET /api/hud
    轻量级状态，给桌面HUD悬浮窗用。
    刷新频率：每次对话后 or 每30秒。
    """
    hex_name = engines["hexagram"].current_hexagram
    lines = engines["hexagram"].current_lines
    level = engines["contribution"].level
    from evolution.hexagram import HEXAGRAM_STRATEGIES
    strat = HEXAGRAM_STRATEGIES.get(hex_name, {})

    return {
        "hexagram": hex_name,
        "hexagram_name": strat.get("name", hex_name),
        "lines": "".join("⚊" if l == 1 else "⚋" for l in lines),
        "style": strat.get("style", ""),
        "level": level[0],
        "points": engines["contribution"].total_points,
        "streak": engines["contribution"].data.get("streak", 0),
        "positive_rate": engines["learner"].get_positive_rate(),
    }


def api_hexagram(engines: dict) -> dict:
    """GET /api/hexagram — 当前卦象详情"""
    hex_name = engines["hexagram"].current_hexagram
    lines = engines["hexagram"].current_lines
    from evolution.hexagram import HEXAGRAM_STRATEGIES
    strat = HEXAGRAM_STRATEGIES.get(hex_name, {})

    return {
        "hexagram": hex_name,
        "name": strat.get("name", hex_name),
        "lines": lines,
        "lines_display": "".join("⚊" if l == 1 else "⚋" for l in lines),
        "strategy": strat.get("strategy", ""),
        "style": strat.get("style", ""),
        "yang_count": sum(lines),
        "yin_count": 6 - sum(lines),
        "dimensions": {
            "emotion": "稳定" if lines[0] else "波动",
            "action": "有目标" if lines[1] else "迷茫",
            "cognition": "清晰" if lines[2] else "混沌",
            "resource": "充足" if lines[3] else "匮乏",
            "direction": "明确" if lines[4] else "摇摆",
            "satisfaction": "正面" if lines[5] else "负面",
        },
    }


def api_contribution(engines: dict) -> dict:
    """GET /api/contribution — 积分详情"""
    c = engines["contribution"]
    return {
        "total_points": c.total_points,
        "level": c.level[0],
        "level_desc": c.level[1],
        "next_level_at": c.level[2],
        "streak": c.data.get("streak", 0),
        "contributor_id": c.get_contributor_id(),
        "history": c.data.get("history", [])[-20:],
    }


def api_ecosystem(engines: dict) -> dict:
    """GET /api/ecosystem — 生态制度 + Agent网络状态"""
    eco = engines["ecosystem"]
    pts = engines["contribution"].total_points
    role = eco.get_role(pts)
    net = eco.get_network_stats()
    unlocked = eco.get_unlocked_achievements()
    locked = eco.get_locked_achievements()

    return {
        "role": {
            "key": role["key"],
            "name": role["name"],
            "desc": role["desc"],
            "rights": role["rights"],
            "duties": role["duties"],
        },
        "agent_network": {
            "known_agents": net["known_agents"],
            "total_exchanges": net["total_exchanges"],
            "total_rules_received": net["total_rules_received"],
        },
        "achievements": {
            "unlocked": unlocked,
            "locked": [{"name": a["name"], "desc": a["desc"]} for a in locked[:5]],
            "total": len(unlocked) + len(locked),
            "unlocked_count": len(unlocked),
        },
        "ecosystem_rules": [
            "经验靠验证 — 被越多Agent采纳，质量越高",
            "分享越多越强 — 帮别人就是帮自己",
            "多样性优先 — 不同Agent的经验交叉验证最有价值",
            "军师无废话 — 只保留真正有用的规则",
            "开放流通 — .taiji文件自由传播，无平台绑定",
            "随时迭代 — 每个Agent随时准备好接收新经验",
        ],
    }


def api_export(engines: dict) -> dict:
    """
    POST /api/export
    请求：{} （无参数，导出当前Agent的经验）
    响应：{"status": "ok", "package": {...完整.taiji v2 JSON...}, "count": 3}

    移动端用法：
      iOS/Android/小程序 调用此接口 → 拿到JSON → 分享给好友（微信/AirDrop/二维码）
      好友的App调 /api/import 导入
    """
    pool = engines["experience_pool"]
    crystallizer = engines["crystallizer"]
    hexagram = engines["hexagram"]
    cognitive = engines["cognitive_map"]
    contribution = engines["contribution"]

    rules = crystallizer.get_active_rules()
    if not rules:
        return {"status": "empty", "message": "还没有经验结晶可导出"}

    from evolution.hexagram import HEXAGRAM_STRATEGIES
    hex_name = hexagram.current_hexagram
    strat = HEXAGRAM_STRATEGIES.get(hex_name, {})

    # 构建v2经验包（不写文件，直接返回JSON给客户端）
    import time
    package = {
        "format": "taiji_experience_v2",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent_id": contribution.get_contributor_id(),
        "count": len(rules),
        "crystals": [
            {
                "rule": r.get("rule", ""),
                "confidence": r.get("confidence", 0.5),
                "scene": r.get("scene", ""),
                "verified_by": 1,
            }
            for r in rules
        ],
        "hexagram": {
            "current": hex_name,
            "lines": hexagram.current_lines,
            "strategy": strat.get("strategy", ""),
        },
        "soul": {
            "dimensions": {
                d: len(cognitive.map.get(d, []))
                for d in ["位置", "本事", "钱财", "野心", "口碑"]
            },
            "patterns": [
                p.get("insight", "")
                for p in cognitive.detect_patterns()
            ],
        },
    }

    engines["contribution"].add_points("export")
    engines["ecosystem"].record_action("export")

    return {
        "status": "ok",
        "count": len(rules),
        "package": package,
        "message": "把package字段的JSON发给朋友，对方调/api/import导入",
    }


def api_import(engines: dict, package: dict) -> dict:
    """
    POST /api/import
    请求：{"package": {...完整.taiji v2 JSON...}}
    响应：{"status": "ok", "imported": 3, "agent_hexagram": "乾"}

    移动端用法：
      收到朋友分享的经验JSON → 调此接口 → 自动导入到本地共享池
      iOS可以通过AirDrop/剪贴板/扫码接收
    """
    if not package or not isinstance(package, dict):
        return {"status": "error", "message": "无效的经验包"}

    fmt = package.get("format", "")
    if fmt not in ("taiji_experience_v1", "taiji_experience_v2"):
        return {"status": "error", "message": "不支持的格式"}

    # 写到临时文件走标准导入流程（复用安全过滤逻辑）
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".taiji",
                                      delete=False, encoding="utf-8")
    try:
        json.dump(package, tmp, ensure_ascii=False)
        tmp.close()

        pool = engines["experience_pool"]
        count = pool.import_crystals(tmp.name)

        result = {
            "status": "ok",
            "imported": count,
        }

        if count > 0:
            engines["contribution"].add_points("import")
            engines["ecosystem"].record_action("import")

            # 返回来源Agent的卦象信息
            snaps = pool.get_agent_snapshots()
            agent_id = package.get("agent_id", "")
            if agent_id and agent_id in snaps:
                snap = snaps[agent_id]
                result["agent_hexagram"] = snap.get("hexagram", {}).get("current", "")
                engines["ecosystem"].record_peer(agent_id, {"rules_count": count})
        else:
            result["message"] = "没有新经验（可能已导入过）"

        return result
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass


# ── WebSocket 接口定义 ──────────────────────────────────────────

"""
WS /ws/chat — 实时对话WebSocket

协议：
  客户端发送：
    {"type": "text", "content": "你好"}
    {"type": "voice_start"}   // 开始语音
    {"type": "voice_chunk", "data": "base64音频块"}
    {"type": "voice_end"}     // 结束语音

  服务端响应：
    {"type": "reply_start"}
    {"type": "reply_chunk", "content": "部分回复..."}
    {"type": "reply_end", "full_reply": "完整回复", "hexagram": {...}}
    {"type": "hud_update", "data": {...}}  // HUD状态推送
"""


# ── FastAPI 应用 ───────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Any
import json as _json
import uvicorn


class _UTF8JSON(JSONResponse):
    """ensure_ascii=True 让 PowerShell 5.1 能正确显示中文（\\uXXXX 转义）"""
    def render(self, content) -> bytes:
        return _json.dumps(content, ensure_ascii=True).encode("utf-8")

_engines: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engines
    import os
    _engines = create_app()
    # 初始化 TaijiBot（内置多模型路由，DeepSeek主力+降级链）
    try:
        from bot_core import TaijiBot
        _model_config = {
            "provider": "DeepSeek",
            "base_url": os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        }
        _engines["bot"] = TaijiBot(_model_config)
        print("[API] TaijiBot 初始化完成（多模型路由已启动）")
    except Exception as e:
        print(f"[API] TaijiBot 初始化失败，/api/chat 无 AI 回复: {e}")
        _engines["bot"] = None
    yield


app = FastAPI(title="TaijiOS API", version="1.0", lifespan=lifespan,
              default_response_class=_UTF8JSON)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


class ChatReq(BaseModel):
    message: str
    user_id: str = "api_default"
    user_name: str = ""
    history: list = []
    model_config: dict = {}

class VoiceReq(BaseModel):
    audio: str
    format: str = "wav"

class ImportReq(BaseModel):
    package: dict


@app.post("/api/chat")
def route_chat(req: ChatReq):
    return api_chat(_engines, req.message, req.user_id, req.user_name,
                    req.history, req.model_config)

@app.post("/api/voice")
def route_voice(req: VoiceReq):
    return api_voice(_engines, req.audio)

@app.get("/api/status")
def route_status():
    return api_status(_engines)

@app.get("/api/hexagram")
def route_hexagram():
    return api_hexagram(_engines)

@app.get("/api/hud")
def route_hud():
    return api_hud(_engines)

@app.get("/api/contribution")
def route_contribution():
    return api_contribution(_engines)

@app.get("/api/ecosystem")
def route_ecosystem():
    return api_ecosystem(_engines)

@app.post("/api/export")
def route_export():
    return api_export(_engines)

@app.post("/api/import")
def route_import(req: ImportReq):
    return api_import(_engines, req.package)

@app.get("/api/cognitive_map")
def route_cognitive_map():
    cm = _engines.get("cognitive_map")
    if not cm:
        raise HTTPException(status_code=503, detail="引擎未初始化")
    return {"display": cm.get_display(), "summary": cm.get_map_summary()}

@app.get("/")
def root():
    return {"service": "TaijiOS API", "port": 8390, "status": "running"}


# ── 启动入口 ──────────────────────────────────────────

if __name__ == "__main__":
    print("TaijiOS Lite API Server — 端口 8390")
    print("接口：/api/chat  /api/status  /api/hexagram  /api/hud  /api/export  /api/import")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8390, reload=False)

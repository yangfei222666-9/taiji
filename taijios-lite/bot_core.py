#!/usr/bin/env python3
"""
TaijiOS Bot 核心 — 多用户集体学习引擎

每个用户一套独立引擎（结晶/学习/卦象/认知/经验池）。
所有用户的经验自动汇入全局共享池，交叉验证，集体进化。
飞书Bot和Telegram Bot共用这个核心。

集体学习流程：
  用户A聊天 → 产出结晶 → 自动脱敏 → 全局共享池
                                         ↓
  用户B聊天 → prompt注入A的经验 → 更精准的回复
                                         ↓
  用户B正面反馈 → A的结晶被验证 → 置信度上升
                                         ↓
  新用户加入 → 直接继承全网最佳经验
"""
import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

sys.path.insert(0, str(APP_DIR))

from evolution.crystallizer import CrystallizationEngine
from evolution.learner import ConversationLearner
from evolution.hexagram import HexagramEngine, HEXAGRAM_STRATEGIES
from evolution.agi_core import CognitiveMap
from evolution.experience_pool import ExperiencePool
from evolution.contribution import ContributionSystem
from evolution.ecosystem import EcosystemManager
from evolution.premium import PremiumManager
from evolution.safe_io import safe_json_save, safe_json_load
from taijios import (build_quick_system, chat, detect_intent,
                     KnowledgeBase, KNOWLEDGE_DIR)
from multi_llm import init_models, get_model, ensemble_call, get_available_names
from model_router import ModelRouter

logger = logging.getLogger("bot_core")

# ── Ising 心跳数据桥接 ──────────────────────────────────────────
# Bot 对话写入 task_executions.jsonl，让 Ising 引擎有真实数据吃
_ISING_EXEC_LOG = Path(__file__).parent.parent / "aios" / "agent_system" / "task_executions.jsonl"


def _log_task_execution(user_id: str, intent: str, start_ts: float,
                        end_ts: float, success: bool, reply_len: int):
    """写一条 task execution 记录到 Ising 引擎的数据源"""
    try:
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task_id": f"chat-{user_id}-{int(start_ts)}",
            "task_type": "chat",
            "description": f"telegram bot chat (intent={intent or 'general'})",
            "result": {
                "success": success,
                "agent": "telegram_bot",
                "duration": round(end_ts - start_ts, 3),
                "reply_length": reply_len,
            },
            "retry_count": 0,
            "total_attempts": 1,
        }
        with open(_ISING_EXEC_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"Ising exec log write failed: {e}")

# ── 比赛分析系统（match_analysis 接入） ──────────────────────────
# match_analysis 可能被 editable install 指向旧目录，强制用同级目录的版本
_MATCH_ANALYSIS_ROOT = APP_DIR.parent  # taijios_full_workspace
_MATCH_ANALYSIS_PKG = _MATCH_ANALYSIS_ROOT / "match_analysis"

if _MATCH_ANALYSIS_PKG.exists():
    # 先移除可能存在的旧 match_analysis 模块引用
    if "match_analysis" in sys.modules:
        del sys.modules["match_analysis"]
    for key in list(sys.modules):
        if key.startswith("match_analysis."):
            del sys.modules[key]
    # 确保正确路径排在最前面
    sys.path.insert(0, str(_MATCH_ANALYSIS_ROOT))

try:
    from match_analysis.adapters.api_football import ApiFootballAdapter
    from match_analysis.services.match_analyzer import MatchAnalyzer
    from match_analysis.main import TEAM_NAME_MAP
    from match_analysis.config import settings as ma_settings
    MATCH_ANALYSIS_OK = bool(ma_settings.API_FOOTBALL_KEY)
    if not MATCH_ANALYSIS_OK:
        logger.warning("match_analysis: API_FOOTBALL_KEY 未设置，比赛分析不可用")
    else:
        logger.info(f"match_analysis: 已加载 ({_MATCH_ANALYSIS_PKG})")
except ImportError as e:
    logger.warning(f"match_analysis 未安装: {e}")
    MATCH_ANALYSIS_OK = False
    TEAM_NAME_MAP = {}

BOT_DATA_DIR = APP_DIR / "data" / "bot_users"
BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)


class UserSession:
    """单个用户的完整引擎套件 + 对话历史"""

    def __init__(self, user_id: str, user_name: str = ""):
        self.user_id = user_id
        self.user_name = user_name
        self.user_dir = BOT_DATA_DIR / user_id
        self.user_dir.mkdir(exist_ok=True)

        evo_dir = str(self.user_dir / "evolution")
        os.makedirs(evo_dir, exist_ok=True)

        self.crystallizer = CrystallizationEngine(evo_dir)
        self.learner = ConversationLearner(evo_dir)
        self.hexagram = HexagramEngine(evo_dir)
        self.cognitive = CognitiveMap(evo_dir)
        self.pool = ExperiencePool(evo_dir)
        self.contribution = ContributionSystem(evo_dir)
        self.ecosystem = EcosystemManager(evo_dir)
        self.premium = PremiumManager(evo_dir)

        self.history = self._load_history()
        self.profile = self._load_profile()
        self.prev_user = ""
        self.prev_reply = ""
        self.onboarding_step = 0  # 0=完成, 1=姓名, 2=职业, 3=处境, 4=优势, 5=目标

        # 恢复上次对话状态
        if self.history and len(self.history) >= 2:
            for msg in reversed(self.history):
                if msg["role"] == "assistant" and not self.prev_reply:
                    self.prev_reply = msg["content"]
                elif msg["role"] == "user" and not self.prev_user:
                    self.prev_user = msg["content"]
                if self.prev_user and self.prev_reply:
                    break

    def _load_history(self) -> list:
        path = str(self.user_dir / "history.json")
        return safe_json_load(path, [])

    def _save_history(self):
        path = str(self.user_dir / "history.json")
        safe_json_save(path, self.history)

    def _load_profile(self) -> str:
        path = str(self.user_dir / "profile.json")
        data = safe_json_load(path, None)
        if data:
            parts = [f"姓名：{data.get('name', self.user_name or '未知')}"]
            for k, label in [("age", "年龄"), ("gender", "性别"),
                             ("job", "职业"), ("situation", "处境"),
                             ("strength", "优势"), ("goal", "目标")]:
                if data.get(k):
                    parts.append(f"{label}：{data[k]}")
            return "个体认知档案（快速版）\n" + "\n".join(parts)
        name = self.user_name or "未知"
        return f"个体认知档案（快速版）\n姓名：{name}"

    def save_profile(self, data: dict):
        path = str(self.user_dir / "profile.json")
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        safe_json_save(path, data)
        self.profile = self._load_profile()

    def get_round_count(self) -> int:
        return len(self.history) // 2 + 1

    def has_profile(self) -> bool:
        """资料卡是否已填写关键字段"""
        data = safe_json_load(str(self.user_dir / "profile.json"), None)
        if data:
            return bool(data.get("name") or data.get("job") or data.get("goal"))
        return False

    def reset(self):
        """重置用户所有数据"""
        import shutil
        self.history = []
        self.prev_user = ""
        self.prev_reply = ""
        self.onboarding_step = 0
        # 清空文件
        for f in self.user_dir.glob("*.json"):
            f.unlink()
        evo_dir = self.user_dir / "evolution"
        if evo_dir.exists():
            shutil.rmtree(evo_dir)
        evo_dir.mkdir(exist_ok=True)
        # 重新初始化引擎
        evo = str(evo_dir)
        self.crystallizer = CrystallizationEngine(evo)
        self.learner = ConversationLearner(evo)
        self.hexagram = HexagramEngine(evo)
        self.cognitive = CognitiveMap(evo)
        self.pool = ExperiencePool(evo)
        self.contribution = ContributionSystem(evo)
        self.ecosystem = EcosystemManager(evo)
        self.premium = PremiumManager(evo)
        self.profile = self._load_profile()


class TaijiBot:
    """
    TaijiOS Bot 核心引擎 — 集体学习版。

    每个用户独立进化，所有经验自动汇入全局共享池。
    交叉验证让经验质量越来越高，新用户直接继承全网最佳。
    """

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.sessions = {}  # user_id → UserSession
        self.knowledge = KnowledgeBase(str(KNOWLEDGE_DIR))

        # ── 多模型路由初始化 ──
        try:
            self.multi_models = init_models()
            available = get_available_names()
            self.router = ModelRouter(available) if available else None
            logger.info(f"多模型路由启动: {available}")
        except Exception as e:
            logger.warning(f"多模型初始化失败，降级到单模型: {e}")
            self.multi_models = {}
            self.router = None

        # 全局共享经验池（跨用户集体学习）
        global_dir = str(BOT_DATA_DIR / "global_evolution")
        os.makedirs(global_dir, exist_ok=True)
        self.global_pool = ExperiencePool(global_dir)

        network = self.global_pool.get_network_summary()
        models_str = ", ".join(self.multi_models.keys()) if self.multi_models else model_config.get('provider', '?')
        logger.info(f"TaijiBot 初始化 | 模型: {models_str} | "
                    f"知识库: {self.knowledge.get_status()} | "
                    f"共享池: {network or '空'}")

    def get_session(self, user_id: str, user_name: str = "") -> UserSession:
        """获取或创建用户会话"""
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id, user_name)
        return self.sessions[user_id]

    def handle_message(self, user_id: str, user_name: str,
                       message: str) -> str:
        """
        处理一条用户消息，返回军师回复。
        流程：引擎更新 → 意图 → 知识库 → 集体经验注入 → AI → 结晶 → 共享。
        """
        session = self.get_session(user_id, user_name)

        # 命令处理
        cmd = message.strip().lower()
        if cmd.startswith("/"):
            cmd = cmd[1:]  # 统一去掉斜杠前缀（兼容飞书/Telegram）
        if cmd in ("status", "状态"):
            return self._cmd_status(session)
        if cmd in ("help", "帮助"):
            return self._cmd_help()
        if cmd in ("kb", "知识库"):
            return self.knowledge.get_status()
        if cmd in ("profile", "资料卡", "我的资料"):
            return self._cmd_profile(session)
        if cmd.startswith("设置资料 ") or cmd.startswith("profile "):
            return self._cmd_set_profile(session, message)
        if cmd in ("reset", "重置", "重新开始"):
            return self._cmd_reset(session)
        if cmd in ("upgrade", "升级"):
            return session.premium.get_upgrade_info()
        if cmd.startswith("activate"):
            code = cmd.split(maxsplit=1)[1].strip() if " " in cmd else ""
            if not code:
                return "格式：activate <激活码>"
            success, msg = session.premium.activate(code)
            return msg
        if cmd in ("models", "模型", "路由"):
            if self.router:
                return self.router.get_status()
            return f"[单模型模式] {self.model_config.get('provider', '?')}"
        if cmd in ("深度分析", "deep", "analysis"):
            return self._cmd_deep_analysis(session)
        if cmd.startswith("match ") or cmd.startswith("比赛 "):
            logger.info(f"[match] 触发比赛分析: MATCH_ANALYSIS_OK={MATCH_ANALYSIS_OK}, cmd={cmd[:30]}")
            return self._cmd_match_analysis(session, message)
        if cmd == "export":
            return self._cmd_export(session)

        # 对话式资料卡引导（新用户前3条消息自动收集）
        if session.onboarding_step > 0:
            return self._handle_onboarding(session, message)

        # 1. 学习器反馈
        if session.prev_user and session.prev_reply:
            session.learner.record_outcome(
                session.prev_user, session.prev_reply, message)

        # 2. 收集最近消息
        recent = [m["content"] for m in session.history
                  if m["role"] == "user"]
        recent.append(message)
        rate = session.learner.get_positive_rate()

        # 3. 推演检测（每3轮，每天最多2次，只在有风险时展示）
        divine_text = ""
        round_count = session.get_round_count()
        if round_count >= 3 and round_count % 3 == 0:
            # 每日限制2次
            today = time.strftime("%Y-%m-%d")
            divine_key = f"divine_{today}"
            divine_count = session.ecosystem.data.get(divine_key, 0)
            if divine_count < 2:
                divination = session.hexagram.divine(recent, rate)
                if divination and divination.get("display"):
                    # 推演展示（Premium功能）
                    if session.premium.limits["hex_trend"]:
                        prediction = divination.get("prediction", "")
                        if any(kw in prediction for kw in ("走弱", "蓄力", "收一收", "防守", "困", "剥", "蒙")):
                            divine_text = divination["display"]
                    elif round_count == 3:
                        divine_text = "[卦象趋势] 升级Premium查看完整走势推演 → 输入 upgrade"
                    session.ecosystem.data[divine_key] = divine_count + 1
                    session.ecosystem._save()
            else:
                session.hexagram.update_from_conversation(recent, rate)
        else:
            session.hexagram.update_from_conversation(recent, rate)

        # 4. 意图检测
        intent_prompt = detect_intent(message)

        # 5. 知识库检索
        kb_prompt = self.knowledge.get_knowledge_prompt(message)

        # 6. 认知提取
        session.cognitive.extract_from_message(message, "")

        # 7. 构建 system prompt（合并个人+全局共享经验）
        personal_shared = session.pool.get_shared_prompt()
        global_shared = self.global_pool.get_shared_prompt()
        if personal_shared and global_shared:
            combined_shared = personal_shared + "\n" + global_shared
        else:
            combined_shared = personal_shared or global_shared

        system = build_quick_system(
            session.profile,
            session.crystallizer.get_active_rules(),
            session.learner.get_experience_summary(),
            session.hexagram.get_strategy_prompt(),
            session.cognitive.get_map_summary(),
            combined_shared,
            intent_prompt,
            kb_prompt)

        # 8. 调用 AI（多模型路由 + 计时 + 写入 Ising 数据源）
        _t0 = time.time()
        used_model = "legacy"
        try:
            if self.router and self.multi_models:
                # ── 多模型智能路由 ──
                primary, fallbacks = self.router.route(message, intent_prompt)
                reply, used_model = ensemble_call(
                    system, session.history, message,
                    primary=primary, fallbacks=fallbacks)
                if used_model == "none":
                    raise RuntimeError("所有模型均不可用")
            else:
                # ── 降级：单模型模式 ──
                reply = chat(system, session.history, message, self.model_config)
            _log_task_execution(user_id, intent_prompt[:30], _t0, time.time(),
                                True, len(reply))
            logger.info(f"[chat] user={user_id} model={used_model} "
                        f"len={len(reply)} time={time.time()-_t0:.1f}s")
        except Exception as e:
            _log_task_execution(user_id, intent_prompt[:30], _t0, time.time(),
                                False, 0)
            err = str(e)
            if "401" in err or "auth" in err.lower():
                return "[错误] API Key 无效，请检查配置"
            elif "429" in err or "rate" in err.lower():
                return "[错误] 请求太频繁，等几秒再试"
            else:
                return f"[错误] {err[:100]}"

        # 9. 后续更新
        session.cognitive.extract_from_message(message, reply)
        session.contribution.add_points("chat")
        session.ecosystem.record_action("chat")

        # 10. 结晶检查 + 集体学习（受Premium限制）
        crystal_text = ""
        crystal_ok, _ = session.premium.check_crystal_limit(
            len(session.crystallizer.get_active_rules()))
        if crystal_ok and session.learner.should_crystallize():
            new_crystals = session.crystallizer.crystallize()
            if new_crystals:
                # 自动贡献到全局共享池（脱敏后）
                contributed = self.global_pool.contribute_crystals(
                    new_crystals, user_id)
                total = len(session.crystallizer.get_active_rules())
                network = self.global_pool.get_network_summary()
                crystal_text = self._format_crystal_guide(
                    new_crystals, total, round_count, contributed, network)
                session.contribution.add_points("crystal", len(new_crystals))
                session.ecosystem.record_action("crystal", len(new_crystals))

        # 11. 集体学习里程碑
        guide_text = self._get_milestone_guide(session, round_count)

        # 12. 成就检查
        achieve_text = ""
        new_ach = session.ecosystem.check_achievements(
            session.ecosystem.get_stats())
        for a in new_ach:
            achieve_text += f"\n  ★ 成就解锁：{a['name']} — {a['desc']}"

        # 13. 保存历史
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": reply})
        max_hist = session.premium.limits["max_history"] * 2  # 每轮2条
        if len(session.history) > max_hist:
            old = session.history[:len(session.history) - max_hist]
            for m in old:
                if m["role"] == "user":
                    session.cognitive.extract_from_message(m["content"], "")
            session.history = session.history[-max_hist:]
        session._save_history()

        session.prev_user = message
        session.prev_reply = reply

        # 14. 组装最终回复
        parts = []
        if divine_text:
            parts.append(divine_text)
        parts.append(reply)
        if crystal_text:
            parts.append(crystal_text)
        if guide_text:
            parts.append(guide_text)
        if achieve_text:
            parts.append(achieve_text)

        return "\n".join(parts)

    def handle_greeting(self, user_id: str, user_name: str) -> str:
        """新用户或回来的用户打招呼"""
        session = self.get_session(user_id, user_name)
        rounds = len(session.history) // 2

        if rounds > 0:
            name = user_name or '主公'
            crystals = len(session.crystallizer.get_active_rules())
            msg = f"{name}，军师候着呢。上次聊了{rounds}轮，都记得。"
            if crystals:
                msg += f"已积累{crystals}条你的经验。"
            msg += "说事吧。"
            return msg
        else:
            # 新用户：启动对话式资料卡引导
            if not session.has_profile():
                session.onboarding_step = 1
                return "我是你的军师TaijiOS。知己知彼方能百战，先认识你——你叫什么？"
            name = user_name or '主公'
            return f"{name}，军师就位。有事直说，我给你拆局。"

    # ── 命令 ──────────────────────────────────────────

    def _cmd_status(self, s: UserSession) -> str:
        """状态命令（含集体学习信息）"""
        hex_name = s.hexagram.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        crystals = len(s.crystallizer.get_active_rules())
        rounds = len(s.history) // 2
        dims = sum(1 for d in ["位置","本事","钱财","野心","口碑"]
                   if s.cognitive.map.get(d))
        level = s.contribution.level[0]
        points = s.contribution.total_points
        shared = self.global_pool.get_shared_rules()
        network = self.global_pool.get_network_summary()

        lines = [
            f"━━ TaijiOS 进化状态 ━━",
            f"{s.premium.get_display()}",
            f"卦象：{strat.get('name', hex_name)}",
            f"策略：{strat.get('style', '')}",
            f"结晶：{crystals}条（你的独有经验）",
            f"认知：{dims}/5维度",
            f"对话：{rounds}轮",
            f"等级：{level} | {points}积分",
            f"知识库：{self.knowledge.get_status()}",
            f"━━ 集体学习 ━━",
            f"共享池：{len(shared)}条经验生效中",
        ]
        if network:
            lines.append(f"网络：{network}")
        lines.append("每个人的经验都不一样，交叉验证让军师越来越准。")
        return "\n".join(lines)

    def _cmd_profile(self, s: UserSession) -> str:
        """查看资料卡"""
        data = safe_json_load(str(s.user_dir / "profile.json"), None)
        if data and any(data.get(k) for k in ("name", "age", "job", "goal")):
            lines = ["━━ 你的资料卡 ━━"]
            for k, label in [("name", "姓名"), ("age", "年龄"),
                             ("gender", "性别"), ("job", "职业"),
                             ("situation", "处境"), ("strength", "优势"),
                             ("goal", "目标")]:
                v = data.get(k, "")
                if v:
                    lines.append(f"  {label}：{v}")
            lines.append(f"\n修改：发送「设置资料 姓名/年龄/性别/职业/目标」")
            lines.append(f"例如：设置资料 小九/31/男/创业者/做产品")
            return "\n".join(lines)

        return ("━━ 资料卡（未填写）━━\n"
                "军师越了解你，建议越准。\n\n"
                "一句话设置：\n"
                "  设置资料 姓名/年龄/性别/职业/目标\n\n"
                "例如：\n"
                "  设置资料 小九/31/男/创业者/做产品\n\n"
                "也可以只填部分：\n"
                "  设置资料 小明///学生/考研上岸")

    def _cmd_set_profile(self, s: UserSession, message: str) -> str:
        """设置资料卡：设置资料 姓名/年龄/性别/职业/目标"""
        # 去掉命令前缀
        text = message.strip()
        for prefix in ("设置资料 ", "设置资料", "profile "):
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
                break

        parts = text.split("/")
        fields = ["name", "age", "gender", "job", "goal"]
        labels = ["姓名", "年龄", "性别", "职业", "目标"]

        # 读取现有资料
        data = safe_json_load(str(s.user_dir / "profile.json"), {})

        # 更新非空字段
        updated = []
        for i, part in enumerate(parts):
            if i < len(fields) and part.strip():
                data[fields[i]] = part.strip()
                updated.append(f"{labels[i]}：{part.strip()}")

        if not updated:
            return ("格式：设置资料 姓名/年龄/性别/职业/目标\n"
                    "例如：设置资料 杨飞/31/男/创业者/做好TaijiOS")

        # 保存
        s.save_profile(data)

        lines = ["━━ 资料卡已更新 ━━"]
        lines.extend(f"  {u}" for u in updated)
        lines.append("\n军师会根据你的情况给出更精准的建议。")
        lines.append("查看完整资料：发送「资料卡」")
        return "\n".join(lines)

    def _handle_onboarding(self, s: UserSession, message: str) -> str:
        """对话式资料卡引导：5步了解主公（姓名→职业→处境→优势→目标）"""
        text = message.strip()

        # 读取现有资料
        data = safe_json_load(str(s.user_dir / "profile.json"), {})

        if s.onboarding_step == 1:
            data["name"] = text
            s.save_profile(data)
            s.onboarding_step = 2
            return f"记住了，{text}。你现在做什么？"

        elif s.onboarding_step == 2:
            data["job"] = text
            s.save_profile(data)
            s.onboarding_step = 3
            return "了解。现在你面对的局势是什么样的？一句话说说你当前的处境。"

        elif s.onboarding_step == 3:
            data["situation"] = text
            s.save_profile(data)
            s.onboarding_step = 4
            return "明白了。你手上最大的筹码是什么——能力、资源、人脉，哪个最强？"

        elif s.onboarding_step == 4:
            data["strength"] = text
            s.save_profile(data)
            s.onboarding_step = 5
            return "好。最后一个——你现在最想解决的一个问题是什么？"

        elif s.onboarding_step == 5:
            data["goal"] = text
            s.save_profile(data)
            s.onboarding_step = 0
            name = data.get("name", "主公")
            return f"{name}，军师已经了解你的局了。说事吧，我给你拆解。"

        s.onboarding_step = 0
        return ""

    def _cmd_reset(self, s: UserSession) -> str:
        """重置命令：清空所有数据重新开始"""
        s.reset()
        s.onboarding_step = 1
        return "已清空。重新来过——你叫什么？"

    def _cmd_help(self) -> str:
        return ("━━ TaijiOS 命令 ━━\n"
                "status — 进化状态\n"
                "资料卡 — 查看/修改个人资料\n"
                "help — 显示本帮助\n"
                "kb — 查看知识库\n"
                "比赛 A vs B — 足球赛事全流程分析\n"
                "深度分析 — 五维认知交叉分析（Premium）\n"
                "export — 导出经验包\n"
                "upgrade — 查看付费版\n"
                "activate <码> — 激活Premium\n"
                "重置 — 清空所有数据重新开始\n"
                "\n示例：比赛 利物浦 vs 巴黎\n"
                "　　　match 马竞 vs 巴萨\n"
                "\n直接打字就是和军师对话。")

    def _cmd_deep_analysis(self, s: UserSession) -> str:
        """深度交叉分析（Premium功能）"""
        can, msg = s.premium.check_deep_analysis()
        if not can:
            return msg
        lines = ["━━ 深度交叉分析 — 五维认知 × 卦象联动 ━━"]
        dims_data = {}
        for d in ["位置", "本事", "钱财", "野心", "口碑"]:
            items = s.cognitive.map.get(d, [])
            dims_data[d] = items
            count = len(items)
            bar = "█" * min(count, 10) + "░" * max(0, 10 - count)
            lines.append(f"  {d}：{bar} ({count}条)")
        patterns = s.cognitive.detect_patterns()
        if patterns:
            lines.append(f"\n  跨维度模式（{len(patterns)}个）：")
            for p in patterns[:5]:
                lines.append(f"    • {p.get('insight', '')}")
        else:
            lines.append("\n  暂未发现跨维度模式，多聊几轮积累数据")
        hex_name = s.hexagram.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        lines_display = "".join("⚊" if l == 1 else "⚋" for l in s.hexagram.current_lines)
        dim_labels = ["情绪", "行动", "认知", "资源", "方向", "满意"]
        yao_status = "  ".join(
            f"{dim_labels[i]}{'＋' if v == 1 else '－'}"
            for i, v in enumerate(s.hexagram.current_lines)
        )
        lines.append(f"\n  当前卦象：{strat.get('name', hex_name)}（{lines_display}）")
        lines.append(f"  六爻状态：{yao_status}")

        # ── 第一层：六爻矛盾检测 ──
        contradictions = s.hexagram.detect_contradictions()
        if contradictions:
            lines.append(f"\n  ⚡ 矛盾检测（{len(contradictions)}个）：")
            for c in contradictions[:3]:  # 最多展示3个，信息过载反而没用
                lines.append(f"    ▸ {c['contradiction']}")
                lines.append(f"      → {c['probe']}")
        else:
            lines.append("\n  六爻状态协调，暂无明显矛盾")

        weak_dims = [d for d, items in dims_data.items() if len(items) < 2]
        if weak_dims:
            lines.append(f"\n  薄弱维度：{'、'.join(weak_dims)}")
            lines.append("  建议：围绕薄弱维度多聊几轮，军师会自动补全认知地图")
        return "\n".join(lines)

    # ── 五虎上将：引擎信号采集 + 交叉分析 ─────────────────────────

    def _gather_engine_signals(self, s: UserSession) -> dict:
        """
        采集五虎上将（五引擎）的当前状态信号，供比赛分析注入。
        返回结构化 dict，方便下游拼 prompt。
        """
        hex_name = s.hexagram.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        dim_labels = ["情绪", "行动", "认知", "资源", "方向", "满意"]

        # 1. 卦象引擎
        hexagram_signal = {
            "name": strat.get("name", hex_name),
            "lines": s.hexagram.current_lines[:],
            "lines_display": "".join(
                "⚊" if v == 1 else "⚋" for v in s.hexagram.current_lines),
            "yao_status": [
                f"{dim_labels[i]}{'＋' if v == 1 else '－'}"
                for i, v in enumerate(s.hexagram.current_lines)
            ],
            "strategy": strat.get("strategy", ""),
            "style": strat.get("style", ""),
            "contradictions": s.hexagram.detect_contradictions(),
        }

        # 2. 认知地图
        cog_dims = {}
        for d in ["位置", "本事", "钱财", "野心", "口碑"]:
            items = s.cognitive.map.get(d, [])
            cog_dims[d] = {"count": len(items), "items": items[-3:]}
        patterns = s.cognitive.detect_patterns()
        cognitive_signal = {
            "dimensions": cog_dims,
            "patterns": [p.get("insight", "") for p in patterns[:3]],
            "fill_ratio": sum(1 for d in cog_dims.values() if d["count"] > 0),
        }

        # 3. 结晶引擎
        active_rules = s.crystallizer.get_active_rules()
        crystal_signal = {
            "count": len(active_rules),
            "top_rules": [r.get("rule", "") for r in active_rules[:3]],
        }

        # 4. 学习器
        learner_signal = {
            "positive_rate": s.learner.get_positive_rate(),
            "summary": s.learner.get_experience_summary(),
        }

        # 5. 经验池
        shared_rules = s.pool.get_shared_rules()
        pool_signal = {
            "shared_count": len(shared_rules),
            "top_shared": [r.get("rule", "") for r in shared_rules[:2]],
        }

        return {
            "hexagram": hexagram_signal,
            "cognitive": cognitive_signal,
            "crystal": crystal_signal,
            "learner": learner_signal,
            "pool": pool_signal,
        }

    def _cross_analyze_hexagram_cognitive(self, signals: dict) -> list:
        """
        Layer 2：六爻状态 × 认知五维 交叉映射。
        检测爻位与认知维度之间的矛盾/共振。

        映射关系：
          爻4(资源) ↔ 钱财    爻5(方向) ↔ 野心
          爻2(行动) ↔ 本事    爻3(认知) ↔ 位置
          爻1(情绪) ↔ 口碑    爻6(满意) ↔ 总体
        """
        hex_lines = signals["hexagram"]["lines"]
        cog_dims = signals["cognitive"]["dimensions"]

        # 映射表：(爻index, 爻标签, 认知维度, 共振描述, 矛盾描述)
        CROSS_MAP = [
            (3, "资源", "钱财",
             "资源充沛且钱财认知清晰——粮草充足可放手一搏",
             "资源{yao_state}但钱财认知{cog_state}——{detail}"),
            (4, "方向", "野心",
             "方向明确且野心认知到位——战略清晰可长驱直入",
             "方向{yao_state}但野心认知{cog_state}——{detail}"),
            (1, "行动", "本事",
             "行动力强且本事认知扎实——有将有兵执行力在线",
             "行动{yao_state}但本事认知{cog_state}——{detail}"),
            (2, "认知", "位置",
             "认知清晰且位置感明确——知己知彼方能百战",
             "认知{yao_state}但位置感{cog_state}——{detail}"),
            (0, "情绪", "口碑",
             "情绪稳定且口碑认知在位——军心稳固后方无忧",
             "情绪{yao_state}但口碑认知{cog_state}——{detail}"),
        ]

        insights = []
        for yao_idx, yao_label, cog_dim, resonance_desc, conflict_template in CROSS_MAP:
            yao_val = hex_lines[yao_idx]  # 1=阳(强), 0=阴(弱)
            cog_count = cog_dims.get(cog_dim, {}).get("count", 0)
            cog_strong = cog_count >= 2  # 2条以上认为认知充足

            if yao_val == 1 and cog_strong:
                # 共振：爻强 + 认知强
                insights.append({"type": "resonance", "detail": resonance_desc})
            elif yao_val == 1 and not cog_strong:
                # 矛盾：爻强但认知弱
                detail = f"{yao_label}爻显阳(强)但{cog_dim}维度仅{cog_count}条认知，自信可能缺乏根基"
                insights.append({
                    "type": "conflict",
                    "detail": conflict_template.format(
                        yao_state="显强", cog_state="薄弱", detail=detail),
                })
            elif yao_val == 0 and cog_strong:
                # 矛盾：爻弱但认知强
                detail = f"{yao_label}爻显阴(弱)但{cog_dim}维度有{cog_count}条认知，潜力未释放"
                insights.append({
                    "type": "conflict",
                    "detail": conflict_template.format(
                        yao_state="显弱", cog_state="充实", detail=detail),
                })
            # 爻弱+认知弱 = 一致，不报

        return insights

    def _format_engine_prompt_section(self, signals: dict,
                                       cross_insights: list) -> str:
        """把五虎上将信号 + Layer 2 交叉分析格式化为 prompt 注入段。"""
        parts = []

        # 卦象引擎
        h = signals["hexagram"]
        parts.append(f"## 五虎上将·卦象引擎")
        parts.append(f"当前卦象：{h['name']}（{h['lines_display']}）")
        parts.append(f"六爻状态：{'  '.join(h['yao_status'])}")
        parts.append(f"军师策略：{h['strategy']}")
        if h["contradictions"]:
            parts.append("六爻矛盾：")
            for c in h["contradictions"][:3]:
                parts.append(f"  ⚡ {c['contradiction']}")

        # 认知地图
        cog = signals["cognitive"]
        parts.append(f"\n## 五虎上将·认知地图（{cog['fill_ratio']}/5维）")
        for dim, data in cog["dimensions"].items():
            if data["count"] > 0:
                parts.append(f"  {dim}({data['count']}条)：{'；'.join(data['items'][-2:])}")
        if cog["patterns"]:
            parts.append("跨维度模式：" + "；".join(cog["patterns"]))

        # 结晶引擎
        cr = signals["crystal"]
        if cr["count"] > 0:
            parts.append(f"\n## 五虎上将·经验结晶（{cr['count']}条）")
            for r in cr["top_rules"]:
                parts.append(f"  • {r}")

        # 学习器
        lr = signals["learner"]
        rate = lr["positive_rate"]
        parts.append(f"\n## 五虎上将·学习器")
        parts.append(f"用户满意度：{rate:.0%}")

        # 经验池
        pl = signals["pool"]
        if pl["shared_count"] > 0:
            parts.append(f"\n## 五虎上将·共享经验池（{pl['shared_count']}条）")
            for r in pl["top_shared"]:
                parts.append(f"  • {r}")

        # Layer 2 交叉分析
        if cross_insights:
            parts.append(f"\n## Layer 2·爻位×认知 交叉映射")
            conflicts = [i for i in cross_insights if i["type"] == "conflict"]
            resonances = [i for i in cross_insights if i["type"] == "resonance"]
            if resonances:
                for r in resonances[:2]:
                    parts.append(f"  ✦ 共振：{r['detail']}")
            if conflicts:
                for c in conflicts[:3]:
                    parts.append(f"  ⚡ 矛盾：{c['detail']}")

        return "\n".join(parts)

    def _cmd_match_analysis(self, session: UserSession, message: str) -> str:
        """比赛分析：调 match_analysis 拉资料卡 → 五虎上将信号 → 交叉分析 → DeepSeek"""
        if not MATCH_ANALYSIS_OK:
            return "比赛分析功能需要 API_FOOTBALL_KEY，请在 .env 中配置"

        # 解析队名：match 利物浦 vs 阿森纳 / match 利物浦 阿森纳 / match 利物浦
        raw = message.strip()
        for prefix in ("match ", "比赛 ", "/match ", "/比赛 "):
            if raw.lower().startswith(prefix):
                raw = raw[len(prefix):]
                break

        # 分割主客队
        for sep in [" vs ", " VS ", " v ", "vs", "对", " - "]:
            if sep in raw:
                parts = raw.split(sep, 1)
                home_name = parts[0].strip()
                away_name = parts[1].strip() if len(parts) > 1 else ""
                break
        else:
            tokens = raw.strip().split()
            home_name = tokens[0] if tokens else ""
            away_name = tokens[1] if len(tokens) > 1 else ""

        if not home_name:
            return "格式：match 利物浦 vs 阿森纳\n或：比赛 利物浦 阿森纳"

        # 异步调 match_analysis
        try:
            card = self._run_match_query(home_name, away_name)
        except Exception as e:
            logger.error(f"比赛分析失败: {e}")
            return f"资料卡拉取失败：{str(e)[:100]}"

        if card is None:
            return f"找不到 {home_name}" + (f" vs {away_name}" if away_name else "") + " 近期的比赛"

        # 格式化资料卡（作为背景数据注入，不直接展示）
        card_text = self._format_match_card(card)

        # 摘要信号（如果有）
        summary_hint = ""
        if card.summary:
            s = card.summary
            if s.key_signals:
                summary_hint += "关键信号：" + "；".join(s.key_signals[:3]) + "\n"
            if s.contradictions:
                summary_hint += "矛盾点：" + "；".join(s.contradictions[:2]) + "\n"
            if s.verdict:
                summary_hint += f"初步判断：{s.verdict}（置信度{s.confidence}）\n"

        # ── 五虎上将：采集引擎信号 + Layer 2 交叉分析 ──
        engine_signals = self._gather_engine_signals(session)
        cross_insights = self._cross_analyze_hexagram_cognitive(engine_signals)
        engine_prompt = self._format_engine_prompt_section(
            engine_signals, cross_insights)

        # 统计五虎上将激活情况
        active_engines = []
        if engine_signals["hexagram"]["strategy"]:
            active_engines.append("卦象引擎")
        if engine_signals["cognitive"]["fill_ratio"] > 0:
            active_engines.append("认知地图")
        if engine_signals["crystal"]["count"] > 0:
            active_engines.append("经验结晶")
        active_engines.append("学习器")  # 学习器始终在线
        if engine_signals["pool"]["shared_count"] > 0:
            active_engines.append("经验池")

        logger.info(f"[match] 五虎上将激活: {active_engines}, "
                    f"Layer2交叉洞察: {len(cross_insights)}条")

        # 把卦象策略翻译成比赛语言
        hex_style = engine_signals["hexagram"]["style"]
        HEX_MATCH_MAP = {
            "进攻型": "当前局势利好进攻，建议关注强势出击型的队伍",
            "防守型": "当前局势宜守不宜攻，关注防守稳固、少丢球的一方",
            "镇定型": "局势多变，先看清再动，关注能在混乱中稳住的队",
            "渗透型": "不宜硬碰硬，关注擅长控场渗透、技术流的一方",
            "穿越型": "双方都有困难，关注逆境反弹能力强、韧性足的队伍",
            "借力型": "关注有主场优势、阵容深度、能借势的一方",
            "止步型": "形势不明朗，观望为主，不宜冒进",
            "清醒型": "表面形势好但暗藏风险，关注盘口是否过热",
            "稳扎型": "关注基本功扎实、稳扎稳打的一方",
            "发力型": "双方实力接近时关注爆发力更强的队",
            "积小型": "大局不明，关注小球、角球等细分市场",
        }
        hex_match_hint = ""
        for key, hint in HEX_MATCH_MAP.items():
            if key in hex_style:
                hex_match_hint = hint
                break
        if not hex_match_hint:
            hex_match_hint = "综合研判，以数据为主"

        system = (
            "你是TaijiOS认知军师——诸葛亮转世，专精赛事分析。\n"
            "你背后有五虎上将（五大认知引擎）同时为你提供情报。\n"
            "用户是你的主公，你用军师的眼光帮他看透战局。\n"
            "说话像诸葛亮分析战场：有气度，用数据说话，一针见血。\n"
            "比如用'地利''兵力''粮草''士气'来比喻主客场、阵容、资源、状态。\n\n"
            f"## 资料卡数据（API实时拉取，所有分析必须基于此数据）\n{card_text}\n"
            + (f"\n## 数据引擎信号\n{summary_hint}" if summary_hint else "")
            + f"\n## 五虎上将·认知引擎情报（{len(active_engines)}引擎在线）\n"
            + engine_prompt + "\n"
            + "\n## 写作规则（必须遵守）\n"
            + "1. 五虎上将·认知研判段：不要写抽象的卦象术语，要翻译成比赛语言。\n"
            + f"   卦象对本场的指导：{hex_match_hint}\n"
            + "2. 认知维度要结合比赛数据解读，比如'主公对进攻数据敏感（本事维度强），"
            + "而本场主队进攻端确实亮眼'。\n"
            + "3. Layer 2 交叉矛盾用战场比喻说清，别用'爻''阴阳'这些术语。\n"
            + "4. 军师总评要长（5-6句），把五虎上将的洞察自然融入总评，"
            + "不是简单复述，而是像真正的军师在做最终决策陈词。\n"
        )

        # 用 user message 给填空模板，强制 DeepSeek 按格式输出
        template_msg = (
            "请严格按以下模板输出分析，每一项都必须填写，不要跳过任何一项：\n\n"
            "**判断：**[一句话结论，不超过25字]\n"
            "**引导：**[一句话操作建议，不超过25字]\n\n"
            "━━ 战场态势 ━━\n"
            "• 排名：[主队]排名第X（积分XX） vs [客队]排名第X（积分XX）\n"
            "• 近况：[主队]近10场X胜X平X负，[客队]近10场X胜X平X负\n"
            "• 地利：[主队]主场X胜X平X负，[客队]客场X胜X平X负\n"
            "• 交锋：近X场[主队]X胜X平X负\n\n"
            "━━ 关键信号 ━━\n"
            "• [信号1，带具体数据]\n"
            "• [信号2，带具体数据]\n"
            "• [信号3，带具体数据]\n\n"
            "━━ 矛盾点 ━━\n"
            "• [如果有数据矛盾写出来，没有就写'数据面一致，无明显矛盾']\n\n"
            "⚠ 风险：\n• [风险1]\n• [风险2]\n\n"
            "━━ 五虎上将·认知研判 ━━\n"
            "• 战略方向：[用比赛语言说明当前策略倾向，比如'局势利好防守反击'，"
            "不要出现'卦象''爻''阴阳'等术语]\n"
            "• 认知优势：[主公在哪些维度认知充分，这对判断本场有什么帮助]\n"
            + ("• 盲区提醒：[主公认知薄弱的维度可能导致什么误判，给出具体建议]\n"
               if [i for i in cross_insights if i["type"] == "conflict"] else "")
            + "\n━━ 军师总评 ━━\n"
            "[用诸葛亮的口吻写5-6句深度总结。要求：\n"
            "第1句：总论战局大势\n"
            "第2句：点出关键胜负手（用数据）\n"
            "第3句：融入五虎上将的认知洞察（翻译成比赛语言）\n"
            "第4句：指出最大不确定性\n"
            "第5-6句：给出最终判断和操作建议，有军师气度]"
        )

        # 直接调 API
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.model_config["api_key"],
                base_url=self.model_config["base_url"],
            )
            resp = client.chat.completions.create(
                model=self.model_config.get("model", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": template_msg},
                ],
                max_tokens=2000,
                temperature=0.5,
            )
            reply = resp.choices[0].message.content or ""
        except Exception as e:
            return f"资料卡已拉取，但分析失败：{str(e)[:50]}"

        # 附加引擎仪表盘（每引擎一句话结论）
        h = engine_signals["hexagram"]
        cog = engine_signals["cognitive"]
        cr = engine_signals["crystal"]
        lr = engine_signals["learner"]
        pl = engine_signals["pool"]

        dashboard_lines = [f"\n\n━━ 五虎上将·仪表盘 ━━"]
        # 卦象引擎
        dashboard_lines.append(
            f"⚙ 卦象｜{h['name']} → {hex_match_hint[:15]}")
        # 认知地图
        filled = [d for d, v in cog["dimensions"].items() if v["count"] > 0]
        weak = [d for d, v in cog["dimensions"].items() if v["count"] == 0]
        if filled:
            dashboard_lines.append(
                f"⚙ 认知｜{''.join(filled)}在线"
                + (f"，{''.join(weak)}待补" if weak else "，全维就绪"))
        else:
            dashboard_lines.append("⚙ 认知｜尚未建立，多聊几轮自动构建")
        # 结晶引擎
        if cr["count"] > 0:
            dashboard_lines.append(
                f"⚙ 结晶｜{cr['count']}条经验加持")
        # 学习器
        rate_pct = lr["positive_rate"]
        if rate_pct >= 0.7:
            rate_label = "默契度高"
        elif rate_pct >= 0.4:
            rate_label = "磨合中"
        else:
            rate_label = "需要更多互动"
        dashboard_lines.append(f"⚙ 学习｜满意度{rate_pct:.0%} {rate_label}")
        # 经验池
        if pl["shared_count"] > 0:
            dashboard_lines.append(
                f"⚙ 经验池｜{pl['shared_count']}条集体智慧在线")
        # 交叉分析汇总
        if cross_insights:
            conflict_count = sum(
                1 for i in cross_insights if i["type"] == "conflict")
            resonance_count = sum(
                1 for i in cross_insights if i["type"] == "resonance")
            cross_summary = []
            if resonance_count:
                cross_summary.append(f"✦共振{resonance_count}")
            if conflict_count:
                cross_summary.append(f"⚡盲区{conflict_count}")
            dashboard_lines.append(
                f"⚙ 交叉｜{' '.join(cross_summary)}")

        dashboard_lines.append(
            f"{'─' * 20}\n"
            f"🔥 {len(active_engines)}引擎协同分析")

        engine_footer = "\n".join(dashboard_lines)
        return reply + engine_footer

    def _run_match_query(self, home_name: str, away_name: str):
        """同步包装异步的 match_analysis 调用"""
        import asyncio
        from match_analysis.adapters.api_football import ApiFootballAdapter
        from match_analysis.services.match_analyzer import MatchAnalyzer
        from match_analysis.main import TEAM_NAME_MAP
        from datetime import date as date_type, timedelta
        from difflib import SequenceMatcher

        async def _query():
            adapter = ApiFootballAdapter()
            analyzer = MatchAnalyzer(adapter)

            home_en = TEAM_NAME_MAP.get(home_name, home_name)
            away_en = TEAM_NAME_MAP.get(away_name, away_name) if away_name else ""
            today = date_type.today()
            year = today.year
            month = today.month
            season = str(year) if month >= 7 else str(year - 1)

            logger.info(f"[match] 搜索: {home_name}({home_en}) vs {away_name}({away_en})")

            # 搜索主队
            teams = await adapter.search_teams(home_en)
            if not teams:
                logger.warning("[match] 找不到主队")
                return None
            logger.info(f"[match] 找到{len(teams)}个队: {[t['name'] for t in teams[:3]]}")

            # 搜索比赛：用 next 参数搜接下来的比赛（1次API调用）
            for team in teams[:3]:
                try:
                    fixtures = await adapter.search_next_fixtures(team["id"], 5)
                    logger.info(f"[match] {team['name']}(id={team['id']}) 未来赛程: {len(fixtures)}场")
                    for f in fixtures:
                        logger.info(f"[match]   {f['home']} vs {f['away']} ({f['date'][:10]})")
                except Exception as e:
                    logger.error(f"[match] search_next_fixtures 失败: {e}", exc_info=True)
                    continue
                if not fixtures:
                    continue
                if away_en:
                    for fix in fixtures:
                        opponent = (fix["away"] if fix.get("home_id") == team["id"]
                                    else fix["home"])
                        ratio = SequenceMatcher(
                            None, away_en.lower(), opponent.lower()).ratio()
                        logger.info(f"[match] 匹配 {away_en} vs {opponent}: ratio={ratio:.2f}")
                        if ratio > 0.5 or away_en.lower() in opponent.lower():
                            logger.info(f"[match] 命中! fixture_id={fix['fixture_id']}")
                            return await analyzer.analyze(
                                fixture_id=fix["fixture_id"])
                else:
                    return await analyzer.analyze(
                        fixture_id=fixtures[0]["fixture_id"])
            return None

        # 兼容已有/没有 event loop 的情况
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 在已有 loop 中（如 Telegram async 环境），用新线程跑
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, _query()).result(timeout=30)
        else:
            return asyncio.run(_query())

    @staticmethod
    def _format_match_card(card) -> str:
        """把 MatchCard 格式化成军师能读懂的文本"""
        ctx = card.match_context
        hp = card.home_profile
        ap = card.away_profile
        hf = card.home_form
        af = card.away_form
        h2h = card.head_to_head
        ha = card.home_availability
        aa = card.away_availability
        odds = card.odds

        parts = []
        parts.append(f"━━ 比赛资料卡 ━━")
        parts.append(f"赛事：{ctx.league_name} {ctx.round}")
        parts.append(f"对阵：{ctx.home_team} vs {ctx.away_team}")
        parts.append(f"日期：{ctx.match_date}  场地：{ctx.venue}")
        if ctx.referee:
            parts.append(f"裁判：{ctx.referee}")

        # 排名档案
        ho = hp.overall
        parts.append(f"\n【主队 {hp.team_name}】排名#{hp.league_rank or '?'}  "
                      f"积分{hp.points or '?'}  "
                      f"总战绩 {ho.played}场 {ho.wins}胜{ho.draws}平{ho.losses}负  "
                      f"进{ho.goals_for}失{ho.goals_against}")
        if hp.home.played:
            h = hp.home
            parts.append(f"  主场：{h.played}场 {h.wins}胜{h.draws}平{h.losses}负 "
                          f"进{h.goals_for}失{h.goals_against}")
        if hp.xg_summary:
            xg = hp.xg_summary
            label = getattr(xg, 'performance_label', '') or ''
            parts.append(f"  xG数据：xG={xg.xg} xGA={xg.xga} ({label})")

        ao = ap.overall
        parts.append(f"\n【客队 {ap.team_name}】排名#{ap.league_rank or '?'}  "
                      f"积分{ap.points or '?'}  "
                      f"总战绩 {ao.played}场 {ao.wins}胜{ao.draws}平{ao.losses}负  "
                      f"进{ao.goals_for}失{ao.goals_against}")
        if ap.away.played:
            a = ap.away
            parts.append(f"  客场：{a.played}场 {a.wins}胜{a.draws}平{a.losses}负 "
                          f"进{a.goals_for}失{a.goals_against}")
        if ap.xg_summary:
            xg = ap.xg_summary
            label = getattr(xg, 'performance_label', '') or ''
            parts.append(f"  xG数据：xG={xg.xg} xGA={xg.xga} ({label})")

        # 近况
        parts.append(f"\n【近况】")
        parts.append(f"  {hf.team_name}：{hf.form_string or '?'} "
                      f"({hf.wins}胜{hf.draws}平{hf.losses}负/{hf.last_n}场)")
        if hf.xg_trend:
            parts.append(f"    xG趋势：{hf.xg_trend}")
        parts.append(f"  {af.team_name}：{af.form_string or '?'} "
                      f"({af.wins}胜{af.draws}平{af.losses}负/{af.last_n}场)")
        if af.xg_trend:
            parts.append(f"    xG趋势：{af.xg_trend}")

        # 交锋
        if h2h.total_matches:
            parts.append(f"\n【交锋记录】{h2h.total_matches}场：{h2h.team1} "
                          f"{h2h.team1_wins}胜{h2h.draws}平{h2h.team2_wins}负")

        # 伤停
        if ha.total_absent or aa.total_absent:
            parts.append(f"\n【伤停】{ha.team_name}缺阵{ha.total_absent}人  "
                          f"{aa.team_name}缺阵{aa.total_absent}人")
            for p in ha.absences[:3]:
                parts.append(f"  {ha.team_name}: {p.player_name} ({p.reason} {p.detail})")
            for p in aa.absences[:3]:
                parts.append(f"  {aa.team_name}: {p.player_name} ({p.reason} {p.detail})")

        # 赔率
        if odds.match_winner:
            bk = odds.match_winner[0]
            parts.append(f"\n【赔率】{bk.bookmaker}: 主{bk.home} 平{bk.draw} 客{bk.away}")
        if odds.cross_validation and odds.cross_validation.agreement_level:
            parts.append(f"  交叉验证：{odds.cross_validation.agreement_level}")

        # 摘要
        if card.summary:
            s = card.summary
            if s.key_signals:
                parts.append(f"\n【关键信号】")
                for sig in s.key_signals[:5]:
                    parts.append(f"  • {sig}")
            if s.contradictions:
                parts.append(f"【矛盾点】")
                for c in s.contradictions[:3]:
                    parts.append(f"  ⚡ {c}")
            if s.verdict:
                parts.append(f"【初步判断】{s.verdict} (置信度: {s.confidence})")

        # 缺失
        if card.missing_fields:
            parts.append(f"\n⚠ 缺失数据：{', '.join(card.missing_fields)}")

        return "\n".join(parts)

    def _cmd_export(self, s: UserSession) -> str:
        """导出经验包（Premium或Lv3解锁）"""
        lv3_unlocked = s.contribution.total_points >= 200
        can_export, export_msg = s.premium.check_export()
        if not can_export and not lv3_unlocked:
            return f"{export_msg}\n（Lv3将军以上也可免费导出，当前{s.contribution.total_points}/200积分）"
        rules = s.crystallizer.get_active_rules()
        if not rules:
            return "还没有经验结晶可导出，多聊几轮再来"
        hex_name = s.hexagram.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        hexagram_export = {
            "hexagram": hex_name,
            "lines": s.hexagram.current_lines,
            "strategy": strat.get("strategy", ""),
        }
        dim_summary = {}
        for d in ["位置", "本事", "钱财", "野心", "口碑"]:
            dim_summary[d] = len(s.cognitive.map.get(d, []))
        cognitive_export = {
            "dimensions": dim_summary,
            "patterns": [p.get("insight", "") for p in s.cognitive.detect_patterns()],
        }
        export_path = str(s.user_dir / "my_experience.taiji")
        result = s.pool.export_crystals(
            rules, export_path,
            hexagram_data=hexagram_export,
            cognitive_data=cognitive_export,
            contributor_id=s.contribution.get_contributor_id())
        if result:
            s.contribution.add_points("export")
            s.ecosystem.record_action("export")
            return f"已导出{len(rules)}条经验 → {result}\n把这个文件发给其他用户，用 import 命令导入"
        return "导出失败"

    # ── 集体学习引导 ──────────────────────────────────

    def _format_crystal_guide(self, new_crystals: list, total: int,
                              round_count: int, contributed: int,
                              network: str) -> str:
        """结晶通知（简短）"""
        rules = "、".join(c['rule'][:15] for c in new_crystals[:2])
        return f"\n[结晶+{len(new_crystals)}] {rules}（共{total}条）"

    def _get_milestone_guide(self, session: UserSession,
                             round_count: int) -> str:
        """里程碑提示（极简）"""
        if round_count == 5:
            return "\n[军师引擎已启动，正在学习你的思维模式]"
        if round_count == 10:
            crystals = len(session.crystallizer.get_active_rules())
            if crystals > 0:
                return f"\n[已积累{crystals}条你的独有经验]"
        return ""

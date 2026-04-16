"""
TaijiOS 多模型统一客户端
支持 DeepSeek / Gemini / GPT(中转) / Claude 四路调用
所有模型统一接口：call(system, history, user_input) -> str
"""

import os
import json
import time
import logging
import threading
import requests
from typing import Optional
from collections import deque

# 失败样本库规则引擎（可选依赖，缺失不影响主流程）
try:
    from aios.core.failure_rules import run_failure_rules as _run_failure_rules
except ImportError:
    _run_failure_rules = None

try:
    from aios.core.failure_samples import should_force_full_validation as _should_force_full
    from aios.core.failure_samples import get_active_l3_count as _get_l3_count
except ImportError:
    _should_force_full = None
    _get_l3_count = None

try:
    from aios.core.validation_meta import ValidationMeta
except ImportError:
    ValidationMeta = None

logger = logging.getLogger("multi_llm")


class LLMClient:
    """单个模型的调用封装"""

    def __init__(self, name: str, provider: str, api_key: str,
                 base_url: str = "", model: str = "",
                 max_tokens: int = 2000, temperature: float = 0.6):
        self.name = name
        self.provider = provider  # "openai_compat" | "gemini"
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def call(self, system: str, history: list, user_input: str,
             max_tokens: int = None, temperature: float = None) -> str:
        """统一调用接口"""
        mt = max_tokens or self.max_tokens
        tp = temperature if temperature is not None else self.temperature

        if self.provider == "gemini":
            return self._call_gemini(system, history, user_input, mt, tp)
        elif self.provider == "anthropic_native":
            return self._call_anthropic_native(system, history, user_input, mt, tp)
        else:
            return self._call_openai_compat(system, history, user_input, mt, tp)

    def _call_anthropic_native(self, system, history, user_input, max_tokens, temperature):
        """Anthropic 原生格式（/v1/messages），用于 Claude 中转站"""
        base = self.base_url.rstrip("/").removesuffix("/v1")
        url = f"{base}/v1/messages"
        messages = []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_input})
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        for attempt in range(2):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=120)
                r.raise_for_status()
                data = r.json()
                return data["content"][0]["text"]
            except Exception as e:
                if attempt == 0 and _is_transient(e):
                    time.sleep(2)
                    continue
                raise

    def _call_openai_compat(self, system, history, user_input, max_tokens, temperature):
        """OpenAI兼容格式（DeepSeek/GPT中转）"""
        messages = [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": user_input}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(2):
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == 0 and _is_transient(e):
                    time.sleep(2)
                    continue
                raise

    def _call_gemini(self, system, history, user_input, max_tokens, temperature):
        """Gemini 原生API（使用 systemInstruction 字段）"""
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_input}]})

        # 思考模型（gemini-2.5-pro 等）用完 token 后 content.parts 为空
        # 保底 1024 token 确保思考 + 正文都有空间
        is_thinking_model = "pro" in self.model or "think" in self.model
        effective_tokens = max(max_tokens, 1024) if is_thinking_model else max_tokens

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": effective_tokens,
                "temperature": temperature,
            }
        }
        # 思考模型限制思考预算，避免思考吃完所有 token
        if is_thinking_model:
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 512}

        # Gemini 原生 system instruction（不用假 user/model 轮）
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{self.model}:generateContent?key={self.api_key}")

        for attempt in range(2):
            try:
                r = requests.post(url, headers={"Content-Type": "application/json"},
                                  json=payload, timeout=90)
                r.raise_for_status()
                data = r.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(f"Gemini empty response: {data}")
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                # 过滤掉 thought=True 的思考过程，只取正文
                texts = [p["text"] for p in parts
                         if "text" in p and not p.get("thought", False)]
                if not texts:
                    # 降级：取所有 text（含思考）
                    texts = [p["text"] for p in parts if "text" in p]
                if not texts:
                    finish = candidates[0].get("finishReason", "")
                    raise RuntimeError(f"Gemini no extractable content (finishReason={finish})")
                return "\n".join(texts)
            except Exception as e:
                if attempt == 0 and _is_transient(e):
                    time.sleep(2)
                    continue
                raise

    def is_available(self) -> bool:
        return bool(self.api_key)

    def __repr__(self):
        return f"LLM({self.name}/{self.model})"


def _is_transient(e):
    err = str(e).lower()
    return any(kw in err for kw in ["timeout", "connect", "rate", "429", "503"])


# ── 验证健康度跟踪（R5规则）──────────────────────────────────────────────────

_validation_history: deque = deque(maxlen=20)
_validation_lock = threading.Lock()


def _track_validation(result: str):
    """记录验证结果用于超时率统计（线程安全）"""
    with _validation_lock:
        _validation_history.append(result)


def _validation_timeout_rate() -> float:
    """最近20次验证中GPT失败的比率（线程安全）"""
    with _validation_lock:
        if not _validation_history:
            return 0.0
        fails = sum(1 for r in _validation_history if r in ("gpt_error", "all_failed"))
        return fails / len(_validation_history)


def get_validation_health() -> dict:
    """获取验证管道健康状态"""
    rate = _validation_timeout_rate()
    return {
        "timeout_rate": f"{rate:.0%}",
        "status": "DEGRADED" if rate > 0.3 else "HEALTHY",
        "recent": list(_validation_history),
    }


# ── 全局模型注册表 ──────────────────────────────────────────────────────────

_registry: dict[str, LLMClient] = {}


def init_models():
    """从环境变量初始化所有可用模型"""
    global _registry
    _registry.clear()

    # DeepSeek
    ds_key = os.getenv("DEEPSEEK_API_KEY", "")
    if ds_key:
        _registry["deepseek"] = LLMClient(
            name="DeepSeek", provider="openai_compat",
            api_key=ds_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        )

    # Gemini
    gem_key = os.getenv("GEMINI_API_KEY", "")
    if gem_key:
        _registry["gemini"] = LLMClient(
            name="Gemini 2.5 Flash", provider="gemini",
            api_key=gem_key,
            model="gemini-2.5-flash",  # 日常对话主力
        )
        _registry["gemini_pro"] = LLMClient(
            name="Gemini 2.5 Pro", provider="gemini",
            api_key=gem_key,
            model="gemini-2.5-pro",  # 深度分析
            max_tokens=4096,
        )

    # GPT (中转站)
    gpt_key = os.getenv("OPENAI_API_KEY", "")
    gpt_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    if gpt_key:
        _registry["gpt"] = LLMClient(
            name="GPT-5.4", provider="openai_compat",
            api_key=gpt_key,
            base_url=gpt_base,
            model="gpt-5.4",
        )

    # Claude Opus 4.6（GPT分组中转，OpenAI-compat；官方 ANTHROPIC_API_KEY 作保底）
    claude_key = os.getenv("CLAUDE_RELAY_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    claude_base = os.getenv("CLAUDE_RELAY_BASE", "https://apiport.cc.cd/v1")
    if claude_key:
        _registry["claude"] = LLMClient(
            name="Claude Opus 4.6", provider="openai_compat",
            api_key=claude_key,
            base_url=claude_base,
            model="claude-opus-4-6",
            max_tokens=4096,
            temperature=0.7,
        )

    logger.info(f"Multi-LLM initialized: {list(_registry.keys())}")
    return _registry


def health_check() -> dict[str, str]:
    """快速健康检查：每个模型发一个 'hi' 测试连通性"""
    results = {}
    for name, client in _registry.items():
        try:
            t0 = time.time()
            client.call("test", [], "hi", max_tokens=5, temperature=0)
            ms = int((time.time() - t0) * 1000)
            results[name] = f"OK ({ms}ms)"
        except Exception as e:
            err = str(e)[:60]
            results[name] = f"FAIL: {err}"
    return results


def get_status_summary() -> str:
    """一行式状态摘要，给用户看"""
    if not _registry:
        return "模型: 未初始化"
    names = list(_registry.keys())
    return f"模型: {', '.join(names)} ({len(names)}个就绪)"


def get_model(name: str) -> Optional[LLMClient]:
    """获取指定模型"""
    return _registry.get(name)


def get_all_models() -> dict[str, LLMClient]:
    """获取所有可用模型"""
    return dict(_registry)


def get_available_names() -> list[str]:
    """获取所有可用模型名"""
    return list(_registry.keys())


# ── 多模型协作工具 ──────────────────────────────────────────────────────────

def cross_validate(prompt: str, models: list[str] = None,
                   max_tokens: int = 800, temperature: float = 0) -> dict:
    """
    多模型交叉验证：并发调用多个模型，返回各自结果。
    用于易经知识验证、卦象计算校验等场景。
    """
    if not models:
        models = list(_registry.keys())

    results = {}
    results_lock = threading.Lock()

    def _call_one(name):
        client = _registry.get(name)
        if not client:
            with results_lock:
                results[name] = {"error": f"Model {name} not available"}
            return
        try:
            if client.provider == "gemini":
                lite = LLMClient(
                    name=f"{client.name}_validate",
                    provider="gemini",
                    api_key=client.api_key,
                    model="gemini-2.5-flash-lite",
                )
                answer = lite.call("", [], prompt,
                                   max_tokens=max_tokens, temperature=temperature)
            else:
                answer = client.call(
                    "You are a precise knowledge validator. Answer concisely.",
                    [], prompt, max_tokens=max_tokens, temperature=temperature)
            with results_lock:
                results[name] = {"answer": answer, "model": client.model}
        except Exception as e:
            with results_lock:
                results[name] = {"error": str(e)}

    # 并发调用，总超时 max(单模型120s, 不超过180s)
    threads = []
    for name in models:
        t = threading.Thread(target=_call_one, args=(name,), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=180)

    return results


def ensemble_call(system: str, history: list, user_input: str,
                  primary: str = "deepseek",
                  fallbacks: list[str] = None) -> tuple[str, str]:
    """
    带降级的模型调用：先用主模型，失败后自动切换。
    返回 (回复内容, 实际使用的模型名)
    """
    if fallbacks is None:
        fallbacks = ["gpt", "gemini"]

    chain = [primary] + fallbacks

    for name in chain:
        client = _registry.get(name)
        if not client:
            continue
        try:
            reply = client.call(system, history, user_input)
            return reply, name
        except Exception as e:
            logger.warning(f"Model {name} failed: {e}, trying next...")
            continue

    return "[错误] 所有模型均不可用", "none"


def _run_rules_safe(original: str, verified: str, val_meta) -> list[dict]:
    """安全调用失败样本库规则引擎，返回完整结构化结果"""
    if _run_failure_rules is None:
        return []
    try:
        # val_meta 可能是 ValidationMeta 或 dict，统一转 dict 给规则引擎
        if hasattr(val_meta, '_to_compat_dict'):
            meta_dict = val_meta._to_compat_dict()
        elif isinstance(val_meta, dict):
            meta_dict = val_meta
        else:
            meta_dict = {}
        return _run_failure_rules(original, verified, meta_dict)
    except Exception as e:
        logger.warning(f"[validated_call] failure_rules 执行异常: {e}")
        return []


def validated_call(system: str, history: list, user_input: str,
                   max_tokens: int = 2000) -> tuple[str, "ValidationMeta | dict"]:
    """
    强制两阶段流水线：DeepSeek 生成 → GPT-5.4 审核/修正。
    集成失败样本库检测规则 + Ising心跳联动。

    Returns:
        (最终回答, ValidationMeta) — ValidationMeta 支持 meta["step1"] 兼容访问
    """
    _t0 = time.time()

    # ── Ising 心跳检查 ──────────────────────────────────────────
    _block = _should_force_full() if _should_force_full else False
    _l3_count = _get_l3_count() if _get_l3_count else 0

    def _make_meta(**kwargs) -> "ValidationMeta | dict":
        """构建 ValidationMeta，缺失时降级为 dict"""
        if ValidationMeta is None:
            return {
                "step1": kwargs.get("primary_model", ""),
                "step2": kwargs.get("validator_model") or "skipped",
                "modified": kwargs.get("modified", False),
                "triggered_rules": kwargs.get("triggered_rules", []),
            }
        return ValidationMeta(
            block_fallback=_block,
            active_l3_count_at_call=_l3_count,
            **kwargs,
        )

    # ── Step 1: DeepSeek 生成 ──────────────────────────────────────
    ds = _registry.get("deepseek")
    if not ds:
        _track_validation("ds_unavailable")
        reply, model = ensemble_call(system, history, user_input)
        elapsed = (time.time() - _t0) * 1000
        meta = _make_meta(
            final_content=reply, primary_model=model,
            model_chain=model, verification_status="skipped",
            total_ms=elapsed,
        )
        return reply, meta

    ds_reply = None
    _t_gen = time.time()
    try:
        ds_reply = ds.call(system, history, user_input, max_tokens=max_tokens)
    except Exception as e:
        logger.warning(f"[validated_call] DeepSeek failed: {e}, fallback to gpt direct")
        _track_validation("ds_failed")
        gen_ms = (time.time() - _t_gen) * 1000
        gpt = _registry.get("gpt")
        if gpt:
            try:
                reply = gpt.call(system, history, user_input, max_tokens=max_tokens)
                elapsed = (time.time() - _t0) * 1000
                meta = _make_meta(
                    final_content=reply, primary_model="gpt_direct",
                    model_chain="gpt_direct", verification_status="skipped",
                    generation_ms=gen_ms, total_ms=elapsed,
                )
                return reply, meta
            except Exception:
                pass
        elapsed = (time.time() - _t0) * 1000
        err_msg = f"[错误] DeepSeek 不可用: {e}"
        meta = _make_meta(
            final_content=err_msg, primary_model="error",
            model_chain="error", verification_status="error",
            generation_ms=gen_ms, total_ms=elapsed,
        )
        return err_msg, meta

    gen_ms = (time.time() - _t_gen) * 1000

    # ── Step 2: GPT-5.4 审核 ──────────────────────────────────────
    gpt = _registry.get("gpt")
    if not gpt:
        logger.info("[validated_call] GPT 未注册，跳过验证")
        _track_validation("gpt_unavailable")
        elapsed = (time.time() - _t0) * 1000
        meta = _make_meta(
            final_content=ds_reply, primary_model="deepseek",
            model_chain="deepseek", verification_status="skipped",
            generation_ms=gen_ms, total_ms=elapsed,
        )
        meta.triggered_rules = _run_rules_safe(ds_reply, ds_reply, meta) if ValidationMeta else []
        return ds_reply, meta

    # 精简验证prompt
    validator_system = (
        "质检员。审核初稿，有错则修正后输出完整版，无错则原样输出。"
        "保持语言风格一致，不解释审核过程。"
    )
    if len(ds_reply) > 2000:
        trimmed = ds_reply[:1500] + "\n...(中间省略)...\n" + ds_reply[-500:]
    else:
        trimmed = ds_reply
    validator_prompt = f"问：{user_input}\n\n初稿：\n{trimmed}"

    def _do_validate(client, name):
        reply = client.call(
            validator_system, [], validator_prompt,
            max_tokens=max_tokens, temperature=0.3
        )
        ds_words = set(ds_reply.split())
        v_words = set(reply.split())
        diff_ratio = len(v_words - ds_words) / max(len(ds_words), 1)
        modified = diff_ratio > 0.15
        if modified:
            logger.info(f"[validated_call] {name} 修正了 DeepSeek 回答 (diff={diff_ratio:.0%})")
        return reply, modified

    # 主验证：GPT-5.4
    _t_val = time.time()
    try:
        gpt_reply, modified = _do_validate(gpt, "GPT-5.4")
        _track_validation("gpt_ok")
        val_ms = (time.time() - _t_val) * 1000
        elapsed = (time.time() - _t0) * 1000
        status = "modified" if modified else "passed"
        meta = _make_meta(
            final_content=gpt_reply, primary_model="deepseek",
            validator_model="gpt", model_chain="deepseek→gpt",
            verification_status=status, modified=modified,
            generation_ms=gen_ms, verification_ms=val_ms, total_ms=elapsed,
        )
        meta.triggered_rules = _run_rules_safe(ds_reply, gpt_reply, meta)
        return gpt_reply, meta
    except Exception as e:
        logger.warning(f"[validated_call] GPT 验证失败: {e}")
        _track_validation("gpt_error")

    # 降级验证
    if not _block and _validation_timeout_rate() < 0.3:
        for fb_name in ["claude", "gemini"]:
            fb = _registry.get(fb_name)
            if not fb:
                continue
            _t_fb = time.time()
            try:
                fb_reply, modified = _do_validate(fb, fb_name)
                _track_validation(f"{fb_name}_ok")
                val_ms = (time.time() - _t_fb) * 1000
                elapsed = (time.time() - _t0) * 1000
                status = "modified" if modified else "degraded"
                meta = _make_meta(
                    final_content=fb_reply, primary_model="deepseek",
                    validator_model=fb_name, model_chain=f"deepseek→{fb_name}",
                    verification_status=status, modified=modified,
                    degraded=True, degradation_reason="gpt_timeout",
                    generation_ms=gen_ms, verification_ms=val_ms,
                    degradation_ms=val_ms, total_ms=elapsed,
                )
                meta.triggered_rules = _run_rules_safe(ds_reply, fb_reply, meta)
                return fb_reply, meta
            except Exception as e2:
                logger.warning(f"[validated_call] {fb_name} 降级验证也失败: {e2}")
                _track_validation(f"{fb_name}_error")
                continue
    elif _block:
        logger.warning("[validated_call] Ising心跳禁止降级（L3活跃数超阈值）")

    # 全部失败
    _track_validation("all_failed")
    logger.warning("[validated_call] 所有验证模型均失败，返回未验证原文")
    elapsed = (time.time() - _t0) * 1000
    meta = _make_meta(
        final_content=ds_reply, primary_model="deepseek",
        model_chain="deepseek→all_failed", verification_status="failed",
        degraded=True, degradation_reason="all_failed",
        generation_ms=gen_ms, total_ms=elapsed,
    )
    meta.triggered_rules = _run_rules_safe(ds_reply, ds_reply, meta)
    return ds_reply, meta

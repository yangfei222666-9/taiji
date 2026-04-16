#!/usr/bin/env python3
"""
共享 LLM 调用层 — 四引擎统一使用

支持多 provider：
- Anthropic (claude-*): client.messages.create()
- DeepSeek  (deepseek-*): OpenAI-compatible API，deepseek-reasoner 含推理链
- 豆包      (doubao-*): ByteDance Ark，OpenAI-compatible API（key 待接入）

模型分级：
- deepseek-reasoner:  易经推理主力（深度思考，推理链最强）
- doubao-pro-32k:     中文润色 / 断语自然度（幻觉率最低）
- claude-sonnet-4-6:  Commander / 高质量决策
- claude-haiku-4-5:   Soldier / 轻量执行

Author: TaijiOS
Date: 2026-04-09 / 2026-04-13 多模型扩展
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)
except ImportError:
    pass

log = logging.getLogger("aios.llm_caller")

# ============================================================
# API 配置加载（复用 real_coder.py 模式）
# ============================================================

_config_cache = None


def _load_config() -> Dict:
    """加载 config.json"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_file = Path(__file__).parent / "config.json"
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                _config_cache = json.load(f)
                return _config_cache
        except Exception as e:
            log.warning(f"config.json 加载失败: {e}")

    _config_cache = {}
    return _config_cache


def _detect_provider(model: str) -> str:
    """根据模型名称判断 provider"""
    if model.startswith("deepseek-"):
        return "deepseek"
    if model.startswith("doubao-") or model.startswith("ep-"):
        return "doubao"
    if model.startswith("claude-"):
        return "relay"  # GPT分组中转，OpenAI-compat；无 relay key 时降级 anthropic
    return "anthropic"


def _get_client():
    """获取官方 Anthropic 客户端（保底兜底）"""
    import anthropic

    config = _load_config()
    api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    base_url = config.get("anthropic_base_url") or "https://api.anthropic.com"

    if not api_key:
        raise RuntimeError("官方 Anthropic API Key 未设置，无法保底。请设置 ANTHROPIC_API_KEY。")

    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def _get_deepseek_client():
    """获取 DeepSeek 客户端（OpenAI-compatible）"""
    from openai import OpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量。")

    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _get_doubao_client():
    """获取豆包客户端（ByteDance Ark，OpenAI-compatible）"""
    from openai import OpenAI

    api_key = os.getenv("DOUBAO_API_KEY")
    if not api_key:
        raise RuntimeError("未设置 DOUBAO_API_KEY 环境变量。")

    return OpenAI(api_key=api_key, base_url="https://ark.cn-beijing.volces.com/api/v3")


def _get_relay_client():
    """获取 Claude 中转客户端（GPT分组，OpenAI-compat，支持 claude-* 模型）"""
    from openai import OpenAI

    api_key = os.getenv("CLAUDE_RELAY_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("CLAUDE_RELAY_BASE") or os.getenv("OPENAI_API_BASE", "https://apiport.cc.cd/v1")
    if not api_key:
        raise RuntimeError("未设置 CLAUDE_RELAY_KEY，无法使用中转站调用 Claude。")
    return OpenAI(api_key=api_key, base_url=base_url)


# ============================================================
# 成本记录
# ============================================================

def _record_cost(model: str, input_tokens: int, output_tokens: int):
    """记录 API 调用成本"""
    try:
        from cost_guardian import CostGuardian
        cg = CostGuardian()
        cost = cg.calculate_cost(model, input_tokens, output_tokens)
        log.info(f"[LLM] model={model} in={input_tokens} out={output_tokens} cost=${cost:.4f}")
    except Exception:
        pass


# ============================================================
# 核心调用函数
# ============================================================

def _call_anthropic(system_prompt: str, user_prompt: str, model: str,
                    max_tokens: int, temperature: float) -> str:
    client = _get_client()
    t0 = time.time()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    elapsed = time.time() - t0
    text = message.content[0].text
    input_tokens = getattr(message.usage, "input_tokens", 0)
    output_tokens = getattr(message.usage, "output_tokens", 0)
    _record_cost(model, input_tokens, output_tokens)
    log.info(f"[LLM] OK model={model} time={elapsed:.1f}s tokens={input_tokens}+{output_tokens}")
    return text


def _call_openai_compat(system_prompt: str, user_prompt: str, model: str,
                        max_tokens: int, temperature: float,
                        client_fn) -> str:
    """通用 OpenAI-compatible 调用（DeepSeek / 豆包共用）"""
    client = client_fn()
    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    elapsed = time.time() - t0
    choice = response.choices[0]
    text = choice.message.content or ""

    # DeepSeek-R1 推理链附加到日志（不计入返回值）
    reasoning = getattr(choice.message, "reasoning_content", None)
    if reasoning:
        log.debug(f"[LLM] reasoning_content length={len(reasoning)}")

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0)
    _record_cost(model, input_tokens, output_tokens)
    log.info(f"[LLM] OK model={model} time={elapsed:.1f}s tokens={input_tokens}+{output_tokens}")
    return text


def call_llm(system_prompt: str,
             user_prompt: str,
             model: str = "deepseek-chat",
             max_tokens: int = 2048,
             temperature: float = 0.7) -> str:
    """
    多 provider LLM 调用，按 model 前缀自动路由。

    model 前缀路由：
      deepseek-* → DeepSeek API（主力，便宜）
      doubao-* / ep-* → 豆包 Ark API
      claude-* → 官方 Anthropic SDK（保底兜底）

    claude-* 调用失败时不抛出，返回 [LLM_ERROR] 前缀。

    Returns:
        LLM 响应文本。失败时返回 "[LLM_ERROR] ..." 前缀字符串
    """
    provider = _detect_provider(model)
    try:
        if provider == "deepseek":
            return _call_openai_compat(system_prompt, user_prompt, model,
                                       max_tokens, temperature, _get_deepseek_client)
        elif provider == "doubao":
            return _call_openai_compat(system_prompt, user_prompt, model,
                                       max_tokens, temperature, _get_doubao_client)
        elif provider == "relay":
            # 优先走 GPT 分组中转（便宜），失败时降级到官方 Anthropic 保底
            try:
                return _call_openai_compat(system_prompt, user_prompt, model,
                                           max_tokens, temperature, _get_relay_client)
            except Exception as relay_err:
                log.warning(f"[LLM] relay failed ({relay_err}), fallback → official Anthropic")
                return _call_anthropic(system_prompt, user_prompt, model,
                                       max_tokens, temperature)
        else:
            return _call_anthropic(system_prompt, user_prompt, model,
                                   max_tokens, temperature)

    except Exception as e:
        log.error(f"[LLM] FAIL model={model} provider={provider} error={e}")
        return f"[LLM_ERROR] {e}"


def call_llm_json(system_prompt: str,
                  user_prompt: str,
                  model: str = "claude-sonnet-4-6",
                  max_tokens: int = 2048) -> Dict[str, Any]:
    """
    调用 Claude API 并解析 JSON 响应

    system_prompt 中应包含"请以 JSON 格式回答"等指令。

    Returns:
        解析后的 dict。失败时返回 {"error": "...", "raw": "..."}
    """
    text = call_llm(system_prompt, user_prompt, model, max_tokens)

    if text.startswith("[LLM_ERROR]"):
        return {"error": text, "raw": text}

    # 清理 markdown 代码块
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 和最后一个 }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"error": "JSON parse failed", "raw": text}


# ============================================================
# 易经专用快捷调用
# ============================================================

def call_yijing_reason(system_prompt: str, user_prompt: str,
                       max_tokens: int = 4096) -> str:
    """易经推理主力 — DeepSeek-R1 深度思考模式"""
    return call_llm(system_prompt, user_prompt,
                    model="deepseek-reasoner", max_tokens=max_tokens, temperature=0.6)


def call_yijing_polish(system_prompt: str, user_prompt: str,
                       max_tokens: int = 2048) -> str:
    """断语中文润色 — 豆包（key 未配置时 fallback 到 claude-haiku）"""
    if os.getenv("DOUBAO_API_KEY"):
        return call_llm(system_prompt, user_prompt,
                        model="doubao-pro-32k", max_tokens=max_tokens, temperature=0.5)
    log.info("[LLM] DOUBAO_API_KEY 未配置，polish fallback → claude-haiku-4-5")
    return call_llm(system_prompt, user_prompt,
                    model="claude-haiku-4-5", max_tokens=max_tokens, temperature=0.5)


def is_llm_available() -> bool:
    """检查 LLM 是否可用（中转 key 或官方 key 任一有效即算可用）"""
    if os.getenv("CLAUDE_RELAY_KEY") or os.getenv("DEEPSEEK_API_KEY"):
        return True
    config = _load_config()
    api_key = config.get("anthropic_api_key")
    if api_key and api_key != "your-api-key-here":
        return True
    return bool(os.getenv("ANTHROPIC_API_KEY"))


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== LLM Caller 测试 ===\n")

    print(f"LLM 可用: {is_llm_available()}")

    if is_llm_available():
        # 文本调用
        print("\n--- 文本调用 ---")
        result = call_llm(
            system_prompt="你是一个简洁的助手，用一句话回答。",
            user_prompt="TaijiOS 是什么？",
            model="claude-haiku-4-5",
            max_tokens=100,
        )
        print(f"响应: {result}")

        # JSON 调用
        print("\n--- JSON 调用 ---")
        result_json = call_llm_json(
            system_prompt="你是一个 JSON 生成器。请严格以 JSON 格式回答，不要包含其他内容。",
            user_prompt='分析这个错误：API timeout。返回 {"error_type": "...", "severity": "...", "suggestion": "..."}',
            model="claude-haiku-4-5",
            max_tokens=200,
        )
        print(f"JSON: {json.dumps(result_json, ensure_ascii=False, indent=2)}")
    else:
        print("⚠️ API Key 未配置，跳过实际调用")

    print("\n✅ LLM Caller 测试完成")

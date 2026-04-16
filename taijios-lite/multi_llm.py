"""
TaijiOS 多模型统一客户端
支持 DeepSeek / Gemini / GPT(中转) / Claude 四路调用
所有模型统一接口：call(system, history, user_input) -> str
"""

import os
import json
import time
import logging
import requests
from typing import Optional

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
                r = requests.post(url, headers=headers, json=payload, timeout=60)
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
                    timeout=60,
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

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            }
        }
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
                # 提取文本（有些模型返回 thoughtSignature 而非 text）
                texts = [p["text"] for p in parts if "text" in p]
                if not texts:
                    # Gemini thinking model 可能只有 thoughtSignature
                    # 尝试把最后一个 part 当文本
                    for p in reversed(parts):
                        if isinstance(p, dict):
                            for key in ("text", "thoughtSignature"):
                                if key in p and isinstance(p[key], str) and len(p[key]) < 500:
                                    texts = [p[key]]
                                    break
                        if texts:
                            break
                if not texts:
                    raise RuntimeError(f"Gemini no extractable content")
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
    多模型交叉验证：同一个问题发给多个模型，返回各自结果。
    用于易经知识验证、卦象计算校验等场景。
    """
    if not models:
        models = list(_registry.keys())

    results = {}
    for name in models:
        client = _registry.get(name)
        if not client:
            results[name] = {"error": f"Model {name} not available"}
            continue
        try:
            if client.provider == "gemini":
                # Gemini thinking模型短回复不稳定，用临时非thinking客户端
                lite = LLMClient(
                    name=f"{client.name}_validate",
                    provider="gemini",
                    api_key=client.api_key,
                    model="gemini-2.5-flash-lite",  # 非thinking，稳定
                )
                answer = lite.call("", [], prompt,
                                   max_tokens=max_tokens, temperature=temperature)
            else:
                answer = client.call(
                    "You are a precise knowledge validator. Answer concisely.",
                    [], prompt, max_tokens=max_tokens, temperature=temperature)
            results[name] = {"answer": answer, "model": client.model}
        except Exception as e:
            results[name] = {"error": str(e)}

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

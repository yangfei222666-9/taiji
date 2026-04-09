"""
aios/core/model_router.py - 智能模型路由

根据任务类型自动选择最合适的模型：
- 简单任务 → Ollama 本地模型（免费、快速）
- 复杂任务 → Claude API（效果好）
"""

import requests
from typing import Literal, Optional

# 任务复杂度分类
TASK_COMPLEXITY = {
    # 简单任务（可以用本地模型）
    "simple": [
        "greeting",  # 打招呼
        "translation",  # 简单翻译
        "summarize_short",  # 短文本摘要
        "classification",  # 文本分类
        "keyword_extraction",  # 关键词提取
        "simple_qa",  # 简单问答
    ],
    # 中等任务（优先本地，失败时用 Claude）
    "medium": [
        "code_completion",  # 代码补全
        "text_generation",  # 文本生成
        "data_analysis",  # 数据分析
        "summarize_long",  # 长文本摘要
    ],
    # 复杂任务（必须用 Claude）
    "complex": [
        "reasoning",  # 复杂推理
        "planning",  # 任务规划
        "code_review",  # 代码审查
        "creative_writing",  # 创意写作
        "decision_making",  # 决策支持
    ],
}


def is_ollama_available() -> bool:
    """检查 Ollama 是否可用"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def call_ollama(
    prompt: str, model: str = "qwen2.5:3b", timeout: int = 30
) -> Optional[str]:
    """
    调用 Ollama 本地模型

    Args:
        prompt: 提示词
        model: 模型名称
        timeout: 超时时间（秒）

    Returns:
        模型回复，失败返回 None
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("response", "")
        else:
            return None

    except Exception as e:
        print(f"Ollama 调用失败: {e}")
        return None


def route_model(
    task_type: str,
    prompt: str,
    force_model: Optional[Literal["ollama", "claude"]] = None,
) -> dict:
    """
    智能路由模型

    Args:
        task_type: 任务类型（见 TASK_COMPLEXITY）
        prompt: 提示词
        force_model: 强制使用指定模型

    Returns:
        {
            "model": "ollama" | "claude",
            "response": str,
            "success": bool,
            "fallback": bool,  # 是否使用了降级
            "cost": float      # 成本（美元）
        }
    """
    result = {
        "model": None,
        "response": None,
        "success": False,
        "fallback": False,
        "cost": 0.0,
    }

    # 强制使用指定模型
    if force_model == "ollama":
        response = call_ollama(prompt)
        if response:
            result["model"] = "ollama"
            result["response"] = response
            result["success"] = True
            result["cost"] = 0.0
        return result

    if force_model == "claude":
        # 这里应该调用 Claude API，暂时返回占位
        result["model"] = "claude"
        result["response"] = "[Claude API 调用]"
        result["success"] = True
        result["cost"] = 0.01  # 估算
        return result

    # 自动路由
    complexity = _get_task_complexity(task_type)

    if complexity == "simple":
        # 简单任务：优先本地
        if is_ollama_available():
            response = call_ollama(prompt)
            if response:
                result["model"] = "ollama"
                result["response"] = response
                result["success"] = True
                result["cost"] = 0.0
                return result

        # 本地失败，降级到 Claude
        result["model"] = "claude"
        result["response"] = "[Claude API 调用]"
        result["success"] = True
        result["fallback"] = True
        result["cost"] = 0.01
        return result

    elif complexity == "medium":
        # 中等任务：尝试本地，失败时用 Claude
        if is_ollama_available():
            response = call_ollama(prompt)
            if response and len(response) > 10:  # 简单质量检查
                result["model"] = "ollama"
                result["response"] = response
                result["success"] = True
                result["cost"] = 0.0
                return result

        # 降级到 Claude
        result["model"] = "claude"
        result["response"] = "[Claude API 调用]"
        result["success"] = True
        result["fallback"] = True
        result["cost"] = 0.01
        return result

    else:  # complex
        # 复杂任务：直接用 Claude
        result["model"] = "claude"
        result["response"] = "[Claude API 调用]"
        result["success"] = True
        result["cost"] = 0.01
        return result


def _get_task_complexity(task_type: str) -> str:
    """获取任务复杂度"""
    for complexity, tasks in TASK_COMPLEXITY.items():
        if task_type in tasks:
            return complexity
    return "complex"  # 默认复杂


def get_model_stats() -> dict:
    """获取模型使用统计"""
    # TODO: 从日志中统计
    return {"ollama_calls": 0, "claude_calls": 0, "total_cost": 0.0, "cost_saved": 0.0}


if __name__ == "__main__":
    # 测试
    print("测试 Ollama 可用性...")
    print(f"Ollama 可用: {is_ollama_available()}")

    print("\n测试简单任务...")
    result = route_model("greeting", "你好，介绍一下自己")
    print(f"使用模型: {result['model']}")
    print(f"回复: {result['response'][:100] if result['response'] else 'None'}")
    print(f"成本: ${result['cost']}")

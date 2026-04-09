"""
aios/core/llm_helper.py - LLM 辅助函数（带队列路由）

在 Pipeline 中需要 LLM 生成文本时使用。
所有调用通过 QueuedRouter 排队执行。
"""

from typing import Optional, Dict, Any
from core.queued_router import queued_route_model


def generate_summary(
    data: Dict[str, Any], task_type: str = "summarize_short", max_length: int = 200
) -> str:
    """
    生成数据摘要

    Args:
        data: 要总结的数据
        task_type: 任务类型
        max_length: 最大长度

    Returns:
        摘要文本
    """
    prompt = f"""请用一句话总结以下数据（不超过{max_length}字）：

{_format_data(data)}

要求：简洁、中文、一句话"""

    result = queued_route_model(
        task_type=task_type,
        prompt=prompt,
        context={"stage": "summary", "data_keys": list(data.keys())},
        priority="normal",
    )

    if result["success"]:
        return result["response"]
    else:
        return "[摘要生成失败]"


def generate_alert_summary(alerts: list) -> str:
    """
    生成告警摘要

    Args:
        alerts: 告警列表

    Returns:
        摘要文本
    """
    if not alerts:
        return "无告警"

    prompt = f"""请总结以下 {len(alerts)} 个告警的主要问题：

{_format_alerts(alerts)}

要求：一句话，突出重点"""

    result = queued_route_model(
        task_type="summarize_short",
        prompt=prompt,
        context={"stage": "alerts", "count": len(alerts)},
        priority="high",
    )

    if result["success"]:
        return result["response"]
    else:
        return f"{len(alerts)} 个告警待处理"


def generate_recommendation(
    context: Dict[str, Any], task_type: str = "reasoning"
) -> str:
    """
    生成建议

    Args:
        context: 上下文信息
        task_type: 任务类型（默认复杂推理）

    Returns:
        建议文本
    """
    prompt = f"""基于以下信息，给出一条简短建议：

{_format_data(context)}

要求：具体、可执行、一句话"""

    result = queued_route_model(
        task_type=task_type,
        prompt=prompt,
        context={"stage": "recommendation"},
        priority="normal",
    )

    if result["success"]:
        return result["response"]
    else:
        return "[建议生成失败]"


def _format_data(data: Dict[str, Any]) -> str:
    """格式化数据为文本"""
    lines = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            lines.append(f"- {key}: {len(value)} 项")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _format_alerts(alerts: list) -> str:
    """格式化告警列表"""
    lines = []
    for i, alert in enumerate(alerts[:5], 1):
        if isinstance(alert, dict):
            alert_id = alert.get("alert_id", "unknown")
            severity = alert.get("severity", "INFO")
            message = alert.get("message", "")[:50]
            lines.append(f"{i}. [{severity}] {alert_id}: {message}")
        else:
            lines.append(f"{i}. {str(alert)[:50]}")

    if len(alerts) > 5:
        lines.append(f"... 还有 {len(alerts) - 5} 个")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    test_data = {
        "evolution_score": 0.455,
        "grade": "healthy",
        "alerts_open": 1,
        "reactor_executed": 7,
    }

    print("测试生成摘要...")
    summary = generate_summary(test_data)
    print(f"摘要: {summary}")

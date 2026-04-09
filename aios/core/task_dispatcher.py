"""
Smart Task Dispatcher - 智能任务分发
根据任务复杂度自动选择执行方式：
- 简单任务：当前 sonnet 会话直接执行
- 复杂任务：spawn opus 子 agent 执行
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aios.core.model_router import route_model, explain_choice


def should_delegate(message: str, context: dict = None) -> tuple[bool, str]:
    """
    判断是否应该委托给子 agent

    Returns:
        (should_delegate, reason)
    """
    tier = route_model(message, context)

    if tier == "opus":
        reason = explain_choice(message, tier)
        return True, f"复杂任务，建议委托给 opus 子 agent: {reason}"
    else:
        return False, "简单任务，当前会话可处理"


def format_spawn_command(task: str, model: str = "claude-opus-4-6") -> str:
    """
    生成 sessions_spawn 命令的参数
    """
    return f"""
sessions_spawn(
    task="{task}",
    model="{model}",
    cleanup="keep",
    label="complex-task"
)
"""


# 使用示例
if __name__ == "__main__":
    test_tasks = [
        "列出所有 Python 文件",
        "重构 AIOS 的事件系统，优化性能并添加批处理支持",
        "检查 Git 状态",
        "创建一个完整的 Web 爬虫项目，支持并发、断点续传和反爬虫",
    ]

    print("Smart Task Dispatcher 测试:\n")
    for task in test_tasks:
        should_del, reason = should_delegate(task)
        print(f"任务: {task}")
        print(f"决策: {'🚀 委托子 agent' if should_del else '✅ 当前会话处理'}")
        print(f"原因: {reason}\n")

        if should_del:
            print(format_spawn_command(task))
            print()

"""
AIOS Auto Intelligence - 全自动智能化入口

整合意图识别、任务规划、参数推断，实现全自动任务执行。

使用示例：
    from aios.core.auto_intelligence import process_user_request
    
    result = process_user_request("优化系统性能")
    if result.auto_execute:
        # 自动执行
        execute_plan(result.plan)
    else:
        # 需要确认
        confirm_and_execute(result.plan)
"""
import sys
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

# Add core to path
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from intent_recognizer import recognize_intent, Intent
from task_planner import plan_task, TaskPlan


@dataclass
class ProcessResult:
    """处理结果"""
    intent: Intent
    plan: TaskPlan
    auto_execute: bool
    reason: str  # 自动执行或需要确认的原因


class AutoIntelligence:
    """全自动智能化处理器"""
    
    def process(self, user_input: str) -> ProcessResult:
        """
        处理用户请求
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            ProcessResult 对象
        """
        # 1. 意图识别
        intent = recognize_intent(user_input)
        
        # 2. 任务规划
        intent_dict = {
            "action": intent.action,
            "target": intent.target,
            "risk": intent.risk,
            "auto_execute": intent.auto_execute,
            "params": intent.params,
        }
        plan = plan_task(user_input, intent_dict)
        
        # 3. 决定是否自动执行
        auto_execute, reason = self._decide_auto_execute(intent, plan)
        
        return ProcessResult(
            intent=intent,
            plan=plan,
            auto_execute=auto_execute,
            reason=reason,
        )
    
    def _decide_auto_execute(self, intent: Intent, plan: TaskPlan) -> tuple[bool, str]:
        """决定是否自动执行"""
        # 高风险任务永远需要确认
        if intent.risk == "high":
            return False, f"高风险操作（{intent.action} {intent.target}），需要确认"
        
        # 低置信度需要确认
        if intent.confidence < 0.3:
            return False, f"意图识别置信度较低（{intent.confidence:.2f}），需要确认"
        
        # 复杂任务（>3个子任务）需要确认
        if len(plan.subtasks) > 3 and intent.risk == "medium":
            return False, f"复杂任务（{len(plan.subtasks)}个步骤），需要确认"
        
        # 预计耗时过长（>5分钟）需要确认
        if plan.total_estimated_duration > 300 and intent.risk == "medium":
            return False, f"耗时较长（预计{plan.total_estimated_duration}秒），需要确认"
        
        # 其他情况自动执行
        return True, f"低风险操作（{intent.risk}），自动执行"


# 全局实例
_auto_intelligence = AutoIntelligence()


def process_user_request(user_input: str) -> ProcessResult:
    """便捷函数：处理用户请求"""
    return _auto_intelligence.process(user_input)


def format_result(result: ProcessResult) -> str:
    """格式化输出结果"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"用户输入: {result.plan.original_task}")
    lines.append("")
    
    # 意图识别
    lines.append("🧠 意图识别:")
    lines.append(f"   动作: {result.intent.action}")
    lines.append(f"   目标: {result.intent.target}")
    lines.append(f"   风险: {result.intent.risk}")
    lines.append(f"   置信度: {result.intent.confidence:.2f}")
    if result.intent.params:
        lines.append(f"   参数: {result.intent.params}")
    lines.append("")
    
    # 任务规划
    lines.append("📋 任务规划:")
    lines.append(f"   类型: {result.plan.task_type.value}")
    lines.append(f"   预计耗时: {result.plan.total_estimated_duration}秒")
    lines.append(f"   子任务数: {len(result.plan.subtasks)}")
    lines.append("")
    
    # 执行决策
    if result.auto_execute:
        lines.append("✅ 自动执行")
    else:
        lines.append("❌ 需要确认")
    lines.append(f"   原因: {result.reason}")
    lines.append("")
    
    # 子任务详情
    if len(result.plan.subtasks) > 1:
        lines.append("📝 执行步骤:")
        for i, st in enumerate(result.plan.subtasks, 1):
            deps = f" (依赖: {', '.join(st.depends_on)})" if st.depends_on else ""
            lines.append(f"   {i}. {st.description} [{st.agent_type}] {st.estimated_duration}s{deps}")
    
    lines.append("=" * 60)
    return "\n".join(lines)


# 测试代码
if __name__ == "__main__":
    test_cases = [
        "查看 Agent 执行情况",
        "优化系统性能",
        "删除所有失败的任务",
        "分析最近 24 小时的任务执行情况",
        "执行待处理的任务",
    ]
    
    print("Auto Intelligence Test\n")
    
    for user_input in test_cases:
        result = process_user_request(user_input)
        print(format_result(result))
        print()

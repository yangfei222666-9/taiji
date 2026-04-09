"""
AIOS Planning Modes - 规划模式选择

支持两种规划模式：
1. Plan-and-Execute（先计划后执行）- 高效，适合明确任务
2. ReAct（边想边做）- 灵活，适合探索性任务

Author: 小九 + 珊瑚海
Date: 2026-02-26
"""

from typing import List, Dict, Any
from enum import Enum


class PlanningMode(Enum):
    """规划模式"""
    PLAN_AND_EXECUTE = "plan-and-execute"  # 先计划后执行
    REACT = "react"                        # 边想边做
    AUTO = "auto"                          # 自动选择


class PlanningModeSelector:
    """规划模式选择器"""
    
    # 探索性任务关键词
    EXPLORATORY_KEYWORDS = [
        "搜索", "查找", "探索", "调研", "分析",
        "对比", "评估", "研究", "发现"
    ]
    
    # 明确任务关键词
    DEFINITE_KEYWORDS = [
        "实现", "开发", "编写", "创建", "生成",
        "修复", "优化", "测试", "部署"
    ]
    
    @classmethod
    def select_mode(cls, task: str) -> PlanningMode:
        """自动选择规划模式"""
        # 1. 检查是否是探索性任务
        if cls._is_exploratory(task):
            return PlanningMode.REACT
        
        # 2. 检查是否是明确任务
        if cls._is_definite(task):
            return PlanningMode.PLAN_AND_EXECUTE
        
        # 3. 默认使用 Plan-and-Execute（更高效）
        return PlanningMode.PLAN_AND_EXECUTE
    
    @classmethod
    def _is_exploratory(cls, task: str) -> bool:
        """判断是否是探索性任务"""
        return any(kw in task for kw in cls.EXPLORATORY_KEYWORDS)
    
    @classmethod
    def _is_definite(cls, task: str) -> bool:
        """判断是否是明确任务"""
        return any(kw in task for kw in cls.DEFINITE_KEYWORDS)
    
    @classmethod
    def get_mode_description(cls, mode: PlanningMode) -> Dict[str, Any]:
        """获取模式描述"""
        descriptions = {
            PlanningMode.PLAN_AND_EXECUTE: {
                "name": "Plan-and-Execute（先计划后执行）",
                "pros": ["高效：只需调用一次LLM规划", "可并行执行多个任务"],
                "cons": ["不灵活：难以根据中间结果调整"],
                "适用场景": "流程明确的任务（步骤固定）"
            },
            PlanningMode.REACT: {
                "name": "ReAct（边想边做）",
                "pros": ["灵活：可以根据中间结果调整计划", "适合探索性任务"],
                "cons": ["Token消耗大：每一步都要调用LLM"],
                "适用场景": "探索性任务（不知道中间会遇到什么）"
            },
            PlanningMode.AUTO: {
                "name": "Auto（自动选择）",
                "pros": ["智能选择最优模式"],
                "cons": ["可能选择不准确"],
                "适用场景": "不确定任务类型时"
            }
        }
        return descriptions.get(mode, {})


# 使用示例
if __name__ == "__main__":
    # 测试任务
    tasks = [
        "搜索2024年AI Agent市场报告",  # 探索性 → ReAct
        "实现 Memory 模块",            # 明确 → Plan-and-Execute
        "对比 AIOS 和标准 Agent",      # 探索性 → ReAct
        "修复 Scheduler 的 bug",       # 明确 → Plan-and-Execute
    ]
    
    for task in tasks:
        mode = PlanningModeSelector.select_mode(task)
        desc = PlanningModeSelector.get_mode_description(mode)
        
        print(f"\n任务: {task}")
        print(f"推荐模式: {desc['name']}")
        print(f"原因: {desc['适用场景']}")
        print(f"优势: {', '.join(desc['pros'])}")

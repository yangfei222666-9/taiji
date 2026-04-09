"""
AIOS Task Planner - 任务自动拆解与编排

将复杂任务自动拆解为子任务，分配给合适的 Agent，编排执行顺序。

示例：
输入："优化系统性能"
输出：
  1. 分析系统瓶颈（Monitor Agent）
  2. 生成优化方案（Analyst Agent）
  3. 执行优化（Coder Agent）
  4. 验证效果（Monitor Agent）
"""
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    SIMPLE = "simple"  # 简单任务，单个 Agent 可完成
    SEQUENTIAL = "sequential"  # 顺序任务，多个步骤依次执行
    PARALLEL = "parallel"  # 并行任务，多个步骤同时执行
    CONDITIONAL = "conditional"  # 条件任务，根据结果决定下一步


@dataclass
class SubTask:
    """子任务"""
    id: str
    description: str
    agent_type: str  # monitor/analyst/coder
    priority: str  # high/normal/low
    depends_on: List[str]  # 依赖的子任务 ID
    params: Dict
    estimated_duration: int  # 预计耗时（秒）


@dataclass
class TaskPlan:
    """任务计划"""
    task_id: str
    original_task: str
    task_type: TaskType
    subtasks: List[SubTask]
    total_estimated_duration: int
    can_auto_execute: bool


class TaskPlanner:
    """任务规划器"""
    
    # 任务模板库（扩展版）
    TASK_TEMPLATES = {
        # 系统优化类
        "优化系统": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "分析系统瓶颈", "agent": "monitor", "duration": 30},
                {"desc": "生成优化方案", "agent": "analysis", "duration": 60},
                {"desc": "执行优化", "agent": "code", "duration": 120},
                {"desc": "验证效果", "agent": "monitor", "duration": 30},
            ]
        },
        
        # 分析类
        "分析问题": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "收集数据", "agent": "monitor", "duration": 20},
                {"desc": "分析数据", "agent": "analysis", "duration": 40},
                {"desc": "生成报告", "agent": "analysis", "duration": 30},
            ]
        },
        
        # 查询类
        "查看状态": {
            "type": TaskType.SIMPLE,
            "steps": [
                {"desc": "查询状态", "agent": "monitor", "duration": 10},
            ]
        },
        
        # 执行类
        "执行任务": {
            "type": TaskType.SIMPLE,
            "steps": [
                {"desc": "执行任务", "agent": "code", "duration": 60},
            ]
        },
        
        # 代码重构类
        "重构代码": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "分析代码结构", "agent": "analysis", "duration": 40},
                {"desc": "生成重构方案", "agent": "analysis", "duration": 60},
                {"desc": "执行重构", "agent": "refactor", "duration": 180},
                {"desc": "运行测试", "agent": "test", "duration": 60},
            ]
        },
        
        # 故障排查类
        "排查故障": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "收集错误日志", "agent": "monitor", "duration": 20},
                {"desc": "分析错误原因", "agent": "analysis", "duration": 60},
                {"desc": "生成修复方案", "agent": "analysis", "duration": 40},
                {"desc": "应用修复", "agent": "code", "duration": 90},
                {"desc": "验证修复", "agent": "test", "duration": 30},
            ]
        },
        
        # 性能测试类
        "性能测试": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "设计测试场景", "agent": "analysis", "duration": 30},
                {"desc": "执行性能测试", "agent": "test", "duration": 120},
                {"desc": "分析测试结果", "agent": "analysis", "duration": 40},
                {"desc": "生成优化建议", "agent": "analysis", "duration": 30},
            ]
        },
        
        # 部署类
        "部署应用": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "运行测试", "agent": "test", "duration": 60},
                {"desc": "构建应用", "agent": "deploy", "duration": 90},
                {"desc": "部署到生产", "agent": "deploy", "duration": 120},
                {"desc": "验证部署", "agent": "monitor", "duration": 30},
            ]
        },
        
        # 研究类
        "技术调研": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "搜索相关资料", "agent": "research", "duration": 60},
                {"desc": "分析技术方案", "agent": "analysis", "duration": 90},
                {"desc": "生成调研报告", "agent": "analysis", "duration": 60},
            ]
        },
        
        # 清理类
        "清理系统": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "扫描临时文件", "agent": "monitor", "duration": 20},
                {"desc": "分析可清理项", "agent": "analysis", "duration": 30},
                {"desc": "执行清理", "agent": "code", "duration": 60},
                {"desc": "验证清理结果", "agent": "monitor", "duration": 20},
            ]
        },
        
        # 备份类
        "备份数据": {
            "type": TaskType.SEQUENTIAL,
            "steps": [
                {"desc": "检查备份空间", "agent": "monitor", "duration": 10},
                {"desc": "执行数据备份", "agent": "code", "duration": 180},
                {"desc": "验证备份完整性", "agent": "test", "duration": 60},
            ]
        },
    }
    
    def plan(self, task_description: str, intent: Optional[Dict] = None) -> TaskPlan:
        """
        规划任务执行计划
        
        Args:
            task_description: 任务描述
            intent: 意图识别结果（可选）
            
        Returns:
            TaskPlan 对象
        """
        # 1. 匹配任务模板
        template = self._match_template(task_description)
        
        # 2. 生成子任务
        subtasks = self._generate_subtasks(template, task_description, intent)
        
        # 3. 计算总耗时
        total_duration = sum(st.estimated_duration for st in subtasks)
        
        # 4. 决定是否可自动执行
        can_auto = self._can_auto_execute(template, intent)
        
        return TaskPlan(
            task_id=f"task-{int(time.time() * 1000)}",
            original_task=task_description,
            task_type=template["type"],
            subtasks=subtasks,
            total_estimated_duration=total_duration,
            can_auto_execute=can_auto,
        )
    
    def _match_template(self, task_description: str) -> Dict:
        """匹配任务模板（增强版）"""
        task_lower = task_description.lower()
        
        # 优先级匹配（从具体到一般）
        
        # 1. 代码重构
        if any(kw in task_lower for kw in ["重构", "refactor", "重写", "改写"]):
            return self.TASK_TEMPLATES["重构代码"]
        
        # 2. 故障排查
        if any(kw in task_lower for kw in ["排查", "故障", "错误", "bug", "修复", "debug"]):
            return self.TASK_TEMPLATES["排查故障"]
        
        # 3. 性能测试
        if any(kw in task_lower for kw in ["性能测试", "压力测试", "负载测试", "benchmark"]):
            return self.TASK_TEMPLATES["性能测试"]
        
        # 4. 部署
        if any(kw in task_lower for kw in ["部署", "deploy", "发布", "上线"]):
            return self.TASK_TEMPLATES["部署应用"]
        
        # 5. 技术调研
        if any(kw in task_lower for kw in ["调研", "研究", "搜索", "查找", "github"]):
            return self.TASK_TEMPLATES["技术调研"]
        
        # 6. 清理
        if any(kw in task_lower for kw in ["清理", "清除", "删除临时", "垃圾"]):
            return self.TASK_TEMPLATES["清理系统"]
        
        # 7. 备份
        if any(kw in task_lower for kw in ["备份", "backup", "归档"]):
            return self.TASK_TEMPLATES["备份数据"]
        
        # 8. 系统优化
        if any(kw in task_lower for kw in ["优化", "提升", "改进", "加速"]):
            return self.TASK_TEMPLATES["优化系统"]
        
        # 9. 分析
        if any(kw in task_lower for kw in ["分析", "统计", "报告", "总结"]):
            return self.TASK_TEMPLATES["分析问题"]
        
        # 10. 查看
        if any(kw in task_lower for kw in ["查看", "检查", "状态", "列出", "显示"]):
            return self.TASK_TEMPLATES["查看状态"]
        
        # 11. 执行
        if any(kw in task_lower for kw in ["执行", "运行", "启动", "开始"]):
            return self.TASK_TEMPLATES["执行任务"]
        
        # 默认为简单任务
        return self.TASK_TEMPLATES["执行任务"]
    
    def _generate_subtasks(
        self, 
        template: Dict, 
        task_description: str,
        intent: Optional[Dict]
    ) -> List[SubTask]:
        """生成子任务列表"""
        subtasks = []
        
        for i, step in enumerate(template["steps"]):
            # 构建依赖关系
            depends_on = []
            if i > 0:
                depends_on.append(f"subtask-{i-1}")
            
            # 合并参数
            params = {}
            if intent and "params" in intent:
                params.update(intent["params"])
            
            subtask = SubTask(
                id=f"subtask-{i}",
                description=step["desc"],
                agent_type=step["agent"],
                priority="normal",
                depends_on=depends_on,
                params=params,
                estimated_duration=step["duration"],
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _can_auto_execute(self, template: Dict, intent: Optional[Dict]) -> bool:
        """判断是否可以自动执行"""
        # 简单任务可以自动执行
        if template["type"] == TaskType.SIMPLE:
            return True
        
        # 如果意图识别结果允许自动执行
        if intent and intent.get("auto_execute"):
            return True
        
        # 默认需要确认
        return False


# 全局实例
_planner = TaskPlanner()


def plan_task(task_description: str, intent: Optional[Dict] = None) -> TaskPlan:
    """便捷函数：规划任务"""
    return _planner.plan(task_description, intent)


# 测试代码
if __name__ == "__main__":
    import time
    from intent_recognizer import recognize_intent
    
    test_cases = [
        "优化系统性能",
        "分析最近 24 小时的任务执行情况",
        "查看 Agent 状态",
        "执行待处理的任务",
    ]
    
    print("Task Planning Test\n" + "=" * 60)
    
    for task_desc in test_cases:
        # 先识别意图
        intent = recognize_intent(task_desc)
        intent_dict = {
            "action": intent.action,
            "target": intent.target,
            "risk": intent.risk,
            "auto_execute": intent.auto_execute,
            "params": intent.params,
        }
        
        # 再规划任务
        plan = plan_task(task_desc, intent_dict)
        
        print(f"\n任务: {task_desc}")
        print(f"  类型: {plan.task_type.value}")
        print(f"  预计耗时: {plan.total_estimated_duration}秒")
        print(f"  自动执行: {'✅ 是' if plan.can_auto_execute else '❌ 否'}")
        print(f"  子任务:")
        for st in plan.subtasks:
            deps = f" (依赖: {', '.join(st.depends_on)})" if st.depends_on else ""
            print(f"    {st.id}: {st.description} [{st.agent_type}] {st.estimated_duration}s{deps}")

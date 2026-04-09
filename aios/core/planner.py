"""
AIOS Planning Module - 任务规划与拆解

实现标准 Agent 的 Planning 能力：
1. Chain of Thought (CoT) - 逐步思考
2. Task Decomposition - 任务拆解
3. Memory 集成 - 检索相关记忆

Author: 小九 + 珊瑚海
Date: 2026-02-26
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Memory 集成
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from memory import MemoryManager
except ImportError:
    MemoryManager = None


@dataclass
class SubTask:
    """子任务"""
    id: str
    description: str
    type: str  # code/analysis/monitor/research/design
    priority: str  # high/normal/low
    dependencies: List[str]  # 依赖的子任务 ID
    estimated_time: int  # 预估耗时（秒）
    status: str = "pending"  # pending/running/completed/failed
    result: Optional[str] = None
    created_at: float = 0.0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class Plan:
    """执行计划"""
    task_id: str
    original_task: str
    subtasks: List[SubTask]
    strategy: str  # sequential/parallel/dag
    created_at: float = 0.0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class Planner:
    """任务规划器"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.plans_dir = workspace / "aios" / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        
        # Memory 集成
        self.memory = MemoryManager(workspace) if MemoryManager else None
        
        # 任务类型关键词
        self.type_keywords = {
            "code": ["写代码", "实现", "开发", "编程", "修复", "重构", "优化代码"],
            "analysis": ["分析", "调研", "研究", "对比", "评估", "总结"],
            "monitor": ["监控", "检查", "观察", "追踪", "报告"],
            "research": ["搜索", "查找", "学习", "了解", "探索"],
            "design": ["设计", "架构", "规划", "方案", "蓝图"]
        }
    
    def plan(self, task: str, strategy: str = "auto", 
             use_memory: bool = True) -> Plan:
        """
        规划任务
        
        Args:
            task: 任务描述
            strategy: 执行策略（auto/sequential/parallel/dag）
            use_memory: 是否使用记忆检索
        
        Returns:
            Plan: 执行计划
        """
        # 0. 检索相关记忆（如果启用）
        related_memories = []
        if use_memory and self.memory:
            related_memories = self.memory.retrieve(task, k=3)
            if related_memories:
                # 记录检索到的记忆（用于后续参考）
                print(f"[Planner] 检索到 {len(related_memories)} 条相关记忆")
        
        # 1. 判断是否需要拆解
        if self._is_simple_task(task):
            # 简单任务，不拆解
            return self._create_simple_plan(task)
        
        # 2. 使用 Chain of Thought 拆解任务
        subtasks = self._decompose_with_cot(task)
        
        # 3. 分析依赖关系
        subtasks = self._analyze_dependencies(subtasks)
        
        # 4. 确定执行策略
        if strategy == "auto":
            strategy = self._determine_strategy(subtasks)
        
        # 5. 创建计划
        task_id = f"plan_{int(time.time() * 1000)}"
        plan = Plan(
            task_id=task_id,
            original_task=task,
            subtasks=subtasks,
            strategy=strategy
        )
        
        # 6. 保存计划
        self._save_plan(plan)
        
        # 7. 存储到记忆（如果启用）
        if self.memory:
            self.memory.store(
                f"规划任务: {task} (拆解为 {len(subtasks)} 个子任务)",
                source="planner",
                importance=0.7,
                metadata={"plan_id": task_id, "subtask_count": len(subtasks)}
            )
        
        return plan
    
    def _is_simple_task(self, task: str) -> bool:
        """判断是否为简单任务（不需要拆解）"""
        # 简单规则：少于 20 个字，且只包含一个动词
        if len(task) < 20:
            action_words = ["打开", "关闭", "查看", "读取", "写入", "删除", "创建"]
            return any(word in task for word in action_words)
        return False
    
    def _create_simple_plan(self, task: str) -> Plan:
        """创建简单任务计划（不拆解）"""
        task_id = f"plan_{int(time.time() * 1000)}"
        task_type = self._infer_task_type(task)
        
        subtask = SubTask(
            id=f"{task_id}_1",
            description=task,
            type=task_type,
            priority="normal",
            dependencies=[],
            estimated_time=60
        )
        
        return Plan(
            task_id=task_id,
            original_task=task,
            subtasks=[subtask],
            strategy="sequential"
        )
    
    def _decompose_with_cot(self, task: str) -> List[SubTask]:
        """
        使用 Chain of Thought 拆解任务
        
        CoT 思路：
        1. 理解任务目标
        2. 识别关键步骤
        3. 拆解为子任务
        4. 估算每个子任务的耗时
        """
        subtasks = []
        
        # 规则1：如果任务包含"并且"/"然后"/"接着"，按连接词拆分
        if any(word in task for word in ["并且", "然后", "接着", "再", "最后"]):
            parts = self._split_by_connectors(task)
            for i, part in enumerate(parts):
                task_type = self._infer_task_type(part)
                subtask = SubTask(
                    id=f"subtask_{i+1}",
                    description=part.strip(),
                    type=task_type,
                    priority=self._infer_priority(part),
                    dependencies=[f"subtask_{i}"] if i > 0 else [],
                    estimated_time=self._estimate_time(part)
                )
                subtasks.append(subtask)
            return subtasks
        
        # 规则2：如果任务包含"对比"/"比较"，拆分为：收集A → 收集B → 对比
        if any(word in task for word in ["对比", "比较", "vs"]):
            entities = self._extract_entities(task)
            if len(entities) >= 2:
                # 收集第一个实体
                subtasks.append(SubTask(
                    id="subtask_1",
                    description=f"收集 {entities[0]} 的信息",
                    type="research",
                    priority="normal",
                    dependencies=[],
                    estimated_time=120
                ))
                # 收集第二个实体
                subtasks.append(SubTask(
                    id="subtask_2",
                    description=f"收集 {entities[1]} 的信息",
                    type="research",
                    priority="normal",
                    dependencies=[],
                    estimated_time=120
                ))
                # 对比
                subtasks.append(SubTask(
                    id="subtask_3",
                    description=f"对比 {entities[0]} 和 {entities[1]}",
                    type="analysis",
                    priority="high",
                    dependencies=["subtask_1", "subtask_2"],
                    estimated_time=180
                ))
                return subtasks
        
        # 规则3：如果任务包含"实现"/"开发"，拆分为：设计 → 实现 → 测试
        if any(word in task for word in ["实现", "开发", "写代码", "编程"]):
            feature = task.replace("实现", "").replace("开发", "").strip()
            subtasks = [
                SubTask(
                    id="subtask_1",
                    description=f"设计 {feature} 的架构",
                    type="design",
                    priority="high",
                    dependencies=[],
                    estimated_time=300
                ),
                SubTask(
                    id="subtask_2",
                    description=f"实现 {feature} 的核心功能",
                    type="code",
                    priority="high",
                    dependencies=["subtask_1"],
                    estimated_time=600
                ),
                SubTask(
                    id="subtask_3",
                    description=f"测试 {feature}",
                    type="code",
                    priority="normal",
                    dependencies=["subtask_2"],
                    estimated_time=180
                )
            ]
            return subtasks
        
        # 规则4：默认不拆解（作为单个子任务）
        task_type = self._infer_task_type(task)
        subtask = SubTask(
            id="subtask_1",
            description=task,
            type=task_type,
            priority=self._infer_priority(task),
            dependencies=[],
            estimated_time=self._estimate_time(task)
        )
        return [subtask]
    
    def _split_by_connectors(self, task: str) -> List[str]:
        """按连接词拆分任务"""
        connectors = ["并且", "然后", "接着", "再", "最后"]
        parts = [task]
        for conn in connectors:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(conn))
            parts = new_parts
        return [p.strip() for p in parts if p.strip()]
    
    def _extract_entities(self, task: str) -> List[str]:
        """提取任务中的实体（简单规则）"""
        # 简单规则：提取引号内的内容或"和"连接的词
        entities = []
        
        # 提取引号内容
        import re
        quoted = re.findall(r'["""](.*?)["""]', task)
        entities.extend(quoted)
        
        # 提取"和"连接的词
        if "和" in task:
            parts = task.split("和")
            for part in parts:
                words = part.strip().split()
                if words:
                    entities.append(words[-1])
        
        return entities[:2]  # 最多返回2个
    
    def _infer_task_type(self, task: str) -> str:
        """推断任务类型"""
        for task_type, keywords in self.type_keywords.items():
            if any(kw in task for kw in keywords):
                return task_type
        return "analysis"  # 默认
    
    def _infer_priority(self, task: str) -> str:
        """推断任务优先级"""
        high_keywords = ["紧急", "立即", "马上", "重要", "关键"]
        low_keywords = ["可选", "有空", "不急", "以后"]
        
        if any(kw in task for kw in high_keywords):
            return "high"
        elif any(kw in task for kw in low_keywords):
            return "low"
        return "normal"
    
    def _estimate_time(self, task: str) -> int:
        """估算任务耗时（秒）"""
        # 简单规则：根据任务类型和长度估算
        base_time = 60  # 基础 1 分钟
        
        # 根据任务类型调整
        if "实现" in task or "开发" in task:
            base_time = 600  # 10 分钟
        elif "分析" in task or "对比" in task:
            base_time = 180  # 3 分钟
        elif "搜索" in task or "查找" in task:
            base_time = 120  # 2 分钟
        
        # 根据任务长度调整
        if len(task) > 50:
            base_time *= 2
        
        return base_time
    
    def _analyze_dependencies(self, subtasks: List[SubTask]) -> List[SubTask]:
        """分析子任务之间的依赖关系"""
        # 简单规则：如果子任务 B 的描述中提到子任务 A 的关键词，则 B 依赖 A
        for i, task_b in enumerate(subtasks):
            for j, task_a in enumerate(subtasks):
                if i <= j:
                    continue
                # 检查 B 是否依赖 A
                if self._has_dependency(task_b.description, task_a.description):
                    if task_a.id not in task_b.dependencies:
                        task_b.dependencies.append(task_a.id)
        
        return subtasks
    
    def _has_dependency(self, task_b: str, task_a: str) -> bool:
        """判断 task_b 是否依赖 task_a"""
        # 简单规则：如果 task_a 的关键词出现在 task_b 中
        keywords_a = set(task_a.split())
        keywords_b = set(task_b.split())
        return len(keywords_a & keywords_b) >= 2
    
    def _determine_strategy(self, subtasks: List[SubTask]) -> str:
        """确定执行策略"""
        # 如果所有子任务都没有依赖，可以并行
        if all(not task.dependencies for task in subtasks):
            return "parallel"
        
        # 如果有复杂依赖关系，用 DAG
        if any(len(task.dependencies) > 1 for task in subtasks):
            return "dag"
        
        # 默认顺序执行
        return "sequential"
    
    def _save_plan(self, plan: Plan):
        """保存计划到文件"""
        plan_file = self.plans_dir / f"{plan.task_id}.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": plan.task_id,
                "original_task": plan.original_task,
                "subtasks": [asdict(st) for st in plan.subtasks],
                "strategy": plan.strategy,
                "created_at": plan.created_at
            }, f, ensure_ascii=False, indent=2)
    
    def load_plan(self, task_id: str) -> Optional[Plan]:
        """加载计划"""
        plan_file = self.plans_dir / f"{task_id}.json"
        if not plan_file.exists():
            return None
        
        with open(plan_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        subtasks = [SubTask(**st) for st in data["subtasks"]]
        return Plan(
            task_id=data["task_id"],
            original_task=data["original_task"],
            subtasks=subtasks,
            strategy=data["strategy"],
            created_at=data["created_at"]
        )
    
    def update_subtask_status(self, task_id: str, subtask_id: str, 
                             status: str, result: Optional[str] = None):
        """更新子任务状态"""
        plan = self.load_plan(task_id)
        if not plan:
            return
        
        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                if result:
                    subtask.result = result
                break
        
        self._save_plan(plan)
    
    def get_next_subtasks(self, task_id: str) -> List[SubTask]:
        """获取下一批可执行的子任务"""
        plan = self.load_plan(task_id)
        if not plan:
            return []
        
        # 找出所有依赖已完成的待执行子任务
        completed_ids = {st.id for st in plan.subtasks if st.status == "completed"}
        next_tasks = []
        
        for subtask in plan.subtasks:
            if subtask.status != "pending":
                continue
            # 检查依赖是否都完成
            if all(dep in completed_ids for dep in subtask.dependencies):
                next_tasks.append(subtask)
        
        return next_tasks


def demo():
    """演示 Planner 功能"""
    workspace = Path(__file__).parent.parent.parent
    planner = Planner(workspace)
    
    print("=== AIOS Planner Demo ===\n")
    
    # 测试1：简单任务（不拆解）
    print("测试1：简单任务")
    task1 = "打开 QQ 音乐"
    plan1 = planner.plan(task1)
    print(f"任务: {task1}")
    print(f"策略: {plan1.strategy}")
    print(f"子任务数: {len(plan1.subtasks)}")
    for st in plan1.subtasks:
        print(f"  - {st.description} ({st.type}, {st.estimated_time}s)")
    print()
    
    # 测试2：对比任务（拆解为3步）
    print("测试2：对比任务")
    task2 = "对比 AIOS 和标准 Agent 架构"
    plan2 = planner.plan(task2)
    print(f"任务: {task2}")
    print(f"策略: {plan2.strategy}")
    print(f"子任务数: {len(plan2.subtasks)}")
    for st in plan2.subtasks:
        deps = f" (依赖: {', '.join(st.dependencies)})" if st.dependencies else ""
        print(f"  - {st.description} ({st.type}, {st.estimated_time}s){deps}")
    print()
    
    # 测试3：开发任务（拆解为设计→实现→测试）
    print("测试3：开发任务")
    task3 = "实现 Planning 模块"
    plan3 = planner.plan(task3)
    print(f"任务: {task3}")
    print(f"策略: {plan3.strategy}")
    print(f"子任务数: {len(plan3.subtasks)}")
    for st in plan3.subtasks:
        deps = f" (依赖: {', '.join(st.dependencies)})" if st.dependencies else ""
        print(f"  - {st.description} ({st.type}, {st.estimated_time}s){deps}")
    print()
    
    # 测试4：复杂任务（多步骤）
    print("测试4：复杂任务")
    task4 = "搜索 GitHub 上的 AIOS 项目，然后分析架构，最后写一份对比报告"
    plan4 = planner.plan(task4)
    print(f"任务: {task4}")
    print(f"策略: {plan4.strategy}")
    print(f"子任务数: {len(plan4.subtasks)}")
    for st in plan4.subtasks:
        deps = f" (依赖: {', '.join(st.dependencies)})" if st.dependencies else ""
        print(f"  - {st.description} ({st.type}, {st.estimated_time}s){deps}")
    print()
    
    print("[OK] Demo 完成！")


if __name__ == "__main__":
    demo()

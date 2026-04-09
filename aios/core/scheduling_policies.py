"""
AIOS Scheduling Policies - 调度算法实现

支持的调度算法：
1. FIFO - 先进先出（First In First Out）
2. SJF - 最短作业优先（Shortest Job First）
3. RR - 轮转调度（Round Robin）
4. EDF - 最早截止时间优先（Earliest Deadline First）
5. Priority - 优先级调度（默认）
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import time
from dataclasses import dataclass


@dataclass
class Task:
    """任务数据类（用于调度算法）"""
    id: str
    priority: int = 3  # 0-3，0最高
    estimated_duration: float = 0  # 预估执行时间（秒）
    deadline: Optional[float] = None  # 截止时间（Unix timestamp）
    created_at: float = 0  # 创建时间
    
    @classmethod
    def from_dict(cls, task_dict: Dict[str, Any]) -> 'Task':
        """从字典创建 Task"""
        return cls(
            id=task_dict.get("id", ""),
            priority=task_dict.get("priority", 3),
            estimated_duration=task_dict.get("estimated_duration", 0),
            deadline=task_dict.get("deadline"),
            created_at=task_dict.get("created_at", time.time()),
        )


class SchedulingPolicy(ABC):
    """调度策略接口"""
    
    @abstractmethod
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """从任务列表中选择下一个要执行的任务。
        
        Args:
            tasks: 就绪任务列表（字典格式）
        
        Returns:
            选中的任务，如果没有返回 None
        """
        pass
    
    @abstractmethod
    def name(self) -> str:
        """返回策略名称"""
        pass


class FIFOPolicy(SchedulingPolicy):
    """先进先出（First In First Out）
    
    最简单的调度算法，按照任务到达顺序执行。
    适用场景：公平性要求高，任务执行时间相近。
    """
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 按创建时间排序，选择最早的
        return min(tasks, key=lambda t: t.get("created_at", 0))
    
    def name(self) -> str:
        return "FIFO"


class SJFPolicy(SchedulingPolicy):
    """最短作业优先（Shortest Job First）
    
    优先执行预估时间最短的任务。
    适用场景：最小化平均等待时间，任务时间差异大。
    
    注意：需要任务提供 estimated_duration 字段。
    """
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 按预估时间排序，选择最短的
        # 如果没有 estimated_duration，默认为无穷大（最后执行）
        return min(tasks, key=lambda t: t.get("estimated_duration", float('inf')))
    
    def name(self) -> str:
        return "SJF"


class RoundRobinPolicy(SchedulingPolicy):
    """轮转调度（Round Robin）
    
    每个任务轮流执行一个时间片。
    适用场景：交互式系统，需要快速响应。
    
    注意：当前实现是简化版，每次选择下一个任务（不支持时间片抢占）。
    """
    
    def __init__(self, time_slice: int = 1):
        """初始化轮转调度。
        
        Args:
            time_slice: 时间片大小（秒），当前未使用（简化实现）
        """
        self.time_slice = time_slice
        self.last_selected_id: Optional[str] = None
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 如果只有一个任务，直接返回
        if len(tasks) == 1:
            self.last_selected_id = tasks[0]["id"]
            return tasks[0]
        
        # 找到上次选择的任务的下一个
        if self.last_selected_id:
            try:
                # 找到上次选择的任务的索引
                last_index = next(i for i, t in enumerate(tasks) if t["id"] == self.last_selected_id)
                # 选择下一个（循环）
                next_index = (last_index + 1) % len(tasks)
                selected = tasks[next_index]
            except StopIteration:
                # 上次选择的任务不在列表中，选择第一个
                selected = tasks[0]
        else:
            # 第一次选择，选择第一个
            selected = tasks[0]
        
        self.last_selected_id = selected["id"]
        return selected
    
    def name(self) -> str:
        return f"RR(slice={self.time_slice}s)"


class EDFPolicy(SchedulingPolicy):
    """最早截止时间优先（Earliest Deadline First）
    
    优先执行截止时间最早的任务。
    适用场景：实时系统，任务有明确的截止时间。
    
    注意：需要任务提供 deadline 字段（Unix timestamp）。
    """
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 过滤出有截止时间的任务
        tasks_with_deadline = [t for t in tasks if t.get("deadline") is not None]
        
        if not tasks_with_deadline:
            # 如果没有任务有截止时间，回退到 FIFO
            return min(tasks, key=lambda t: t.get("created_at", 0))
        
        # 按截止时间排序，选择最早的
        return min(tasks_with_deadline, key=lambda t: t.get("deadline", float('inf')))
    
    def name(self) -> str:
        return "EDF"


class PriorityPolicy(SchedulingPolicy):
    """优先级调度（Priority Scheduling）
    
    按照任务优先级执行（0最高，3最低）。
    适用场景：任务有明确的重要性区分。
    
    这是 Scheduler v2.1 的默认策略。
    """
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 按优先级排序，选择最高优先级的
        return min(tasks, key=lambda t: t.get("priority", 3))
    
    def name(self) -> str:
        return "Priority"


class HybridPolicy(SchedulingPolicy):
    """混合调度策略
    
    结合多种调度算法的优点：
    1. 优先级 > 0 的任务使用优先级调度
    2. 优先级 = 0 的任务使用 EDF 或 SJF
    
    适用场景：复杂系统，需要灵活的调度策略。
    """
    
    def __init__(self, fallback_policy: SchedulingPolicy = None):
        """初始化混合调度。
        
        Args:
            fallback_policy: 低优先级任务的调度策略（默认 SJF）
        """
        self.fallback_policy = fallback_policy or SJFPolicy()
    
    def select_next(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tasks:
            return None
        
        # 分离高优先级和低优先级任务
        high_priority = [t for t in tasks if t.get("priority", 3) < 3]
        low_priority = [t for t in tasks if t.get("priority", 3) == 3]
        
        # 优先处理高优先级任务
        if high_priority:
            return min(high_priority, key=lambda t: t.get("priority", 3))
        
        # 低优先级任务使用 fallback 策略
        return self.fallback_policy.select_next(low_priority)
    
    def name(self) -> str:
        return f"Hybrid({self.fallback_policy.name()})"


# ==================== 测试示例 ====================
if __name__ == "__main__":
    import time
    
    # 创建测试任务
    tasks = [
        {"id": "A", "priority": 2, "estimated_duration": 5, "deadline": time.time() + 10, "created_at": time.time()},
        {"id": "B", "priority": 1, "estimated_duration": 2, "deadline": time.time() + 5, "created_at": time.time() + 1},
        {"id": "C", "priority": 3, "estimated_duration": 1, "deadline": time.time() + 20, "created_at": time.time() + 2},
        {"id": "D", "priority": 0, "estimated_duration": 10, "deadline": time.time() + 3, "created_at": time.time() + 3},
    ]
    
    print("=" * 80)
    print("调度算法测试")
    print("=" * 80)
    
    # 测试所有策略
    policies = [
        FIFOPolicy(),
        SJFPolicy(),
        RoundRobinPolicy(time_slice=2),
        EDFPolicy(),
        PriorityPolicy(),
        HybridPolicy(fallback_policy=SJFPolicy()),
    ]
    
    for policy in policies:
        print(f"\n=== {policy.name()} ===")
        remaining = tasks.copy()
        order = []
        
        while remaining:
            selected = policy.select_next(remaining)
            if selected:
                order.append(selected["id"])
                remaining.remove(selected)
        
        print(f"执行顺序: {' → '.join(order)}")
    
    print("\n" + "=" * 80)
    print("✅ 所有策略测试完成")
    print("=" * 80)

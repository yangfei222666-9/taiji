"""
AIOS Production Scheduler - 兼容层

这个文件提供了与旧版 production_scheduler.py 兼容的接口，
但内部使用新的 Scheduler v2.3。

迁移策略：
1. 保持旧的 API（get_scheduler, Priority, Task）
2. 内部使用 Scheduler v2.3
3. 逐步迁移到新 API
"""

from typing import Dict, Any, Optional
from enum import IntEnum
from dataclasses import dataclass, field
import time
import logging

# 导入新版 Scheduler
from scheduler_v2_3 import Scheduler as SchedulerV23
from scheduling_policies import PriorityPolicy

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """任务优先级（兼容旧版）"""
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


@dataclass
class Task:
    """调度任务（兼容旧版）"""
    priority: int
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    timeout_sec: int = 60
    retry_count: int = 0
    max_retries: int = 3


class ProductionScheduler:
    """生产级调度器 - 兼容层（内部使用 Scheduler v2.3）"""
    
    def __init__(
        self,
        max_concurrent: int = 5,
        enable_cpu_binding: bool = False,
        cpu_pool: Optional[list] = None
    ):
        """初始化调度器。
        
        Args:
            max_concurrent: 最大并发任务数
            enable_cpu_binding: 是否启用 CPU 绑定（新功能）
            cpu_pool: CPU 池（新功能）
        """
        self.scheduler = SchedulerV23(
            max_concurrent=max_concurrent,
            default_timeout=60,
            policy=PriorityPolicy(),
            enable_cpu_binding=enable_cpu_binding,
            cpu_pool=cpu_pool
        )
        
        self.running = True
        logger.info(f"ProductionScheduler initialized (v2.3 backend, max_concurrent={max_concurrent})")
    
    def submit(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: Priority = Priority.P3_LOW,
        timeout_sec: int = 60
    ) -> str:
        """提交任务到队列（兼容旧版 API）。
        
        Args:
            task_type: 任务类型
            payload: 任务参数
            priority: 优先级
            timeout_sec: 超时时间
        
        Returns:
            任务 ID
        """
        # 创建任务函数（从 payload 中提取）
        def task_func():
            # 这里需要根据 task_type 执行不同的逻辑
            # 暂时返回 payload（实际使用时需要实现具体逻辑）
            return payload
        
        # 使用新版 API
        task_id = self.scheduler.schedule({
            "func": task_func,
            "priority": priority.value,
            "timeout_sec": timeout_sec,
            "task_type": task_type,
            "payload": payload,
        })
        
        return task_id
    
    def start(self):
        """启动调度器（兼容旧版 API）。"""
        self.running = True
        logger.info("ProductionScheduler started")
    
    def stop(self):
        """停止调度器（兼容旧版 API）。"""
        self.running = False
        self.scheduler.shutdown(wait=True)
        logger.info("ProductionScheduler stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（兼容旧版 API）。"""
        return self.scheduler.get_stats()


# 全局单例（兼容旧版 API）
_scheduler_instance: Optional[ProductionScheduler] = None


def get_scheduler(
    max_concurrent: int = 5,
    enable_cpu_binding: bool = False,
    cpu_pool: Optional[list] = None
) -> ProductionScheduler:
    """获取全局调度器实例（兼容旧版 API）。
    
    Args:
        max_concurrent: 最大并发任务数
        enable_cpu_binding: 是否启用 CPU 绑定（新功能）
        cpu_pool: CPU 池（新功能）
    
    Returns:
        调度器实例
    """
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = ProductionScheduler(
            max_concurrent=max_concurrent,
            enable_cpu_binding=enable_cpu_binding,
            cpu_pool=cpu_pool
        )
    
    return _scheduler_instance


# ==================== 测试示例 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("Production Scheduler - 兼容层测试")
    print("=" * 80)
    
    # 测试旧版 API
    scheduler = get_scheduler(max_concurrent=3)
    scheduler.start()
    
    # 提交任务
    task_id1 = scheduler.submit(
        task_type="test",
        payload={"data": "task1"},
        priority=Priority.P1_HIGH
    )
    
    task_id2 = scheduler.submit(
        task_type="test",
        payload={"data": "task2"},
        priority=Priority.P3_LOW
    )
    
    print(f"Submitted tasks: {task_id1}, {task_id2}")
    
    time.sleep(1.0)
    
    # 获取统计
    stats = scheduler.get_stats()
    print(f"Stats: {stats}")
    
    scheduler.stop()
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

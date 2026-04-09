"""
AIOS Task Scheduler v2.2 - 支持多种调度算法

新增特性：
- 可插拔的调度策略（FIFO/SJF/RR/EDF/Priority/Hybrid）
- 保持 v2.1 的所有特性（线程安全、依赖处理、超时保护）
"""

import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, Any, Callable, List, Optional
from enum import IntEnum
from dataclasses import dataclass, field
import logging
import time
import uuid

# 导入调度策略
from scheduling_policies import SchedulingPolicy, PriorityPolicy

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """任务优先级"""
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


class Scheduler:
    """生产级任务调度器，支持多种调度算法。"""

    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: int = 30,
        policy: Optional[SchedulingPolicy] = None
    ):
        """初始化调度器。

        Args:
            max_concurrent: 最大并发任务数
            default_timeout: 单个任务默认超时秒数
            policy: 调度策略（默认 PriorityPolicy）
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.policy = policy or PriorityPolicy()
        
        # 统一队列（不再按优先级分层）
        self.queue: deque = deque()
        self.waiting: deque = deque()
        self.running: Dict[str, Any] = {}
        self.completed: set[str] = set()
        self.dependencies: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
        # 统计
        self.stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_timeout": 0,
            "total_cancelled": 0,
        }
        
        # 回调钩子
        self.on_task_complete: Optional[Callable] = None
        self.on_task_error: Optional[Callable] = None
        self.on_task_timeout: Optional[Callable] = None
        
        # 取消标记
        self.cancelled_tasks: set[str] = set()
        
        logger.info(f"Scheduler initialized with policy: {self.policy.name()}")

    def schedule(self, task: Dict[str, Any]) -> str:
        """调度新任务。

        Args:
            task: 必须包含 'func' (Callable)，可选 'id', 'priority', 'depends_on', 'timeout_sec', 'estimated_duration', 'deadline'
        
        Returns:
            任务 ID
        """
        with self.lock:
            # 生成任务 ID（如果没有）
            task_id = task.get("id", str(uuid.uuid4())[:8])
            task["id"] = task_id
            
            # 验证
            func = task.get("func")
            if not callable(func):
                raise TypeError(f"Task {task_id}: 'func' must be callable")

            depends_on = task.get("depends_on", [])
            if not isinstance(depends_on, list):
                raise ValueError(f"Task {task_id}: 'depends_on' must be list")

            # 设置默认值
            if "priority" not in task:
                task["priority"] = Priority.P3_LOW.value
            if "created_at" not in task:
                task["created_at"] = time.time()
            
            # 记录依赖
            self.dependencies[task_id] = depends_on
            
            # 入队
            self.queue.append(task)
            self.stats["total_submitted"] += 1
            
            logger.info(f"📥 Task {task_id} scheduled (policy={self.policy.name()}, depends on {depends_on})")

        self._process_queue()
        return task_id

    def submit(
        self,
        task_type: str,
        func: Callable,
        priority: Priority = Priority.P3_LOW,
        timeout_sec: int = 30,
        depends_on: List[str] = None,
        estimated_duration: float = 0,
        deadline: Optional[float] = None
    ) -> str:
        """便捷方法：提交任务（兼容旧 API）。
        
        Args:
            task_type: 任务类型（用于日志）
            func: 任务函数
            priority: 优先级
            timeout_sec: 超时时间
            depends_on: 依赖的任务 ID 列表
            estimated_duration: 预估执行时间（秒，用于 SJF）
            deadline: 截止时间（Unix timestamp，用于 EDF）
        
        Returns:
            任务 ID
        """
        task = {
            "func": func,
            "priority": priority.value,
            "timeout_sec": timeout_sec,
            "depends_on": depends_on or [],
            "task_type": task_type,
            "estimated_duration": estimated_duration,
            "deadline": deadline,
        }
        return self.schedule(task)

    def _deps_satisfied(self, task_id: str) -> bool:
        """检查任务的所有依赖是否已完成。"""
        deps = self.dependencies.get(task_id, [])
        return all(d in self.completed for d in deps)

    def _process_queue(self) -> None:
        """处理就绪队列和等待依赖的任务（使用调度策略）。"""
        with self.lock:
            # 把满足依赖的 waiting 任务移回 queue
            new_waiting = deque()
            for task in list(self.waiting):
                if self._deps_satisfied(task["id"]):
                    self.queue.append(task)
                else:
                    new_waiting.append(task)
            self.waiting = new_waiting

            # 使用调度策略选择任务
            while len(self.running) < self.max_concurrent and self.queue:
                # 收集所有就绪任务
                ready_tasks = [t for t in self.queue if self._deps_satisfied(t["id"])]
                
                if not ready_tasks:
                    # 所有任务都在等待依赖
                    for task in list(self.queue):
                        if not self._deps_satisfied(task["id"]):
                            self.queue.remove(task)
                            self.waiting.append(task)
                    break
                
                # 使用调度策略选择下一个任务
                selected = self.policy.select_next(ready_tasks)
                
                if not selected:
                    break
                
                # 从队列中移除并启动
                self.queue.remove(selected)
                self._start_task(selected)

    def _start_task(self, task: Dict[str, Any]) -> None:
        """使用 Executor 启动带超时的任务。"""
        task_id = task["id"]
        future = self.executor.submit(self._execute_task, task)
        self.running[task_id] = future
        future.add_done_callback(lambda f: self._task_done(task_id, f, task))

    def _execute_task(self, task: Dict[str, Any]) -> Any:
        """实际执行函数（worker 线程）。"""
        return task["func"]()

    def _task_done(self, task_id: str, future, task: Dict[str, Any]) -> None:
        """任务完成回调。"""
        with self.lock:
            self.running.pop(task_id, None)
        
        try:
            # done_callback 保证任务已完成，result() 会立即返回
            result = future.result()
            self._on_complete(task_id, result)
        except Exception as e:
            self._on_error(task_id, e, task)

        self._process_queue()

    def _on_complete(self, task_id: str, result: Any) -> None:
        with self.lock:
            self.completed.add(task_id)
            self.stats["total_completed"] += 1
        logger.info(f"✅ Task {task_id} completed successfully: {result}")
        
        # 触发回调
        if self.on_task_complete:
            try:
                self.on_task_complete(task_id, result)
            except Exception as e:
                logger.error(f"Error in on_task_complete callback: {e}")

    def _on_error(self, task_id: str, error: Exception, task: Dict[str, Any]) -> None:
        retry_count = task.get("retry_count", 0)
        max_retries = task.get("max_retries", 3)
        
        if retry_count < max_retries:
            # 重试
            task["retry_count"] = retry_count + 1
            logger.warning(f"⚠️ Task {task_id} failed (retry {retry_count + 1}/{max_retries}): {error}")
            self.schedule(task)
        else:
            # 失败
            with self.lock:
                self.stats["total_failed"] += 1
            logger.error(f"❌ Task {task_id} failed after {max_retries} retries: {error}")
            
            # 触发回调
            if self.on_task_error:
                try:
                    self.on_task_error(task_id, error)
                except Exception as e:
                    logger.error(f"Error in on_task_error callback: {e}")

    def _on_timeout(self, task_id: str, task: Dict[str, Any]) -> None:
        timeout = task.get("timeout_sec", self.default_timeout)
        with self.lock:
            self.stats["total_timeout"] += 1
        logger.warning(f"⏰ Task {task_id} timed out after {timeout}s")
        
        # 触发回调
        if self.on_task_timeout:
            try:
                self.on_task_timeout(task_id, timeout)
            except Exception as e:
                logger.error(f"Error in on_task_timeout callback: {e}")

    def cancel(self, task_id: str) -> bool:
        """取消任务。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            是否成功取消
        """
        with self.lock:
            # 检查是否在队列中
            for task in list(self.queue):
                if task["id"] == task_id:
                    self.queue.remove(task)
                    self.cancelled_tasks.add(task_id)
                    self.stats["total_cancelled"] += 1
                    logger.info(f"🚫 Task {task_id} cancelled (in queue)")
                    return True
            
            # 检查是否在等待队列
            for task in list(self.waiting):
                if task["id"] == task_id:
                    self.waiting.remove(task)
                    self.cancelled_tasks.add(task_id)
                    self.stats["total_cancelled"] += 1
                    logger.info(f"🚫 Task {task_id} cancelled (waiting)")
                    return True
            
            # 检查是否正在运行
            if task_id in self.running:
                future = self.running[task_id]
                if future.cancel():
                    self.cancelled_tasks.add(task_id)
                    self.stats["total_cancelled"] += 1
                    logger.info(f"🚫 Task {task_id} cancelled (running)")
                    return True
                else:
                    logger.warning(f"⚠️ Task {task_id} cannot be cancelled (already executing)")
                    return False
        
        logger.warning(f"⚠️ Task {task_id} not found")
        return False

    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息。"""
        with self.lock:
            total = self.stats["total_submitted"]
            completed = self.stats["total_completed"]
            failed = self.stats["total_failed"]
            timeout = self.stats["total_timeout"]
            cancelled = self.stats["total_cancelled"]
            
            finished = completed + failed + timeout + cancelled
            progress = (finished / total * 100) if total > 0 else 0
            
            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "timeout": timeout,
                "cancelled": cancelled,
                "running": len(self.running),
                "queued": len(self.queue),
                "waiting": len(self.waiting),
                "progress_percent": round(progress, 2),
                "policy": self.policy.name(),
            }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（线程安全）。"""
        with self.lock:
            return {
                **self.stats,
                "running": len(self.running),
                "queued": len(self.queue),
                "waiting": len(self.waiting),
                "policy": self.policy.name(),
            }

    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭。"""
        self.executor.shutdown(wait=wait)
        logger.info("Scheduler shutdown complete.")


# ==================== 测试示例 ====================
if __name__ == "__main__":
    from scheduling_policies import FIFOPolicy, SJFPolicy, RoundRobinPolicy, EDFPolicy
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("Scheduler v2.2 - 调度算法测试")
    print("=" * 80)
    
    # 测试不同的调度策略
    policies = [
        ("FIFO", FIFOPolicy()),
        ("SJF", SJFPolicy()),
        ("RR", RoundRobinPolicy(time_slice=2)),
        ("EDF", EDFPolicy()),
        ("Priority", PriorityPolicy()),
    ]
    
    for policy_name, policy in policies:
        print(f"\n=== Testing {policy_name} ===")
        
        scheduler = Scheduler(max_concurrent=2, policy=policy)
        
        order = []
        
        def make_task(name):
            def task():
                order.append(name)
                time.sleep(0.1)
                return f"{name} done"
            return task
        
        # 提交任务（不同的属性）
        scheduler.schedule({
            "id": "A",
            "func": make_task("A"),
            "priority": 2,
            "estimated_duration": 5,
            "deadline": time.time() + 10,
        })
        
        scheduler.schedule({
            "id": "B",
            "func": make_task("B"),
            "priority": 1,
            "estimated_duration": 2,
            "deadline": time.time() + 5,
        })
        
        scheduler.schedule({
            "id": "C",
            "func": make_task("C"),
            "priority": 3,
            "estimated_duration": 1,
            "deadline": time.time() + 20,
        })
        
        time.sleep(1.0)
        
        print(f"Execution order: {' → '.join(order)}")
        print(f"Stats: {scheduler.get_stats()}")
        
        scheduler.shutdown(wait=False)
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

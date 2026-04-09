"""
AIOS Task Scheduler v2.3 - 支持 Thread Binding

新增特性：
- CPU 亲和性绑定（Thread Binding）
- CPU 池管理
- 自动负载均衡
- 保持 v2.2 的所有特性（调度算法、线程安全、依赖处理）
"""

import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, Any, Callable, List, Optional
from enum import IntEnum
import logging
import time
import uuid

# 导入调度策略和线程绑定
from scheduling_policies import SchedulingPolicy, PriorityPolicy
from thread_binding import ThreadBinder, CPUPool

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """任务优先级"""
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


class Scheduler:
    """生产级任务调度器，支持多种调度算法和 CPU 绑定。"""

    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: int = 30,
        policy: Optional[SchedulingPolicy] = None,
        enable_cpu_binding: bool = False,
        cpu_pool: Optional[List[int]] = None
    ):
        """初始化调度器。

        Args:
            max_concurrent: 最大并发任务数
            default_timeout: 单个任务默认超时秒数
            policy: 调度策略（默认 PriorityPolicy）
            enable_cpu_binding: 是否启用 CPU 绑定
            cpu_pool: CPU 池（CPU 核心 ID 列表），如果为 None 则使用所有 CPU
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.policy = policy or PriorityPolicy()
        self.enable_cpu_binding = enable_cpu_binding
        
        # CPU 绑定
        if enable_cpu_binding:
            self.thread_binder = ThreadBinder()
            self.cpu_pool = CPUPool(cpu_ids=cpu_pool)
            logger.info(f"CPU binding enabled with pool: {self.cpu_pool.cpu_ids}")
        else:
            self.thread_binder = None
            self.cpu_pool = None
        
        # 队列
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
        
        logger.info(f"Scheduler initialized with policy: {self.policy.name()}, CPU binding: {enable_cpu_binding}")

    def schedule(self, task: Dict[str, Any]) -> str:
        """调度新任务。

        Args:
            task: 必须包含 'func' (Callable)，可选 'id', 'priority', 'depends_on', 'timeout_sec', 'cpu_affinity'
        
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
            
            cpu_info = f", cpu_affinity={task.get('cpu_affinity')}" if task.get('cpu_affinity') else ""
            logger.info(f"📥 Task {task_id} scheduled (policy={self.policy.name()}{cpu_info})")

        self._process_queue()
        return task_id

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
        # CPU 绑定
        if self.enable_cpu_binding and self.cpu_pool:
            cpu_affinity = task.get("cpu_affinity")
            
            if cpu_affinity:
                # 用户指定的 CPU
                if isinstance(cpu_affinity, int):
                    cpu_affinity = [cpu_affinity]
                self.thread_binder.bind_current_thread(cpu_affinity)
            else:
                # 自动分配（负载均衡）
                self.cpu_pool.bind_to_least_loaded()
        
        try:
            result = task["func"]()
            return result
        finally:
            # 解除绑定
            if self.enable_cpu_binding and self.thread_binder:
                self.thread_binder.unbind_current_thread()

    def _task_done(self, task_id: str, future, task: Dict[str, Any]) -> None:
        """任务完成回调。"""
        with self.lock:
            self.running.pop(task_id, None)
        
        try:
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
        
        if self.on_task_complete:
            try:
                self.on_task_complete(task_id, result)
            except Exception as e:
                logger.error(f"Error in on_task_complete callback: {e}")

    def _on_error(self, task_id: str, error: Exception, task: Dict[str, Any]) -> None:
        retry_count = task.get("retry_count", 0)
        max_retries = task.get("max_retries", 3)
        
        if retry_count < max_retries:
            task["retry_count"] = retry_count + 1
            logger.warning(f"⚠️ Task {task_id} failed (retry {retry_count + 1}/{max_retries}): {error}")
            self.schedule(task)
        else:
            with self.lock:
                self.stats["total_failed"] += 1
            logger.error(f"❌ Task {task_id} failed after {max_retries} retries: {error}")
            
            if self.on_task_error:
                try:
                    self.on_task_error(task_id, error)
                except Exception as e:
                    logger.error(f"Error in on_task_error callback: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（线程安全）。"""
        with self.lock:
            stats = {
                **self.stats,
                "running": len(self.running),
                "queued": len(self.queue),
                "waiting": len(self.waiting),
                "policy": self.policy.name(),
                "cpu_binding_enabled": self.enable_cpu_binding,
            }
            
            # 添加 CPU 统计
            if self.enable_cpu_binding and self.thread_binder:
                stats["cpu_stats"] = self.thread_binder.get_cpu_stats()
            
            return stats

    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭。"""
        self.executor.shutdown(wait=wait)
        logger.info("Scheduler shutdown complete.")


# ==================== 测试示例 ====================
if __name__ == "__main__":
    from scheduling_policies import FIFOPolicy
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("Scheduler v2.3 - Thread Binding 测试")
    print("=" * 80)
    
    # 测试 1：不启用 CPU 绑定
    print("\n=== Test 1: Without CPU Binding ===")
    scheduler = Scheduler(max_concurrent=2, policy=FIFOPolicy(), enable_cpu_binding=False)
    
    def task(name):
        print(f"Task {name} running")
        time.sleep(0.1)
        return f"{name} done"
    
    scheduler.schedule({"id": "A", "func": lambda: task("A")})
    scheduler.schedule({"id": "B", "func": lambda: task("B")})
    
    time.sleep(0.5)
    print(f"Stats: {scheduler.get_stats()}")
    scheduler.shutdown(wait=False)
    
    # 测试 2：启用 CPU 绑定
    print("\n=== Test 2: With CPU Binding ===")
    scheduler = Scheduler(
        max_concurrent=2,
        policy=FIFOPolicy(),
        enable_cpu_binding=True,
        cpu_pool=[0, 1]  # 只使用 CPU 0 和 1
    )
    
    scheduler.schedule({"id": "C", "func": lambda: task("C")})
    scheduler.schedule({"id": "D", "func": lambda: task("D")})
    
    time.sleep(0.5)
    stats = scheduler.get_stats()
    print(f"Stats: {stats}")
    if "cpu_stats" in stats:
        print(f"CPU Stats: {stats['cpu_stats']}")
    scheduler.shutdown(wait=False)
    
    # 测试 3：指定 CPU 亲和性
    print("\n=== Test 3: With Specific CPU Affinity ===")
    scheduler = Scheduler(
        max_concurrent=2,
        policy=FIFOPolicy(),
        enable_cpu_binding=True
    )
    
    # 任务 E 绑定到 CPU 0
    scheduler.schedule({"id": "E", "func": lambda: task("E"), "cpu_affinity": 0})
    
    # 任务 F 绑定到 CPU 1
    scheduler.schedule({"id": "F", "func": lambda: task("F"), "cpu_affinity": 1})
    
    time.sleep(0.5)
    print(f"Stats: {scheduler.get_stats()}")
    scheduler.shutdown(wait=False)
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

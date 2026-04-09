"""
AIOS Scheduler v2 - 优先级队列调度系统

从 ToyScheduler 的简单 if/else 升级为：
- P0/P1/P2 优先级队列
- 优先级 + 等待时间排序算法
- 并发控制（最多 5 个并行任务）
- 超时重试机制
- 完全向后兼容 ToyScheduler API

用法:
    # 向后兼容（drop-in replacement）
    scheduler = SchedulerV2()
    scheduler.start()

    # 新 API
    scheduler.submit(Task(name="fix_cpu", priority=Priority.P0, handler=my_fn))
"""
from __future__ import annotations

import heapq
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import sys

AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType, create_event
from core.event_bus import get_event_bus, EventBus


# ---------------------------------------------------------------------------
# Priority & Task
# ---------------------------------------------------------------------------

class Priority(IntEnum):
    """任务优先级，数值越小越优先"""
    P0 = 0  # 紧急：系统崩溃、资源临界
    P1 = 1  # 高：agent 错误、任务失败
    P2 = 2  # 普通：日志记录、pipeline 完成


class TaskState(IntEnum):
    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    TIMEOUT = 4
    RETRYING = 5


@dataclass(order=False)
class Task:
    """调度任务"""
    name: str
    priority: Priority = Priority.P2
    handler: Optional[Callable[[], Any]] = None
    timeout_sec: float = 30.0
    max_retries: int = 2
    payload: Dict[str, Any] = field(default_factory=dict)

    # 内部状态（用户不需要设置）
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = TaskState.PENDING
    retries: int = 0
    created_at: float = field(default_factory=time.monotonic)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result: Any = None


# ---------------------------------------------------------------------------
# Priority Queue（线程安全）
# ---------------------------------------------------------------------------

class _PriorityQueue:
    """
    线程安全的优先级队列。

    排序规则：
    1. priority 越小越优先（P0 > P1 > P2）
    2. 同优先级按等待时间排序（等得越久越优先 → created_at 越小越优先）
    3. 再相同则按插入序号（FIFO）
    """

    def __init__(self):
        self._heap: List[tuple] = []
        self._counter = 0
        self._lock = threading.Lock()

    def push(self, task: Task) -> None:
        with self._lock:
            entry = (int(task.priority), task.created_at, self._counter, task)
            heapq.heappush(self._heap, entry)
            self._counter += 1

    def pop(self) -> Optional[Task]:
        with self._lock:
            if not self._heap:
                return None
            _, _, _, task = heapq.heappop(self._heap)
            return task

    def peek(self) -> Optional[Task]:
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0][3]

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)

    def __bool__(self) -> bool:
        return len(self) > 0

    def drain(self) -> List[Task]:
        """取出所有任务"""
        with self._lock:
            tasks = [entry[3] for entry in sorted(self._heap)]
            self._heap.clear()
            return tasks


# ---------------------------------------------------------------------------
# Scheduler V2
# ---------------------------------------------------------------------------

_DEFAULT_MAX_CONCURRENCY = 5


class SchedulerV2:
    """
    优先级队列调度器。

    向后兼容 ToyScheduler 的全部公开 API：
    - start()
    - get_actions() -> List[dict]

    新增能力：
    - submit(task) 提交任务
    - 并发控制（semaphore）
    - 超时 + 自动重试
    - 事件驱动决策
    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ):
        self.bus = bus or get_event_bus()
        self.max_concurrency = max_concurrency

        # 内部状态
        self._queue = _PriorityQueue()
        self._semaphore = threading.Semaphore(max_concurrency)
        self._actions: List[Dict[str, Any]] = []       # 兼容 ToyScheduler
        self._completed: List[Task] = []
        self._running: Dict[str, Task] = {}            # task_id → Task
        self._lock = threading.Lock()
        self._started = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # 向后兼容 ToyScheduler API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动调度器，订阅事件（兼容 ToyScheduler.start）"""
        if self._started:
            return
        self._started = True

        # 订阅与 ToyScheduler 相同的事件
        self.bus.subscribe("resource.*", self._handle_resource_event)
        self.bus.subscribe("agent.error", self._handle_agent_error)
        self.bus.subscribe("pipeline.completed", self._handle_pipeline_completed)

        # 启动后台 worker
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="scheduler-v2-worker"
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """停止调度器"""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        self._started = False

    def get_actions(self) -> List[Dict[str, Any]]:
        """获取所有决策记录（兼容 ToyScheduler.get_actions）"""
        return list(self._actions)

    # ------------------------------------------------------------------
    # 新 API
    # ------------------------------------------------------------------

    def submit(self, task: Task) -> str:
        """
        提交任务到优先级队列。

        Returns:
            task.id
        """
        task.state = TaskState.PENDING
        self._queue.push(task)
        self.bus.emit(create_event(
            "scheduler.task_submitted",
            source="scheduler_v2",
            task_id=task.id,
            task_name=task.name,
            priority=int(task.priority),
        ))
        return task.id

    def get_queue_size(self) -> int:
        return len(self._queue)

    def get_running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def get_completed_tasks(self) -> List[Task]:
        return list(self._completed)

    def get_stats(self) -> Dict[str, Any]:
        """返回调度器统计信息"""
        completed = self._completed
        failed = [t for t in completed if t.state == TaskState.FAILED]
        timed_out = [t for t in completed if t.state == TaskState.TIMEOUT]
        success = [t for t in completed if t.state == TaskState.COMPLETED]
        return {
            "queued": len(self._queue),
            "running": self.get_running_count(),
            "completed": len(success),
            "failed": len(failed),
            "timed_out": len(timed_out),
            "total_decisions": len(self._actions),
            "max_concurrency": self.max_concurrency,
        }

    # ------------------------------------------------------------------
    # 事件处理（兼容 ToyScheduler 行为 + 优先级增强）
    # ------------------------------------------------------------------

    def _record_action(self, action: str, reason: str, event_id: str,
                       priority: Priority = Priority.P2) -> Dict[str, Any]:
        """记录决策并返回"""
        decision = {
            "action": action,
            "reason": reason,
            "event_id": event_id,
            "priority": int(priority),
        }
        self._actions.append(decision)
        return decision

    def _handle_resource_event(self, event: Event) -> None:
        """处理资源事件 → P0 优先级"""
        decision = self._record_action(
            "trigger_reactor",
            f"资源告警: {event.type}",
            event.id,
            priority=Priority.P0,
        )

        # 发射决策事件（兼容 ToyScheduler）
        self.bus.emit(create_event(
            "scheduler.decision",
            source="scheduler_v2",
            action="trigger_reactor",
            target_event=event.id,
            reason=decision["reason"],
        ))

        # 如果有 payload 中的具体值，创建修复任务
        cpu = event.payload.get("cpu_percent")
        mem = event.payload.get("memory_percent")
        if cpu and cpu > 90:
            self.submit(Task(
                name="reduce_concurrency",
                priority=Priority.P0,
                timeout_sec=10,
                payload={"trigger_event": event.id, "cpu": cpu},
            ))
        elif mem and mem > 90:
            self.submit(Task(
                name="free_memory",
                priority=Priority.P0,
                timeout_sec=15,
                payload={"trigger_event": event.id, "memory": mem},
            ))

    def _handle_agent_error(self, event: Event) -> None:
        """处理 agent 错误 → P1 优先级"""
        decision = self._record_action(
            "trigger_reactor",
            "Agent 执行失败",
            event.id,
            priority=Priority.P1,
        )

        self.bus.emit(create_event(
            "scheduler.decision",
            source="scheduler_v2",
            action="trigger_reactor",
            target_event=event.id,
            reason=decision["reason"],
        ))

    def _handle_pipeline_completed(self, event: Event) -> None:
        """处理 pipeline 完成 → P2 优先级"""
        self._record_action(
            "log_completion",
            "Pipeline 正常完成",
            event.id,
            priority=Priority.P2,
        )

    # ------------------------------------------------------------------
    # Worker：从队列取任务 → 并发执行 → 超时/重试
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """后台 worker：持续从队列取任务并执行"""
        while not self._stop_event.is_set():
            task = self._queue.pop()
            if task is None:
                # 队列空，短暂休眠
                self._stop_event.wait(timeout=0.05)
                continue

            # 获取并发许可
            acquired = self._semaphore.acquire(timeout=1.0)
            if not acquired:
                # 并发已满，放回队列
                self._queue.push(task)
                self._stop_event.wait(timeout=0.1)
                continue

            # 在独立线程中执行任务
            t = threading.Thread(
                target=self._execute_task,
                args=(task,),
                daemon=True,
                name=f"task-{task.name}-{task.id[:8]}",
            )
            t.start()

    def _execute_task(self, task: Task) -> None:
        """执行单个任务（带超时和重试）"""
        try:
            task.state = TaskState.RUNNING
            task.started_at = time.monotonic()

            with self._lock:
                self._running[task.id] = task

            self.bus.emit(create_event(
                "scheduler.task_started",
                source="scheduler_v2",
                task_id=task.id,
                task_name=task.name,
                priority=int(task.priority),
            ))

            if task.handler is None:
                # 无 handler 的任务视为纯事件驱动决策，直接完成
                task.state = TaskState.COMPLETED
                task.finished_at = time.monotonic()
                self._finish_task(task)
                return

            # 带超时执行
            result_container: Dict[str, Any] = {}
            error_container: Dict[str, Any] = {}

            def _run():
                try:
                    result_container["value"] = task.handler()
                except Exception as exc:
                    error_container["exc"] = exc

            runner = threading.Thread(target=_run, daemon=True)
            runner.start()
            runner.join(timeout=task.timeout_sec)

            if runner.is_alive():
                # 超时
                task.state = TaskState.TIMEOUT
                task.error = f"Timeout after {task.timeout_sec}s"
                task.finished_at = time.monotonic()
                self._handle_task_failure(task)
                return

            if "exc" in error_container:
                task.state = TaskState.FAILED
                task.error = str(error_container["exc"])
                task.finished_at = time.monotonic()
                self._handle_task_failure(task)
                return

            # 成功
            task.state = TaskState.COMPLETED
            task.result = result_container.get("value")
            task.finished_at = time.monotonic()
            self._finish_task(task)

        except Exception as exc:
            task.state = TaskState.FAILED
            task.error = str(exc)
            task.finished_at = time.monotonic()
            self._handle_task_failure(task)
        finally:
            with self._lock:
                self._running.pop(task.id, None)
            self._semaphore.release()

    def _handle_task_failure(self, task: Task) -> None:
        """处理任务失败：决定重试或放弃"""
        if task.retries < task.max_retries:
            task.retries += 1
            task.state = TaskState.RETRYING
            task.error = None
            task.started_at = None
            task.finished_at = None
            # 重新入队（保留原始 created_at 以维持等待时间优先）
            self._queue.push(task)

            self.bus.emit(create_event(
                "scheduler.task_retrying",
                source="scheduler_v2",
                task_id=task.id,
                task_name=task.name,
                retry=task.retries,
                max_retries=task.max_retries,
            ))
        else:
            # 重试耗尽
            self._finish_task(task)

    def _finish_task(self, task: Task) -> None:
        """任务最终完成（成功或彻底失败）"""
        self._completed.append(task)

        event_type = (
            "scheduler.task_completed"
            if task.state == TaskState.COMPLETED
            else "scheduler.task_failed"
        )
        self.bus.emit(create_event(
            event_type,
            source="scheduler_v2",
            task_id=task.id,
            task_name=task.name,
            state=task.state.name,
            retries=task.retries,
            error=task.error,
        ))


# ---------------------------------------------------------------------------
# 便捷函数（兼容 toy_scheduler.start_scheduler）
# ---------------------------------------------------------------------------

def start_scheduler(bus: Optional[EventBus] = None,
                    max_concurrency: int = _DEFAULT_MAX_CONCURRENCY) -> SchedulerV2:
    """启动调度器（drop-in replacement for toy_scheduler.start_scheduler）"""
    scheduler = SchedulerV2(bus=bus, max_concurrency=max_concurrency)
    scheduler.start()
    return scheduler


# ---------------------------------------------------------------------------
# 向后兼容别名
# ---------------------------------------------------------------------------
ToyScheduler = SchedulerV2


if __name__ == "__main__":
    import textwrap

    print("=" * 60)
    print("Scheduler V2 - 优先级队列调度器测试")
    print("=" * 60)

    scheduler = start_scheduler()

    # 1. 兼容性测试：模拟 ToyScheduler 的事件
    from core.event_bus import emit as bus_emit

    print("\n[1] 模拟资源峰值事件...")
    bus_emit(create_event(EventType.RESOURCE_CPU_SPIKE, "monitor", cpu_percent=90.0))

    print("[2] 模拟 agent 错误...")
    bus_emit(create_event(EventType.AGENT_ERROR, "agent_system", error="Task failed"))

    print("[3] 模拟 pipeline 完成...")
    bus_emit(create_event(EventType.PIPELINE_COMPLETED, "pipeline", duration_ms=5000))

    # 2. 新 API 测试：提交带 handler 的任务
    def slow_task():
        time.sleep(0.2)
        return "done"

    print("\n[4] 提交 P0 任务...")
    scheduler.submit(Task(name="critical_fix", priority=Priority.P0, handler=slow_task))

    print("[5] 提交 P2 任务...")
    scheduler.submit(Task(name="log_cleanup", priority=Priority.P2, handler=slow_task))

    # 等待执行
    time.sleep(2)

    # 3. 查看结果
    print("\n" + "=" * 60)
    print(f"决策记录 (兼容 get_actions): {len(scheduler.get_actions())}")
    for i, action in enumerate(scheduler.get_actions(), 1):
        print(f"  {i}. [{Priority(action.get('priority', 2)).name}] "
              f"{action['action']} - {action['reason']}")

    print(f"\n统计: {scheduler.get_stats()}")
    print("=" * 60)

    scheduler.stop()

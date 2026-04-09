"""
AIOS Thread Pool Manager - Thread binding with CPU affinity.

Features:
- Named thread pools for different resource types (llm, memory, storage)
- Thread-to-queue binding (each pool serves one queue)
- CPU affinity hints (best-effort on Windows/Linux)
- Pool lifecycle management (start, stop, resize)
- Worker stats (utilization, idle time)
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import sys
from pathlib import Path

AIOS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import create_event
from core.event_bus import EventBus, get_event_bus


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

@dataclass
class WorkerStats:
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_busy_sec: float = 0.0
    total_idle_sec: float = 0.0
    last_active: float = 0.0


class _Worker:
    """A single worker thread bound to a pool."""

    def __init__(self, name: str, pool: "ThreadPool"):
        self.name = name
        self.pool = pool
        self.stats = WorkerStats()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=name,
        )

    def start(self) -> None:
        self._stop.clear()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 5.0) -> None:
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        idle_start = time.monotonic()
        while not self._stop.is_set():
            task = self.pool._get_task(timeout=0.1)
            if task is None:
                continue

            # Track idle time
            now = time.monotonic()
            self.stats.total_idle_sec += now - idle_start

            # Execute
            busy_start = now
            try:
                task()
                self.stats.tasks_completed += 1
            except Exception:
                self.stats.tasks_failed += 1
            finally:
                elapsed = time.monotonic() - busy_start
                self.stats.total_busy_sec += elapsed
                self.stats.last_active = time.monotonic()
                idle_start = time.monotonic()

        # Final idle accounting
        self.stats.total_idle_sec += time.monotonic() - idle_start


# ---------------------------------------------------------------------------
# ThreadPool
# ---------------------------------------------------------------------------

class ThreadPool:
    """
    A named thread pool bound to a specific resource queue.

    Workers pull tasks from an internal queue. The pool owner
    submits callables via submit().
    """

    def __init__(
        self,
        name: str,
        size: int = 4,
        cpu_affinity: Optional[List[int]] = None,
    ):
        self.name = name
        self._size = size
        self._cpu_affinity = cpu_affinity
        self._workers: List[_Worker] = []
        self._task_queue: List[Callable] = []
        self._task_lock = threading.Lock()
        self._task_event = threading.Event()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._size):
            w = _Worker(f"{self.name}-worker-{i}", self)
            w.start()
            self._workers.append(w)

        # Best-effort CPU affinity
        if self._cpu_affinity:
            self._set_affinity()

    def stop(self) -> None:
        for w in self._workers:
            w.stop()
        self._task_event.set()  # wake blocked workers
        for w in self._workers:
            w.join()
        self._workers.clear()
        self._started = False

    def submit(self, task: Callable) -> None:
        """Submit a callable to be executed by a pool worker."""
        with self._task_lock:
            self._task_queue.append(task)
        self._task_event.set()

    def resize(self, new_size: int) -> None:
        """Resize the pool. Adds or removes workers."""
        if new_size == self._size:
            return
        if new_size > self._size:
            for i in range(self._size, new_size):
                w = _Worker(f"{self.name}-worker-{i}", self)
                w.start()
                self._workers.append(w)
        else:
            # Remove excess workers
            excess = self._workers[new_size:]
            self._workers = self._workers[:new_size]
            for w in excess:
                w.stop()
            for w in excess:
                w.join()
        self._size = new_size

    @property
    def size(self) -> int:
        return self._size

    def stats(self) -> Dict[str, Any]:
        worker_stats = []
        for w in self._workers:
            total = w.stats.total_busy_sec + w.stats.total_idle_sec
            utilization = (
                w.stats.total_busy_sec / total * 100 if total > 0 else 0.0
            )
            worker_stats.append({
                "name": w.name,
                "tasks_completed": w.stats.tasks_completed,
                "tasks_failed": w.stats.tasks_failed,
                "utilization_pct": round(utilization, 1),
                "alive": w.alive,
            })
        return {
            "pool": self.name,
            "size": self._size,
            "pending_tasks": len(self._task_queue),
            "workers": worker_stats,
        }

    # internal: called by workers
    def _get_task(self, timeout: float = 0.1) -> Optional[Callable]:
        self._task_event.wait(timeout=timeout)
        with self._task_lock:
            if self._task_queue:
                task = self._task_queue.pop(0)
                if not self._task_queue:
                    self._task_event.clear()
                return task
            self._task_event.clear()
            return None

    def _set_affinity(self) -> None:
        """Best-effort CPU affinity (Windows only for now)."""
        if os.name != "nt" or not self._cpu_affinity:
            return
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            for w in self._workers:
                if not w._thread.ident:
                    continue
                handle = kernel32.OpenThread(0x0060, False, w._thread.ident)
                if handle:
                    mask = sum(1 << cpu for cpu in self._cpu_affinity)
                    kernel32.SetThreadAffinityMask(handle, mask)
                    kernel32.CloseHandle(handle)
        except Exception:
            pass  # best effort


# ---------------------------------------------------------------------------
# ThreadPoolManager
# ---------------------------------------------------------------------------

class ThreadPoolManager:
    """
    Manages multiple named thread pools.

    Typical setup:
        manager = ThreadPoolManager()
        manager.create_pool("llm", size=4)
        manager.create_pool("memory", size=2)
        manager.create_pool("storage", size=2, cpu_affinity=[0, 1])
        manager.start_all()
    """

    def __init__(self, bus: Optional[EventBus] = None):
        self.bus = bus or get_event_bus()
        self._pools: Dict[str, ThreadPool] = {}

    def create_pool(
        self,
        name: str,
        size: int = 4,
        cpu_affinity: Optional[List[int]] = None,
    ) -> ThreadPool:
        """Create a named thread pool."""
        if name in self._pools:
            raise ValueError(f"Pool '{name}' already exists")
        pool = ThreadPool(name=name, size=size, cpu_affinity=cpu_affinity)
        self._pools[name] = pool
        return pool

    def get_pool(self, name: str) -> Optional[ThreadPool]:
        return self._pools.get(name)

    def start_all(self) -> None:
        for pool in self._pools.values():
            pool.start()
        try:
            self.bus.emit(create_event(
                "threadpool.all_started",
                source="thread_pool_manager",
                pool_names=",".join(self._pools.keys()),
            ))
        except Exception:
            pass

    def stop_all(self) -> None:
        for pool in self._pools.values():
            pool.stop()
        try:
            self.bus.emit(create_event(
                "threadpool.all_stopped",
                source="thread_pool_manager",
            ))
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        return {
            name: pool.stats()
            for name, pool in self._pools.items()
        }

    def resize_pool(self, name: str, new_size: int) -> None:
        pool = self._pools.get(name)
        if pool is None:
            raise ValueError(f"Pool '{name}' not found")
        pool.resize(new_size)

    @property
    def pool_names(self) -> List[str]:
        return list(self._pools.keys())

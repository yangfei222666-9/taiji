"""
Durable Task Queue with atomic state transitions and crash recovery.
"""
from __future__ import annotations
import json
import os
import platform
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Literal
from pathlib import Path

TaskStatus = Literal["queued", "running", "succeeded", "failed", "permanently_failed"]

# ── 进程内互斥锁（多线程安全）────────────────────────────────────────────────
_QUEUE_LOCK = threading.Lock()


@contextmanager
def _file_mutex(path: Path):
    """跨平台文件互斥锁（多进程安全）"""
    lock_path = path.with_suffix(".lock")
    lock_path.touch(exist_ok=True)
    fh = open(lock_path, "r+")
    try:
        if platform.system() == "Windows":
            import msvcrt
            # Windows: 非阻塞尝试，失败则等待重试
            for _ in range(50):  # 最多等 500ms
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            else:
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        if platform.system() == "Windows":
            import msvcrt
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()

@dataclass
class TaskRecord:
    task_id: str
    payload: Dict[str, Any]
    status: TaskStatus
    retry_count: int
    max_retries: int
    worker_id: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    last_heartbeat_at: Optional[float] = None
    recovered_at: Optional[float] = None
    recovered_by: Optional[str] = None
    recover_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class TaskQueue:
    """Durable task queue with atomic state transitions."""
    
    def __init__(self, queue_file: str = None):
        if queue_file is None:
            try:
                from paths import TASK_QUEUE
                queue_file = str(TASK_QUEUE)
            except ImportError:
                queue_file = "data/task_queue.jsonl"
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self.queue_file.touch()
    
    def _load_all(self) -> Dict[str, TaskRecord]:
        """Load all tasks into memory (indexed by task_id)."""
        tasks = {}
        if not self.queue_file.exists():
            return tasks
        
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                task_id = data.get("task_id")
                if task_id:
                    tasks[task_id] = TaskRecord(
                        task_id=task_id,
                        payload=data.get("payload", {}),
                        status=data.get("status", "queued"),
                        retry_count=data.get("retry_count", 0),
                        max_retries=data.get("max_retries", 3),
                        worker_id=data.get("worker_id"),
                        started_at=data.get("started_at"),
                        finished_at=data.get("finished_at"),
                        last_heartbeat_at=data.get("last_heartbeat_at"),
                        recovered_at=data.get("recovered_at"),
                        recovered_by=data.get("recovered_by"),
                        recover_reason=data.get("recover_reason"),
                    )
        return tasks
    
    def _save_all(self, tasks: Dict[str, TaskRecord]) -> None:
        """Save all tasks to disk (atomic write)."""
        tmp_file = self.queue_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            for task in tasks.values():
                f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")
        # Windows: 目标文件存在时 replace 可能失败，先删除再替换
        if self.queue_file.exists():
            try:
                self.queue_file.unlink()
            except Exception:
                pass
        tmp_file.replace(self.queue_file)
    
    def enqueue_task(
        self, 
        task_id: str, 
        payload: Dict[str, Any], 
        max_retries: int = 3
    ) -> None:
        """Add a new task to the queue. Raises ValueError if task_id already exists."""
        with _QUEUE_LOCK:
            with _file_mutex(self.queue_file):
                tasks = self._load_all()
                if task_id in tasks:
                    raise ValueError(f"Task '{task_id}' already exists (status={tasks[task_id].status})")
                
                tasks[task_id] = TaskRecord(
                    task_id=task_id,
                    payload=payload,
                    status="queued",
                    retry_count=0,
                    max_retries=max_retries,
                )
                self._save_all(tasks)
    
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Get a single task by ID."""
        tasks = self._load_all()
        return tasks.get(task_id)
    
    def acquire_task(self, worker_id: str) -> Optional[TaskRecord]:
        """
        Atomically acquire the next queued task.
        Returns the task if acquired, None if no tasks available.
        """
        with _QUEUE_LOCK:
            with _file_mutex(self.queue_file):
                tasks = self._load_all()
                
                # Find first queued task
                queued_tasks = [t for t in tasks.values() if t.status == "queued"]
                if not queued_tasks:
                    return None
                
                # Sort by task_id for deterministic order
                queued_tasks.sort(key=lambda t: t.task_id)
                task = queued_tasks[0]
                
                # Transition to running
                task.status = "running"
                task.worker_id = worker_id
                task.started_at = time.time()
                task.last_heartbeat_at = task.started_at
                
                self._save_all(tasks)
                return task
    
    def list_tasks_by_status(
        self, 
        status: TaskStatus, 
        limit: int = 1000
    ) -> List[TaskRecord]:
        """List all tasks with a given status."""
        tasks = self._load_all()
        result = [t for t in tasks.values() if t.status == status]
        return result[:limit]
    
    def transition_status(
        self,
        task_id: str,
        from_status: TaskStatus,
        to_status: TaskStatus,
        patch: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Atomically transition a task from one status to another.
        Returns True if transition succeeded, False if task not in expected state.
        """
        with _QUEUE_LOCK:
            with _file_mutex(self.queue_file):
                tasks = self._load_all()
                task = tasks.get(task_id)
                
                if not task:
                    return False
                
                if task.status != from_status:
                    # Task not in expected state
                    return False
                
                # Apply transition
                task.status = to_status
                
                # Auto-set timestamps (before patch, so patch can override)
                if to_status == "running" and not task.started_at:
                    task.started_at = time.time()
                    if task.last_heartbeat_at is None:
                        task.last_heartbeat_at = task.started_at
                
                if to_status in ("succeeded", "failed", "permanently_failed"):
                    task.finished_at = time.time()
                
                # Apply patch (can override auto-set values)
                if patch:
                    for key, value in patch.items():
                        if hasattr(task, key):
                            setattr(task, key, value)
                
                self._save_all(tasks)
                return True
    
    def heartbeat_running_task(
        self, 
        task_id: str, 
        worker_id: str, 
        ts: Optional[float] = None
    ) -> bool:
        """Update heartbeat timestamp for a running task."""
        tasks = self._load_all()
        task = tasks.get(task_id)
        
        if not task or task.status != "running":
            return False
        
        task.last_heartbeat_at = ts or time.time()
        task.worker_id = worker_id
        
        self._save_all(tasks)
        return True
    
    def list_recoverable_running(
        self,
        now_ts: float,
        timeout_seconds: int,
        limit: int = 1000,
    ) -> List[TaskRecord]:
        """
        List running tasks that have timed out and need recovery.
        A task is recoverable if:
        - status == "running"
        - last_heartbeat_at is older than timeout_seconds OR is None
        
        Sorting priority:
        1. Tasks with no heartbeat (NULL) first
        2. Then by oldest heartbeat
        
        SQL equivalent (for future migration):
        SELECT task_id, status, retry_count, max_retries, last_heartbeat_at, updated_at
        FROM tasks
        WHERE status = 'running'
          AND (last_heartbeat_at IS NULL OR last_heartbeat_at <= :cutoff)
        ORDER BY
          CASE WHEN last_heartbeat_at IS NULL THEN 0 ELSE 1 END ASC,
          last_heartbeat_at ASC
        LIMIT :limit;
        """
        tasks = self._load_all()
        cutoff = now_ts - timeout_seconds
        result = []
        
        for task in tasks.values():
            if task.status != "running":
                continue
            
            if not task.last_heartbeat_at:
                # No heartbeat recorded, consider it timed out
                result.append(task)
                continue
            
            if task.last_heartbeat_at <= cutoff:
                result.append(task)
        
        # Sort: NULL heartbeats first, then by oldest heartbeat
        result.sort(key=lambda t: (
            0 if t.last_heartbeat_at is None else 1,
            t.last_heartbeat_at or 0
        ))
        
        return result[:limit]
    
    def mark_recovered(
        self,
        task_id: str,
        recovered_by: str,
        recover_reason: str,
        recovered_at: Optional[float] = None,
    ) -> bool:
        """Mark a task as recovered (for audit trail)."""
        tasks = self._load_all()
        task = tasks.get(task_id)
        
        if not task:
            return False
        
        task.recovered_at = recovered_at or time.time()
        task.recovered_by = recovered_by
        task.recover_reason = recover_reason
        
        self._save_all(tasks)
        return True

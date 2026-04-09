"""
AIOS Queue System - Base abstractions

Defines:
- QueueRequest: universal request envelope
- RequestState: lifecycle states
- SchedulingPolicy: algorithm enum
- BaseQueue: abstract queue with EventBus integration
"""
from __future__ import annotations

import abc
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional

import sys
from pathlib import Path

AIOS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, create_event
from core.event_bus import EventBus, get_event_bus


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RequestState(IntEnum):
    PENDING = 0
    QUEUED = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    TIMEOUT = 5
    CANCELLED = 6


class SchedulingPolicy(IntEnum):
    """Scheduling algorithms available across queues."""
    FIFO = auto()       # First In First Out
    PRIORITY = auto()   # Priority-based (lower value = higher priority)
    SJF = auto()        # Shortest Job First
    RR = auto()         # Round Robin
    EDF = auto()        # Earliest Deadline First


class RequestPriority(IntEnum):
    """Request priority levels (lower = more urgent)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


# ---------------------------------------------------------------------------
# QueueRequest
# ---------------------------------------------------------------------------

@dataclass
class QueueRequest:
    """
    Universal request envelope for all queue types.

    Fields marked 'internal' are managed by the queue; callers set the rest.
    """
    # --- caller-provided ---
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: RequestPriority = RequestPriority.NORMAL
    estimated_cost: float = 1.0          # abstract cost unit (tokens, bytes, ms)
    deadline: Optional[float] = None     # absolute monotonic time; None = no deadline
    timeout_sec: float = 30.0
    callback: Optional[Callable[["QueueRequest", Any], None]] = None
    agent_id: Optional[str] = None       # owning agent (for RR fairness)

    # --- internal ---
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: RequestState = RequestState.PENDING
    created_at: float = field(default_factory=time.monotonic)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0

    # RR bookkeeping
    remaining_quantum: float = 0.0

    def elapsed(self) -> float:
        """Wall-clock seconds since creation."""
        return time.monotonic() - self.created_at

    def wait_time(self) -> float:
        """Seconds spent waiting (before execution started)."""
        if self.started_at is not None:
            return self.started_at - self.created_at
        return self.elapsed()


# ---------------------------------------------------------------------------
# BaseQueue (abstract)
# ---------------------------------------------------------------------------

class BaseQueue(abc.ABC):
    """
    Abstract base for all AIOS resource queues.

    Subclasses implement _pick_next() which encodes the scheduling policy.
    The base class provides:
    - thread-safe enqueue / dequeue
    - EventBus integration (emit on enqueue, start, complete, fail)
    - stats collection
    """

    queue_kind: str = "base"  # override in subclass

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        max_concurrency: int = 4,
    ):
        self.bus = bus or get_event_bus()
        self.max_concurrency = max_concurrency

        self._pending: List[QueueRequest] = []
        self._running: Dict[str, QueueRequest] = {}
        self._completed: List[QueueRequest] = []
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrency)

        # stats
        self._total_enqueued = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_wait_ms = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, req: QueueRequest) -> str:
        """Add a request to the queue. Returns request id."""
        req.state = RequestState.QUEUED
        with self._lock:
            self._pending.append(req)
            self._total_enqueued += 1

        self._emit(f"queue.{self.queue_kind}.enqueued", req)
        return req.id

    def dequeue(self) -> Optional[QueueRequest]:
        """
        Pick the next request according to the scheduling policy.
        Returns None if the queue is empty.
        """
        with self._lock:
            if not self._pending:
                return None
            req = self._pick_next(self._pending)
            if req is None:
                return None
            self._pending.remove(req)
            req.state = RequestState.RUNNING
            req.started_at = time.monotonic()
            self._running[req.id] = req
            self._total_wait_ms += req.wait_time() * 1000

        self._emit(f"queue.{self.queue_kind}.started", req)
        return req

    def complete(self, req_id: str, result: Any = None) -> None:
        """Mark a request as successfully completed."""
        with self._lock:
            req = self._running.pop(req_id, None)
        if req is None:
            return
        req.state = RequestState.COMPLETED
        req.finished_at = time.monotonic()
        req.result = result
        self._completed.append(req)
        self._total_completed += 1
        self._emit(f"queue.{self.queue_kind}.completed", req)
        if req.callback:
            try:
                req.callback(req, result)
            except Exception:
                pass

    def fail(self, req_id: str, error: str) -> None:
        """Mark a request as failed."""
        with self._lock:
            req = self._running.pop(req_id, None)
        if req is None:
            return
        req.state = RequestState.FAILED
        req.finished_at = time.monotonic()
        req.error = error
        self._completed.append(req)
        self._total_failed += 1
        self._emit(f"queue.{self.queue_kind}.failed", req)

    def cancel(self, req_id: str) -> bool:
        """Cancel a pending request. Returns True if found and cancelled."""
        with self._lock:
            for i, req in enumerate(self._pending):
                if req.id == req_id:
                    req.state = RequestState.CANCELLED
                    self._pending.pop(i)
                    self._completed.append(req)
                    return True
        return False

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def stats(self) -> Dict[str, Any]:
        avg_wait = (
            self._total_wait_ms / self._total_completed
            if self._total_completed > 0
            else 0.0
        )
        return {
            "queue": self.queue_kind,
            "pending": self.pending_count(),
            "running": self.running_count(),
            "total_enqueued": self._total_enqueued,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "avg_wait_ms": round(avg_wait, 2),
            "max_concurrency": self.max_concurrency,
        }

    # ------------------------------------------------------------------
    # Abstract: scheduling policy
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _pick_next(self, pending: List[QueueRequest]) -> Optional[QueueRequest]:
        """
        Select the next request from the pending list.
        Called while holding self._lock.
        Must NOT modify the list (caller removes the chosen item).
        """
        ...

    # ------------------------------------------------------------------
    # EventBus helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, req: QueueRequest) -> None:
        try:
            self.bus.emit(create_event(
                event_type,
                source=f"queue.{self.queue_kind}",
                request_id=req.id,
                request_name=req.name,
                agent_id=req.agent_id or "",
                priority=int(req.priority),
                state=req.state.name,
            ))
        except Exception:
            pass  # never let bus errors break the queue

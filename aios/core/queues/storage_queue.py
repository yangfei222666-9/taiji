"""
AIOS Storage Queue - SJF / RR scheduling for storage I/O.

Features:
- SJF and RR scheduling (same as MemoryQueue)
- Batch coalescing: groups small requests into batches
- I/O priority: reads before writes (configurable)
- EventBus integration
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import (
    BaseQueue,
    QueueRequest,
    RequestPriority,
    RequestState,
    SchedulingPolicy,
)


# Batch settings
_DEFAULT_BATCH_SIZE = 10
_DEFAULT_BATCH_WINDOW_SEC = 0.5


class StorageQueue(BaseQueue):
    """
    Storage I/O queue with SJF/RR scheduling and batch coalescing.

    Requests with payload["op"] == "read" are prioritized over writes
    when reads_first=True (default).

    Batch coalescing: when multiple small requests target the same
    resource (payload["path"]), they can be grouped.
    """

    queue_kind = "storage"

    def __init__(
        self,
        bus=None,
        max_concurrency: int = 4,
        policy: SchedulingPolicy = SchedulingPolicy.SJF,
        reads_first: bool = True,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        batch_window_sec: float = _DEFAULT_BATCH_WINDOW_SEC,
    ):
        super().__init__(bus=bus, max_concurrency=max_concurrency)
        self._policy = policy
        self._reads_first = reads_first
        self._batch_size = batch_size
        self._batch_window_sec = batch_window_sec

        # RR state
        self._rr_agent_order: List[str] = []
        self._rr_index: int = 0

        # batch stats
        self._batches_created = 0

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    def set_policy(self, policy: SchedulingPolicy) -> None:
        if policy not in (SchedulingPolicy.SJF, SchedulingPolicy.RR):
            raise ValueError(f"StorageQueue supports SJF and RR, not {policy.name}")
        self._policy = policy

    @property
    def policy(self) -> SchedulingPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Batch coalescing
    # ------------------------------------------------------------------

    def try_batch(self) -> Optional[List[QueueRequest]]:
        """
        Try to coalesce pending requests into a batch.

        Returns a list of requests that can be executed together,
        or None if no batch is possible.

        Batching criteria:
        - Same operation type (read/write)
        - Same target path
        - Within batch window
        - Up to batch_size
        """
        with self._lock:
            if len(self._pending) < 2:
                return None

            now = time.monotonic()
            # Group by (op, path)
            groups: Dict[tuple, List[QueueRequest]] = {}
            for req in self._pending:
                op = req.payload.get("op", "unknown")
                path = req.payload.get("path", "")
                key = (op, path)
                if key not in groups:
                    groups[key] = []
                groups[key].append(req)

            # Find a group that qualifies for batching
            for key, reqs in groups.items():
                if len(reqs) < 2:
                    continue
                # Check if oldest request is within batch window
                oldest = min(reqs, key=lambda r: r.created_at)
                if now - oldest.created_at < self._batch_window_sec:
                    continue  # wait a bit more for accumulation

                batch = reqs[:self._batch_size]
                for req in batch:
                    req.state = RequestState.RUNNING
                    req.started_at = now
                    self._pending.remove(req)
                    self._running[req.id] = req

                self._batches_created += 1
                return batch

            return None

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def _pick_next(self, pending: List[QueueRequest]) -> Optional[QueueRequest]:
        if not pending:
            return None

        # Separate reads and writes
        if self._reads_first:
            reads = [r for r in pending if r.payload.get("op") == "read"]
            writes = [r for r in pending if r.payload.get("op") != "read"]
            pool = reads if reads else writes
        else:
            pool = pending

        if self._policy == SchedulingPolicy.SJF:
            return self._pick_sjf(pool)
        elif self._policy == SchedulingPolicy.RR:
            return self._pick_rr(pool)
        else:
            return pool[0]

    def _pick_sjf(self, pool: List[QueueRequest]) -> QueueRequest:
        return min(pool, key=lambda r: (r.estimated_cost, r.created_at))

    def _pick_rr(self, pool: List[QueueRequest]) -> Optional[QueueRequest]:
        agents = list(dict.fromkeys(
            r.agent_id or "__default__" for r in pool
        ))
        if not agents:
            return pool[0]

        for a in agents:
            if a not in self._rr_agent_order:
                self._rr_agent_order.append(a)
        self._rr_agent_order = [a for a in self._rr_agent_order if a in agents]
        if not self._rr_agent_order:
            return pool[0]

        self._rr_index = self._rr_index % len(self._rr_agent_order)
        current_agent = self._rr_agent_order[self._rr_index]

        agent_reqs = [
            r for r in pool
            if (r.agent_id or "__default__") == current_agent
        ]
        if not agent_reqs:
            self._rr_index = (self._rr_index + 1) % len(self._rr_agent_order)
            return pool[0]

        chosen = min(agent_reqs, key=lambda r: r.created_at)
        self._rr_index = (self._rr_index + 1) % len(self._rr_agent_order)
        return chosen

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        base = super().stats()
        base["policy"] = self._policy.name
        base["reads_first"] = self._reads_first
        base["batch_size"] = self._batch_size
        base["batches_created"] = self._batches_created
        return base

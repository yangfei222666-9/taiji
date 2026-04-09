"""
AIOS Memory Queue - SJF / RR / EDF scheduling for memory operations.

Features:
- Three scheduling algorithms, switchable at runtime
- SJF: Shortest Job First (by estimated_cost)
- RR:  Round Robin (fair share across agents, quantum-based)
- EDF: Earliest Deadline First (for time-critical operations)
- Aging: long-waiting requests get priority boost
- EventBus integration
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import (
    BaseQueue,
    QueueRequest,
    RequestState,
    SchedulingPolicy,
)


# Default RR quantum in abstract cost units
_DEFAULT_QUANTUM = 5.0
# Aging: after this many seconds, boost priority by 1 level
_AGING_THRESHOLD_SEC = 10.0


class MemoryQueue(BaseQueue):
    """
    Memory operation queue with pluggable scheduling.

    Supports SJF, RR, and EDF. Default is SJF.
    Switch at runtime via set_policy().
    """

    queue_kind = "memory"

    def __init__(
        self,
        bus=None,
        max_concurrency: int = 4,
        policy: SchedulingPolicy = SchedulingPolicy.SJF,
        rr_quantum: float = _DEFAULT_QUANTUM,
        enable_aging: bool = True,
    ):
        super().__init__(bus=bus, max_concurrency=max_concurrency)
        self._policy = policy
        self._rr_quantum = rr_quantum
        self._enable_aging = enable_aging

        # RR state: tracks last-served agent index for fairness
        self._rr_agent_order: List[str] = []
        self._rr_index: int = 0

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def set_policy(self, policy: SchedulingPolicy) -> None:
        """Switch scheduling policy at runtime."""
        if policy not in (SchedulingPolicy.SJF, SchedulingPolicy.RR, SchedulingPolicy.EDF):
            raise ValueError(f"MemoryQueue does not support {policy.name}")
        self._policy = policy

    @property
    def policy(self) -> SchedulingPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def _pick_next(self, pending: List[QueueRequest]) -> Optional[QueueRequest]:
        if not pending:
            return None

        # Apply aging boost
        if self._enable_aging:
            self._apply_aging(pending)

        if self._policy == SchedulingPolicy.SJF:
            return self._pick_sjf(pending)
        elif self._policy == SchedulingPolicy.RR:
            return self._pick_rr(pending)
        elif self._policy == SchedulingPolicy.EDF:
            return self._pick_edf(pending)
        else:
            # fallback FIFO
            return pending[0]

    # --- SJF ---
    def _pick_sjf(self, pending: List[QueueRequest]) -> QueueRequest:
        """Shortest Job First: pick request with smallest estimated_cost."""
        return min(pending, key=lambda r: (r.estimated_cost, r.created_at))

    # --- RR ---
    def _pick_rr(self, pending: List[QueueRequest]) -> Optional[QueueRequest]:
        """
        Round Robin across agents.

        Each agent gets a quantum of work. When an agent's quantum is
        exhausted, move to the next agent. Requests without agent_id
        are treated as a shared 'default' agent.
        """
        # Build agent set from pending
        agents = list(dict.fromkeys(
            r.agent_id or "__default__" for r in pending
        ))
        if not agents:
            return pending[0]

        # Sync agent order
        for a in agents:
            if a not in self._rr_agent_order:
                self._rr_agent_order.append(a)
        # Remove agents with no pending requests
        self._rr_agent_order = [
            a for a in self._rr_agent_order if a in agents
        ]
        if not self._rr_agent_order:
            return pending[0]

        # Wrap index
        self._rr_index = self._rr_index % len(self._rr_agent_order)
        current_agent = self._rr_agent_order[self._rr_index]

        # Find requests for current agent
        agent_reqs = [
            r for r in pending
            if (r.agent_id or "__default__") == current_agent
        ]
        if not agent_reqs:
            # Advance to next agent
            self._rr_index = (self._rr_index + 1) % len(self._rr_agent_order)
            return pending[0]

        # Pick first request for this agent (FIFO within agent)
        chosen = min(agent_reqs, key=lambda r: r.created_at)

        # Quantum tracking
        if chosen.remaining_quantum <= 0:
            chosen.remaining_quantum = self._rr_quantum

        # Advance to next agent for next call
        self._rr_index = (self._rr_index + 1) % len(self._rr_agent_order)

        return chosen

    # --- EDF ---
    def _pick_edf(self, pending: List[QueueRequest]) -> QueueRequest:
        """
        Earliest Deadline First: pick request with nearest deadline.
        Requests without deadline go last.
        """
        now = time.monotonic()
        with_deadline = [r for r in pending if r.deadline is not None]
        if with_deadline:
            return min(with_deadline, key=lambda r: r.deadline)
        # No deadlines — fall back to FIFO
        return min(pending, key=lambda r: r.created_at)

    # --- Aging ---
    def _apply_aging(self, pending: List[QueueRequest]) -> None:
        """Boost priority of long-waiting requests."""
        now = time.monotonic()
        for req in pending:
            wait = now - req.created_at
            if wait > _AGING_THRESHOLD_SEC and req.priority.value > 0:
                # Boost by 1 level for every aging threshold exceeded
                levels = int(wait / _AGING_THRESHOLD_SEC)
                new_val = max(0, req.priority.value - levels)
                from .base import RequestPriority
                req.priority = RequestPriority(new_val)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        base = super().stats()
        base["policy"] = self._policy.name
        base["rr_quantum"] = self._rr_quantum
        base["aging_enabled"] = self._enable_aging
        return base

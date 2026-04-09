"""
AIOS LLM Queue - FIFO + Priority scheduling for LLM API calls.

Features:
- FIFO within same priority level
- Priority preemption (CRITICAL > HIGH > NORMAL > LOW)
- Token budget awareness (estimated_cost = token count)
- Rate limiting (requests per second)
- EventBus integration
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from .base import (
    BaseQueue,
    QueueRequest,
    RequestPriority,
    RequestState,
    SchedulingPolicy,
)


class LLMQueue(BaseQueue):
    """
    LLM request queue with FIFO + priority scheduling.

    Scheduling: requests are grouped by priority; within each group, FIFO.
    Higher priority (lower numeric value) always goes first.

    Optional rate limiting: max N requests per second.
    """

    queue_kind = "llm"

    def __init__(
        self,
        bus=None,
        max_concurrency: int = 4,
        rate_limit_rps: Optional[float] = None,
        token_budget_per_min: Optional[int] = None,
    ):
        super().__init__(bus=bus, max_concurrency=max_concurrency)
        self.rate_limit_rps = rate_limit_rps
        self.token_budget_per_min = token_budget_per_min

        # rate limiter state
        self._last_dequeue_time: float = 0.0
        self._tokens_used_window: List[tuple] = []  # (timestamp, tokens)
        self._rate_lock = threading.Lock()

        # stats
        self._total_tokens = 0

    # ------------------------------------------------------------------
    # Scheduling: Priority + FIFO
    # ------------------------------------------------------------------

    def _pick_next(self, pending: List[QueueRequest]) -> Optional[QueueRequest]:
        """Pick highest priority request; FIFO within same priority."""
        if not pending:
            return None

        # Rate limit check
        if not self._check_rate_limit():
            return None

        # Token budget check
        if not self._check_token_budget(pending):
            # Try to find a smaller request that fits
            pass  # fall through to normal selection

        # Sort by (priority, created_at) — stable sort preserves FIFO
        best = min(pending, key=lambda r: (int(r.priority), r.created_at))
        return best

    def _check_rate_limit(self) -> bool:
        """Returns True if we're within rate limits."""
        if self.rate_limit_rps is None:
            return True
        with self._rate_lock:
            now = time.monotonic()
            min_interval = 1.0 / self.rate_limit_rps
            if now - self._last_dequeue_time < min_interval:
                return False
            self._last_dequeue_time = now
            return True

    def _check_token_budget(self, pending: List[QueueRequest]) -> bool:
        """Returns True if token budget allows more requests."""
        if self.token_budget_per_min is None:
            return True
        now = time.monotonic()
        with self._rate_lock:
            # Prune old entries (older than 60s)
            self._tokens_used_window = [
                (t, tokens) for t, tokens in self._tokens_used_window
                if now - t < 60.0
            ]
            used = sum(tokens for _, tokens in self._tokens_used_window)
            return used < self.token_budget_per_min

    # ------------------------------------------------------------------
    # Override complete to track tokens
    # ------------------------------------------------------------------

    def complete(self, req_id: str, result: Any = None, tokens_used: int = 0) -> None:
        """Complete with optional token tracking."""
        if tokens_used > 0:
            with self._rate_lock:
                self._tokens_used_window.append((time.monotonic(), tokens_used))
                self._total_tokens += tokens_used
        super().complete(req_id, result)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        base = super().stats()
        base["total_tokens"] = self._total_tokens
        base["rate_limit_rps"] = self.rate_limit_rps
        base["token_budget_per_min"] = self.token_budget_per_min
        return base

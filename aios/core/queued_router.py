"""
AIOS Queued Model Router - LLMQueue + ModelRouter integration.

Wraps model_router_v2.route_model() with LLMQueue for:
- Priority-based queuing (CRITICAL/HIGH/NORMAL/LOW)
- Rate limiting (requests per second)
- Token budget tracking
- Concurrency control
- Full EventBus observability

Usage (drop-in replacement for route_model):
    from core.queued_router import queued_route_model

    result = queued_route_model(
        task_type="reasoning",
        prompt="...",
        priority="high",       # optional, default "normal"
        agent_id="coder-001",  # optional, for stats
    )
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Literal, Optional

import sys
from pathlib import Path

AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.queues.base import QueueRequest, RequestPriority
from core.queues.llm_queue import LLMQueue
from core.model_router_v2 import route_model as _raw_route_model
from core.event_bus import get_event_bus

# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

_PRIORITY_MAP = {
    "critical": RequestPriority.CRITICAL,
    "high": RequestPriority.HIGH,
    "normal": RequestPriority.NORMAL,
    "low": RequestPriority.LOW,
}

# Task type → default priority
_TASK_PRIORITY = {
    "reasoning": RequestPriority.HIGH,
    "code_generation": RequestPriority.HIGH,
    "summarize_short": RequestPriority.NORMAL,
    "simple_qa": RequestPriority.LOW,
}


# ---------------------------------------------------------------------------
# Global queued router
# ---------------------------------------------------------------------------

class QueuedRouter:
    """
    Wraps ModelRouter with LLMQueue for queuing and rate limiting.

    All calls go through the queue. The router processes them
    one at a time (or up to max_concurrency).
    """

    def __init__(
        self,
        max_concurrency: int = 4,
        rate_limit_rps: Optional[float] = None,
        token_budget_per_min: Optional[int] = None,
    ):
        self._queue = LLMQueue(
            bus=get_event_bus(),
            max_concurrency=max_concurrency,
            rate_limit_rps=rate_limit_rps,
            token_budget_per_min=token_budget_per_min,
        )
        self._worker_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._results: Dict[str, Dict[str, Any]] = {}
        self._result_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """Start the background worker that processes queued requests."""
        if self._started:
            return
        self._started = True
        self._stop.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="queued-router-worker",
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        self._started = False

    def route(
        self,
        task_type: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        force_model: Optional[Literal["ollama", "claude"]] = None,
        priority: str = "normal",
        agent_id: Optional[str] = None,
        timeout_sec: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Queue a model call and wait for the result.

        Args:
            task_type: Task type for routing
            prompt: The prompt
            context: Optional context
            force_model: Force a specific provider
            priority: "critical" / "high" / "normal" / "low"
            agent_id: Owning agent ID
            timeout_sec: Max wait time

        Returns:
            Same dict as route_model() + queue metadata
        """
        if not self._started:
            self.start()

        # Resolve priority
        req_priority = _PRIORITY_MAP.get(
            priority.lower(),
            _TASK_PRIORITY.get(task_type, RequestPriority.NORMAL),
        )

        # Estimate token cost from prompt length
        estimated_tokens = max(1, len(prompt) // 4)

        # Create request
        req = QueueRequest(
            name=f"llm_{task_type}",
            payload={
                "task_type": task_type,
                "prompt": prompt,
                "context": context,
                "force_model": force_model,
            },
            priority=req_priority,
            estimated_cost=estimated_tokens,
            agent_id=agent_id,
            timeout_sec=timeout_sec,
        )

        # Prepare result event
        event = threading.Event()
        with self._lock:
            self._result_events[req.id] = event

        # Enqueue
        self._queue.enqueue(req)

        # Wait for result
        if not event.wait(timeout=timeout_sec):
            # Timeout
            self._queue.cancel(req.id)
            with self._lock:
                self._result_events.pop(req.id, None)
                self._results.pop(req.id, None)
            return {
                "provider": "none",
                "model": "none",
                "response": None,
                "success": False,
                "reason": "queue_timeout",
                "estimated_cost": 0.0,
                "latency_ms": int(timeout_sec * 1000),
                "queue_wait_ms": int(timeout_sec * 1000),
            }

        # Get result
        with self._lock:
            result = self._results.pop(req.id, {})
            self._result_events.pop(req.id, None)

        return result

    def stats(self) -> Dict[str, Any]:
        return self._queue.stats()

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            req = self._queue.dequeue()
            if req is None:
                self._stop.wait(timeout=0.05)
                continue

            # Execute the actual LLM call
            t = threading.Thread(
                target=self._execute_request,
                args=(req,),
                daemon=True,
            )
            t.start()

    def _execute_request(self, req: QueueRequest) -> None:
        queue_wait_ms = int(req.wait_time() * 1000)
        start = time.monotonic()

        try:
            payload = req.payload
            result = _raw_route_model(
                task_type=payload["task_type"],
                prompt=payload["prompt"],
                context=payload.get("context"),
                force_model=payload.get("force_model"),
            )

            # Add queue metadata
            result["queue_wait_ms"] = queue_wait_ms
            result["queue_request_id"] = req.id
            result["queue_agent_id"] = req.agent_id

            # Track tokens
            tokens = result.get("tokens_used", int(req.estimated_cost))
            self._queue.complete(req.id, result=result, tokens_used=tokens)

            # Signal the waiting caller
            with self._lock:
                self._results[req.id] = result
                event = self._result_events.get(req.id)
            if event:
                event.set()

        except Exception as e:
            error_result = {
                "provider": "none",
                "model": "none",
                "response": None,
                "success": False,
                "reason": f"execution_error: {e}",
                "estimated_cost": 0.0,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "queue_wait_ms": queue_wait_ms,
                "queue_request_id": req.id,
            }
            self._queue.fail(req.id, str(e))

            with self._lock:
                self._results[req.id] = error_result
                event = self._result_events.get(req.id)
            if event:
                event.set()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_queued_router: Optional[QueuedRouter] = None


def get_queued_router(
    max_concurrency: int = 4,
    rate_limit_rps: Optional[float] = None,
    token_budget_per_min: Optional[int] = None,
) -> QueuedRouter:
    """Get or create the global QueuedRouter."""
    global _queued_router
    if _queued_router is None:
        _queued_router = QueuedRouter(
            max_concurrency=max_concurrency,
            rate_limit_rps=rate_limit_rps,
            token_budget_per_min=token_budget_per_min,
        )
    return _queued_router


def queued_route_model(
    task_type: str,
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    force_model: Optional[Literal["ollama", "claude"]] = None,
    priority: str = "normal",
    agent_id: Optional[str] = None,
    timeout_sec: float = 60.0,
) -> Dict[str, Any]:
    """
    Drop-in replacement for route_model() with queuing.

    Same interface + extra kwargs (priority, agent_id, timeout_sec).
    """
    router = get_queued_router()
    return router.route(
        task_type=task_type,
        prompt=prompt,
        context=context,
        force_model=force_model,
        priority=priority,
        agent_id=agent_id,
        timeout_sec=timeout_sec,
    )

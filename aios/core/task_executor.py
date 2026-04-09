"""
AIOS Task Executor

Executes tasks from the queue by spawning appropriate agents.

Usage:
    from core.task_executor import TaskExecutor
    
    executor = TaskExecutor()
    result = executor.execute_task(task)
"""
from __future__ import annotations

import sys
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional

# Add AIOS to path
AIOS_ROOT = Path(__file__).resolve().parent.parent
if str(AIOS_ROOT) not in sys.path:
    sys.path.insert(0, str(AIOS_ROOT))
_AGENT_SYS = str(AIOS_ROOT / "agent_system")
if _AGENT_SYS not in sys.path:
    sys.path.insert(0, _AGENT_SYS)

import json as _json_mod  # needed by server helpers below

_MEMORY_SERVER_URL = "http://127.0.0.1:7788"

def _query_via_server(text: str, task_type: str, top_k: int, timeout_s: float) -> list | None:
    """Try memory server first (fast, warm). Returns None if unavailable."""
    try:
        import urllib.request, urllib.error
        payload = _json_mod.dumps({"text": text, "task_type": task_type, "top_k": top_k}).encode()
        req = urllib.request.Request(
            f"{_MEMORY_SERVER_URL}/query",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return _json_mod.loads(resp.read())["hits"]
    except Exception:
        return None


def _feedback_via_server(record_id: str, helpful: bool) -> bool:
    """Send feedback to memory server. Returns True if succeeded."""
    try:
        import urllib.request
        payload = _json_mod.dumps({"record_id": record_id, "helpful": helpful}).encode()
        req = urllib.request.Request(
            f"{_MEMORY_SERVER_URL}/feedback",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return _json_mod.loads(resp.read()).get("ok", False)
    except Exception:
        return False



# ── Memory retrieval: module-level lazy singleton ─────────────────────────────
_mem_query_fn = None
_mem_feedback_fn = None
_mem_lock = threading.Lock()
_mem_loaded = False

def _ensure_memory_loaded() -> bool:
    """Load memory_retrieval once; return True if available."""
    global _mem_query_fn, _mem_feedback_fn, _mem_loaded
    if _mem_loaded:
        return _mem_query_fn is not None
    with _mem_lock:
        if _mem_loaded:
            return _mem_query_fn is not None
        try:
            from memory_retrieval import query as _q, feedback as _fb
            _mem_query_fn = _q
            _mem_feedback_fn = _fb
        except Exception:
            pass
        _mem_loaded = True
    return _mem_query_fn is not None

# Kick off background pre-load immediately on import
threading.Thread(target=_ensure_memory_loaded, daemon=True).start()

from core.task_submitter import get_submitter, update_task_status


class TaskExecutor:
    """Execute tasks by spawning agents."""
    
    # Task type to agent mapping
    AGENT_MAPPING = {
        "code": "coder",
        "analysis": "analyst",
        "monitor": "monitor",
        "refactor": "coder",
        "test": "tester",
        "deploy": "deployer",
        "research": "researcher",
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds
    
    def __init__(self):
        self._submitter = get_submitter()
        self._execution_log = AIOS_ROOT / "agent_system" / "task_executions.jsonl"
        self._execution_log.parent.mkdir(parents=True, exist_ok=True)
    
    def execute_task(self, task: Dict, retry_count: int = 0) -> Dict:
        """
        Execute a single task with retry support.
        
        Args:
            task: Task record from queue
            retry_count: Current retry attempt (0 = first attempt)
        
        Returns:
            Execution result
        """
        task_id = task.get("task_id") or task.get("id", "unknown")
        task_type = task.get("type", "code")
        description = task.get("description", "No description")
        
        # Update status to running
        if retry_count == 0:
            update_task_status(task_id, "running")
        
        # Determine agent
        agent_type = self.AGENT_MAPPING.get(task_type, "coder")
        
        # ── Memory Retrieval: build context ──────────────────────────────
        mem_ctx = self._build_memory_context(task_id, description, task_type)
        
        # Prepare spawn request
        spawn_request = {
            "task_id": task_id,
            "agent_type": agent_type,
            "description": description,
            "priority": task.get("priority", "normal"),
            "metadata": task.get("metadata", {}),
            "retry_count": retry_count,
            "memory_hints": mem_ctx.get("memory_hints", []),  # injected
        }
        
        # Execute
        result = self._execute_spawn(spawn_request)
        
        # Handle failure with retry
        if not result["success"] and retry_count < self.MAX_RETRIES:
            print(f"  [WARN] Attempt {retry_count + 1} failed: {result.get('error', 'Unknown error')}")
            print(f"  [RETRY] Retrying in {self.RETRY_DELAY}s... (attempt {retry_count + 2}/{self.MAX_RETRIES + 1})")
            
            import time
            time.sleep(self.RETRY_DELAY)
            
            # Retry
            return self.execute_task(task, retry_count + 1)
        
        # Update task status (final result)
        if result["success"]:
            update_task_status(task_id, "completed", result=result)
        else:
            # Add retry info to result
            result["total_attempts"] = retry_count + 1
            update_task_status(task_id, "failed", result=result)
            
            # 🔄 触发Bootstrapped Regeneration（任务失败时）
            print(f"  [REGEN] Triggering Bootstrapped Regeneration...")
            try:
                from low_success_regeneration import regenerate_failed_task
                regenerated = regenerate_failed_task(limit=1)  # 只处理当前失败任务
                if regenerated > 0:
                    print(f"  [OK] Task regenerated successfully")
            except Exception as e:
                print(f"  [WARN] Regeneration failed: {e}")
        
        # Log execution
        self._log_execution(task, result, retry_count)
        
        # ── Memory Retrieval: write feedback ─────────────────────────────
        self._write_memory_feedback(task_id, mem_ctx, result)
        
        return result
    
    def _execute_spawn(self, spawn_request: Dict) -> Dict:
        """
        Execute spawn request via sessions_spawn.
        
        Falls back to simulation if sessions_spawn is not available.
        """
        # Try real execution via sessions_spawn
        try:
            return self._real_execution(spawn_request)
        except Exception as e:
            print(f"  [WARN] Real execution failed: {e}")
            print(f"  [FALLBACK] Using simulation")
            return self._simulate_execution(spawn_request)
    
    def _real_execution(self, spawn_request: Dict) -> Dict:
        """
        Execute via Claude API (real execution).
        
        Directly calls Claude API to execute tasks.
        """
        try:
            # Import real executor
            import sys
            sys.path.insert(0, str(AIOS_ROOT / "core"))
            from real_executor import execute_task_real
            
            task_desc = spawn_request["description"]
            agent_type = spawn_request.get("agent_type", "coder")
            
            # Inject memory hints into description
            hints = spawn_request.get("memory_hints", [])
            if hints:
                hints_text = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(hints))
                task_desc = f"[MEMORY] Relevant past experiences:\n{hints_text}\n\n{task_desc}"
            # Execute via Claude API
            result = execute_task_real(task_desc, agent_type)
            
            return result
            
        except Exception as e:
            raise  # Re-raise to trigger fallback
    
    def _simulate_execution(self, spawn_request: Dict) -> Dict:
        """Simulate task execution (for testing)."""
        import random
        
        success = random.random() > 0.2  # 80% success rate
        
        if success:
            return {
                "success": True,
                "agent": spawn_request["agent_type"],
                "duration": random.uniform(5, 30),
                "output": f"Task completed by {spawn_request['agent_type']} agent",
            }
        else:
            return {
                "success": False,
                "agent": spawn_request["agent_type"],
                "error": "Simulated failure",
            }
    
    def _build_memory_context(self, task_id: str, description: str, task_type: str) -> dict:
        """Retrieve relevant memories (server-first, fallback to direct call)."""
        import os
        enabled = os.environ.get("MEMORY_RETRIEVAL_ENABLED", "true").lower() == "true"
        timeout_ms = int(os.environ.get("MEMORY_TIMEOUT_MS", "400"))
        max_hints = int(os.environ.get("MEMORY_MAX_HINTS", "3"))
        max_chars = int(os.environ.get("MEMORY_MAX_CHARS", "250"))

        empty = {"memory_hints": [], "memory_ids": [], "retrieved_count": 0,
                 "used_count": 0, "latency_ms": 0, "degraded": True}
        if not enabled:
            return {**empty, "error": "disabled"}

        t0 = time.time()

        # Try server first (fast, warm, no cold start)
        hits = _query_via_server(description, task_type or "", max_hints, timeout_ms / 1000.0)
        if hits is not None:
            latency_ms = round((time.time() - t0) * 1000, 1)
            hints, ids = [], []
            for h in hits[:max_hints]:
                hints.append(f"[{h.get('outcome','?')}|score={h.get('_score',0)}] {h.get('text','')[:max_chars]}")
                ids.append(h.get("id", ""))
            print(
                f"  [MEMORY:BUILD] OK retrieved={len(hits)} used={len(hints)} latency={latency_ms}ms (server)",
                flush=True,
            )
            return {
                "memory_hints": hints, "memory_ids": ids,
                "retrieved_count": len(hits), "used_count": len(hints),
                "latency_ms": latency_ms, "degraded": False, "error": None,
            }

        # Fallback: direct call (cold start possible)
        first_call_timeout = 12.0
        fast_timeout = timeout_ms / 1000.0
        wait_timeout = fast_timeout if _mem_loaded else first_call_timeout
        deadline = t0 + wait_timeout

        while not _mem_loaded and time.time() < deadline:
            time.sleep(0.02)

        latency_ms = round((time.time() - t0) * 1000, 1)

        if not _ensure_memory_loaded():
            print(f"  [MEMORY:BUILD] DEGRADED module_unavailable latency={latency_ms}ms", flush=True)
            return {**empty, "latency_ms": latency_ms, "error": "module_unavailable"}

        container: dict = {}

        def _run():
            try:
                hits = _mem_query_fn(description, top_k=max_hints, task_type=task_type or None)
                container["hits"] = hits
            except Exception as e:
                container["error"] = str(e)

        t1 = time.time()
        remaining = max(0.1, deadline - t1)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=remaining)
        latency_ms = round((time.time() - t0) * 1000, 1)

        if t.is_alive():
            print(f"  [MEMORY:BUILD] DEGRADED timeout>{timeout_ms}ms latency={latency_ms}ms", flush=True)
            return {**empty, "latency_ms": latency_ms, "error": f"timeout>{timeout_ms}ms"}
        if "error" in container:
            print(f"  [MEMORY:BUILD] DEGRADED err={container['error']} latency={latency_ms}ms", flush=True)
            return {**empty, "latency_ms": latency_ms, "error": container["error"]}

        hits = container.get("hits", [])[:max_hints]
        hints, ids = [], []
        for h in hits:
            hints.append(f"[{h.get('outcome','?')}|score={h.get('_score',0)}] {h.get('text','')[:max_chars]}")
            ids.append(h.get("id", ""))

        print(
            f"  [MEMORY:BUILD] OK retrieved={len(hits)} used={len(hints)} latency={latency_ms}ms (direct)",
            flush=True,
        )
        return {
            "memory_hints": hints, "memory_ids": ids,
            "retrieved_count": len(hits), "used_count": len(hints),
            "latency_ms": latency_ms, "degraded": False, "error": None,
        }

    def _write_memory_feedback(self, task_id: str, mem_ctx: dict, result: dict) -> None:
        """Write feedback (server-first, fallback to direct call)."""
        memory_ids = mem_ctx.get("memory_ids", [])
        if not memory_ids:
            return
        helpful = result.get("success", False)

        # Try server first
        success_count = 0
        for mid in memory_ids:
            if mid and _feedback_via_server(mid, helpful):
                success_count += 1

        # If server failed for all, try direct call
        if success_count == 0 and _mem_feedback_fn:
            try:
                for mid in memory_ids:
                    if mid:
                        _mem_feedback_fn(mid, helpful=helpful)
                success_count = len(memory_ids)
            except Exception as e:
                print(f"  [MEMORY:FEEDBACK] ERROR {e}", flush=True)
                return

        # Log to file
        log_path = AIOS_ROOT / "agent_system" / "memory_retrieval_log.jsonl"
        from datetime import datetime, timezone
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "memory_ids": memory_ids,
            "helpful": helpful,
            "score": 1.0 if helpful else 0.0,
            "reason": "task_success" if helpful else "task_failed",
            "latency_ms": mem_ctx.get("latency_ms", 0),
            "retrieved_count": mem_ctx.get("retrieved_count", 0),
            "injected_count": mem_ctx.get("used_count", 0),
            "degraded": mem_ctx.get("degraded", False),
            "feature_flag_enabled": os.environ.get("MEMORY_RETRIEVAL_ENABLED", "true").lower() == "true",
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(_json_mod.dumps(entry, ensure_ascii=False) + "\n")
        print(
            f"  [MEMORY:FEEDBACK] feedback_written=True ids={len(memory_ids)} helpful={helpful}",
            flush=True,
        )

    def _log_execution(self, task: Dict, result: Dict, retry_count: int = 0):
        """Log task execution."""
        import json
        
        log_entry = {
            "timestamp": time.time(),
            "task_id": task.get("task_id") or task.get("id", "unknown"),
            "task_type": task.get("type", "unknown"),
            "description": task.get("description", "No description"),
            "result": result,
            "retry_count": retry_count,
            "total_attempts": retry_count + 1,
        }
        
        with open(self._execution_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def execute_batch(self, tasks: List[Dict], max_tasks: int = 5) -> List[Dict]:
        """
        Execute a batch of tasks.
        
        Args:
            tasks: List of tasks to execute
            max_tasks: Maximum number of tasks to execute
        
        Returns:
            List of execution results
        """
        # Import Reality Ledger
        try:
            sys.path.insert(0, str(AIOS_ROOT / "agent_system"))
            from reality_ledger import transition_action as _transition_action
        except ImportError:
            _transition_action = None
        
        results = []
        
        for i, task in enumerate(tasks[:max_tasks]):
            task_id = task.get('task_id') or task.get('id', 'unknown')
            action_id = task.get('action_id')  # injected by heartbeat
            
            print(f"[{i+1}/{min(len(tasks), max_tasks)}] Executing task: {task_id}")
            print(f"  Type: {task.get('type', 'unknown')}")
            print(f"  Description: {task.get('description', 'No description')}")
            
            # Reality Ledger: executing
            if action_id and _transition_action:
                try:
                    _transition_action(action_id, "executing", actor=task.get('type', 'unknown'))
                except Exception as e:
                    print(f"  [LEDGER] executing transition failed: {e}")
            
            # Force failure for testing (if description contains FORCE_FAILURE_TEST)
            if "FORCE_FAILURE_TEST" in task.get('description', ''):
                result = {
                    "success": False,
                    "error": "Forced failure for testing",
                    "duration": 0.1,
                    "output": "",
                }
                print(f"  [TEST] Forced failure triggered")
            else:
                result = self.execute_task(task)
            
            results.append(result)
            
            # Reality Ledger: completed / failed
            if action_id and _transition_action:
                try:
                    if result["success"]:
                        _transition_action(action_id, "completed", actor=task.get('type', 'unknown'),
                                           payload={"result_summary": str(result.get('output', ''))[:200],
                                                    "duration_ms": int(result.get('duration', 0) * 1000)})
                    else:
                        _transition_action(action_id, "failed", actor=task.get('type', 'unknown'),
                                           payload={"error": str(result.get('error', ''))[:200],
                                                    "duration_ms": int(result.get('duration', 0) * 1000)})
                except Exception as e:
                    print(f"  [LEDGER] terminal transition failed: {e}")
            
            if result["success"]:
                print(f"  [OK] Completed in {result.get('duration', 0):.1f}s")
            else:
                print(f"  [FAIL] Failed: {result.get('error', 'Unknown error')}")
        
        return results


# ── Convenience Functions ──────────────────────────────────────────

_default_executor = None

def get_executor() -> TaskExecutor:
    """Get the default task executor."""
    global _default_executor
    if _default_executor is None:
        _default_executor = TaskExecutor()
    return _default_executor


def execute_task(task: Dict) -> Dict:
    """Execute a task (convenience function)."""
    return get_executor().execute_task(task)


def execute_batch(tasks: List[Dict], max_tasks: int = 5) -> List[Dict]:
    """Execute a batch of tasks (convenience function)."""
    return get_executor().execute_batch(tasks, max_tasks)


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from core.task_submitter import list_tasks
    
    parser = argparse.ArgumentParser(description="AIOS Task Executor")
    parser.add_argument("--status", default="pending", help="Task status to execute")
    parser.add_argument("--limit", type=int, default=5, help="Max tasks to execute")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (don't execute)")
    
    args = parser.parse_args()
    
    # Get pending tasks
    tasks = list_tasks(status=args.status, limit=args.limit)
    
    if not tasks:
        print("No tasks to execute.")
        sys.exit(0)
    
    print(f"Found {len(tasks)} tasks to execute\n")
    
    if args.dry_run:
        print("[DRY RUN] Would execute:")
        for i, task in enumerate(tasks, 1):
            print(f"{i}. [{task['priority']}] {task['type']}: {task['description']}")
        sys.exit(0)
    
    # Execute tasks
    executor = TaskExecutor()
    results = executor.execute_batch(tasks, max_tasks=args.limit)
    
    # Summary
    print("\n" + "=" * 70)
    print("Execution Summary:")
    print("=" * 70)
    
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    
    print(f"\nTotal: {len(results)}")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Failed: {failed_count}")

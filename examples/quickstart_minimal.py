#!/usr/bin/env python3
"""
TaijiOS Quickstart — 3 minutes, no Ollama required.

This demo shows the core TaijiOS loop:
  1. A task enters the system
  2. A pipeline processes it (with self-healing retry)
  3. Evidence and trace are generated

Run:
    pip install -e .
    python examples/quickstart_minimal.py
"""
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

OUTPUT_DIR = Path(__file__).parent / "quickstart_output"


# ── 1. Event Bus (simplified core) ─────────────────────────────

class EventBus:
    """Minimal event bus — publish/subscribe."""
    def __init__(self):
        self._subs: Dict[str, list] = {}
        self.log: List[Dict] = []

    def subscribe(self, event_type: str, handler):
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, data: dict):
        entry = {"ts": time.time(), "type": event_type, "data": data}
        self.log.append(entry)
        for handler in self._subs.get(event_type, []):
            handler(data)
        for handler in self._subs.get("*", []):
            handler(data)


# ── 2. Task Queue (from aios/agent_system) ─────────────────────

@dataclass
class Task:
    task_id: str
    payload: Dict[str, Any]
    status: str = "queued"  # queued → running → succeeded | failed
    attempts: int = 0
    max_retries: int = 2


# ── 3. Validator (mock — no Ollama needed) ─────────────────────

def validate(data: dict, attempt: int) -> dict:
    """Mock validator. Fails on first attempt, passes on retry (self-healing demo)."""
    score = 0.35 + (attempt - 1) * 0.55  # attempt 1: 0.35, attempt 2: 0.90
    passed = score >= 0.80
    failed_checks = []
    if not passed:
        failed_checks = ["style_consistency", "character_consistency"]
    return {
        "score": round(score, 4),
        "passed": passed,
        "failed_checks": failed_checks,
        "reason_code": "OK" if passed else "coherent.validator.style_consistency",
    }


# ── 4. Guidance from failures (self-healing) ──────────────────

def guidance_from_failures(failed_checks: list) -> dict:
    """Turn failures into guidance for next attempt."""
    guidance = {}
    if "style_consistency" in failed_checks:
        guidance["stable_style"] = True
    if "character_consistency" in failed_checks:
        guidance["stable_character"] = True
    return guidance


# ── 5. Run Trace (evidence) ────────────────────────────────────

@dataclass
class RunStep:
    name: str
    status: str = "pending"
    started_at: float = 0.0
    ended_at: float = 0.0
    output: Optional[Dict] = None
    error: Optional[Dict] = None

@dataclass
class RunTrace:
    task_id: str
    status: str = "running"
    steps: List[RunStep] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0

    def add_step(self, name: str) -> RunStep:
        step = RunStep(name=name, started_at=time.time())
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "steps": [asdict(s) for s in self.steps],
        }


# ── 6. The Pipeline ───────────────────────────────────────────

def run_pipeline(task: Task, bus: EventBus) -> dict:
    """
    Core TaijiOS pipeline:
      generate → validate → (fail? → guidance → retry) → deliver → evidence
    """
    trace = RunTrace(task_id=task.task_id, started_at=time.time())
    bus.publish("task.started", {"task_id": task.task_id})

    guidance = {}
    last_scores = None

    for attempt in range(1, task.max_retries + 1):
        task.attempts = attempt
        rev = attempt

        # Generate step
        step_gen = trace.add_step(f"generate:rev{rev}")
        step_gen.status = "running"
        content_hash = hashlib.sha256(
            f"{task.task_id}:rev{rev}:{json.dumps(guidance)}".encode()
        ).hexdigest()[:16]
        step_gen.output = {"revision": rev, "guidance": guidance, "content_hash": content_hash}
        step_gen.status = "completed"
        step_gen.ended_at = time.time()

        bus.publish("step.completed", {"step": f"generate:rev{rev}", "task_id": task.task_id})

        # Validate step
        step_val = trace.add_step(f"validate:rev{rev}")
        step_val.status = "running"
        scores = validate(task.payload, attempt)
        last_scores = scores
        step_val.output = scores
        step_val.ended_at = time.time()

        if scores["passed"]:
            step_val.status = "completed"
            bus.publish("validation.passed", {"task_id": task.task_id, "score": scores["score"], "rev": rev})
            break
        else:
            step_val.status = "failed"
            step_val.error = {"failed_checks": scores["failed_checks"], "reason_code": scores["reason_code"]}
            bus.publish("validation.failed", {
                "task_id": task.task_id, "score": scores["score"],
                "failed_checks": scores["failed_checks"], "rev": rev,
            })
            guidance = guidance_from_failures(scores["failed_checks"])

    # Deliver step
    step_del = trace.add_step("deliver")
    step_del.status = "running"
    passed = last_scores and last_scores["passed"]

    if passed:
        task.status = "succeeded"
        trace.status = "succeeded"
        step_del.output = {"delivered": True, "final_score": last_scores["score"]}
        step_del.status = "completed"
        bus.publish("task.delivered", {"task_id": task.task_id, "score": last_scores["score"]})
    else:
        task.status = "failed"
        trace.status = "failed"
        step_del.output = {"delivered": False, "reason": "max_retries_exhausted"}
        step_del.status = "failed"
        bus.publish("task.dlq", {"task_id": task.task_id, "reason_code": last_scores.get("reason_code", "")})

    step_del.ended_at = time.time()
    trace.ended_at = time.time()

    return {
        "task_id": task.task_id,
        "status": task.status,
        "attempts": task.attempts,
        "final_score": last_scores["score"] if last_scores else 0,
        "self_healed": task.attempts > 1 and passed,
        "trace": trace.to_dict(),
    }


# ── 7. Main ───────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  TaijiOS Quickstart — No Ollama Required")
    print("=" * 60)

    # Setup
    bus = EventBus()
    bus.subscribe("*", lambda d: None)  # catch-all

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create 3 tasks
    tasks = [
        Task(task_id=f"quickstart-{i:03d}", payload={"job_id": f"demo-{i:03d}"})
        for i in range(1, 4)
    ]

    results = []
    for task in tasks:
        print(f"\n--- Task: {task.task_id} ---")
        result = run_pipeline(task, bus)
        results.append(result)

        healed = "YES (self-healed)" if result["self_healed"] else "no"
        print(f"  Status: {result['status']}")
        print(f"  Attempts: {result['attempts']}")
        print(f"  Final score: {result['final_score']}")
        print(f"  Self-healed: {healed}")

    # Write evidence
    evidence = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_tasks": len(results),
        "succeeded": sum(1 for r in results if r["status"] == "succeeded"),
        "self_healed": sum(1 for r in results if r["self_healed"]),
        "results": results,
        "event_log_count": len(bus.log),
    }

    evidence_path = OUTPUT_DIR / "quickstart_evidence.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    trace_path = OUTPUT_DIR / "quickstart_trace.json"
    trace_path.write_text(
        json.dumps([r["trace"] for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    event_log_path = OUTPUT_DIR / "quickstart_events.json"
    event_log_path.write_text(json.dumps(bus.log, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"  Results: {evidence['succeeded']}/{evidence['total_tasks']} succeeded")
    print(f"  Self-healed: {evidence['self_healed']}/{evidence['total_tasks']}")
    print(f"  Events logged: {evidence['event_log_count']}")
    print(f"\n  Evidence:   {evidence_path}")
    print(f"  Traces:     {trace_path}")
    print(f"  Event log:  {event_log_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

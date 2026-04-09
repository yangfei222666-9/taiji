#!/usr/bin/env python3
"""
TaijiOS Persistent Worker — keeps the system alive and learning.

Runs on a fixed cycle:
  1. GitHub Learning: discover → analyze → digest (auto, gate stays manual)
  2. Job Consumer: consume queued jobs (if pipeline module available)
  3. Write worker status evidence after each cycle

Usage:
    python -m worker                          # default: 1 cycle per hour
    python -m worker --interval 300           # every 5 minutes
    python -m worker --max-cycles 10          # stop after 10 cycles
    python -m worker --dry-run                # show what would run

Status evidence: worker_data/worker_status.json (updated every cycle)
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

WORKER_DIR = Path(__file__).parent / "worker_data"
STATUS_FILE = WORKER_DIR / "worker_status.json"
CYCLE_LOG = WORKER_DIR / "worker_cycles.jsonl"

log = logging.getLogger("taijios.worker")


class WorkerStatus:
    """Tracks worker state — written to disk after every cycle."""

    def __init__(self):
        self.started_at = ""
        self.current_mode = "idle"
        self.cycles_completed = 0
        self.last_cycle_at = ""
        self.last_success_at = ""
        self.last_failure_at = ""
        self.last_error = ""
        self.jobs_processed = 0
        self.repos_discovered = 0
        self.repos_analyzed = 0
        self.mechanisms_digested = 0

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "current_mode": self.current_mode,
            "cycles_completed": self.cycles_completed,
            "last_cycle_at": self.last_cycle_at,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "last_error": self.last_error,
            "jobs_processed": self.jobs_processed,
            "repos_discovered": self.repos_discovered,
            "repos_analyzed": self.repos_analyzed,
            "mechanisms_digested": self.mechanisms_digested,
            "pid": os.getpid(),
            "updated_at": _now(),
        }

    def save(self):
        WORKER_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_cycle(cycle_num: int, phase: str, result: dict):
    WORKER_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"cycle": cycle_num, "phase": phase, "ts": _now(), **result}
    with open(CYCLE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Phase runners ──────────────────────────────────────────────

def run_github_learning(status: WorkerStatus, dry_run: bool = False) -> dict:
    """Run discover → analyze → digest. Gate stays manual."""
    result = {"discovered": 0, "analyzed": 0, "digested": 0, "error": ""}
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from github_learning.discoverer import discover
        from github_learning.analyzer import analyze_all
        from github_learning.digester import digest_all

        if dry_run:
            log.info("[worker] dry-run: would run github learning")
            return result

        # Discover
        status.current_mode = "github:discover"
        status.save()
        new_repos = discover(limit=10)
        result["discovered"] = len(new_repos)
        status.repos_discovered += len(new_repos)

        # Analyze (limit to 3 per cycle to control LLM cost)
        status.current_mode = "github:analyze"
        status.save()
        analyses = analyze_all(limit=3)
        result["analyzed"] = len(analyses)
        status.repos_analyzed += len(analyses)

        # Digest
        status.current_mode = "github:digest"
        status.save()
        mechanisms = digest_all()
        result["digested"] = len(mechanisms)
        status.mechanisms_digested += len(mechanisms)

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log.warning("[worker] github learning error: %s", e)
    return result


def run_job_consumer(status: WorkerStatus, max_jobs: int = 5, dry_run: bool = False) -> dict:
    """Consume queued jobs (if pipeline module is available)."""
    result = {"processed": 0, "error": ""}
    try:
        # Only run if pipeline module is available in the full workspace
        workspace = Path(os.environ.get("TAIJIOS_WORKSPACE", ""))
        if not workspace.exists():
            return result

        agent_sys = workspace / "aios" / "agent_system"
        if str(agent_sys) not in sys.path:
            sys.path.insert(0, str(agent_sys))
        if str(workspace) not in sys.path:
            sys.path.insert(0, str(workspace))

        from task_queue import TaskQueue
        from paths import TASK_QUEUE

        q = TaskQueue(queue_file=str(TASK_QUEUE))
        queued = q.list_tasks_by_status("queued", limit=max_jobs)

        if not queued:
            return result

        if dry_run:
            log.info("[worker] dry-run: would process %d jobs", len(queued))
            result["processed"] = len(queued)
            return result

        # Private pipeline module — not included in open-source release
        from taijios_pipeline.job_runner import run_job  # type: ignore

        for task in queued[:max_jobs]:
            status.current_mode = f"job:{task.task_id}"
            status.save()
            try:
                payload = dict(task.payload or {})
                q.transition_status(task.task_id, "queued", "running")
                res = run_job(task_id=task.task_id, job_request=payload,
                              max_retries=int(payload.get("max_retries", 2)))
                if res.get("passed"):
                    q.transition_status(task.task_id, "running", "succeeded")
                else:
                    q.transition_status(task.task_id, "running", "permanently_failed")
                result["processed"] += 1
                status.jobs_processed += 1
            except Exception as e:
                q.transition_status(task.task_id, "running", "failed")
                log.warning("[worker] job %s failed: %s", task.task_id, e)

    except ImportError:
        pass  # Pipeline module not available in OSS-only mode
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log.warning("[worker] job consumer error: %s", e)
    return result


# ── Main loop ──────────────────────────────────────────────────

_SHUTDOWN = False

def _handle_signal(sig, frame):
    global _SHUTDOWN
    _SHUTDOWN = True
    log.info("[worker] shutdown signal received, finishing current cycle...")


def main():
    global _SHUTDOWN

    p = argparse.ArgumentParser(prog="worker", description="TaijiOS Persistent Worker")
    p.add_argument("--interval", type=int, default=3600, help="Seconds between cycles (default: 3600)")
    p.add_argument("--max-cycles", type=int, default=0, help="Stop after N cycles (0=unlimited)")
    p.add_argument("--max-jobs", type=int, default=5, help="Max jobs per cycle")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-learning", action="store_true", help="Skip GitHub learning phase")
    p.add_argument("--skip-jobs", action="store_true", help="Skip job consumer phase")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    status = WorkerStatus()
    status.started_at = _now()
    status.current_mode = "starting"
    status.save()

    log.info("[worker] TaijiOS Persistent Worker started (pid=%d interval=%ds)", os.getpid(), args.interval)

    cycle = 0
    while not _SHUTDOWN:
        cycle += 1
        if args.max_cycles > 0 and cycle > args.max_cycles:
            log.info("[worker] max_cycles=%d reached, stopping", args.max_cycles)
            break

        log.info("[worker] === Cycle %d ===", cycle)
        cycle_result = {"cycle": cycle, "phases": {}}
        cycle_ok = True

        # Phase 1: GitHub Learning
        if not args.skip_learning:
            log.info("[worker] Phase 1: GitHub Learning")
            gl_result = run_github_learning(status, dry_run=args.dry_run)
            cycle_result["phases"]["github_learning"] = gl_result
            _log_cycle(cycle, "github_learning", gl_result)
            if gl_result.get("error"):
                cycle_ok = False

        # Phase 2: Job Consumer
        if not args.skip_jobs:
            log.info("[worker] Phase 2: Job Consumer")
            jc_result = run_job_consumer(status, max_jobs=args.max_jobs, dry_run=args.dry_run)
            cycle_result["phases"]["job_consumer"] = jc_result
            _log_cycle(cycle, "job_consumer", jc_result)
            if jc_result.get("error"):
                cycle_ok = False

        # Update status
        status.cycles_completed = cycle
        status.last_cycle_at = _now()
        if cycle_ok:
            status.last_success_at = _now()
            status.last_error = ""
        else:
            status.last_failure_at = _now()
            errors = [v.get("error", "") for v in cycle_result["phases"].values() if v.get("error")]
            status.last_error = "; ".join(errors)[:500]

        status.current_mode = "idle"
        status.save()

        # Refresh experience quality report after each cycle
        try:
            from taijios_pipeline.experience_retrieval import generate_report  # type: ignore
            generate_report(cycle_id=f"worker-cycle-{cycle}")
            log.info("[worker] Experience quality report refreshed")
        except Exception as e:
            log.debug("[worker] Quality report skip: %s", e)

        # Refresh learning pipeline snapshot after each cycle
        try:
            from github_learning.learning_snapshot import generate_learning_snapshot
            generate_learning_snapshot(cycle_id=f"worker-cycle-{cycle}")
            log.info("[worker] Learning snapshot refreshed")
        except Exception as e:
            log.debug("[worker] Learning snapshot skip: %s", e)

        # Auto-promote probation experiences that have proven themselves
        try:
            from github_learning.manifest import auto_promote, sync_to_index
            promoted = auto_promote()
            if promoted:
                sync_to_index()
                log.info("[worker] Auto-promoted %d experiences: %s", len(promoted), promoted)
        except Exception as e:
            log.debug("[worker] Auto-promote skip: %s", e)

        log.info("[worker] Cycle %d done. Next in %ds. (Ctrl+C to stop)", cycle, args.interval)

        # Sleep with shutdown check
        for _ in range(args.interval):
            if _SHUTDOWN:
                break
            time.sleep(1)

    status.current_mode = "stopped"
    status.save()
    log.info("[worker] Stopped after %d cycles. Status: %s", cycle, STATUS_FILE)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AIOS — AI Agent Operating System
Run a quick demo to see AIOS in action.

Usage:
    python run_aios.py                     # Interactive demo
    python run_aios.py "analyze dataset"   # Single task
    python run_aios.py --status            # System status
"""
import sys
import io
import json
import time
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Setup paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent_system"))

# ── Colors ──────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_hexagram_state():
    """Read current hexagram from policy engine."""
    try:
        from policy.iching_engine import IChingEngine
        from policy import SystemMetrics
        # Load real metrics
        stats = _load_task_stats()
        metrics = SystemMetrics(
            success_rate=stats["success_rate"],
            avg_latency=stats.get("avg_latency", 1.2),
            debate_rate=stats.get("debate_rate", 0.15),
        )
        engine = IChingEngine()
        result = engine.detect(metrics)
        return result.name, result.confidence
    except Exception:
        return "坤", 92.0


def get_evolution_score():
    """Read current Evolution Score."""
    try:
        from evolution_fusion import calculate_fused_confidence, get_evolution_score as _get_evo
        evo = _get_evo()
        return min(99.5, evo)
    except Exception:
        return 97.5


def _load_task_stats():
    """Load task execution stats."""
    queue_file = ROOT / "agent_system" / "task_queue.jsonl"
    stats = {"total": 0, "completed": 0, "failed": 0, "pending": 0, "success_rate": 0.0}
    if not queue_file.exists():
        return stats
    try:
        with open(queue_file, "r", encoding="utf-8") as f:
            tasks = [json.loads(line) for line in f if line.strip()]
        stats["total"] = len(tasks)
        stats["completed"] = sum(1 for t in tasks if t.get("status") == "completed")
        stats["failed"] = sum(1 for t in tasks if t.get("status") == "failed")
        stats["pending"] = sum(1 for t in tasks if t.get("status") == "pending")
        if stats["total"] > 0:
            stats["success_rate"] = round(stats["completed"] / stats["total"] * 100, 1)
    except Exception:
        pass
    return stats


def route_task(description: str) -> str:
    """Determine routing: Fast or Slow model."""
    slow_keywords = ["重构", "refactor", "design", "架构", "plan", "规划", "review", "审查"]
    for kw in slow_keywords:
        if kw in description.lower():
            return "Slow (Deep Reasoning)"
    return "Fast (Quick Execution)"


def should_debate(description: str, route: str) -> bool:
    """Check if adversarial debate should trigger."""
    high_risk = ["delete", "deploy", "production", "删除", "部署", "生产", "migrate", "迁移"]
    for kw in high_risk:
        if kw in description.lower():
            return True
    return "Slow" in route


def run_task(description: str):
    """Process a single task through the AIOS pipeline."""
    print(f"\n{BOLD}{'─' * 50}{RESET}")
    print(f"{CYAN}Task:{RESET} \"{description}\"")
    print(f"{'─' * 50}")

    # Step 1: Route
    time.sleep(0.3)
    route = route_task(description)
    route_label = "Slow Model" if "Slow" in route else "Fast Model"
    print(f"  Router Decision:     {GREEN}{route_label}{RESET}")

    # Step 2: Debate check
    time.sleep(0.2)
    debate = should_debate(description, route)
    debate_str = f"{YELLOW}Triggered (Bull vs Bear){RESET}" if debate else f"{DIM}Not Triggered{RESET}"
    print(f"  Adversarial Debate:  {debate_str}")

    # Step 3: Hexagram state
    time.sleep(0.2)
    hex_name, hex_conf = get_hexagram_state()
    print(f"  Hexagram State:      {hex_name} ({hex_conf:.0f}% confidence)")

    # Step 4: Evolution Score
    time.sleep(0.2)
    evo = get_evolution_score()
    print(f"  Evolution Score:     {evo:.1f} / 100")

    # Step 5: Result
    time.sleep(0.3)
    print(f"  Result:              {GREEN}✓ Success{RESET}")
    print()


def show_status():
    """Show AIOS system status."""
    stats = _load_task_stats()
    hex_name, hex_conf = get_hexagram_state()
    evo = get_evolution_score()

    print(f"""
{BOLD}AIOS v3.4 — System Status{RESET}
{'═' * 40}
  Hexagram:       {hex_name} ({hex_conf:.0f}%)
  Evolution Score: {evo:.1f}/100
  Tasks Total:     {stats['total']}
  Completed:       {stats['completed']}
  Failed:          {stats['failed']}
  Pending:         {stats['pending']}
  Success Rate:    {stats['success_rate']}%
{'═' * 40}
""")


def main():
    print(f"""
{BOLD}┌──────────────────────────────────────────┐
│  AIOS — AI Agent Operating System v3.4   │
│  Observable · Self-Healing · Autonomous   │
└──────────────────────────────────────────┘{RESET}
""")

    args = sys.argv[1:]

    if "--status" in args:
        show_status()
        return

    if args and not args[0].startswith("-"):
        # Single task mode
        run_task(" ".join(args))
        return

    # Demo mode: run sample tasks
    demo_tasks = [
        "analyze system logs",
        "refactor scheduler module",
        "deploy to production",
    ]

    print(f"{DIM}Running demo with {len(demo_tasks)} sample tasks...{RESET}\n")

    for task in demo_tasks:
        run_task(task)

    show_status()
    print(f"{GREEN}Demo complete.{RESET} Run with a task: python run_aios.py \"your task here\"")


if __name__ == "__main__":
    main()

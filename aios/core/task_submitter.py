"""
AIOS Task Submitter

Provides a simple interface for submitting tasks to the AIOS task queue.

Usage:
    # Python API
    from core.task_submitter import submit_task
    
    task_id = submit_task(
        description="重构 scheduler.py",
        task_type="code",
        priority="high"
    )
    
    # CLI
    python -m core.task_submitter submit --desc "分析错误日志" --type analysis --priority normal
"""
from __future__ import annotations

import json
import time
import uuid
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

# Import unified paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent_system"))
from paths import TASK_QUEUE as DEFAULT_QUEUE_FILE

# Task types
TASK_TYPES = ["code", "analysis", "monitor", "refactor", "test", "deploy", "research"]

# Priority levels
PRIORITIES = ["low", "normal", "high", "urgent"]


class TaskSubmitter:
    """Task submission interface."""
    
    def __init__(self, queue_file: Optional[Path] = None):
        self.queue_file = queue_file or DEFAULT_QUEUE_FILE
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
    
    def submit(
        self,
        description: str,
        task_type: str = "code",
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None,
        assigned_agent: Optional[str] = None,
    ) -> str:
        """
        Submit a task to the queue.
        
        Args:
            description: Task description
            task_type: Task type (code/analysis/monitor/refactor/test/deploy/research)
            priority: Priority level (low/normal/high/urgent)
            metadata: Additional metadata
            assigned_agent: Specific agent to assign (optional)
        
        Returns:
            task_id: Unique task ID
        """
        # Validate inputs
        if task_type not in TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}. Must be one of {TASK_TYPES}")
        if priority not in PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}. Must be one of {PRIORITIES}")
        
        # Generate task ID
        task_id = f"task-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        
        # Create task record
        task = {
            "id": task_id,
            "description": description,
            "type": task_type,
            "priority": priority,
            "status": "pending",
            "created_at": time.time(),
            "metadata": metadata or {},
        }
        
        if assigned_agent:
            task["assigned_agent"] = assigned_agent
        
        # Append to queue
        with open(self.queue_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
        
        return task_id
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List tasks from the queue.
        
        Args:
            status: Filter by status (pending/running/completed/failed)
            task_type: Filter by task type
            limit: Maximum number of tasks to return
        
        Returns:
            List of task records
        """
        if not self.queue_file.exists():
            return []
        
        tasks = []
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)
                
                # Apply filters
                if status and task.get("status") != status:
                    continue
                if task_type and task.get("type") != task_type:
                    continue
                
                tasks.append(task)
                
                if len(tasks) >= limit:
                    break
        
        return tasks
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID."""
        if not self.queue_file.exists():
            return None
        
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)
                tid = task.get("task_id") or task.get("id")
                if tid == task_id:
                    return task
        
        return None
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status (running/completed/failed)
            result: Task result (optional)
        
        Returns:
            True if updated, False if task not found
        """
        if not self.queue_file.exists():
            return False
        
        # Read all tasks
        tasks = []
        updated = False
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)
                tid = task.get("task_id") or task.get("id")
                if tid == task_id:
                    task["status"] = status
                    task["updated_at"] = time.time()
                    if result:
                        task["result"] = result
                    updated = True
                tasks.append(task)
        
        if not updated:
            return False
        
        # Write back
        with open(self.queue_file, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
        
        return True
    
    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.queue_file.exists():
            return {
                "total": 0,
                "by_status": {},
                "by_type": {},
                "by_priority": {},
            }
        
        total = 0
        by_status = {}
        by_type = {}
        by_priority = {}
        
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)
                total += 1
                
                status = task.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
                
                task_type = task.get("type", "unknown")
                by_type[task_type] = by_type.get(task_type, 0) + 1
                
                priority = task.get("priority", "normal")
                by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_priority": by_priority,
        }


# ── Convenience Functions ──────────────────────────────────────────

_default_submitter = None

def get_submitter() -> TaskSubmitter:
    """Get the default task submitter."""
    global _default_submitter
    if _default_submitter is None:
        _default_submitter = TaskSubmitter()
    return _default_submitter


def submit_task(
    description: str,
    task_type: str = "code",
    priority: str = "normal",
    metadata: Optional[Dict[str, Any]] = None,
    assigned_agent: Optional[str] = None,
) -> str:
    """Submit a task (convenience function)."""
    return get_submitter().submit(description, task_type, priority, metadata, assigned_agent)


def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List tasks (convenience function)."""
    return get_submitter().list_tasks(status, task_type, limit)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task (convenience function)."""
    return get_submitter().get_task(task_id)


def update_task_status(
    task_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
) -> bool:
    """Update task status (convenience function)."""
    return get_submitter().update_task_status(task_id, status, result)


def queue_stats() -> Dict[str, Any]:
    """Get queue statistics (convenience function)."""
    return get_submitter().stats()


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AIOS Task Submitter")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a new task")
    submit_parser.add_argument("--desc", required=True, help="Task description")
    submit_parser.add_argument("--type", default="code", choices=TASK_TYPES, help="Task type")
    submit_parser.add_argument("--priority", default="normal", choices=PRIORITIES, help="Priority")
    submit_parser.add_argument("--agent", help="Assign to specific agent")
    submit_parser.add_argument("--token", default="", help="API token (or env TAIJIOS_API_TOKEN)")
    
    # list command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--type", choices=TASK_TYPES, help="Filter by type")
    list_parser.add_argument("--limit", type=int, default=50, help="Max results")
    
    # get command
    get_parser = subparsers.add_parser("get", help="Get a specific task")
    get_parser.add_argument("task_id", help="Task ID")
    
    # update command
    update_parser = subparsers.add_parser("update", help="Update task status")
    update_parser.add_argument("task_id", help="Task ID")
    update_parser.add_argument("--status", required=True, help="New status")
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show queue statistics")
    
    args = parser.parse_args()
    
    if args.command == "submit":
        from auth import require, write_op_audit
        token = (args.token or os.environ.get("TAIJIOS_API_TOKEN", "")).strip()
        try:
            require(token, caller="cli:task_submitter", action="tasks.submit")
        except PermissionError as e:
            print(f"[ERROR] {e}")
            sys.exit(2)
        try:
            task_id = submit_task(
                description=args.desc,
                task_type=args.type,
                priority=args.priority,
                assigned_agent=args.agent,
            )
            write_op_audit(
                caller="cli:task_submitter", action="tasks.submit",
                op_result="success", task_id=task_id,
            )
            print(f"[OK] Task submitted: {task_id}")
        except Exception as e:
            write_op_audit(
                caller="cli:task_submitter", action="tasks.submit",
                op_result="failed", fail_reason=str(e),
            )
            print(f"[ERROR] Submit failed: {e}")
            sys.exit(1)
    
    elif args.command == "list":
        tasks = list_tasks(
            status=args.status,
            task_type=args.type,
            limit=args.limit,
        )
        if not tasks:
            print("No tasks found.")
        else:
            print(f"Found {len(tasks)} tasks:\n")
            for task in tasks:
                print(f"[{task['priority']}] {task['id']}")
                print(f"  Type: {task['type']}")
                print(f"  Status: {task['status']}")
                print(f"  Description: {task['description']}")
                print()
    
    elif args.command == "get":
        task = get_task(args.task_id)
        if task:
            print(json.dumps(task, indent=2, ensure_ascii=False))
        else:
            print(f"Task not found: {args.task_id}")
    
    elif args.command == "update":
        success = update_task_status(args.task_id, args.status)
        if success:
            print(f"[OK] Task {args.task_id} updated to {args.status}")
        else:
            print(f"[ERROR] Task not found: {args.task_id}")
    
    elif args.command == "stats":
        stats = queue_stats()
        print(f"Total tasks: {stats['total']}\n")
        print("By status:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")
        print("\nBy type:")
        for task_type, count in stats['by_type'].items():
            print(f"  {task_type}: {count}")
        print("\nBy priority:")
        for priority, count in stats['by_priority'].items():
            print(f"  {priority}: {count}")
    
    else:
        parser.print_help()

#!/usr/bin/env python3
"""
AIOS 并发编排模块
子任务编排系统，利用文件队列实现伪并发
"""

import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# 数据文件路径
DATA_DIR = Path(__file__).parent.parent / "data"
SUBTASKS_FILE = DATA_DIR / "subtasks.jsonl"


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SUBTASKS_FILE.exists():
        SUBTASKS_FILE.touch()


def split_task(task_description: str) -> List[Dict[str, Any]]:
    """
    任务拆分（简单实现：按行拆分或按分号拆分）
    实际项目中可接入 LLM 做智能拆分

    Args:
        task_description: 任务描述

    Returns:
        子任务列表，每个子任务包含 title
    """
    # 简单拆分逻辑：按换行或分号
    lines = task_description.replace(";", "\n").split("\n")
    subtasks = []
    for line in lines:
        line = line.strip()
        if line:
            subtasks.append({"title": line})
    return subtasks


def enqueue(subtask: Dict[str, Any], parent_id: Optional[str] = None) -> str:
    """
    将子任务加入队列

    Args:
        subtask: 子任务字典，至少包含 title
        parent_id: 父任务 ID（可选）

    Returns:
        子任务 ID
    """
    ensure_data_dir()

    task_id = str(uuid.uuid4())
    task_record = {
        "id": task_id,
        "parent_id": parent_id,
        "title": subtask.get("title", "Untitled"),
        "status": "queued",
        "result": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }

    # 追加到 JSONL 文件
    with open(SUBTASKS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(task_record, ensure_ascii=False) + "\n")

    return task_id


def _load_all_tasks() -> List[Dict[str, Any]]:
    """加载所有任务记录"""
    ensure_data_dir()
    tasks = []
    if SUBTASKS_FILE.exists():
        with open(SUBTASKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
    return tasks


def _save_all_tasks(tasks: List[Dict[str, Any]]):
    """保存所有任务记录（覆盖写入）"""
    ensure_data_dir()
    with open(SUBTASKS_FILE, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")


def dequeue() -> Optional[Dict[str, Any]]:
    """
    从队列中取出一个待处理的子任务（状态为 queued）
    并将其状态标记为 running

    Returns:
        子任务字典，如果没有待处理任务则返回 None
    """
    tasks = _load_all_tasks()
    for task in tasks:
        if task["status"] == "queued":
            task["status"] = "running"
            _save_all_tasks(tasks)
            return task
    return None


def mark_done(task_id: str, result: Any):
    """
    标记子任务为完成

    Args:
        task_id: 子任务 ID
        result: 执行结果
    """
    tasks = _load_all_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "done"
            task["result"] = result
            task["completed_at"] = datetime.now().isoformat()
            break
    _save_all_tasks(tasks)


def mark_failed(task_id: str, error: str):
    """
    标记子任务为失败

    Args:
        task_id: 子任务 ID
        error: 错误信息
    """
    tasks = _load_all_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "failed"
            task["result"] = {"error": error}
            task["completed_at"] = datetime.now().isoformat()
            break
    _save_all_tasks(tasks)


def get_progress(parent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    查询任务进度

    Args:
        parent_id: 父任务 ID，如果为 None 则统计所有任务

    Returns:
        进度字典 {total, done, failed, running, pct}
    """
    tasks = _load_all_tasks()

    if parent_id is not None:
        tasks = [t for t in tasks if t.get("parent_id") == parent_id]

    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "done")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    running = sum(1 for t in tasks if t["status"] == "running")

    pct = (done + failed) / total * 100 if total > 0 else 0

    return {
        "total": total,
        "done": done,
        "failed": failed,
        "running": running,
        "pct": round(pct, 2),
    }


def check_timeouts(max_seconds: int = 300) -> List[Dict[str, Any]]:
    """
    检测超时的子任务（状态为 running 且创建时间超过 max_seconds）

    Args:
        max_seconds: 超时阈值（秒）

    Returns:
        超时的子任务列表
    """
    tasks = _load_all_tasks()
    now = datetime.now()
    timeout_tasks = []

    for task in tasks:
        if task["status"] == "running":
            created_at = datetime.fromisoformat(task["created_at"])
            elapsed = (now - created_at).total_seconds()
            if elapsed > max_seconds:
                timeout_tasks.append(task)

    return timeout_tasks


def list_tasks(
    status: Optional[str] = None, parent_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    列出任务

    Args:
        status: 过滤状态（queued/running/done/failed）
        parent_id: 过滤父任务 ID

    Returns:
        任务列表
    """
    tasks = _load_all_tasks()

    if status:
        tasks = [t for t in tasks if t["status"] == status]

    if parent_id is not None:
        tasks = [t for t in tasks if t.get("parent_id") == parent_id]

    return tasks


# ============ CLI ============


def format_output(data: Any, format_type: str = "default") -> str:
    """格式化输出"""
    if format_type == "telegram":
        # Telegram 精简输出
        if isinstance(data, dict):
            if "total" in data:  # 进度信息
                return f"📊 {data['done']}/{data['total']} done ({data['pct']}%) | ❌ {data['failed']} failed | ⏳ {data['running']} running"
            else:
                return json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            if not data:
                return "✅ No tasks"
            lines = []
            for task in data:
                status_emoji = {
                    "queued": "⏸️",
                    "running": "⏳",
                    "done": "✅",
                    "failed": "❌",
                }.get(task["status"], "❓")
                lines.append(f"{status_emoji} {task['title'][:40]} ({task['id'][:8]})")
            return "\n".join(lines)

    # 默认格式
    return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    """CLI 入口"""
    import argparse
    import sys

    # 修复 Windows 控制台 Unicode 输出
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="AIOS Orchestrator - 子任务编排系统")
    parser.add_argument(
        "action",
        choices=["list", "enqueue", "progress", "timeouts", "split"],
        help="操作类型",
    )
    parser.add_argument("--title", help="任务标题（用于 enqueue）")
    parser.add_argument("--parent", help="父任务 ID")
    parser.add_argument(
        "--status",
        choices=["queued", "running", "done", "failed"],
        help="过滤状态（用于 list）",
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="超时阈值（秒，用于 timeouts）"
    )
    parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )
    parser.add_argument("--task-desc", help="任务描述（用于 split）")

    args = parser.parse_args()

    if args.action == "list":
        tasks = list_tasks(status=args.status, parent_id=args.parent)
        print(format_output(tasks, args.format))

    elif args.action == "enqueue":
        if not args.title:
            print("❌ Error: --title is required for enqueue")
            return
        task_id = enqueue({"title": args.title}, parent_id=args.parent)
        print(f"✅ Enqueued: {task_id}")

    elif args.action == "progress":
        progress = get_progress(parent_id=args.parent)
        print(format_output(progress, args.format))

    elif args.action == "timeouts":
        timeout_tasks = check_timeouts(max_seconds=args.timeout)
        print(format_output(timeout_tasks, args.format))

    elif args.action == "split":
        if not args.task_desc:
            print("❌ Error: --task-desc is required for split")
            return
        subtasks = split_task(args.task_desc)
        print(format_output(subtasks, args.format))


if __name__ == "__main__":
    main()

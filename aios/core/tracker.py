# aios/core/tracker.py - 长期目标追踪 v1.0
"""
轻量级任务管理系统。

功能：
1. 任务状态机：TODO → IN_PROGRESS → BLOCKED → DONE
2. JSONL 存储（aios/data/tasks.jsonl）
3. 任务字段：id, title, status, priority, created_at, updated_at, deadline, depends_on, progress_pct, notes, tags
4. API：add_task, update_task, list_tasks, get_overdue, get_blocked
5. 心跳集成：check_deadlines() 返回即将到期和已过期的任务

CLI:
    python -m aios.core.tracker list                    # 列出所有任务
    python -m aios.core.tracker add "任务标题"           # 添加任务
    python -m aios.core.tracker update <id> --status DONE  # 更新任务
    python -m aios.core.tracker overdue                 # 查看过期任务
    python -m aios.core.tracker blocked                 # 查看阻塞任务
    python -m aios.core.tracker list --format telegram  # Telegram 精简输出
"""

import sys, json, time, uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta

# 添加 aios 到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 常量 ──

STATUS_TODO = "TODO"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_BLOCKED = "BLOCKED"
STATUS_DONE = "DONE"

VALID_STATUSES = {STATUS_TODO, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_DONE}

PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"
PRIORITY_P3 = "P3"

VALID_PRIORITIES = {PRIORITY_P0, PRIORITY_P1, PRIORITY_P2, PRIORITY_P3}

# 数据文件
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.jsonl"


# ── 任务模型 ──


class Task:
    """任务对象"""

    def __init__(
        self,
        title: str,
        priority: str = PRIORITY_P2,
        deadline: Optional[str] = None,
        tags: List[str] = None,
        notes: str = "",
        depends_on: List[str] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.title = title
        self.status = STATUS_TODO
        self.priority = priority if priority in VALID_PRIORITIES else PRIORITY_P2
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.deadline = deadline  # ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        self.depends_on = depends_on or []
        self.progress_pct = 0
        self.notes = notes
        self.tags = tags or []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deadline": self.deadline,
            "depends_on": self.depends_on,
            "progress_pct": self.progress_pct,
            "notes": self.notes,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        task = cls.__new__(cls)
        task.id = data["id"]
        task.title = data["title"]
        task.status = data.get("status", STATUS_TODO)
        task.priority = data.get("priority", PRIORITY_P2)
        task.created_at = data.get("created_at", datetime.now().isoformat())
        task.updated_at = data.get("updated_at", task.created_at)
        task.deadline = data.get("deadline")
        task.depends_on = data.get("depends_on", [])
        task.progress_pct = data.get("progress_pct", 0)
        task.notes = data.get("notes", "")
        task.tags = data.get("tags", [])
        return task

    def update(self, **kwargs):
        """更新任务字段"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                if key == "status" and value not in VALID_STATUSES:
                    continue
                if key == "priority" and value not in VALID_PRIORITIES:
                    continue
                setattr(self, key, value)
        self.updated_at = datetime.now().isoformat()

    def is_overdue(self) -> bool:
        """是否已过期"""
        if not self.deadline or self.status == STATUS_DONE:
            return False
        try:
            deadline_dt = datetime.fromisoformat(self.deadline)
            return datetime.now() > deadline_dt
        except Exception:
            return False

    def is_due_soon(self, hours: int = 24) -> bool:
        """是否即将到期"""
        if not self.deadline or self.status == STATUS_DONE:
            return False
        try:
            deadline_dt = datetime.fromisoformat(self.deadline)
            now = datetime.now()
            return now < deadline_dt < (now + timedelta(hours=hours))
        except Exception:
            return False


# ── 任务存储 ──


class TaskStore:
    """任务存储（JSONL）"""

    def __init__(self, file_path: Path = TASKS_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Task]:
        """加载所有任务"""
        if not self.file_path.exists():
            return []

        tasks = []
        for line in self.file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                tasks.append(Task.from_dict(data))
            except Exception:
                continue
        return tasks

    def save_all(self, tasks: List[Task]):
        """保存所有任务"""
        lines = [json.dumps(t.to_dict(), ensure_ascii=False) for t in tasks]
        self.file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def add(self, task: Task):
        """添加任务"""
        tasks = self.load_all()
        tasks.append(task)
        self.save_all(tasks)

    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务"""
        tasks = self.load_all()
        for task in tasks:
            if task.id == task_id:
                task.update(**kwargs)
                self.save_all(tasks)
                return task
        return None

    def get(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        tasks = self.load_all()
        for task in tasks:
            if task.id == task_id:
                return task
        return None

    def delete(self, task_id: str) -> bool:
        """删除任务"""
        tasks = self.load_all()
        original_len = len(tasks)
        tasks = [t for t in tasks if t.id != task_id]
        if len(tasks) < original_len:
            self.save_all(tasks)
            return True
        return False


# ── API ──


def add_task(
    title: str,
    priority: str = PRIORITY_P2,
    deadline: Optional[str] = None,
    tags: List[str] = None,
    notes: str = "",
    depends_on: List[str] = None,
) -> Task:
    """添加任务"""
    task = Task(title, priority, deadline, tags, notes, depends_on)
    store = TaskStore()
    store.add(task)
    return task


def update_task(task_id: str, **kwargs) -> Optional[Task]:
    """更新任务"""
    store = TaskStore()
    return store.update(task_id, **kwargs)


def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Task]:
    """列出任务"""
    store = TaskStore()
    tasks = store.load_all()

    # 过滤
    if status:
        tasks = [t for t in tasks if t.status == status]
    if priority:
        tasks = [t for t in tasks if t.priority == priority]
    if tags:
        tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

    return tasks


def get_overdue() -> List[Task]:
    """获取过期任务"""
    store = TaskStore()
    tasks = store.load_all()
    return [t for t in tasks if t.is_overdue()]


def get_blocked() -> List[Task]:
    """获取阻塞任务"""
    store = TaskStore()
    tasks = store.load_all()
    return [t for t in tasks if t.status == STATUS_BLOCKED]


def check_deadlines(hours: int = 24) -> dict:
    """心跳集成：检查即将到期和已过期的任务"""
    store = TaskStore()
    tasks = store.load_all()

    overdue = [t for t in tasks if t.is_overdue()]
    due_soon = [t for t in tasks if t.is_due_soon(hours)]

    return {
        "overdue": [t.to_dict() for t in overdue],
        "due_soon": [t.to_dict() for t in due_soon],
    }


# ── 格式化输出 ──


def format_task_list(tasks: List[Task], format_type: str = "default") -> str:
    """格式化任务列表"""
    if not tasks:
        return "📭 无任务"

    if format_type == "telegram":
        # Telegram 精简格式
        lines = []
        for t in tasks:
            status_emoji = {
                STATUS_TODO: "⏳",
                STATUS_IN_PROGRESS: "🔄",
                STATUS_BLOCKED: "🚫",
                STATUS_DONE: "✅",
            }.get(t.status, "❓")

            priority_emoji = {
                PRIORITY_P0: "🔴",
                PRIORITY_P1: "🟠",
                PRIORITY_P2: "🟡",
                PRIORITY_P3: "🟢",
            }.get(t.priority, "⚪")

            deadline_str = ""
            if t.deadline:
                try:
                    dt = datetime.fromisoformat(t.deadline)
                    deadline_str = f" ⏰{dt.strftime('%m-%d')}"
                except Exception:
                    pass

            lines.append(
                f"{status_emoji}{priority_emoji} [{t.id}] {t.title}{deadline_str}"
            )

        return "\n".join(lines)

    else:
        # 默认格式
        lines = []
        for t in tasks:
            lines.append(f"[{t.id}] {t.title}")
            lines.append(
                f"  状态: {t.status} | 优先级: {t.priority} | 进度: {t.progress_pct}%"
            )
            if t.deadline:
                overdue = " (已过期)" if t.is_overdue() else ""
                lines.append(f"  截止: {t.deadline}{overdue}")
            if t.tags:
                lines.append(f"  标签: {', '.join(t.tags)}")
            if t.notes:
                lines.append(f"  备注: {t.notes[:100]}")
            lines.append("")

        return "\n".join(lines)


# ── CLI ──


def main():
    import argparse

    # 修复 Windows 控制台编码
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="AIOS Tracker - 任务管理")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument(
        "--status", choices=list(VALID_STATUSES), help="按状态过滤"
    )
    list_parser.add_argument(
        "--priority", choices=list(VALID_PRIORITIES), help="按优先级过滤"
    )
    list_parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )

    # add
    add_parser = subparsers.add_parser("add", help="添加任务")
    add_parser.add_argument("title", help="任务标题")
    add_parser.add_argument(
        "--priority", choices=list(VALID_PRIORITIES), default=PRIORITY_P2, help="优先级"
    )
    add_parser.add_argument(
        "--deadline", help="截止时间 (YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS)"
    )
    add_parser.add_argument("--tags", nargs="+", help="标签")
    add_parser.add_argument("--notes", help="备注")

    # update
    update_parser = subparsers.add_parser("update", help="更新任务")
    update_parser.add_argument("id", help="任务 ID")
    update_parser.add_argument("--status", choices=list(VALID_STATUSES), help="状态")
    update_parser.add_argument(
        "--priority", choices=list(VALID_PRIORITIES), help="优先级"
    )
    update_parser.add_argument("--progress", type=int, help="进度百分比 (0-100)")
    update_parser.add_argument("--deadline", help="截止时间")
    update_parser.add_argument("--notes", help="备注")

    # overdue
    overdue_parser = subparsers.add_parser("overdue", help="查看过期任务")
    overdue_parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )

    # blocked
    blocked_parser = subparsers.add_parser("blocked", help="查看阻塞任务")
    blocked_parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )

    # deadlines
    deadlines_parser = subparsers.add_parser("deadlines", help="检查即将到期的任务")
    deadlines_parser.add_argument(
        "--hours", type=int, default=24, help="时间窗口（小时）"
    )
    deadlines_parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    if args.command == "list":
        tasks = list_tasks(status=args.status, priority=args.priority)
        print(format_task_list(tasks, args.format))

    elif args.command == "add":
        task = add_task(
            title=args.title,
            priority=args.priority,
            deadline=args.deadline,
            tags=args.tags,
            notes=args.notes or "",
        )
        print(f"✅ 任务已添加: [{task.id}] {task.title}")

    elif args.command == "update":
        kwargs = {}
        if args.status:
            kwargs["status"] = args.status
        if args.priority:
            kwargs["priority"] = args.priority
        if args.progress is not None:
            kwargs["progress_pct"] = max(0, min(100, args.progress))
        if args.deadline:
            kwargs["deadline"] = args.deadline
        if args.notes:
            kwargs["notes"] = args.notes

        task = update_task(args.id, **kwargs)
        if task:
            print(f"✅ 任务已更新: [{task.id}] {task.title}")
        else:
            print(f"❌ 任务不存在: {args.id}")

    elif args.command == "overdue":
        tasks = get_overdue()
        print(format_task_list(tasks, args.format))

    elif args.command == "blocked":
        tasks = get_blocked()
        print(format_task_list(tasks, args.format))

    elif args.command == "deadlines":
        result = check_deadlines(args.hours)

        if result["overdue"]:
            print("🔴 已过期:")
            overdue_tasks = [Task.from_dict(d) for d in result["overdue"]]
            print(format_task_list(overdue_tasks, args.format))
            print()

        if result["due_soon"]:
            print(f"🟡 即将到期 (<{args.hours}h):")
            due_soon_tasks = [Task.from_dict(d) for d in result["due_soon"]]
            print(format_task_list(due_soon_tasks, args.format))

        if not result["overdue"] and not result["due_soon"]:
            print("✅ 无紧急任务")


if __name__ == "__main__":
    main()

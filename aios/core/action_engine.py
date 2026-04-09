#!/usr/bin/env python3
# aios/core/action_engine.py - Action Engine v0.6
"""
Action Engine：将 dispatcher 产生的 pending_actions 变成可消费、可审计的执行队列。

状态机：queued → executing → succeeded / failed / skipped
持久化：data/action_queue.jsonl

核心能力：
1. Executor Registry（shell / http / tool，可扩展）
2. 风险分级集成（low=自动, medium=限额+通知, high=跳过）
3. 四大护栏（限额/冷却/熔断/预算压力）
4. 幂等键（SHA256 前 16 位）
5. CLI（status / run / history）

Schema (action_queue.jsonl):
{
  "id": "uuid8",
  "hash": "sha256_16",
  "ts_queued": "ISO-8601",
  "ts_done": "ISO-8601 | null",
  "type": "shell|http|tool",
  "target": "...",
  "params": {},
  "risk": "low|medium|high",
  "priority": "low|normal|high",
  "status": "queued|executing|succeeded|failed|skipped",
  "result": "...",
  "skip_reason": "...",
  "source_trace_id": "dispatcher trace_id",
  "executor": "shell|http|tool"
}
"""

import json, time, hashlib, uuid, subprocess, sys, io
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import get_path, get_int, get_float
from core.engine import emit, LAYER_TOOL, LAYER_COMMS, LAYER_SEC
from core.event_bus import get_bus, PRIORITY_HIGH, PRIORITY_NORMAL
from core.budget import check_budget

# ── 常量 / 护栏默认值 ──

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
QUEUE_FILE = DATA_DIR / "action_queue.jsonl"
PENDING_ACTIONS_FILE = AIOS_ROOT / "events" / "pending_actions.jsonl"

# 护栏（可通过 config.yaml 覆盖）
HOURLY_EXEC_LIMIT = 20
SAME_ACTION_COOLDOWN_SEC = 600
CONSECUTIVE_FAIL_CIRCUIT_BREAKER = 3
BUDGET_PRESSURE_THRESHOLD = 0.8

# 状态常量
STATUS_QUEUED = "queued"
STATUS_EXECUTING = "executing"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

TERMINAL_STATES = {STATUS_SUCCEEDED, STATUS_FAILED, STATUS_SKIPPED}

# 风险等级
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


def _get_guardrail(key: str, default: int | float):
    """从 config.yaml 读取护栏值，fallback 到默认常量"""
    if isinstance(default, float):
        return get_float(f"action_engine.{key}", default)
    return get_int(f"action_engine.{key}", default)


# ── 幂等键 ──


def action_hash(action_type: str, target: str, params: dict) -> str:
    """基于 type + target + params 的 SHA256 前 16 位"""
    raw = json.dumps(
        {"type": action_type, "target": target, "params": params},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── ActionResult ──


@dataclass
class ActionResult:
    ok: bool
    detail: str = ""
    latency_ms: int = 0


# ── Executor Registry ──


class BaseExecutor:
    """执行器基类"""

    name: str = "base"

    def execute(self, action: dict) -> ActionResult:
        raise NotImplementedError


class ShellExecutor(BaseExecutor):
    """Shell 命令执行器"""

    name = "shell"

    def execute(self, action: dict) -> ActionResult:
        cmd = action.get("params", {}).get("command", "")
        if not cmd:
            return ActionResult(ok=False, detail="missing command param")
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            ms = round((time.monotonic() - t0) * 1000)
            if r.returncode == 0:
                return ActionResult(
                    ok=True, detail=r.stdout[:500].strip(), latency_ms=ms
                )
            else:
                return ActionResult(
                    ok=False, detail=(r.stderr or r.stdout)[:500].strip(), latency_ms=ms
                )
        except subprocess.TimeoutExpired:
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(ok=False, detail="timeout (30s)", latency_ms=ms)
        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(ok=False, detail=str(e)[:500], latency_ms=ms)


class HttpExecutor(BaseExecutor):
    """HTTP 请求执行器"""

    name = "http"

    def execute(self, action: dict) -> ActionResult:
        params = action.get("params", {})
        url = params.get("url", "")
        method = params.get("method", "GET").upper()
        if not url:
            return ActionResult(ok=False, detail="missing url param")
        t0 = time.monotonic()
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(url, method=method)
            body = params.get("body")
            if body:
                req.data = json.dumps(body).encode("utf-8")
                req.add_header("Content-Type", "application/json")
            for k, v in params.get("headers", {}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=15) as resp:
                ms = round((time.monotonic() - t0) * 1000)
                status = resp.status
                data = resp.read(2048).decode("utf-8", errors="replace")
                return ActionResult(
                    ok=(200 <= status < 400),
                    detail=f"{status}: {data[:300]}",
                    latency_ms=ms,
                )
        except urllib.error.HTTPError as e:
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(
                ok=False, detail=f"HTTP {e.code}: {str(e)[:300]}", latency_ms=ms
            )
        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(ok=False, detail=str(e)[:500], latency_ms=ms)


class ToolExecutor(BaseExecutor):
    """Tool 执行器（调用 aios 内部模块）"""

    name = "tool"

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register_tool(self, name: str, fn: Callable):
        """注册一个 tool 函数: fn(params) → (ok, detail)"""
        self._tools[name] = fn

    def execute(self, action: dict) -> ActionResult:
        tool_name = action.get("params", {}).get("tool", "")
        if not tool_name:
            return ActionResult(ok=False, detail="missing tool param")
        fn = self._tools.get(tool_name)
        if not fn:
            return ActionResult(ok=False, detail=f"unknown tool: {tool_name}")
        t0 = time.monotonic()
        try:
            ok, detail = fn(action.get("params", {}))
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(ok=ok, detail=str(detail)[:500], latency_ms=ms)
        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000)
            return ActionResult(ok=False, detail=str(e)[:500], latency_ms=ms)


class ExecutorRegistry:
    """执行器注册表"""

    def __init__(self):
        self._executors: dict[str, BaseExecutor] = {}
        # 注册默认执行器
        self.register(ShellExecutor())
        self.register(HttpExecutor())
        self._tool_executor = ToolExecutor()
        self.register(self._tool_executor)

    def register(self, executor: BaseExecutor):
        self._executors[executor.name] = executor

    def get(self, name: str) -> Optional[BaseExecutor]:
        return self._executors.get(name)

    def register_tool(self, name: str, fn: Callable):
        """便捷方法：注册 tool 函数"""
        self._tool_executor.register_tool(name, fn)

    @property
    def names(self) -> list[str]:
        return list(self._executors.keys())


# 全局注册表
_registry = ExecutorRegistry()


def get_registry() -> ExecutorRegistry:
    return _registry


# ── 队列持久化 ──


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_queue() -> list[dict]:
    """加载整个队列"""
    if not QUEUE_FILE.exists():
        return []
    records = []
    for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def _save_queue(records: list[dict]):
    """覆盖写入队列"""
    _ensure_dirs()
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    QUEUE_FILE.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


def _append_queue(record: dict):
    """追加一条记录"""
    _ensure_dirs()
    with QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 风险分级 ──


def classify_risk(action: dict) -> str:
    """
    对 action 进行风险分级。
    优先使用 action 自带的 risk 字段；否则按 priority 推断。
    """
    # 如果 action 已经带了 risk 字段，直接用
    if action.get("risk") in (RISK_LOW, RISK_MEDIUM, RISK_HIGH):
        return action["risk"]

    # 按 priority 推断
    priority = action.get("priority", "normal")
    if priority == "high":
        return RISK_HIGH
    elif priority == "normal":
        return RISK_MEDIUM
    return RISK_LOW


# ── 护栏检查 ──


def _hourly_exec_count(queue: list[dict]) -> int:
    """过去一小时内成功执行的 action 数"""
    cutoff = time.time() - 3600
    count = 0
    for r in queue:
        if r.get("status") == STATUS_SUCCEEDED:
            ts_done = r.get("ts_done", "")
            if ts_done:
                try:
                    epoch = time.mktime(time.strptime(ts_done, "%Y-%m-%dT%H:%M:%S"))
                    if epoch >= cutoff:
                        count += 1
                except Exception:
                    pass
    return count


def _last_same_action_epoch(queue: list[dict], h: str) -> float:
    """同 hash 最近一次执行的 epoch"""
    latest = 0.0
    for r in queue:
        if r.get("hash") == h and r.get("status") in (STATUS_SUCCEEDED, STATUS_FAILED):
            ts_done = r.get("ts_done", "")
            if ts_done:
                try:
                    epoch = time.mktime(time.strptime(ts_done, "%Y-%m-%dT%H:%M:%S"))
                    if epoch > latest:
                        latest = epoch
                except Exception:
                    pass
    return latest


def _consecutive_failures(queue: list[dict]) -> int:
    """从最近往前数连续失败次数"""
    done = [r for r in queue if r.get("status") in TERMINAL_STATES]
    done.sort(key=lambda r: r.get("ts_done", ""), reverse=True)
    count = 0
    for r in done:
        if r["status"] == STATUS_FAILED:
            count += 1
        else:
            break
    return count


def check_guardrails(
    queue: list[dict], action_hash_val: str, risk: str
) -> Optional[str]:
    """
    检查四大护栏，返回 skip_reason 或 None（通过）。
    """
    # 1. 每小时执行上限
    limit = _get_guardrail("hourly_exec_limit", HOURLY_EXEC_LIMIT)
    if _hourly_exec_count(queue) >= limit:
        return f"hourly_limit_reached ({limit})"

    # 2. 同类动作冷却
    cooldown = _get_guardrail("same_action_cooldown_sec", SAME_ACTION_COOLDOWN_SEC)
    last_epoch = _last_same_action_epoch(queue, action_hash_val)
    if last_epoch > 0 and (time.time() - last_epoch) < cooldown:
        return f"cooldown ({cooldown}s)"

    # 3. 连续失败熔断
    breaker = _get_guardrail(
        "consecutive_fail_circuit_breaker", CONSECUTIVE_FAIL_CIRCUIT_BREAKER
    )
    if _consecutive_failures(queue) >= breaker:
        return f"circuit_breaker ({breaker} consecutive failures)"

    # 4. 预算压力
    threshold = _get_guardrail("budget_pressure_threshold", BUDGET_PRESSURE_THRESHOLD)
    budget = check_budget()
    pressure = max(budget.get("daily_pct", 0), budget.get("weekly_pct", 0))
    if pressure >= threshold and risk != RISK_LOW:
        return f"budget_pressure ({pressure:.0%} >= {threshold:.0%}, only low-risk allowed)"

    return None


# ── 入队 ──


def enqueue(action: dict) -> Optional[dict]:
    """
    将一个 pending action 入队。
    返回入队的 record，如果是重复则返回 None。
    """
    _ensure_dirs()
    queue = _load_queue()

    a_type = action.get("type", "unknown")
    target = action.get("detail", action.get("target", ""))
    params = action.get("params", {})
    h = action_hash(a_type, target, params)

    # 幂等：同 hash 且未终结的 action 不重复入队
    for r in queue:
        if r.get("hash") == h and r.get("status") not in TERMINAL_STATES:
            return None

    risk = classify_risk(action)

    record = {
        "id": uuid.uuid4().hex[:8],
        "hash": h,
        "ts_queued": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts_done": None,
        "type": a_type,
        "target": target,
        "params": params,
        "risk": risk,
        "priority": action.get("priority", "normal"),
        "status": STATUS_QUEUED,
        "result": None,
        "skip_reason": None,
        "source_trace_id": action.get("trace_id", ""),
        "executor": _infer_executor(a_type, params),
    }

    _append_queue(record)

    emit(
        LAYER_TOOL,
        "action_enqueued",
        "ok",
        payload={"id": record["id"], "type": a_type, "risk": risk, "hash": h},
    )

    return record


def _infer_executor(action_type: str, params: dict) -> str:
    """根据 action type / params 推断执行器"""
    if params.get("command"):
        return "shell"
    if params.get("url"):
        return "http"
    if params.get("tool"):
        return "tool"
    # 默认按 type 猜
    if action_type in ("shell", "http", "tool"):
        return action_type
    return "shell"


# ── 从 dispatcher 导入 ──


def ingest_pending_actions() -> int:
    """
    读取 dispatcher 的 pending_actions.jsonl，入队后清空。
    返回入队数量。
    """
    if not PENDING_ACTIONS_FILE.exists():
        return 0

    lines = PENDING_ACTIONS_FILE.read_text(encoding="utf-8").splitlines()
    count = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            action = json.loads(line)
            if enqueue(action):
                count += 1
        except Exception:
            continue

    # 清空已消费的 pending actions
    if count > 0:
        PENDING_ACTIONS_FILE.write_text("", encoding="utf-8")

    return count


# ── 执行一轮 ──


def run_queue(limit: int = 10) -> list[dict]:
    """
    消费一轮队列：
    1. 导入 pending actions
    2. 按优先级取 queued actions
    3. 护栏检查
    4. 风险分级决策
    5. 执行 / 跳过
    返回本轮处理的 records。
    """
    # 先导入新的 pending actions
    ingest_pending_actions()

    queue = _load_queue()
    queued = [r for r in queue if r["status"] == STATUS_QUEUED]

    # 按优先级排序：high > normal > low
    priority_order = {"high": 0, "normal": 1, "low": 2}
    queued.sort(key=lambda r: priority_order.get(r.get("priority", "normal"), 1))

    processed = []
    registry = get_registry()

    # medium 风险自动执行计数（本轮）
    medium_auto_count = 0
    medium_auto_limit = 5  # 每轮 medium 自动执行上限

    for record in queued[:limit]:
        risk = record.get("risk", RISK_LOW)

        # 风险分级决策
        if risk == RISK_HIGH:
            record["status"] = STATUS_SKIPPED
            record["skip_reason"] = "needs_approval"
            record["ts_done"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            emit(
                LAYER_SEC,
                "action_skipped_high_risk",
                "ok",
                payload={"id": record["id"], "type": record["type"]},
            )
            processed.append(record)
            continue

        # 护栏检查
        skip_reason = check_guardrails(queue, record["hash"], risk)
        if skip_reason:
            record["status"] = STATUS_SKIPPED
            record["skip_reason"] = skip_reason
            record["ts_done"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            emit(
                LAYER_SEC,
                "action_skipped_guardrail",
                "ok",
                payload={"id": record["id"], "reason": skip_reason},
            )
            processed.append(record)
            continue

        # medium 风险：限额 + 通知
        if risk == RISK_MEDIUM:
            if medium_auto_count >= medium_auto_limit:
                record["status"] = STATUS_SKIPPED
                record["skip_reason"] = "medium_risk_batch_limit"
                record["ts_done"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                processed.append(record)
                continue
            medium_auto_count += 1
            # 发送通知
            bus = get_bus()
            bus.emit(
                "action.medium_risk_auto",
                {
                    "id": record["id"],
                    "type": record["type"],
                    "target": record["target"],
                    "summary": f"自动执行 medium-risk: {record['type']}",
                },
                PRIORITY_HIGH,
                "action_engine",
            )
            emit(
                LAYER_COMMS,
                "action_medium_notify",
                "ok",
                payload={"id": record["id"], "type": record["type"]},
            )

        # 执行
        record["status"] = STATUS_EXECUTING
        executor = registry.get(record.get("executor", "shell"))
        if not executor:
            record["status"] = STATUS_FAILED
            record["result"] = f"no executor: {record.get('executor')}"
            record["ts_done"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            processed.append(record)
            continue

        result = executor.execute(record)
        record["ts_done"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        if result.ok:
            record["status"] = STATUS_SUCCEEDED
            record["result"] = result.detail
            emit(
                LAYER_TOOL,
                "action_succeeded",
                "ok",
                latency_ms=result.latency_ms,
                payload={"id": record["id"], "type": record["type"]},
            )
        else:
            record["status"] = STATUS_FAILED
            record["result"] = result.detail
            emit(
                LAYER_TOOL,
                "action_failed",
                "err",
                latency_ms=result.latency_ms,
                payload={
                    "id": record["id"],
                    "type": record["type"],
                    "error": result.detail[:200],
                },
            )

        processed.append(record)

    # 回写队列
    if processed:
        # 用 id 索引更新
        id_map = {r["id"]: r for r in processed}
        for i, r in enumerate(queue):
            if r["id"] in id_map:
                queue[i] = id_map[r["id"]]
        _save_queue(queue)

    return processed


# ── 查询 API ──


def get_status() -> dict:
    """队列状态摘要"""
    queue = _load_queue()
    counts = {}
    for r in queue:
        s = r.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1

    return {
        "total": len(queue),
        "by_status": counts,
        "queued": counts.get(STATUS_QUEUED, 0),
        "executing": counts.get(STATUS_EXECUTING, 0),
        "succeeded": counts.get(STATUS_SUCCEEDED, 0),
        "failed": counts.get(STATUS_FAILED, 0),
        "skipped": counts.get(STATUS_SKIPPED, 0),
        "hourly_exec_count": _hourly_exec_count(queue),
        "consecutive_failures": _consecutive_failures(queue),
    }


def get_history(limit: int = 20) -> list[dict]:
    """执行历史（已终结的 action，最近的在前）"""
    queue = _load_queue()
    done = [r for r in queue if r.get("status") in TERMINAL_STATES]
    done.sort(key=lambda r: r.get("ts_done", ""), reverse=True)
    return done[:limit]


def get_queued() -> list[dict]:
    """待执行的 action"""
    queue = _load_queue()
    return [r for r in queue if r.get("status") == STATUS_QUEUED]


# ── 格式化输出 ──


def _format_status(status: dict, fmt: str = "default") -> str:
    if fmt == "telegram":
        return (
            f"⚙️ Action Queue\n"
            f"待执行: {status['queued']} | 执行中: {status['executing']}\n"
            f"✅ {status['succeeded']} | ❌ {status['failed']} | ⏭️ {status['skipped']}\n"
            f"本小时已执行: {status['hourly_exec_count']}/{_get_guardrail('hourly_exec_limit', HOURLY_EXEC_LIMIT)}\n"
            f"连续失败: {status['consecutive_failures']}/{_get_guardrail('consecutive_fail_circuit_breaker', CONSECUTIVE_FAIL_CIRCUIT_BREAKER)}"
        )
    lines = [
        "=== Action Queue Status ===",
        f"Total: {status['total']}",
        f"  Queued:    {status['queued']}",
        f"  Executing: {status['executing']}",
        f"  Succeeded: {status['succeeded']}",
        f"  Failed:    {status['failed']}",
        f"  Skipped:   {status['skipped']}",
        f"",
        f"Hourly exec: {status['hourly_exec_count']}/{_get_guardrail('hourly_exec_limit', HOURLY_EXEC_LIMIT)}",
        f"Consecutive failures: {status['consecutive_failures']}/{_get_guardrail('consecutive_fail_circuit_breaker', CONSECUTIVE_FAIL_CIRCUIT_BREAKER)}",
    ]
    return "\n".join(lines)


def _format_history(records: list[dict], fmt: str = "default") -> str:
    if not records:
        return "📭 无执行历史" if fmt == "telegram" else "No history."

    if fmt == "telegram":
        lines = []
        for r in records:
            icon = {"succeeded": "✅", "failed": "❌", "skipped": "⏭️"}.get(
                r["status"], "❓"
            )
            skip = f" ({r['skip_reason']})" if r.get("skip_reason") else ""
            lines.append(f"{icon} [{r['id']}] {r['type']}{skip}")
            if r.get("result"):
                lines.append(f"   {str(r['result'])[:60]}")
        return "\n".join(lines)

    lines = []
    for r in records:
        lines.append(
            f"[{r.get('ts_done', '?')}] {r['id']} | {r['type']} → {r['status']}"
        )
        if r.get("skip_reason"):
            lines.append(f"  skip: {r['skip_reason']}")
        if r.get("result"):
            lines.append(f"  result: {str(r['result'])[:100]}")
        lines.append("")
    return "\n".join(lines)


def _format_run_result(processed: list[dict], fmt: str = "default") -> str:
    if not processed:
        return "📭 队列为空" if fmt == "telegram" else "Nothing to process."

    if fmt == "telegram":
        lines = [f"⚙️ 本轮处理 {len(processed)} 个 action:"]
        for r in processed:
            icon = {"succeeded": "✅", "failed": "❌", "skipped": "⏭️"}.get(
                r["status"], "❓"
            )
            lines.append(f"{icon} {r['type']} → {r['status']}")
        return "\n".join(lines)

    lines = [f"Processed {len(processed)} action(s):"]
    for r in processed:
        lines.append(f"  {r['id']} | {r['type']} → {r['status']}")
        if r.get("skip_reason"):
            lines.append(f"    skip: {r['skip_reason']}")
        if r.get("result"):
            lines.append(f"    result: {str(r['result'])[:80]}")
    return "\n".join(lines)


# ── CLI ──


def main():
    import argparse

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="AIOS Action Engine v0.6")
    parser.add_argument(
        "action",
        choices=["status", "run", "history", "ingest"],
        help="status=队列状态, run=消费一轮, history=执行历史, ingest=导入pending",
    )
    parser.add_argument("--limit", type=int, default=10, help="处理/显示数量上限")
    parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )
    args = parser.parse_args()

    if args.action == "status":
        print(_format_status(get_status(), args.format))

    elif args.action == "run":
        processed = run_queue(limit=args.limit)
        print(_format_run_result(processed, args.format))

    elif args.action == "history":
        records = get_history(limit=args.limit)
        print(_format_history(records, args.format))

    elif args.action == "ingest":
        count = ingest_pending_actions()
        if args.format == "telegram":
            print(f"📥 导入 {count} 个 pending action")
        else:
            print(f"Ingested {count} pending action(s)")


if __name__ == "__main__":
    main()

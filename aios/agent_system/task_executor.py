#!/usr/bin/env python3
"""
AIOS Task Executor - 从队列取任务并通过 sessions_spawn 真实执行

由小九在 OpenClaw 主会话中调用，读取 heartbeat 分发的任务，生成 spawn 指令。
用法（在 OpenClaw 中）:
  python task_executor.py          # 输出待执行任务的 JSON
  python task_executor.py --count  # 仅输出待执行数量
"""

import json
import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
try:
    from paths import TASK_QUEUE as QUEUE_PATH, TASK_EXECUTIONS as _EXEC_PATH
    EXEC_LOG = _EXEC_PATH
except ImportError:
    QUEUE_PATH = BASE_DIR / "data" / "task_queue.jsonl"
    EXEC_LOG = BASE_DIR / "data" / "task_executions_v2.jsonl"
MEMORY_LOG = BASE_DIR / "memory_retrieval_log.jsonl"

# ── Memory Retrieval 开关 ──
MEMORY_RETRIEVAL_ENABLED = os.environ.get("MEMORY_RETRIEVAL_ENABLED", "true").lower() == "true"
MEMORY_TIMEOUT_MS = int(os.environ.get("MEMORY_TIMEOUT_MS", "400"))
MEMORY_MAX_HINTS = int(os.environ.get("MEMORY_MAX_HINTS", "3"))
MEMORY_MAX_CHARS = int(os.environ.get("MEMORY_MAX_CHARS", "250"))


def _warn_optional_failure(event: str, **fields) -> None:
    """Emit a loud-but-nonblocking warning for optional integrations."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "warning",
        "event": event,
        **fields,
    }
    print(json.dumps(entry, ensure_ascii=False), file=sys.stderr, flush=True)


def _retrieve_with_timeout(task_desc: str, task_type: str) -> dict:
    """带超时的记忆检索，超时降级为空 context"""
    result = {"hits": [], "latency_ms": 0, "error": None}
    if not MEMORY_RETRIEVAL_ENABLED:
        result["error"] = "disabled"
        return result

    t0 = time.time()
    container = {}

    def _run():
        try:
            from memory_retrieval import query
            hits = query(task_desc, top_k=MEMORY_MAX_HINTS, task_type=task_type or None)
            container["hits"] = hits
        except Exception as e:
            container["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=MEMORY_TIMEOUT_MS / 1000.0)

    result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    if t.is_alive():
        result["error"] = f"timeout>{MEMORY_TIMEOUT_MS}ms"
    elif "error" in container:
        result["error"] = container["error"]
    else:
        result["hits"] = container.get("hits", [])
    return result


def build_memory_context(task_desc: str, task_type: str = "") -> dict:
    """
    检索记忆并构建 execution_context.memory_hints。
    返回:
      {
        "memory_hints": [...],   # 注入到 prompt 的摘要列表
        "memory_ids": [...],     # 用于 feedback 回写
        "retrieved_count": N,
        "used_count": N,
        "latency_ms": N,
        "degraded": bool,        # True = 超时/异常降级
      }
    """
    ret = _retrieve_with_timeout(task_desc, task_type)
    degraded = bool(ret["error"])
    hits = ret["hits"][:MEMORY_MAX_HINTS]

    hints = []
    ids = []
    for h in hits:
        text = h.get("text", "")[:MEMORY_MAX_CHARS]
        outcome = h.get("outcome", "?")
        score = h.get("_score", 0)
        hints.append(f"[{outcome}|score={score}] {text}")
        ids.append(h.get("id", ""))

    return {
        "memory_hints": hints,
        "memory_ids": ids,
        "retrieved_count": len(ret["hits"]),
        "used_count": len(hints),
        "latency_ms": ret["latency_ms"],
        "degraded": degraded,
        "error": ret.get("error"),
    }


def write_execution_record(
    task_id: str,
    agent_id: str,
    status: str,  # "completed" | "failed" | "timeout"
    start_time: str,
    end_time: str,
    duration_ms: int,
    retry_count: int = 0,
    side_effects: dict = None,
    error: str = None,
    result: dict = None,
    metadata: dict = None,
) -> None:
    """
    标准化执行记录写入 task_executions_v2.jsonl

    字段说明:
    - 核心字段(7个): task_id, agent_id, status, start_time, end_time, duration_ms, retry_count, side_effects
    - 条件字段: error(status=failed时), result(status=completed时), metadata(可选)

    side_effects 格式:
    {
      "files_written": ["path1", "path2"],
      "tasks_created": ["task-id-1"],
      "api_calls": 3
    }
    """
    record = {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
        "duration_ms": duration_ms,
        "retry_count": retry_count,
        "side_effects": side_effects or {"files_written": [], "tasks_created": [], "api_calls": 0},
    }

    # 条件字段
    if status == "failed" and error:
        record["error"] = error
    if status == "completed" and result:
        record["result"] = result
    if metadata:
        record["metadata"] = metadata

    with open(EXEC_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── Skill Memory 集成：自动追踪 Skill 执行 ──
    if "-skill" in agent_id.lower() or "skill-" in agent_id.lower():
        try:
            from skill_memory import skill_memory

            skill_id = agent_id.replace("-dispatcher", "")

            command = "unknown"
            if metadata and "command" in metadata:
                command = metadata["command"]
            elif result and isinstance(result, dict) and "command" in result:
                command = result["command"]

            skill_memory.track_execution(
                skill_id=skill_id,
                skill_name=skill_id.replace("-", " ").title(),
                task_id=task_id,
                command=command,
                status="success" if status == "completed" else "failed",
                duration_ms=duration_ms,
                input_params=metadata.get("input_params") if metadata else None,
                output_summary=str(result)[:200] if result else None,
                error=error,
                context={
                    "agent_id": agent_id,
                    "retry_count": retry_count,
                    "side_effects": side_effects
                }
            )
        except Exception as e:
            _warn_optional_failure(
                "skill_memory_track_failed",
                task_id=task_id,
                agent_id=agent_id,
                error=str(e),
            )


def write_memory_feedback(task_id: str, memory_ids: list, helpful: bool,
                          score: float, reason: str) -> None:
    """执行后写 feedback，成功/失败都写（避免只学习成功样本）"""
    if not memory_ids:
        return
    try:
        from memory_retrieval import feedback as mem_feedback
        for mid in memory_ids:
            if mid:
                mem_feedback(mid, helpful=helpful)
    except Exception as e:
        _warn_optional_failure(
            "memory_feedback_failed",
            task_id=task_id,
            error=str(e),
        )

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "memory_ids": memory_ids,
        "helpful": helpful,
        "score": score,
        "reason": reason,
    }
    with open(MEMORY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _log_memory_event(task_id: str, ctx: dict, phase: str) -> None:
    """结构化日志：retrieved_count, used_count, latency_ms"""
    tag = "DEGRADED" if ctx.get("degraded") else "OK"
    print(
        f"  [MEMORY:{phase}] {tag} | "
        f"retrieved={ctx.get('retrieved_count',0)} "
        f"used={ctx.get('used_count',0)} "
        f"latency={ctx.get('latency_ms',0)}ms"
        + (f" err={ctx['error']}" if ctx.get("error") else ""),
        flush=True,
    )

# Agent prompt 模板
AGENT_PROMPTS = {
    "coder": "You are a coding expert. Complete this task:\n{desc}\n\nWrite clean, tested code. Save output to test_runs/.",
    "analyst": "You are a data analyst. Complete this task:\n{desc}\n\nProvide data-driven insights. Save report to test_runs/.",
    "monitor": "You are a system monitor. Complete this task:\n{desc}\n\nCheck system metrics and report status. Save to test_runs/.",
    "reactor": "You are an auto-fixer. Complete this task:\n{desc}\n\nDiagnose and fix the issue. Save results to test_runs/.",
    "researcher": "You are a researcher. Complete this task:\n{desc}\n\nSearch, analyze, and summarize findings. Save to test_runs/.",
    "designer": "You are an architect. Complete this task:\n{desc}\n\nDesign the solution with clear diagrams/specs. Save to test_runs/.",
    "evolution": "You are the evolution engine. Complete this task:\n{desc}\n\nEvaluate and suggest improvements. Save to test_runs/.",
    "security": "You are a security auditor. Complete this task:\n{desc}\n\nAudit for vulnerabilities and risks. Save to test_runs/.",
    "automation": "You are an automation specialist. Complete this task:\n{desc}\n\nAutomate the process efficiently. Save to test_runs/.",
    "document": "You are a document processor. Complete this task:\n{desc}\n\nExtract, summarize, or generate documentation. Save to test_runs/.",
    "tester": "You are a test engineer. Complete this task:\n{desc}\n\nWrite comprehensive tests. Save to test_runs/.",
    "game-dev": "You are a game developer. Complete this task:\n{desc}\n\nCreate a fun, playable game. Save to test_runs/.",
}

SPAWN_CONFIG = {
    "coder":      {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},
    "analyst":    {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 120},
    "monitor":    {"model": "claude-sonnet-4-6",                       "timeout": 90},
    "reactor":    {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 120},
    "researcher": {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},
    "designer":   {"model": "claude-sonnet-4-6", "thinking": "high",   "timeout": 180},
    "evolution":  {"model": "claude-sonnet-4-6", "thinking": "high",   "timeout": 120},
    "security":   {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 90},
    "automation": {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 120},
    "document":   {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 90},
    "tester":     {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 120},
    "game-dev":   {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},
}


def get_pending_tasks():
    """获取待执行任务（status=running，已被 heartbeat 分发）"""
    if not QUEUE_PATH.exists():
        return []
    tasks = []
    for line in QUEUE_PATH.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                t = json.loads(line)
                if t.get("status") == "running":
                    tasks.append(t)
            except json.JSONDecodeError:
                continue
    return tasks


def generate_spawn_commands(tasks):
    """生成 spawn 命令列表（集成 Memory Retrieval）"""
    commands = []
    for task in tasks:
        agent_id = task["agent_id"]
        desc = task["description"]
        task_type = task.get("type", "")

        # 1. 检索记忆
        mem_ctx = build_memory_context(desc, task_type)
        _log_memory_event(task["id"], mem_ctx, "BUILD")

        # 2. 构建 prompt（注入 memory_hints）
        config = SPAWN_CONFIG.get(agent_id, {"model": "claude-sonnet-4-6", "timeout": 90})
        prompt_template = AGENT_PROMPTS.get(agent_id, "Complete this task:\n{desc}")
        base_prompt = prompt_template.format(desc=desc)

        if mem_ctx["memory_hints"]:
            hints_text = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(mem_ctx["memory_hints"]))
            injected_prompt = (
                f"[MEMORY] Relevant past experiences:\n{hints_text}\n\n"
                f"{base_prompt}"
            )
        else:
            injected_prompt = base_prompt

        # 3. 生成 spawn 命令
        cmd = {
            "task": injected_prompt,
            "label": f"agent-{agent_id}",
            "model": config.get("model", "claude-sonnet-4-6"),
            "runTimeoutSeconds": config.get("timeout", 90),
        }
        if config.get("thinking"):
            cmd["thinking"] = config["thinking"]

        commands.append({
            "task_id": task["id"],
            "agent_id": agent_id,
            "model_used": config.get("model", "claude-sonnet-4-6"),
            "spawn": cmd,
            "memory_context": mem_ctx,
        })
    return commands


def mark_tasks_dispatched(task_ids):
    """标记任务为已分发"""
    if not QUEUE_PATH.exists():
        return
    lines = QUEUE_PATH.read_text(encoding="utf-8").strip().split("\n")
    new_lines = []
    for line in lines:
        if line.strip():
            try:
                t = json.loads(line)
                if t.get("id") in task_ids:
                    t["status"] = "dispatched"
                    t["dispatched_at"] = datetime.now(timezone.utc).isoformat()
                new_lines.append(json.dumps(t, ensure_ascii=False))
            except json.JSONDecodeError:
                new_lines.append(line)
    QUEUE_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main():
    if "--count" in sys.argv:
        tasks = get_pending_tasks()
        print(len(tasks))
        return

    tasks = get_pending_tasks()
    if not tasks:
        print(json.dumps({"status": "empty", "tasks": []}, ensure_ascii=False))
        return

    commands = generate_spawn_commands(tasks)

    # 输出 JSON（供 OpenClaw 读取）
    output = {
        "status": "ready",
        "count": len(commands),
        "commands": commands,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # 标记为已分发
    mark_tasks_dispatched([t["id"] for t in tasks])


if __name__ == "__main__":
    main()

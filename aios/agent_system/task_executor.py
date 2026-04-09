#!/usr/bin/env python3
"""
AIOS Task Executor - 浠庨槦鍒楀彇浠诲姟骞堕€氳繃 sessions_spawn 鐪熷疄鎵ц

杩欎釜鑴氭湰鐢卞皬涔濆湪 OpenClaw 涓讳細璇濅腑璋冪敤锛?璇诲彇 heartbeat 鍒嗗彂鐨勪换鍔★紝鐢熸垚 spawn 鎸囦护銆?
鐢ㄦ硶锛堝湪 OpenClaw 涓級:
  python task_executor.py          # 杈撳嚭寰呮墽琛屼换鍔＄殑 JSON
  python task_executor.py --count  # 浠呰緭鍑哄緟鎵ц鏁伴噺
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

# 鈹€鈹€ Memory Retrieval 寮€鍏?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
MEMORY_RETRIEVAL_ENABLED = os.environ.get("MEMORY_RETRIEVAL_ENABLED", "true").lower() == "true"
MEMORY_TIMEOUT_MS = int(os.environ.get("MEMORY_TIMEOUT_MS", "400"))   # 闄嶇骇闃堝€?MEMORY_MAX_HINTS = int(os.environ.get("MEMORY_MAX_HINTS", "3"))        # 鏈€澶氭敞鍏ユ潯鏁?MEMORY_MAX_CHARS = int(os.environ.get("MEMORY_MAX_CHARS", "250"))      # 姣忔潯鎽樿瀛楃鏁?

def _retrieve_with_timeout(task_desc: str, task_type: str) -> dict:
    """甯﹁秴鏃剁殑璁板繂妫€绱紝瓒呮椂闄嶇骇涓虹┖ context銆?""
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
    妫€绱㈣蹇嗗苟鏋勫缓 execution_context.memory_hints銆?    杩斿洖:
      {
        "memory_hints": [...],   # 娉ㄥ叆鍒?prompt 鐨勬憳瑕佸垪琛?        "memory_ids": [...],     # 鐢ㄤ簬 feedback 鍥炲啓
        "retrieved_count": N,
        "used_count": N,
        "latency_ms": N,
        "degraded": bool,        # True = 瓒呮椂/寮傚父闄嶇骇
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
    鏍囧噯鍖栨墽琛岃褰曞啓鍏?task_executions_v2.jsonl
    
    瀛楁璇存槑锛?    - 鏍稿績瀛楁锛?涓級锛歵ask_id, agent_id, status, start_time, end_time, duration_ms, retry_count, side_effects
    - 鏉′欢瀛楁锛歟rror锛坰tatus=failed鏃讹級, result锛坰tatus=completed鏃讹級, metadata锛堝彲閫夛級
    
    side_effects 鏍煎紡锛?    {
      "files_written": ["path1", "path2"],
      "tasks_created": ["task-id-1"],
      "api_calls": 3
    }
    
    TODO: auto-collect side_effects - 褰撳墠闇€瑕佹墜鍔ㄤ紶鍏ワ紝鏈潵搴斿湪 task_executor 閲?hook 鏂囦欢鍐欏叆鍜屼换鍔″垱寤虹殑璋冪敤鐐硅嚜鍔ㄦ敹闆?    """
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
    
    # 鏉′欢瀛楁
    if status == "failed" and error:
        record["error"] = error
    if status == "completed" and result:
        record["result"] = result
    if metadata:
        record["metadata"] = metadata
    
    with open(EXEC_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # 鈹€鈹€ Skill Memory 闆嗘垚锛氳嚜鍔ㄨ拷韪?Skill 鎵ц 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # 濡傛灉 agent_id 鏄?Skill锛堝寘鍚?"-skill" 鎴?"skill-"锛夛紝鑷姩璁板綍鍒?Skill Memory
    if "-skill" in agent_id.lower() or "skill-" in agent_id.lower():
        try:
            from skill_memory import skill_memory
            
            # 鎻愬彇 skill_id锛堝幓鎺?-dispatcher 鍚庣紑锛?            skill_id = agent_id.replace("-dispatcher", "")
            
            # 鏋勫缓 command锛堜粠 metadata 鎴?result 涓彁鍙栵級
            command = "unknown"
            if metadata and "command" in metadata:
                command = metadata["command"]
            elif result and isinstance(result, dict) and "command" in result:
                command = result["command"]
            
            # 璁板綍鎵ц
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
            # 闈欓粯澶辫触锛屼笉褰卞搷涓绘祦绋?            pass


def write_memory_feedback(task_id: str, memory_ids: list, helpful: bool,
                          score: float, reason: str) -> None:
    """鎵ц鍚庡啓 feedback锛屾垚鍔?澶辫触閮藉啓锛堥伩鍏嶅彧瀛︿範鎴愬姛鏍锋湰锛夈€?""
    if not memory_ids:
        return
    try:
        from memory_retrieval import feedback as mem_feedback
        for mid in memory_ids:
            if mid:
                mem_feedback(mid, helpful=helpful)
    except Exception:
        pass  # feedback 澶辫触涓嶅奖鍝嶄富娴佺▼

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
    """缁撴瀯鍖栨棩蹇楋細retrieved_count, used_count, latency_ms, feedback_written"""
    tag = "DEGRADED" if ctx.get("degraded") else "OK"
    print(
        f"  [MEMORY:{phase}] {tag} | "
        f"retrieved={ctx.get('retrieved_count',0)} "
        f"used={ctx.get('used_count',0)} "
        f"latency={ctx.get('latency_ms',0)}ms"
        + (f" err={ctx['error']}" if ctx.get("error") else ""),
        flush=True,
    )

# Agent prompt 妯℃澘
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
    "coder":      {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},  # 澧炲姞鍒?180s (lesson-001)
    "analyst":    {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 120},  # 澧炲姞鍒?120s
    "monitor":    {"model": "claude-sonnet-4-6",                       "timeout": 90},   # 澧炲姞鍒?90s
    "reactor":    {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 120},  # 澧炲姞鍒?120s
    "researcher": {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},  # 澧炲姞鍒?180s (lesson-001)
    "designer":   {"model": "claude-sonnet-4-6", "thinking": "high",   "timeout": 180},  # 澧炲姞鍒?180s (lesson-001)
    "evolution":  {"model": "claude-sonnet-4-6", "thinking": "high",   "timeout": 120},  # 澧炲姞鍒?120s
    "security":   {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 90},   # 澧炲姞鍒?90s
    "automation": {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 120},  # 澧炲姞鍒?120s
    "document":   {"model": "claude-sonnet-4-6", "thinking": "low",    "timeout": 90},   # 澧炲姞鍒?90s
    "tester":     {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 120},  # 澧炲姞鍒?120s
    "game-dev":   {"model": "claude-sonnet-4-6", "thinking": "medium", "timeout": 180},  # 澧炲姞鍒?180s (lesson-001)
}


def get_pending_tasks():
    """鑾峰彇寰呮墽琛屼换鍔★紙status=running锛屽凡琚?heartbeat 鍒嗗彂锛?""
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
    """鐢熸垚 spawn 鍛戒护鍒楄〃锛堥泦鎴?Memory Retrieval锛?""
    commands = []
    for task in tasks:
        agent_id = task["agent_id"]
        desc = task["description"]
        task_type = task.get("type", "")

        # 鈹€鈹€ 1. 妫€绱㈣蹇?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
        mem_ctx = build_memory_context(desc, task_type)
        _log_memory_event(task["id"], mem_ctx, "BUILD")

        # 鈹€鈹€ 2. 鏋勫缓 prompt锛堟敞鍏?memory_hints锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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

        # 鈹€鈹€ 3. 鐢熸垚 spawn 鍛戒护 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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
            "memory_context": mem_ctx,  # 淇濈暀鐢ㄤ簬 feedback
        })
    return commands


def mark_tasks_dispatched(task_ids):
    """鏍囪浠诲姟涓哄凡鍒嗗彂"""
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

    # 杈撳嚭 JSON锛堜緵 OpenClaw 璇诲彇锛?    output = {
        "status": "ready",
        "count": len(commands),
        "commands": commands,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # 鏍囪涓哄凡鍒嗗彂
    mark_tasks_dispatched([t["id"] for t in tasks])


if __name__ == "__main__":
    main()


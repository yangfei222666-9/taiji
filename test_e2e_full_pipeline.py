#!/usr/bin/env python3
"""
TaijiOS 端到端全链路测试
启动系统 → 提交任务 → 五引擎路由 → Agent 执行 → 结果写回
+ taijios-lite 多轮对话（DeepSeek API）

用法: python test_e2e_full_pipeline.py
"""
import sys, os, io, json, time, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone

os.environ["PYTHONUTF8"] = "1"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── 路径 ──
AIOS_DIR = Path(__file__).parent / "aios"
AGENT_SYS = AIOS_DIR / "agent_system"
LITE_DIR = Path(__file__).parent / "taijios-lite"
# aios/ 必须在 agent_system/ 之前（在 sys.path 中），避免 agent_system/core/ 覆盖 aios/core/
# insert(0) 会把后插入的放到最前面，所以 AIOS_DIR 最后插入 = 最优先
sys.path.insert(0, str(LITE_DIR))
sys.path.insert(0, str(AGENT_SYS))
sys.path.insert(0, str(AIOS_DIR))

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY")
MODEL_CONFIG = {
    "provider": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "api_key": DEEPSEEK_KEY,
}

results = {"passed": 0, "failed": 0, "errors": []}


def check(name, condition, detail=""):
    if condition:
        results["passed"] += 1
        print(f"  ✅ {name}")
    else:
        results["failed"] += 1
        results["errors"].append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


# ═══════════════════════════════════════════════════════════════
# PHASE 1: AIOS 核心引擎（无网络）
# ═══════════════════════════════════════════════════════════════
def test_phase1_core_engine():
    print("\n" + "═" * 60)
    print("  PHASE 1: AIOS 核心引擎")
    print("═" * 60)

    # 1.1 事件发射
    print("\n[1.1] 事件发射 (engine.emit)")
    tmpdir = tempfile.mkdtemp()
    try:
        from unittest.mock import patch
        import core.engine as engine_mod
        from core.engine import emit, LAYER_KERNEL, LAYER_TOOL, LAYER_SEC
        events_file = Path(tmpdir) / "events.jsonl"
        with patch.object(engine_mod, "_events_path", return_value=events_file):
            r1 = emit(LAYER_KERNEL, "system_boot", "ok", payload={"version": "0.2.0"})
            r2 = emit(LAYER_TOOL, "tool_exec", "ok", latency_ms=42, payload={"name": "test_tool"})
            r3 = emit(LAYER_SEC, "auth_fail", "err", payload={"reason": "bad_token"})

        lines = events_file.read_text(encoding="utf-8").strip().split("\n")
        check("emit 写入 3 条事件", len(lines) == 3, f"got {len(lines)}")
        check("KERNEL 事件 severity=INFO", r1["severity"] == "INFO")
        check("SEC err severity=CRIT", r3["severity"] == "CRIT")
        check("latency_ms 字段", r2.get("latency_ms") == 42)
    finally:
        shutil.rmtree(tmpdir)

    # 1.2 执行器幂等
    print("\n[1.2] 执行器幂等 (executor)")
    import core.executor as executor_mod
    from core.executor import idempotency_guard
    tmpdir2 = tempfile.mkdtemp()
    try:
        dedup = Path(tmpdir2) / "dedup.json"
        with patch.object(executor_mod, "DEDUP_STATE", dedup):
            ok1 = idempotency_guard("test_cmd", window=10)
            ok2 = idempotency_guard("test_cmd", window=10)
            ok3 = idempotency_guard("other_cmd", window=10)
        check("首次执行允许", ok1 is None)  # None = allow
        check("重复执行拦截", ok2 is not None)  # dict = blocked
        check("不同命令允许", ok3 is None)
    finally:
        shutil.rmtree(tmpdir2)


# ═══════════════════════════════════════════════════════════════
# PHASE 2: 五引擎路由
# ═══════════════════════════════════════════════════════════════
def test_phase2_router():
    print("\n" + "═" * 60)
    print("  PHASE 2: 五引擎路由 (TaskRouter)")
    print("═" * 60)

    # task_router 需要 agent_system/core/（含 status_adapter），
    # 而 Phase 1 已缓存 aios/core/。清除缓存让它重新解析。
    for mod_name in list(sys.modules.keys()):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    # 临时把 agent_system/ 放到最前
    old_path = sys.path[:]
    sys.path.insert(0, str(AGENT_SYS))

    tmpdir = tempfile.mkdtemp()
    try:
        from unittest.mock import patch
        import task_router as tr_mod
        from task_router import TaskRouter
        queue = Path(tmpdir) / "task_queue.jsonl"
        queue.write_text("", encoding="utf-8")

        with patch.object(tr_mod, "QUEUE_PATH", queue), \
             patch.object(tr_mod, "ROUTE_LOG_PATH", Path(tmpdir) / "route_log.jsonl"), \
             patch.object(tr_mod, "STATS_PATH", Path(tmpdir) / "router_stats.json"):
            router = TaskRouter()

            # 提交多种任务并验证路由有输出
            test_cases = [
                "写一个 Python 排序函数",
                "分析最近一周的错误日志",
                "检查系统健康度",
                "调试内存泄漏问题",
                "写单元测试覆盖 executor",
            ]

            for desc in test_cases:
                task = router.submit(desc, priority="normal")
                route = router.route(desc)
                check(f"路由 '{desc[:15]}…' → {route.task_type}/{route.agent_id}",
                      bool(route.agent_id and route.task_type),
                      f"type={route.task_type} agent={route.agent_id}")

        # 验证队列写入
        lines = [l for l in queue.read_text(encoding="utf-8").strip().split("\n") if l.strip()]
        check(f"队列写入 {len(test_cases)} 条", len(lines) == len(test_cases), f"got {len(lines)}")

    finally:
        shutil.rmtree(tmpdir)
        # 恢复 path 和 core 模块
        sys.path[:] = old_path
        for mod_name in list(sys.modules.keys()):
            if mod_name == "core" or mod_name.startswith("core."):
                del sys.modules[mod_name]


# ═══════════════════════════════════════════════════════════════
# PHASE 3: Agent 执行 + 结果写回
# ═══════════════════════════════════════════════════════════════
def test_phase3_execute_writeback():
    print("\n" + "═" * 60)
    print("  PHASE 3: Agent 执行 + 结果写回")
    print("═" * 60)

    # agent_system 的 task_executor 需要 agent_system 在 path 最前
    for mod_name in list(sys.modules.keys()):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    old_path = sys.path[:]
    sys.path.insert(0, str(AGENT_SYS))

    tmpdir = tempfile.mkdtemp()
    try:
        from unittest.mock import patch
        queue = Path(tmpdir) / "task_queue.jsonl"
        exec_log = Path(tmpdir) / "task_executions_v2.jsonl"

        # 写入一个 running 任务
        task = {
            "id": "task-e2e-001",
            "description": "写一个 hello world 脚本",
            "type": "code",
            "agent_id": "coder",
            "priority": "normal",
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        queue.write_text(json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8")

        import task_executor
        with patch.object(task_executor, "QUEUE_PATH", queue), \
             patch.object(task_executor, "EXEC_LOG", exec_log), \
             patch.object(task_executor, "build_memory_context",
                          return_value={"memory_hints": ["[success|score=0.9] 上次用 Claude 写排序成功"],
                                        "memory_ids": ["mem-001"],
                                        "retrieved_count": 1, "used_count": 1,
                                        "latency_ms": 50, "degraded": False, "error": None}):

            # 3a. 取待执行任务
            pending = task_executor.get_pending_tasks()
            check("get_pending_tasks 取到任务", len(pending) == 1)

            # 3b. 生成 spawn 命令
            commands = task_executor.generate_spawn_commands(pending)
            check("generate_spawn_commands 生成命令", len(commands) == 1)
            cmd = commands[0]
            check("spawn.task 包含 memory hint", "MEMORY" in cmd["spawn"]["task"])
            check("model 配置正确", "claude" in cmd["model_used"].lower() or "sonnet" in cmd["model_used"].lower())

            # 3c. 写回执行记录
            start = datetime.now(timezone.utc).isoformat()
            time.sleep(0.01)
            end = datetime.now(timezone.utc).isoformat()
            task_executor.write_execution_record(
                task_id="task-e2e-001",
                agent_id="coder",
                status="completed",
                start_time=start,
                end_time=end,
                duration_ms=1234,
                result={"output": "hello world script created"},
                side_effects={"files_written": ["test_runs/hello.py"], "tasks_created": [], "api_calls": 1},
            )

            # 验证写回
            exec_lines = exec_log.read_text(encoding="utf-8").strip().split("\n")
            check("execution_record 写入", len(exec_lines) == 1)
            rec = json.loads(exec_lines[0])
            check("record.status = completed", rec["status"] == "completed")
            check("record.duration_ms = 1234", rec["duration_ms"] == 1234)
            check("record.side_effects 有 files_written", len(rec["side_effects"]["files_written"]) == 1)

            # 3d. 标记已分发
            task_executor.mark_tasks_dispatched(["task-e2e-001"])
            after = task_executor.get_pending_tasks()
            check("分发后 pending 为空", len(after) == 0)

    finally:
        shutil.rmtree(tmpdir)
        sys.path[:] = old_path
        for mod_name in list(sys.modules.keys()):
            if mod_name == "core" or mod_name.startswith("core."):
                del sys.modules[mod_name]


# ═══════════════════════════════════════════════════════════════
# PHASE 4: Lifecycle Engine
# ═══════════════════════════════════════════════════════════════
def test_phase4_lifecycle():
    print("\n" + "═" * 60)
    print("  PHASE 4: Agent 生命周期引擎")
    print("═" * 60)

    # lifecycle engine 在 agent_system/ 下
    sys.path.insert(0, str(AGENT_SYS))

    tmpdir = tempfile.mkdtemp()
    try:
        from unittest.mock import patch
        exec_path = Path(tmpdir) / "task_executions_v2.jsonl"
        agents_path = Path(tmpdir) / "agents.json"

        # 写入执行记录（模拟健康 agent）
        for i in range(10):
            rec = {
                "agent_id": "coder",
                "status": "completed" if i < 8 else "failed",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 100 + i * 10,
            }
            with open(exec_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

        # 写入 agents.json
        agents_data = {
            "agents": [
                {"id": "coder", "name": "coder", "lifecycle_state": "active"},
                {"id": "analyst", "name": "analyst", "lifecycle_state": "active"},
            ]
        }
        agents_path.write_text(json.dumps(agents_data), encoding="utf-8")

        with patch("agent_lifecycle_engine.TASK_EXECUTIONS", exec_path), \
             patch("agent_lifecycle_engine.AGENTS_STATE", agents_path):
            from agent_lifecycle_engine import run_lifecycle_engine, calculate_all_lifecycle_scores

            scores = calculate_all_lifecycle_scores()
            check("lifecycle 计算出 coder 评分", "coder" in scores)
            check("coder 保持 active（失败率20%<70%）", scores["coder"]["lifecycle_state"] == "active")

            summary = run_lifecycle_engine()
            check("lifecycle engine 返回 summary", isinstance(summary, dict) and len(summary) > 0)

            # 验证写回
            updated_agents = json.loads(agents_path.read_text(encoding="utf-8"))
            coder = [a for a in updated_agents["agents"] if a["id"] == "coder"][0]
            check("agents.json 写回 lifecycle_state", "lifecycle_state" in coder)

    finally:
        shutil.rmtree(tmpdir)


# ═══════════════════════════════════════════════════════════════
# PHASE 5: TaijiOS-Lite 多轮真实对话（DeepSeek API）
# ═══════════════════════════════════════════════════════════════
def test_phase5_live_conversation():
    print("\n" + "═" * 60)
    print("  PHASE 5: TaijiOS-Lite 多轮对话（DeepSeek API）")
    print("═" * 60)

    from bot_core import TaijiBot

    bot = TaijiBot(MODEL_CONFIG)
    user_id = f"e2e_test_{int(time.time())}"
    user_name = "小九"

    rounds = [
        ("我想做一个AI认知军师产品，你觉得怎么样？", ["主公", "好", "方向", "产品", "资源", "认知", "军师", "做", "核心", "开"]),
        ("竞品太多了，怎么做差异化？", ["对手", "优势", "竞", "聚焦", "逻辑", "不同", "核心", "差异", "独", "深"]),
        ("我只有5万块，一个人干，怎么冷启动？", ["先", "做", "小", "聚焦", "产品", "原型", "测", "用户", "最小", "钱"]),
        ("最近焦虑，觉得在自嗨怎么办？", ["做", "焦虑", "行动", "写", "看", "今天", "先", "不是", "循环", "产品"]),
        ("好的收到，我先去找10个种子用户", ["先", "做", "产品", "原型", "用户", "给", "好", "对", "行动", "今"]),
        ("找到3个了，他们愿意付费，下一步？", ["好", "先", "设计", "付费", "定价", "服务", "产品", "用户", "简单", "立刻"]),
    ]

    all_replies = []
    for i, (msg, keywords) in enumerate(rounds, 1):
        print(f"\n{'━' * 55}")
        print(f"  第{i}轮 | 用户: {msg[:40]}")

        t0 = time.time()
        try:
            reply = bot.handle_message(user_id, user_name, msg)
            elapsed = time.time() - t0
        except Exception as e:
            elapsed = time.time() - t0
            check(f"第{i}轮 API 调用", False, f"异常: {str(e)[:80]}")
            continue

        short = reply[:80].replace("\n", " ")
        print(f"  军师({elapsed:.1f}s): {short}...")
        all_replies.append(reply)

        # 基础检查
        check(f"第{i}轮 回复非空且>20字", len(reply) > 20, f"len={len(reply)}")
        check(f"第{i}轮 延迟<30s", elapsed < 30, f"{elapsed:.1f}s")

        # 关键词命中（至少命中1个）
        hit = [kw for kw in keywords if kw in reply]
        check(f"第{i}轮 关键词命中({len(hit)}/{len(keywords)})",
              len(hit) >= 1, f"miss={[kw for kw in keywords if kw not in reply]}")

        # 非套话
        boilerplate = ["作为AI", "作为语言模型", "我无法", "I'm an AI"]
        has_boilerplate = any(b in reply for b in boilerplate)
        check(f"第{i}轮 非套话", not has_boilerplate)

        if i < len(rounds):
            time.sleep(1)

    # 总体质量
    if all_replies:
        avg_len = sum(len(r) for r in all_replies) / len(all_replies)
        check(f"平均回复长度>30字", avg_len > 30, f"avg={avg_len:.0f}")

    # 卦象引擎状态
    session = bot.get_session(user_id)
    hex_name = session.hexagram.current_hexagram
    lines = session.hexagram.current_lines
    from evolution.hexagram import HEXAGRAM_STRATEGIES
    strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
    print(f"\n  卦象: {strat.get('name', hex_name)} {''.join('⚊' if l == 1 else '⚋' for l in lines)}")
    print(f"  策略: {strat.get('strategy', 'N/A')[:60]}")
    check("卦象引擎有输出", bool(hex_name))

    # 认知地图
    cog_map = session.cognitive.map
    total_entries = sum(len(v) if isinstance(v, (list, dict)) else (1 if v else 0) for v in cog_map.values())
    check(f"认知地图有条目({total_entries})", total_entries > 0)

    # 清理
    session.reset()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("╔" + "═" * 58 + "╗")
    print("║  TaijiOS 端到端全链路测试                             ║")
    print("║  启动系统 → 提交任务 → 五引擎路由 → Agent执行 → 结果写回  ║")
    print("╚" + "═" * 58 + "╝")

    t_start = time.time()

    try:
        test_phase1_core_engine()
        test_phase2_router()
        test_phase3_execute_writeback()
        test_phase4_lifecycle()
        test_phase5_live_conversation()
    except Exception as e:
        print(f"\n💥 致命错误: {e}")
        import traceback
        traceback.print_exc()
        results["failed"] += 1
        results["errors"].append(f"FATAL: {e}")

    elapsed = time.time() - t_start
    total = results["passed"] + results["failed"]

    print(f"\n{'═' * 60}")
    print(f"  总计: {total} 项 | ✅ {results['passed']} 通过 | ❌ {results['failed']} 失败 | ⏱ {elapsed:.1f}s")
    if results["errors"]:
        print(f"\n  失败项:")
        for e in results["errors"]:
            print(f"    • {e}")
    print(f"{'═' * 60}")

    if results["failed"] == 0:
        print("\n  🟢 全链路全绿，可以打 tag")
    else:
        print(f"\n  🔴 有 {results['failed']} 项失败，修复后再打 tag")

    sys.exit(0 if results["failed"] == 0 else 1)

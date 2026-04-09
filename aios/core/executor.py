# aios/core/executor.py - 通用执行器 v0.1
"""
三大能力：
1. idempotency_guard  — 命令去重窗口（同一 command_key N秒内只执行一次）
2. preflight_check    — 预检（进程已存在→NOOP，文件锁等）
3. classify_error     — 错误分类（RETRYABLE / NON_RETRYABLE）

终态：SUCCESS / NOOP_ALREADY_RUNNING / NOOP_DEDUP / FAILED_RETRYABLE / FAILED_NON_RETRYABLE
每次执行结果写入 execution_log.jsonl 供审计。
"""

import json, time, re, subprocess, sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.engine import emit, LAYER_TOOL

# ── 配置 ──

EXEC_LOG = Path(__file__).resolve().parent.parent / "events" / "execution_log.jsonl"
DEDUP_STATE = Path(__file__).resolve().parent.parent / "events" / "dedup_state.json"
DEFAULT_DEDUP_WINDOW = 60  # 秒

# 不可重试的错误模式（正则）
NON_RETRYABLE_PATTERNS = [
    r"WnsUniversalSDK",  # 环境/依赖错误
    r"FileNotFoundError",  # 文件不存在
    r"ModuleNotFoundError",  # 模块缺失
    r"PermissionError",  # 权限不足
    r"Access is denied",  # Windows 权限
    r"not recognized as.*command",  # 命令不存在
    r"No such file or directory",  # 路径不存在
    r"ImportError",  # 导入失败
    r"SyntaxError",  # 语法错误
]

# ── 终态常量 ──

SUCCESS = "SUCCESS"
NOOP_ALREADY_RUNNING = "NOOP_ALREADY_RUNNING"
NOOP_DEDUP = "NOOP_DEDUP"
FAILED_RETRYABLE = "FAILED_RETRYABLE"
FAILED_NON_RETRYABLE = "FAILED_NON_RETRYABLE"


# ── 执行日志 ──


def _log_execution(
    command_key: str,
    terminal_state: str,
    reason_code: str,
    detail: str = "",
    latency_ms: int = 0,
):
    """写入 execution_log.jsonl + emit 事件"""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": int(time.time()),
        "command_key": command_key,
        "terminal_state": terminal_state,
        "reason_code": reason_code,
        "detail": detail[:500] if detail else "",
        "latency_ms": latency_ms,
    }
    EXEC_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXEC_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 同步 emit 到事件流
    status = (
        "ok" if terminal_state in (SUCCESS, NOOP_ALREADY_RUNNING, NOOP_DEDUP) else "err"
    )
    emit(
        LAYER_TOOL,
        f"exec_{command_key}",
        status,
        latency_ms,
        {"terminal_state": terminal_state, "reason_code": reason_code},
    )

    return record


# ── 1. 幂等去重 ──


def _load_dedup() -> dict:
    if DEDUP_STATE.exists():
        try:
            return json.loads(DEDUP_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_dedup(state: dict):
    DEDUP_STATE.parent.mkdir(parents=True, exist_ok=True)
    DEDUP_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def idempotency_guard(
    command_key: str, window: int = DEFAULT_DEDUP_WINDOW
) -> Optional[dict]:
    """
    检查 command_key 是否在 window 秒内已执行过。
    如果是 → 返回 NOOP_DEDUP 结果（调用方应短路）。
    如果否 → 返回 None（允许执行），并记录时间戳。
    """
    state = _load_dedup()
    now = time.time()

    # 清理过期条目
    state = {k: v for k, v in state.items() if now - v < 300}

    last = state.get(command_key, 0)
    if now - last < window:
        result = _log_execution(
            command_key,
            NOOP_DEDUP,
            "dedup_window",
            f"上次执行 {int(now - last)}s 前，窗口 {window}s",
        )
        _save_dedup(state)
        return result

    # 标记本次执行
    state[command_key] = now
    _save_dedup(state)
    return None


# ── 2. 预检 ──


def preflight_check(action: str, process_name: str = None) -> Optional[dict]:
    """
    执行前预检。当前支持：
    - 进程存在检查：如果 process_name 已在运行，返回 NOOP_ALREADY_RUNNING

    返回 None = 预检通过，可以执行。
    返回 dict = 应短路，不执行。
    """
    if process_name:
        if _is_process_running(process_name):
            return _log_execution(
                action,
                NOOP_ALREADY_RUNNING,
                "process_exists",
                f"{process_name} 已在运行",
            )
    return None


def _is_process_running(name: str) -> bool:
    """检查 Windows 进程是否存在"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # tasklist 输出包含进程名 = 正在运行
        return name.lower() in r.stdout.lower()
    except Exception:
        return False


# ── 3. 错误分类 ──


def classify_error(err: str) -> str:
    """
    分类错误：
    - NON_RETRYABLE: 环境/依赖/权限问题，重试无意义
    - RETRYABLE: 网络超时、临时故障等
    """
    if not err:
        return "RETRYABLE"

    for pattern in NON_RETRYABLE_PATTERNS:
        if re.search(pattern, err, re.IGNORECASE):
            return "NON_RETRYABLE"

    return "RETRYABLE"


# ── 4. 统一执行入口 ──


def execute(
    command_key: str,
    fn,
    *args,
    dedup_window: int = DEFAULT_DEDUP_WINDOW,
    process_name: str = None,
    **kwargs,
) -> dict:
    """
    通用执行入口，自动串联：去重 → 预检 → 执行 → 错误分类 → 终态回写。

    command_key: 命令标识（如 "open_qqmusic"）
    fn: 实际执行函数，应返回 (ok: bool, result_or_error: str)
    process_name: 可选，预检用的进程名（如 "QQMusic.exe"）
    dedup_window: 去重窗口秒数

    返回 execution record dict。
    """
    # Step 1: 去重
    dedup = idempotency_guard(command_key, dedup_window)
    if dedup:
        return dedup

    # Step 2: 预检
    preflight = preflight_check(command_key, process_name)
    if preflight:
        return preflight

    # Step 3: 执行
    t0 = time.monotonic()
    try:
        ok, detail = fn(*args, **kwargs)
        ms = round((time.monotonic() - t0) * 1000)

        if ok:
            return _log_execution(command_key, SUCCESS, "executed", detail, ms)
        else:
            # Step 4: 错误分类
            err_class = classify_error(detail)
            terminal = (
                FAILED_NON_RETRYABLE
                if err_class == "NON_RETRYABLE"
                else FAILED_RETRYABLE
            )
            return _log_execution(command_key, terminal, err_class, detail, ms)

    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000)
        err_str = str(e)
        err_class = classify_error(err_str)
        terminal = (
            FAILED_NON_RETRYABLE if err_class == "NON_RETRYABLE" else FAILED_RETRYABLE
        )
        return _log_execution(command_key, terminal, err_class, err_str, ms)


# ── CLI 测试 ──

if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) < 2:
        print("用法: executor.py [test|log|dedup-clear]")
        print("  test        — 跑一轮测试（去重+预检+执行）")
        print("  log         — 查看最近执行日志")
        print("  dedup-clear — 清空去重状态")
        _sys.exit(0)

    cmd = _sys.argv[1]

    if cmd == "test":
        # 模拟执行
        def fake_task():
            return True, "模拟执行成功"

        r1 = execute("test_cmd", fake_task, dedup_window=10)
        print(f"第1次: {r1['terminal_state']} ({r1['reason_code']})")

        r2 = execute("test_cmd", fake_task, dedup_window=10)
        print(f"第2次: {r2['terminal_state']} ({r2['reason_code']})")

        # 模拟失败
        def fail_task():
            return False, "WnsUniversalSDK create failed"

        r3 = execute("test_fail", fail_task, dedup_window=5)
        print(f"失败: {r3['terminal_state']} ({r3['reason_code']})")

    elif cmd == "log":
        if EXEC_LOG.exists():
            lines = EXEC_LOG.read_text(encoding="utf-8").splitlines()
            for line in lines[-10:]:
                try:
                    r = json.loads(line)
                    print(
                        f"[{r['ts']}] {r['command_key']}: {r['terminal_state']} ({r['reason_code']})"
                    )
                except:
                    pass
        else:
            print("无执行日志")

    elif cmd == "dedup-clear":
        DEDUP_STATE.unlink(missing_ok=True)
        print("去重状态已清空")

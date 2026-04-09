#!/usr/bin/env python3
"""
AIOS 死循环检测 + 自动熔断 v1.0
检测认知死循环（连续 KERNEL 无 TOOL 产出 / 同命令短时间重复失败）
触发 circuit_breaker 熔断 + alert_fsm CRIT 告警 + 事件落盘

用法:
  from aios.core.deadloop_breaker import check, DeadloopResult
  result = check()  # 返回检测结果

  # 或 CLI
  python -m aios.core.deadloop_breaker          # 检测
  python -m aios.core.deadloop_breaker --status  # 查看熔断状态
  python -m aios.core.deadloop_breaker --reset   # 重置所有熔断
"""

import json, sys, time, io
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.engine import (
    load_events,
    emit,
    LAYER_SEC,
    LAYER_KERNEL,
    LAYER_TOOL,
    VALID_LAYERS,
)

# ── 配置 ──
CONSECUTIVE_KERNEL_THRESHOLD = 5  # 连续 N 个 KERNEL 无 TOOL = 疑似卡住
RAPID_FAIL_WINDOW_SEC = 120  # 快速失败窗口（秒）
RAPID_FAIL_THRESHOLD = 3  # 窗口内同命令失败 >= N 次触发
BREAKER_COOLDOWN_SEC = 3600  # 熔断冷却 1 小时
RECOVERY_WATCH_SEC = 1800  # 恢复后观测窗口 30 分钟
SCAN_HOURS = 1  # 扫描最近 N 小时

# 熔断状态文件
BREAKER_STATE_FILE = (
    Path(__file__).resolve().parent.parent / "events" / "deadloop_breaker_state.json"
)


@dataclass
class DeadloopResult:
    """检测结果"""

    cognitive_loops: list = field(default_factory=list)  # 认知死循环
    rapid_failures: list = field(default_factory=list)  # 快速重复失败
    tripped_breakers: list = field(default_factory=list)  # 本次触发的熔断
    existing_breakers: list = field(default_factory=list)  # 已有的熔断
    recovery_watches: list = field(default_factory=list)  # 恢复观测中的熔断
    clean: bool = True

    @property
    def has_issues(self) -> bool:
        return bool(self.cognitive_loops or self.rapid_failures)


# ── 熔断状态管理 ──


def _load_breaker_state() -> dict:
    if BREAKER_STATE_FILE.exists():
        try:
            return json.loads(BREAKER_STATE_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"tripped": {}}


def _save_breaker_state(state: dict):
    BREAKER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BREAKER_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _is_tripped(sig: str) -> bool:
    """检查某个签名是否已熔断"""
    state = _load_breaker_state()
    trip = state["tripped"].get(sig)
    if not trip:
        return False
    now = time.time()
    if now - trip["ts"] > BREAKER_COOLDOWN_SEC:
        # 冷却期结束，进入恢复观测窗口
        if "recovered_at" not in trip:
            trip["recovered_at"] = int(now)
            trip["recovery_watch_until"] = int(now) + RECOVERY_WATCH_SEC
            _save_breaker_state(state)
            # 记录恢复事件
            emit(
                LAYER_SEC,
                "deadloop_breaker_recovered",
                "ok",
                payload={
                    "sig": sig,
                    "reason": trip["reason"],
                    "watch_until": trip["recovery_watch_until"],
                },
            )
        # 观测窗口也过了，彻底清除
        if now > trip.get("recovery_watch_until", 0):
            del state["tripped"][sig]
            _save_breaker_state(state)
            emit(
                LAYER_SEC,
                "deadloop_recovery_confirmed",
                "ok",
                payload={
                    "sig": sig,
                    "verdict": "clean",
                },
            )
        return False
    return True


def _trip_breaker(sig: str, reason: str, details: dict = None):
    """触发熔断"""
    state = _load_breaker_state()
    state["tripped"][sig] = {
        "ts": int(time.time()),
        "reason": reason,
        "details": details or {},
        "expires": int(time.time()) + BREAKER_COOLDOWN_SEC,
    }
    _save_breaker_state(state)

    # 记录事件到 AIOS 事件流
    emit(
        LAYER_SEC,
        "deadloop_breaker_tripped",
        "err",
        payload={
            "sig": sig,
            "reason": reason,
            "cooldown_sec": BREAKER_COOLDOWN_SEC,
            **(details or {}),
        },
    )


def _reset_all():
    """重置所有熔断"""
    _save_breaker_state({"tripped": {}})


# ── 检测逻辑 ──


def _detect_cognitive_loops(events: list) -> list:
    """
    检测认知死循环：连续 KERNEL 事件无 TOOL 产出
    排除部署窗口（deploy/restart/rollout）
    """
    loops = []
    consecutive_kernel = 0
    kernel_window = []

    for e in events:
        layer = e.get("layer", "")
        if layer not in VALID_LAYERS:
            continue

        event_name = e.get("event", "").lower()

        if layer == "KERNEL":
            consecutive_kernel += 1
            kernel_window.append(e)
        elif layer == "TOOL":
            consecutive_kernel = 0
            kernel_window = []

        if consecutive_kernel >= CONSECUTIVE_KERNEL_THRESHOLD:
            # 排除部署窗口
            is_deploy = all(
                any(
                    k in (ev.get("event", "").lower())
                    for k in ("deploy", "restart", "rollout")
                )
                for ev in kernel_window
            )
            if not is_deploy:
                loops.append(
                    {
                        "type": "cognitive_loop",
                        "count": consecutive_kernel,
                        "start_ts": kernel_window[0].get("ts", "?"),
                        "end_ts": kernel_window[-1].get("ts", "?"),
                        "events": [ev.get("event", "?") for ev in kernel_window[-5:]],
                    }
                )
            consecutive_kernel = 0
            kernel_window = []

    return loops


def _detect_rapid_failures(events: list) -> list:
    """
    检测快速重复失败：同一命令在短时间窗口内连续失败
    """
    # 收集失败的 TOOL 事件
    failures = defaultdict(list)
    for e in events:
        if e.get("layer") != "TOOL":
            continue
        if e.get("status") != "err":
            continue
        name = e.get("event", "unknown")
        epoch = e.get("epoch", 0)
        if epoch > 0:
            failures[name].append(epoch)

    rapid = []
    for name, epochs in failures.items():
        epochs.sort()
        # 滑动窗口检测
        for i in range(len(epochs)):
            window_end = epochs[i] + RAPID_FAIL_WINDOW_SEC
            count = sum(1 for ep in epochs[i:] if ep <= window_end)
            if count >= RAPID_FAIL_THRESHOLD:
                rapid.append(
                    {
                        "type": "rapid_failure",
                        "command": name,
                        "count": count,
                        "window_sec": RAPID_FAIL_WINDOW_SEC,
                        "first_fail": time.strftime(
                            "%H:%M:%S", time.localtime(epochs[i])
                        ),
                    }
                )
                break  # 每个命令只报一次

    return rapid


# ── 主检测入口 ──


def check(scan_hours: int = None) -> DeadloopResult:
    """
    执行死循环检测，发现问题自动熔断。
    返回 DeadloopResult。
    """
    hours = scan_hours or SCAN_HOURS
    # load_events 接受 days，转换一下
    days = max(hours / 24, 1 / 24)  # 至少 1 小时
    events = load_events(days=1)  # 加载最近 1 天，后面按时间过滤

    # 按时间过滤到指定窗口
    cutoff = time.time() - hours * 3600
    events = [e for e in events if e.get("epoch", 0) >= cutoff]

    result = DeadloopResult()

    # 1. 认知死循环检测
    result.cognitive_loops = _detect_cognitive_loops(events)

    # 2. 快速重复失败检测
    result.rapid_failures = _detect_rapid_failures(events)

    # 3. 自动熔断
    for loop in result.cognitive_loops:
        sig = f"cognitive_loop_{loop['start_ts']}"
        if not _is_tripped(sig):
            _trip_breaker(sig, "认知死循环：连续 KERNEL 无 TOOL 产出", loop)
            result.tripped_breakers.append(sig)

    for fail in result.rapid_failures:
        sig = f"rapid_fail_{fail['command']}"
        if not _is_tripped(sig):
            _trip_breaker(
                sig,
                f"快速重复失败：{fail['command']} {fail['count']}次/{fail['window_sec']}s",
                fail,
            )
            result.tripped_breakers.append(sig)

    # 4. 列出已有熔断 + 恢复观测
    state = _load_breaker_state()
    now = time.time()
    for sig, info in list(state["tripped"].items()):
        expires = info.get("expires", 0)
        recovered_at = info.get("recovered_at")
        watch_until = info.get("recovery_watch_until", 0)

        if recovered_at and now <= watch_until:
            # 在恢复观测窗口内
            remaining_watch = round((watch_until - now) / 60)
            # 检查观测期内是否复发
            relapsed = False
            for loop in result.cognitive_loops:
                if sig.startswith("cognitive_loop"):
                    relapsed = True
            for fail in result.rapid_failures:
                if f"rapid_fail_{fail['command']}" == sig:
                    relapsed = True

            result.recovery_watches.append(
                {
                    "sig": sig,
                    "reason": info["reason"],
                    "remaining_watch_min": remaining_watch,
                    "relapsed": relapsed,
                }
            )
            if relapsed:
                # 复发：重新熔断，延长冷却
                info["ts"] = int(now)
                info["expires"] = int(now) + BREAKER_COOLDOWN_SEC
                info.pop("recovered_at", None)
                info.pop("recovery_watch_until", None)
                info["relapse_count"] = info.get("relapse_count", 0) + 1
                _save_breaker_state(state)
                emit(
                    LAYER_SEC,
                    "deadloop_breaker_relapsed",
                    "err",
                    payload={
                        "sig": sig,
                        "relapse_count": info["relapse_count"],
                    },
                )
                result.tripped_breakers.append(f"{sig} (复发#{info['relapse_count']})")
        elif expires > now:
            remaining = round((expires - now) / 60)
            result.existing_breakers.append(
                {
                    "sig": sig,
                    "reason": info["reason"],
                    "remaining_min": remaining,
                }
            )

    result.clean = (
        not result.has_issues
        and not result.existing_breakers
        and not result.recovery_watches
    )
    return result


def is_blocked(command_sig: str) -> bool:
    """
    供外部调用：检查某个命令签名是否被熔断。
    用法：
        if deadloop_breaker.is_blocked("tool_web_search"):
            return "该操作已被熔断，请稍后重试"
    """
    return _is_tripped(f"rapid_fail_{command_sig}")


def format_result(result: DeadloopResult, compact: bool = False) -> str:
    """格式化检测结果"""
    now = time.strftime("%Y-%m-%d %H:%M")

    if compact:
        lines = [f"🔒 死循环检测 | {now}"]
        if result.clean:
            lines.append("✅ 无死循环，无熔断")
            return "\n".join(lines)

        if result.cognitive_loops:
            lines.append(f"⚠️ 认知死循环: {len(result.cognitive_loops)} 处")
            for l in result.cognitive_loops:
                lines.append(f"  连续 {l['count']} 个 KERNEL 无 TOOL ({l['start_ts']})")

        if result.rapid_failures:
            lines.append(f"⚠️ 快速重复失败: {len(result.rapid_failures)} 个命令")
            for f in result.rapid_failures:
                lines.append(f"  {f['command']} {f['count']}次/{f['window_sec']}s")

        if result.tripped_breakers:
            lines.append(f"\n🔴 新触发熔断: {len(result.tripped_breakers)}")
            for sig in result.tripped_breakers:
                lines.append(f"  {sig}")

        if result.existing_breakers:
            lines.append(f"\n🟡 活跃熔断: {len(result.existing_breakers)}")
            for b in result.existing_breakers:
                lines.append(f"  {b['sig']} (剩余 {b['remaining_min']}min)")

        if result.recovery_watches:
            lines.append(f"\n👁️ 恢复观测中: {len(result.recovery_watches)}")
            for w in result.recovery_watches:
                status = "🔴 复发!" if w["relapsed"] else "✅ 正常"
                lines.append(
                    f"  {w['sig']} ({status}, 观测剩余 {w['remaining_watch_min']}min)"
                )

        return "\n".join(lines)

    # 完整版
    lines = [
        f"# 🔒 AIOS 死循环检测报告",
        f"时间: {now} | 扫描窗口: {SCAN_HOURS}h",
        "",
    ]

    if result.clean:
        lines.append("✅ 系统正常，无死循环，无活跃熔断。")
        return "\n".join(lines)

    if result.cognitive_loops:
        lines.append("## 认知死循环")
        for l in result.cognitive_loops:
            lines.append(f"- 连续 {l['count']} 个 KERNEL 事件无 TOOL 产出")
            lines.append(f"  时间: {l['start_ts']} → {l['end_ts']}")
            lines.append(f"  事件: {', '.join(l['events'])}")
        lines.append("")

    if result.rapid_failures:
        lines.append("## 快速重复失败")
        for f in result.rapid_failures:
            lines.append(
                f"- {f['command']}: {f['count']} 次失败 / {f['window_sec']}s 窗口"
            )
            lines.append(f"  首次失败: {f['first_fail']}")
        lines.append("")

    if result.tripped_breakers:
        lines.append("## 新触发熔断")
        for sig in result.tripped_breakers:
            lines.append(f"- 🔴 {sig} (冷却 {BREAKER_COOLDOWN_SEC//60}min)")
        lines.append("")

    if result.existing_breakers:
        lines.append("## 活跃熔断")
        for b in result.existing_breakers:
            lines.append(
                f"- 🟡 {b['sig']}: {b['reason']} (剩余 {b['remaining_min']}min)"
            )

    if result.recovery_watches:
        lines.append("")
        lines.append("## 恢复观测")
        for w in result.recovery_watches:
            status = "🔴 复发!" if w["relapsed"] else "✅ 运行正常"
            lines.append(
                f"- 👁️ {w['sig']}: {status} (观测剩余 {w['remaining_watch_min']}min)"
            )

    return "\n".join(lines)


# ── CLI ──


def main():
    import argparse

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="AIOS 死循环检测 + 自动熔断")
    p.add_argument("--status", action="store_true", help="查看熔断状态")
    p.add_argument("--reset", action="store_true", help="重置所有熔断")
    p.add_argument("--hours", type=int, default=SCAN_HOURS, help="扫描窗口（小时）")
    p.add_argument("--format", choices=["markdown", "telegram"], default="telegram")
    args = p.parse_args()

    if args.reset:
        _reset_all()
        print("✅ 所有熔断已重置")
        return

    if args.status:
        state = _load_breaker_state()
        now = time.time()
        active = {k: v for k, v in state["tripped"].items() if v["expires"] > now}
        if not active:
            print("✅ 无活跃熔断")
        else:
            print(f"🔒 活跃熔断: {len(active)}")
            for sig, info in active.items():
                remaining = round((info["expires"] - now) / 60)
                print(f"  {sig}: {info['reason']} (剩余 {remaining}min)")
        return

    result = check(scan_hours=args.hours)
    print(format_result(result, compact=(args.format == "telegram")))


if __name__ == "__main__":
    main()

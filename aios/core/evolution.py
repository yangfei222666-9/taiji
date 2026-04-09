#!/usr/bin/env python3
# aios/core/evolution.py - 进化评分 v0.7
"""
升级 evolution_score，纳入 reactor 自动响应指标。

新维度（在原有 TSR/CR/502/p95 基础上）：
- auto_fix_rate：自动修复率（reactor 成功执行 / 总告警）
- mean_response_time：平均响应时间（告警创建→reactor 执行）
- false_positive_rate：误报率（验证失败 / 总验证）

综合评分：
  evolution_v2 = base_score * 0.6 + reactor_score * 0.4

等级：
  >= 0.35 healthy
  >= 0.2  degraded
  < 0.2   critical
"""

import json, sys, io
from pathlib import Path
from datetime import datetime, timedelta

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
WS = AIOS_ROOT.parent
EVOLUTION_LOG = DATA_DIR / "evolution_history.jsonl"

sys.path.insert(0, str(AIOS_ROOT))


def compute_base_score():
    """原有 evolution_score（从 baseline 获取）"""
    try:
        from learning.baseline import snapshot

        result = snapshot()
        return result.get("evolution_score", 0.4)
    except:
        return 0.4  # 默认 healthy


def compute_reactor_score():
    """reactor 维度评分"""
    reaction_log = DATA_DIR / "reactions.jsonl"
    verify_log = DATA_DIR / "verify_log.jsonl"
    alerts_history = WS / "memory" / "alerts_history.jsonl"

    # 自动修复率
    total_reactions = 0
    success_reactions = 0
    if reaction_log.exists():
        with open(reaction_log, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                    if r.get("status") != "no_match":
                        total_reactions += 1
                        if r.get("status") == "success":
                            success_reactions += 1
                except:
                    continue

    auto_fix_rate = success_reactions / total_reactions if total_reactions > 0 else 0

    # 误报率（验证失败 / 总验证）
    v_total = 0
    v_failed = 0
    if verify_log.exists():
        with open(verify_log, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    v = json.loads(line)
                    v_total += 1
                    if not v.get("passed"):
                        v_failed += 1
                except:
                    continue

    false_positive_rate = v_failed / v_total if v_total > 0 else 0

    # 自动关闭率
    auto_closed = 0
    total_resolved = 0
    if alerts_history.exists():
        with open(alerts_history, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    h = json.loads(line)
                    if h.get("to") == "RESOLVED":
                        total_resolved += 1
                        reason = h.get("reason", "")
                        if "auto" in reason.lower() or "reactor" in reason.lower():
                            auto_closed += 1
                except:
                    continue

    auto_close_rate = auto_closed / total_resolved if total_resolved > 0 else 0

    # reactor_score = fix_rate * 0.5 - false_positive * 0.3 + auto_close * 0.2
    reactor_score = (
        auto_fix_rate * 0.5 - false_positive_rate * 0.3 + auto_close_rate * 0.2
    )
    reactor_score = max(0, min(1.0, reactor_score))

    return {
        "reactor_score": round(reactor_score, 4),
        "auto_fix_rate": round(auto_fix_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "auto_close_rate": round(auto_close_rate, 4),
        "total_reactions": total_reactions,
        "total_verifications": v_total,
        "total_resolved": total_resolved,
    }


def compute_evolution_v2():
    """综合进化评分 v2"""
    base = compute_base_score()
    reactor = compute_reactor_score()
    r_score = reactor["reactor_score"]

    # 加权合成
    v2_score = base * 0.6 + r_score * 0.4
    v2_score = round(max(0, min(1.0, v2_score)), 4)

    # 等级
    if v2_score >= 0.35:
        grade = "healthy"
    elif v2_score >= 0.2:
        grade = "degraded"
    else:
        grade = "critical"

    result = {
        "ts": datetime.now().isoformat(),
        "evolution_v2": v2_score,
        "grade": grade,
        "base_score": round(base, 4),
        "reactor_score": r_score,
        "detail": reactor,
    }

    # 持久化
    _log_evolution(result)

    return result


def _log_evolution(entry):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_trend(days=7):
    """获取最近 N 天的进化趋势"""
    if not EVOLUTION_LOG.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    records = []
    with open(EVOLUTION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                if r.get("ts", "") >= cutoff:
                    records.append(r)
            except:
                continue
    return records


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print("用法: python evolution.py [score|trend|detail]")
        return

    cmd = sys.argv[1]

    if cmd == "score":
        result = compute_evolution_v2()
        grade_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(
            result["grade"], "⚪"
        )
        print(
            f"{grade_icon} Evolution v2: {result['evolution_v2']} ({result['grade']})"
        )
        print(
            f"  基础分: {result['base_score']} | Reactor分: {result['reactor_score']}"
        )

    elif cmd == "detail":
        result = compute_evolution_v2()
        grade_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(
            result["grade"], "⚪"
        )
        d = result["detail"]
        print(
            f"{grade_icon} Evolution v2: {result['evolution_v2']} ({result['grade']})"
        )
        print(f"  基础分: {result['base_score']}")
        print(f"  Reactor分: {result['reactor_score']}")
        print(
            f"    自动修复率: {d['auto_fix_rate']:.0%} ({d['total_reactions']} reactions)"
        )
        print(
            f"    误报率: {d['false_positive_rate']:.0%} ({d['total_verifications']} verifications)"
        )
        print(
            f"    自动关闭率: {d['auto_close_rate']:.0%} ({d['total_resolved']} resolved)"
        )

    elif cmd == "trend":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        records = get_trend(days)
        if not records:
            print("无趋势数据")
            return
        print(f"📈 最近 {days} 天进化趋势 ({len(records)} 条):")
        for r in records[-10:]:
            ts = r.get("ts", "?")[:16]
            grade_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(
                r.get("grade"), "⚪"
            )
            print(
                f"  {grade_icon} {ts} v2={r.get('evolution_v2')} (base={r.get('base_score')} reactor={r.get('reactor_score')})"
            )

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

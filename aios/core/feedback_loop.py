#!/usr/bin/env python3
# aios/core/feedback_loop.py - 反馈闭环 v0.7
"""
从执行历史中提取模式，生成优化建议。

数据源：
- reactions.jsonl（reactor 执行记录）
- verify_log.jsonl（验证结果）
- decisions.jsonl（决策审计）
- playbook_stats.json（剧本成功率）

输出：
- 优化建议列表（调冷却/调风险/禁用/启用）
- feedback_suggestions.jsonl（持久化）
"""

import json, sys, io
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
REACTION_LOG = DATA_DIR / "reactions.jsonl"
VERIFY_LOG = DATA_DIR / "verify_log.jsonl"
PB_STATS_FILE = DATA_DIR / "playbook_stats.json"
SUGGESTIONS_FILE = DATA_DIR / "feedback_suggestions.jsonl"

sys.path.insert(0, str(AIOS_ROOT))


# ── 数据加载 ──


def _load_jsonl(path, since_hours=168):
    """加载 JSONL，过滤最近 N 小时"""
    if not path.exists():
        return []
    cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                if r.get("ts", "") >= cutoff:
                    records.append(r)
            except Exception:
                continue
    return records


def _load_pb_stats():
    if PB_STATS_FILE.exists():
        with open(PB_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── 模式分析 ──


def analyze_playbook_patterns(since_hours=168):
    """分析每个 playbook 的执行模式"""
    reactions = _load_jsonl(REACTION_LOG, since_hours)
    verifications = _load_jsonl(VERIFY_LOG, since_hours)
    pb_stats = _load_pb_stats()

    # 按 playbook 分组
    pb_reactions = defaultdict(list)
    for r in reactions:
        pid = r.get("playbook_id", "")
        if pid:
            pb_reactions[pid].append(r)

    # 验证结果按 playbook 分组
    pb_verifies = defaultdict(list)
    for v in verifications:
        pid = v.get("playbook_id", "")
        if pid:
            pb_verifies[pid].append(v)

    patterns = {}
    for pid, rxns in pb_reactions.items():
        total = len(rxns)
        success = sum(1 for r in rxns if r.get("status") == "success")
        pending = sum(1 for r in rxns if r.get("status") == "pending_confirm")
        failed = total - success - pending

        # 验证通过率
        vlist = pb_verifies.get(pid, [])
        v_total = len(vlist)
        v_passed = sum(1 for v in vlist if v.get("passed"))

        # 时间分布
        hours = [datetime.fromisoformat(r["ts"]).hour for r in rxns if "ts" in r]
        peak_hour = max(set(hours), key=hours.count) if hours else None

        # 连续失败检测
        consecutive_fails = 0
        max_consecutive_fails = 0
        for r in sorted(rxns, key=lambda x: x.get("ts", "")):
            if r.get("status") != "success":
                consecutive_fails += 1
                max_consecutive_fails = max(max_consecutive_fails, consecutive_fails)
            else:
                consecutive_fails = 0

        patterns[pid] = {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending,
            "success_rate": success / total if total > 0 else 0,
            "verify_total": v_total,
            "verify_passed": v_passed,
            "verify_rate": v_passed / v_total if v_total > 0 else 1.0,
            "peak_hour": peak_hour,
            "max_consecutive_fails": max_consecutive_fails,
            "stats": pb_stats.get(pid, {}),
        }

    return patterns


# ── 建议生成 ──


def generate_suggestions(since_hours=168):
    """基于模式分析生成优化建议"""
    patterns = analyze_playbook_patterns(since_hours)
    suggestions = []

    for pid, p in patterns.items():
        rate = p["success_rate"]
        total = p["total"]
        max_fails = p["max_consecutive_fails"]

        # 规则1：成功率持续高 → 缩短冷却
        if rate >= 0.9 and total >= 5:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "reduce_cooldown",
                    "reason": f"成功率 {rate:.0%} (n={total})，建议缩短冷却加速响应",
                    "confidence": min(rate, 0.95),
                    "priority": "low",
                }
            )

        # 规则2：成功率低 → 拉长冷却或禁用
        if rate < 0.3 and total >= 3:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "disable",
                    "reason": f"成功率仅 {rate:.0%} (n={total})，建议禁用并排查",
                    "confidence": 0.8,
                    "priority": "high",
                }
            )
        elif rate < 0.5 and total >= 3:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "increase_cooldown",
                    "reason": f"成功率 {rate:.0%} (n={total})，建议拉长冷却",
                    "confidence": 0.7,
                    "priority": "medium",
                }
            )

        # 规则3：连续失败 → 升级风险
        if max_fails >= 3:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "upgrade_risk",
                    "reason": f"连续失败 {max_fails} 次，建议升级为 require_confirm",
                    "confidence": 0.85,
                    "priority": "high",
                }
            )

        # 规则4：验证通过率低 → 检查验证规则
        if p["verify_total"] >= 3 and p["verify_rate"] < 0.5:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "review_verifier",
                    "reason": f"验证通过率 {p['verify_rate']:.0%}，执行成功但验证失败，检查验证规则",
                    "confidence": 0.7,
                    "priority": "medium",
                }
            )

        # 规则5：只有 pending_confirm 没有实际执行 → 可能风险过高
        if p["pending"] > 0 and p["success"] == 0 and total >= 3:
            suggestions.append(
                {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "type": "review_risk_level",
                    "reason": f"全部 {p['pending']} 次都需确认，从未自动执行，检查风险分级是否过严",
                    "confidence": 0.6,
                    "priority": "low",
                }
            )

    # 持久化
    if suggestions:
        _save_suggestions(suggestions)

    return suggestions


def _save_suggestions(suggestions):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUGGESTIONS_FILE, "a", encoding="utf-8") as f:
        for s in suggestions:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print("用法: python feedback_loop.py [analyze|suggest|history]")
        return

    cmd = sys.argv[1]
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 168

    if cmd == "analyze":
        patterns = analyze_playbook_patterns(hours)
        if not patterns:
            print("📊 无执行数据")
            return
        print(f"📊 剧本模式分析 (最近 {hours}h):")
        for pid, p in patterns.items():
            icon = (
                "🟢"
                if p["success_rate"] >= 0.8
                else "🟡" if p["success_rate"] >= 0.5 else "🔴"
            )
            print(f"  {icon} [{pid}]")
            print(
                f"      执行: {p['total']} (成功{p['success']} 失败{p['failed']} 待确认{p['pending']})"
            )
            print(
                f"      成功率: {p['success_rate']:.0%} | 验证率: {p['verify_rate']:.0%}"
            )
            if p["max_consecutive_fails"] > 0:
                print(f"      ⚠️ 最大连续失败: {p['max_consecutive_fails']}")

    elif cmd == "suggest":
        suggestions = generate_suggestions(hours)
        if not suggestions:
            print("✅ 无优化建议")
            return
        print(f"💡 {len(suggestions)} 条优化建议:")
        for s in suggestions:
            prio_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                s["priority"], "⚪"
            )
            print(f"  {prio_icon} [{s['playbook_id']}] {s['type']}")
            print(f"      {s['reason']}")

    elif cmd == "history":
        if not SUGGESTIONS_FILE.exists():
            print("无历史建议")
            return
        with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-10:] if len(lines) > 10 else lines
        for line in recent:
            s = json.loads(line.strip())
            ts = s.get("ts", "?")[:16]
            print(
                f"  {ts} [{s.get('playbook_id')}] {s.get('type')} — {s.get('reason','')[:60]}"
            )

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

#!/usr/bin/env python3
# aios/core/policy_learner.py - 策略自学习 v0.7
"""
基于历史数据自动调整 playbook 参数。

学习规则：
1. 成功率持续高(>=90%, n>=10) → 缩短冷却 (÷1.5, 最小15min)
2. 成功率持续低(<30%, n>=5) → 自动 disable + 通知
3. 成功率中等(<50%, n>=5) → 拉长冷却 (×2, 最大1440min)
4. 新告警模式无匹配 → 生成候选 playbook (draft)

所有调整记录到 policy_changes.jsonl，可审计可回滚。
"""

import json, sys, io
from pathlib import Path
from datetime import datetime
from typing import Optional

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
PB_STATS_FILE = DATA_DIR / "playbook_stats.json"
POLICY_LOG = DATA_DIR / "policy_changes.jsonl"
DRAFT_PLAYBOOKS = DATA_DIR / "draft_playbooks.json"

sys.path.insert(0, str(AIOS_ROOT))

from core.playbook import load_playbooks, PLAYBOOK_FILE, BUILTIN_PLAYBOOKS

# ── 策略调整 ──


def _load_pb_stats():
    if PB_STATS_FILE.exists():
        with open(PB_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_custom_playbooks():
    if PLAYBOOK_FILE.exists():
        with open(PLAYBOOK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_custom_playbooks(pbs):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAYBOOK_FILE, "w", encoding="utf-8") as f:
        json.dump(pbs, f, ensure_ascii=False, indent=2)


def _log_change(change):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(POLICY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(change, ensure_ascii=False) + "\n")


def learn_and_adjust():
    """分析统计数据，自动调整 playbook 参数"""
    stats = _load_pb_stats()
    all_pbs = load_playbooks()
    pb_map = {p["id"]: p for p in all_pbs}
    custom = _load_custom_playbooks()
    custom_map = {p["id"]: p for p in custom}

    changes = []

    for pid, s in stats.items():
        total = s.get("total", 0)
        if total < 3:
            continue  # 样本太少

        success = s.get("success", 0)
        rate = success / total

        pb = pb_map.get(pid)
        if not pb:
            continue

        current_cd = pb.get("cooldown_min", 60)

        # 规则1：高成功率 → 缩短冷却
        if rate >= 0.9 and total >= 10:
            new_cd = max(15, int(current_cd / 1.5))
            if new_cd < current_cd:
                change = {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "action": "reduce_cooldown",
                    "old_value": current_cd,
                    "new_value": new_cd,
                    "reason": f"成功率 {rate:.0%} (n={total})，缩短冷却 {current_cd}→{new_cd}min",
                    "auto_applied": True,
                }
                _apply_cooldown_change(pid, new_cd, custom, custom_map)
                changes.append(change)

        # 规则2：极低成功率 → 禁用
        elif rate < 0.3 and total >= 5:
            if pb.get("enabled", True):
                change = {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "action": "disable",
                    "old_value": True,
                    "new_value": False,
                    "reason": f"成功率仅 {rate:.0%} (n={total})，自动禁用",
                    "auto_applied": True,
                }
                _apply_enable_change(pid, False, custom, custom_map)
                changes.append(change)

        # 规则3：低成功率 → 拉长冷却
        elif rate < 0.5 and total >= 5:
            new_cd = min(1440, current_cd * 2)
            if new_cd > current_cd:
                change = {
                    "ts": datetime.now().isoformat(),
                    "playbook_id": pid,
                    "action": "increase_cooldown",
                    "old_value": current_cd,
                    "new_value": new_cd,
                    "reason": f"成功率 {rate:.0%} (n={total})，拉长冷却 {current_cd}→{new_cd}min",
                    "auto_applied": True,
                }
                _apply_cooldown_change(pid, new_cd, custom, custom_map)
                changes.append(change)

    # 保存自定义 playbook
    _save_custom_playbooks(list(custom_map.values()))

    # 记录变更
    for c in changes:
        _log_change(c)

    return changes


def _apply_cooldown_change(pid, new_cd, custom_list, custom_map):
    """应用冷却变更到自定义 playbook"""
    if pid in custom_map:
        custom_map[pid]["cooldown_min"] = new_cd
    else:
        # 从内置复制一份到自定义
        builtin = {p["id"]: p for p in BUILTIN_PLAYBOOKS}
        if pid in builtin:
            pb = dict(builtin[pid])
            pb["cooldown_min"] = new_cd
            custom_map[pid] = pb


def _apply_enable_change(pid, enabled, custom_list, custom_map):
    """应用启用/禁用变更"""
    if pid in custom_map:
        custom_map[pid]["enabled"] = enabled
    else:
        builtin = {p["id"]: p for p in BUILTIN_PLAYBOOKS}
        if pid in builtin:
            pb = dict(builtin[pid])
            pb["enabled"] = enabled
            custom_map[pid] = pb


# ── 候选 Playbook 生成 ──


def generate_draft_playbook(rule_id, severity, message_pattern):
    """为新告警模式生成候选 playbook（draft 状态）"""
    draft = {
        "id": f"draft_{rule_id}_{datetime.now().strftime('%Y%m%d%H%M')}",
        "name": f"[DRAFT] {rule_id} 自动响应",
        "match": {
            "rule_id": rule_id,
            "severity": [severity] if isinstance(severity, str) else severity,
            "message_contains": message_pattern,
        },
        "actions": [
            {
                "type": "shell",
                "target": f'echo "TODO: implement action for {rule_id}"',
                "params": {},
                "risk": "medium",
                "timeout": 30,
            }
        ],
        "cooldown_min": 120,
        "enabled": False,  # draft 默认禁用
        "require_confirm": True,
        "draft": True,
        "created_at": datetime.now().isoformat(),
    }

    # 保存到 draft 文件
    drafts = []
    if DRAFT_PLAYBOOKS.exists():
        with open(DRAFT_PLAYBOOKS, "r", encoding="utf-8") as f:
            drafts = json.load(f)
    drafts.append(draft)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DRAFT_PLAYBOOKS, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)

    _log_change(
        {
            "ts": datetime.now().isoformat(),
            "playbook_id": draft["id"],
            "action": "draft_created",
            "reason": f"新告警模式 {rule_id}/{severity}，生成候选剧本",
            "auto_applied": False,
        }
    )

    return draft


# ── 回滚 ──


def rollback_last_change():
    """回滚最近一次自动调整"""
    if not POLICY_LOG.exists():
        return None, "无变更记录"

    with open(POLICY_LOG, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    if not lines:
        return None, "无变更记录"

    last = json.loads(lines[-1])
    if not last.get("auto_applied"):
        return None, "最近变更非自动应用，无需回滚"

    pid = last["playbook_id"]
    action = last["action"]
    old_value = last["old_value"]

    custom = _load_custom_playbooks()
    custom_map = {p["id"]: p for p in custom}

    if action in ("reduce_cooldown", "increase_cooldown"):
        if pid in custom_map:
            custom_map[pid]["cooldown_min"] = old_value
    elif action == "disable":
        if pid in custom_map:
            custom_map[pid]["enabled"] = old_value

    _save_custom_playbooks(list(custom_map.values()))
    _log_change(
        {
            "ts": datetime.now().isoformat(),
            "playbook_id": pid,
            "action": f"rollback_{action}",
            "old_value": last["new_value"],
            "new_value": old_value,
            "reason": f"回滚: {last['reason']}",
            "auto_applied": False,
        }
    )

    return last, "OK"


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print("用法: python policy_learner.py [learn|drafts|history|rollback]")
        return

    cmd = sys.argv[1]

    if cmd == "learn":
        changes = learn_and_adjust()
        if not changes:
            print("✅ 无需调整")
        else:
            print(f"🔧 {len(changes)} 项自动调整:")
            for c in changes:
                print(f"  [{c['playbook_id']}] {c['action']}: {c['reason']}")

    elif cmd == "drafts":
        if not DRAFT_PLAYBOOKS.exists():
            print("无候选剧本")
            return
        with open(DRAFT_PLAYBOOKS, "r", encoding="utf-8") as f:
            drafts = json.load(f)
        if not drafts:
            print("无候选剧本")
            return
        print(f"📝 {len(drafts)} 条候选剧本:")
        for d in drafts:
            print(
                f"  [{d['id']}] {d['name']} (created: {d.get('created_at','?')[:16]})"
            )

    elif cmd == "history":
        if not POLICY_LOG.exists():
            print("无变更记录")
            return
        with open(POLICY_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-10:] if len(lines) > 10 else lines
        for line in recent:
            c = json.loads(line.strip())
            ts = c.get("ts", "?")[:16]
            auto = "🤖" if c.get("auto_applied") else "👤"
            print(
                f"  {auto} {ts} [{c.get('playbook_id')}] {c.get('action')} — {c.get('reason','')[:60]}"
            )

    elif cmd == "rollback":
        last, msg = rollback_last_change()
        if last:
            print(f"↩️ 已回滚: [{last['playbook_id']}] {last['action']}")
        else:
            print(f"❌ {msg}")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

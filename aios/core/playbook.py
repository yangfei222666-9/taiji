#!/usr/bin/env python3
# aios/core/playbook.py - 响应剧本 v0.6
"""
Playbook：定义告警→动作的映射规则。

每条 playbook entry:
{
  "id": "backup_expired",
  "name": "备份过期自动备份",
  "match": {
    "rule_id": "backup",          # 精确匹配
    "severity": ["WARN", "CRIT"], # 列表=任一匹配
    "min_hit_count": 2            # 至少命中N次才触发
  },
  "actions": [
    {
      "type": "shell",
      "target": "python -m autolearn backup",
      "params": {},
      "risk": "low",
      "timeout": 60
    }
  ],
  "cooldown_min": 60,             # 同一 playbook 冷却时间
  "enabled": true,
  "require_confirm": false        # true=high-risk，需人工确认
}

存储：data/playbooks.json（可手动编辑扩展）
"""

import json, os, sys, io
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
PLAYBOOK_FILE = DATA_DIR / "playbooks.json"
COOLDOWN_FILE = DATA_DIR / "playbook_cooldowns.json"

# ── 内置剧本 ──

BUILTIN_PLAYBOOKS = [
    {
        "id": "backup_expired",
        "name": "备份过期自动备份",
        "match": {
            "rule_id": "backup",
            "severity": ["WARN", "CRIT"],
            "min_hit_count": 2,
        },
        "actions": [
            {
                "type": "shell",
                "target": '& sys.executable -m autolearn backup',
                "params": {},
                "risk": "low",
                "timeout": 120,
            }
        ],
        "cooldown_min": 120,
        "enabled": True,
        "require_confirm": False,
    },
    {
        "id": "disk_full",
        "name": "磁盘空间不足清理",
        "match": {
            "rule_id": "system_health",
            "severity": ["WARN", "CRIT"],
            "message_contains": "磁盘",
        },
        "actions": [
            {
                "type": "shell",
                "target": "Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue",
                "params": {},
                "risk": "medium",
                "timeout": 60,
            }
        ],
        "cooldown_min": 360,
        "enabled": False,
        "require_confirm": False,
    },
    {
        "id": "loop_breaker_alert",
        "name": "死循环熔断告警",
        "match": {
            "rule_id": "event_severity",
            "severity": ["CRIT"],
            "message_contains": "死循环",
        },
        "actions": [
            {
                "type": "shell",
                "target": '& sys.executable -m aios.core.deadloop_breaker status',
                "params": {},
                "risk": "low",
                "timeout": 30,
            }
        ],
        "cooldown_min": 30,
        "enabled": True,
        "require_confirm": False,
    },
    {
        "id": "high_error_rate",
        "name": "高错误率诊断",
        "match": {"rule_id": "error_rate", "severity": ["CRIT"], "min_hit_count": 3},
        "actions": [
            {
                "type": "shell",
                "target": '& sys.executable -m aios.scripts.insight --since 1h --format markdown',
                "params": {},
                "risk": "low",
                "timeout": 30,
            }
        ],
        "cooldown_min": 60,
        "enabled": True,
        "require_confirm": False,
    },
]


# ── 存储 ──


def load_playbooks():
    """加载剧本，合并内置+自定义"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    custom = []
    if PLAYBOOK_FILE.exists():
        with open(PLAYBOOK_FILE, "r", encoding="utf-8") as f:
            custom = json.load(f)

    # 内置 + 自定义，自定义同 id 覆盖内置
    merged = {p["id"]: p for p in BUILTIN_PLAYBOOKS}
    for p in custom:
        merged[p["id"]] = p
    return list(merged.values())


def save_custom_playbooks(playbooks):
    """保存自定义剧本"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAYBOOK_FILE, "w", encoding="utf-8") as f:
        json.dump(playbooks, f, ensure_ascii=False, indent=2)


def _load_cooldowns():
    if COOLDOWN_FILE.exists():
        with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cooldowns(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 匹配 ──


def match_alert(playbook, alert):
    """检查一条 playbook 是否匹配一条告警"""
    if not playbook.get("enabled", True):
        return False

    m = playbook.get("match", {})

    # rule_id 精确匹配
    if "rule_id" in m:
        if alert.get("rule_id") != m["rule_id"]:
            return False

    # severity 列表匹配
    if "severity" in m:
        sev = m["severity"]
        if isinstance(sev, str):
            sev = [sev]
        if alert.get("severity") not in sev:
            return False

    # min_hit_count
    if "min_hit_count" in m:
        if alert.get("hit_count", 1) < m["min_hit_count"]:
            return False

    # message_contains 子串匹配
    if "message_contains" in m:
        msg = alert.get("message", "")
        if m["message_contains"] not in msg:
            return False

    return True


def check_cooldown(playbook_id):
    """检查冷却是否已过"""
    cooldowns = _load_cooldowns()
    if playbook_id not in cooldowns:
        return True
    last = datetime.fromisoformat(cooldowns[playbook_id])
    playbooks = {p["id"]: p for p in load_playbooks()}
    pb = playbooks.get(playbook_id)
    if not pb:
        return True
    cd_min = pb.get("cooldown_min", 60)
    return datetime.now() > last + timedelta(minutes=cd_min)


def record_cooldown(playbook_id):
    """记录执行时间"""
    cooldowns = _load_cooldowns()
    cooldowns[playbook_id] = datetime.now().isoformat()
    _save_cooldowns(cooldowns)


def find_matching_playbooks(alert):
    """找到所有匹配的 playbook，按优先级排序"""
    playbooks = load_playbooks()
    matched = []
    for pb in playbooks:
        if match_alert(pb, alert) and check_cooldown(pb["id"]):
            matched.append(pb)
    return matched


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print("用法: python playbook.py [list|match <alert_json>|add <json>]")
        return

    cmd = sys.argv[1]

    if cmd == "list":
        playbooks = load_playbooks()
        print(f"📋 共 {len(playbooks)} 条剧本:")
        for pb in playbooks:
            status = "✅" if pb.get("enabled", True) else "❌"
            confirm = "🔒" if pb.get("require_confirm") else "⚡"
            cd = pb.get("cooldown_min", 60)
            print(f"  {status}{confirm} [{pb['id']}] {pb['name']} (冷却{cd}min)")
            for a in pb.get("actions", []):
                print(
                    f"      → {a['type']}: {a['target'][:60]}... risk={a.get('risk','low')}"
                )

    elif cmd == "match":
        if len(sys.argv) < 3:
            print("需要 alert JSON")
            return
        alert = json.loads(sys.argv[2])
        matched = find_matching_playbooks(alert)
        if not matched:
            print("❌ 无匹配剧本")
        else:
            for pb in matched:
                print(f"✅ [{pb['id']}] {pb['name']}")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

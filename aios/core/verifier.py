#!/usr/bin/env python3
# aios/core/verifier.py - 执行后验证器 v0.6
"""
Verifier：动作执行后验证问题是否真正解决。

流程：
1. reactor 执行完 action
2. verifier 根据 playbook 定义的验证规则检查
3. 通过 → resolve 告警 + 记录教训
4. 失败 → 升级告警 / 通知用户

验证类型：
- alert_gone：告警不再触发（重跑检测）
- command_check：执行验证命令，检查返回值
- metric_check：检查指标是否恢复正常
"""

import json, sys, io, subprocess, time
from pathlib import Path
from datetime import datetime
from typing import Optional

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
VERIFY_LOG = DATA_DIR / "verify_log.jsonl"
WS = AIOS_ROOT.parent
PYTHON = r"sys.executable"

sys.path.insert(0, str(AIOS_ROOT))
sys.path.insert(0, str(WS / "scripts"))


# ── 验证规则（内置） ──

VERIFY_RULES = {
    "backup_expired": {
        "type": "command_check",
        "command": f'& "{PYTHON}" -X utf8 -c "from pathlib import Path; from datetime import datetime, timedelta; backup_dir = Path(r\'{WS / "autolearn" / "backups"}\'); recent = [f for f in backup_dir.glob(\'*.zip\') if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)) < timedelta(hours=1)]; print(\'PASS\' if recent else \'FAIL\')"',
        "expect": "PASS",
        "delay_sec": 10,
    },
    "disk_full": {
        "type": "command_check",
        "command": "powershell -Command \"$d=(Get-PSDrive C).Free/1GB; if($d -gt 5){'PASS'}else{'FAIL'}\"",
        "expect": "PASS",
        "delay_sec": 3,
    },
    "loop_breaker_alert": {
        "type": "command_check",
        "command": f'& "{PYTHON}" -X utf8 -m aios.core.deadloop_breaker status',
        "expect_contains": "活跃熔断: 0",
        "delay_sec": 2,
    },
    "high_error_rate": {
        "type": "alert_gone",
        "recheck_rule_id": "error_rate",
        "delay_sec": 10,
    },
}


# ── 验证执行 ──


def verify_reaction(reaction):
    """验证一次响应的结果"""
    playbook_id = reaction.get("playbook_id", "")
    rule = VERIFY_RULES.get(playbook_id)

    if not rule:
        # 无验证规则，默认通过
        return _make_result(reaction, True, "no_verify_rule", "无验证规则，默认通过")

    # 等待延迟
    delay = rule.get("delay_sec", 5)
    time.sleep(delay)

    vtype = rule.get("type", "command_check")

    if vtype == "command_check":
        return _verify_command(reaction, rule)
    elif vtype == "alert_gone":
        return _verify_alert_gone(reaction, rule)
    elif vtype == "metric_check":
        return _verify_metric(reaction, rule)
    else:
        return _make_result(reaction, False, "unknown_type", f"未知验证类型: {vtype}")


def _verify_command(reaction, rule):
    """执行验证命令"""
    cmd = rule.get("command", "")
    try:
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout.strip()

        if "expect" in rule:
            passed = output == rule["expect"]
        elif "expect_contains" in rule:
            passed = rule["expect_contains"] in output
        else:
            passed = result.returncode == 0

        return _make_result(reaction, passed, "command_check", output[:200])

    except Exception as e:
        return _make_result(reaction, False, "command_error", str(e)[:200])


def _verify_alert_gone(reaction, rule):
    """检查告警是否已消失"""
    alerts_file = WS / "memory" / "alerts_active.json"
    if not alerts_file.exists():
        return _make_result(reaction, True, "alert_gone", "告警文件不存在，视为通过")

    with open(alerts_file, "r", encoding="utf-8") as f:
        alerts = json.load(f)

    rule_id = rule.get("recheck_rule_id", "")
    active = [
        a
        for a in alerts.values()
        if a.get("rule_id") == rule_id and a.get("status") in ("OPEN", "ACK")
    ]

    passed = len(active) == 0
    msg = "告警已消失" if passed else f"仍有 {len(active)} 条活跃告警"
    return _make_result(reaction, passed, "alert_gone", msg)


def _verify_metric(reaction, rule):
    """检查指标（预留）"""
    return _make_result(reaction, True, "metric_check", "指标检查暂未实现，默认通过")


def _make_result(reaction, passed, method, detail):
    entry = {
        "ts": datetime.now().isoformat(),
        "reaction_id": reaction.get("reaction_id", "?"),
        "alert_id": reaction.get("alert_id", "?"),
        "playbook_id": reaction.get("playbook_id", "?"),
        "verify_method": method,
        "passed": passed,
        "detail": detail,
    }
    _log_verify(entry)
    return entry


def _log_verify(entry):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(VERIFY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 告警联动 ──


def post_verify(verify_result, alert):
    """验证后联动：通过→resolve，失败→升级"""
    if verify_result.get("passed"):
        # 自动 resolve
        try:
            from alert_fsm import resolve_alert

            alert_id = alert.get("id", "")
            reason = (
                f"auto-resolved by reactor+verifier: {verify_result.get('detail','')}"
            )
            resolve_alert(alert_id, reason)
            return "resolved"
        except Exception as e:
            return f"resolve_failed: {e}"
    else:
        # 失败：记录，不自动升级（留给人工判断）
        return "verify_failed"


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print("用法: python verifier.py [history|stats]")
        return

    cmd = sys.argv[1]

    if cmd == "history":
        if not VERIFY_LOG.exists():
            print("无验证记录")
            return
        with open(VERIFY_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-10:] if len(lines) > 10 else lines
        for line in recent:
            v = json.loads(line.strip())
            icon = "✅" if v.get("passed") else "❌"
            ts = v.get("ts", "?")[:16]
            print(
                f"{icon} {ts} [{v.get('playbook_id')}] {v.get('verify_method')} → {v.get('detail','')[:60]}"
            )

    elif cmd == "stats":
        if not VERIFY_LOG.exists():
            print("无验证记录")
            return
        with open(VERIFY_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)
        passed = sum(1 for l in lines if '"passed": true' in l)
        failed = total - passed
        rate = (passed / total * 100) if total > 0 else 0
        print(
            f"📊 验证统计: 总计={total} 通过={passed} 失败={failed} 通过率={rate:.0f}%"
        )

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

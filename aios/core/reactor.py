#!/usr/bin/env python3
# aios/core/reactor.py - 自动响应引擎 v0.6.1
"""
Reactor：告警→策略匹配→执行→验证 的闭环引擎。

v0.6.1 新增：
- decision_log 集成：每次响应记录决策审计
- 全局熔断：单位时间失败超阈值 → auto 降级为 confirm
- 剧本成功率统计 + 动态冷却（失败多→冷却拉长）
"""

import json, sys, io, time, subprocess, uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

# 跨平台文件锁
try:
    import msvcrt
    def _lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    def _unlock_file(f):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
except ImportError:
    import fcntl
    def _lock_file(f):
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    def _unlock_file(f):
        fcntl.flock(f, fcntl.LOCK_UN)

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

AIOS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AIOS_ROOT / "data"
REACTION_LOG = DATA_DIR / "reactions.jsonl"
FUSE_FILE = DATA_DIR / "reactor_fuse.json"
PLAYBOOK_STATS_FILE = DATA_DIR / "playbook_stats.json"
PYTHON = r"sys.executable"

sys.path.insert(0, str(AIOS_ROOT))

from core.playbook import find_matching_playbooks, record_cooldown, load_playbooks
from core.decision_log import log_decision, update_outcome

# ── 全局熔断配置 ──
FUSE_WINDOW_MIN = 30  # 熔断窗口：30 分钟
FUSE_FAIL_THRESHOLD = 5  # 窗口内失败 >= 5 次触发熔断
FUSE_COOLDOWN_MIN = 60  # 熔断后冷却 60 分钟

# ── 动态冷却配置 ──
DYNAMIC_COOLDOWN_MULTIPLIER = 2.0  # 失败率 > 50% 时冷却翻倍
DYNAMIC_COOLDOWN_MAX = 1440  # 最大冷却 24h


# ── 全局熔断 ──


def _load_fuse():
    if FUSE_FILE.exists():
        with open(FUSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"failures": [], "tripped": False, "tripped_at": None}


def _save_fuse(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(FUSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _record_fuse_failure():
    """记录一次失败"""
    fuse = _load_fuse()
    now = datetime.now()
    fuse["failures"].append(now.isoformat())
    # 清理窗口外的记录
    cutoff = (now - timedelta(minutes=FUSE_WINDOW_MIN)).isoformat()
    fuse["failures"] = [f for f in fuse["failures"] if f > cutoff]
    # 检查是否触发熔断
    if len(fuse["failures"]) >= FUSE_FAIL_THRESHOLD and not fuse["tripped"]:
        fuse["tripped"] = True
        fuse["tripped_at"] = now.isoformat()
    _save_fuse(fuse)


def _record_fuse_success():
    """记录一次成功（不重置熔断，但记录）"""
    pass  # 熔断只看失败数，成功不影响


def is_fuse_tripped():
    """检查全局熔断是否生效"""
    fuse = _load_fuse()
    if not fuse.get("tripped"):
        return False
    # 检查冷却是否已过
    tripped_at = datetime.fromisoformat(fuse["tripped_at"])
    if datetime.now() > tripped_at + timedelta(minutes=FUSE_COOLDOWN_MIN):
        fuse["tripped"] = False
        fuse["tripped_at"] = None
        fuse["failures"] = []
        _save_fuse(fuse)
        return False
    return True


# ── 剧本成功率统计 ──


def _load_pb_stats():
    if PLAYBOOK_STATS_FILE.exists():
        with open(PLAYBOOK_STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_pb_stats(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAYBOOK_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_pb_outcome(playbook_id, success):
    """记录剧本执行结果"""
    stats = _load_pb_stats()
    if playbook_id not in stats:
        stats[playbook_id] = {"total": 0, "success": 0, "fail": 0, "last_fail": None}
    stats[playbook_id]["total"] += 1
    if success:
        stats[playbook_id]["success"] += 1
    else:
        stats[playbook_id]["fail"] += 1
        stats[playbook_id]["last_fail"] = datetime.now().isoformat()
    _save_pb_stats(stats)


def get_pb_success_rate(playbook_id):
    """获取剧本成功率"""
    stats = _load_pb_stats()
    s = stats.get(playbook_id, {})
    total = s.get("total", 0)
    if total == 0:
        return 1.0  # 无历史，默认 100%
    return s.get("success", 0) / total


def get_dynamic_cooldown(playbook_id, base_cooldown_min):
    """根据成功率动态调整冷却时间"""
    rate = get_pb_success_rate(playbook_id)
    if rate < 0.5:
        # 失败率 > 50%，冷却翻倍
        adjusted = min(
            base_cooldown_min * DYNAMIC_COOLDOWN_MULTIPLIER, DYNAMIC_COOLDOWN_MAX
        )
        return int(adjusted)
    return base_cooldown_min


# ── 执行 ──


def execute_action(action, dry_run=False):
    """执行单个 action，返回 (success, result)"""
    atype = action.get("type", "shell")
    target = action.get("target", "")
    # 优化：降低默认超时从 60s 到 30s，硬上限从 300s 到 120s
    timeout = min(action.get("timeout", 30), 120)

    if dry_run:
        return True, f"[DRY_RUN] would execute: {atype} → {target}"

    if atype == "shell":
        try:
            result = subprocess.run(
                ["powershell", "-Command", target],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            ok = result.returncode == 0
            output = stdout if ok else f"EXIT {result.returncode}: {stderr[:200]}"
            return ok, output
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT after {timeout}s"
        except Exception as e:
            return False, f"ERROR: {str(e)[:200]}"

    elif atype == "python":
        try:
            result = subprocess.run(
                [PYTHON, "-X", "utf8", "-c", target],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                cwd=str(AIOS_ROOT.parent),
            )
            ok = result.returncode == 0
            output = result.stdout.strip() if ok else result.stderr.strip()[:200]
            return ok, output
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT after {timeout}s"
        except Exception as e:
            return False, f"ERROR: {str(e)[:200]}"

    else:
        return False, f"Unknown action type: {atype}"


def _log_reaction(entry):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(REACTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 核心：react ──


def react(alert, mode="auto"):
    """
    对一条告警执行自动响应。
    mode: auto / dry_run / confirm
    返回: list of reaction results
    """
    # 全局熔断检查：auto 降级为 confirm
    effective_mode = mode
    fuse_tripped = False
    if mode == "auto" and is_fuse_tripped():
        effective_mode = "confirm"
        fuse_tripped = True

    playbooks = find_matching_playbooks(alert)

    if not playbooks:
        return [
            {
                "alert_id": alert.get("id", "?"),
                "status": "no_match",
                "message": "无匹配剧本",
            }
        ]

    results = []

    for pb in playbooks:
        # 动态冷却检查
        base_cd = pb.get("cooldown_min", 60)
        dynamic_cd = get_dynamic_cooldown(pb["id"], base_cd)

        # 风险升级检查
        need_confirm = pb.get("require_confirm", False)
        if alert.get("severity") == "CRIT":
            for a in pb.get("actions", []):
                if a.get("risk", "low") in ("medium", "high"):
                    need_confirm = True

        # 熔断降级
        if fuse_tripped:
            need_confirm = True

        # 记录决策到 decision_log
        options = ["execute_auto", "execute_confirm", "skip"]
        if need_confirm and effective_mode == "auto":
            chosen = "pending_confirm"
        elif effective_mode == "dry_run":
            chosen = "dry_run"
        else:
            chosen = "execute_auto"

        confidence = get_pb_success_rate(pb["id"])
        decision_id = log_decision(
            context=f"reactor:{pb['id']}|alert:{alert.get('id','?')}|sev:{alert.get('severity','?')}",
            options=options,
            chosen=chosen,
            reason=f"fuse={'tripped' if fuse_tripped else 'ok'}|pb_rate={confidence:.0%}|dynamic_cd={dynamic_cd}min",
            confidence=confidence,
        )

        if need_confirm and effective_mode != "dry_run":
            entry = {
                "ts": datetime.now().isoformat(),
                "reaction_id": uuid.uuid4().hex[:8],
                "decision_id": decision_id,
                "alert_id": alert.get("id", "?"),
                "alert_severity": alert.get("severity", "?"),
                "alert_message": alert.get("message", "")[:100],
                "playbook_id": pb["id"],
                "playbook_name": pb["name"],
                "status": "pending_confirm",
                "message": f"需要确认: {pb['name']}"
                + (" [全局熔断]" if fuse_tripped else ""),
                "actions": pb.get("actions", []),
                "mode": effective_mode,
                "fuse_tripped": fuse_tripped,
            }
            _log_reaction(entry)
            # pending_confirm 不是失败，保持 pending 状态
            results.append(entry)
            continue

        # 执行所有 actions
        is_dry = effective_mode == "dry_run"
        action_results = []
        all_ok = True
        fast_fail = False  # 快速失败标志

        for action in pb.get("actions", []):
            # 快速失败：如果前一个 action 失败且是高风险，跳过后续
            if fast_fail:
                action_results.append({
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": False,
                    "output": "SKIPPED: 前置操作失败",
                })
                continue
            
            ok, output = execute_action(action, dry_run=is_dry)
            action_results.append(
                {
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": ok,
                    "output": output[:500],
                }
            )
            if not ok:
                all_ok = False
                # 如果是高风险操作失败，启用快速失败
                if action.get("risk", "low") in ("medium", "high"):
                    fast_fail = True

        # 记录冷却 + 统计
        if not is_dry:
            record_cooldown(pb["id"])
            record_pb_outcome(pb["id"], all_ok)
            if not all_ok:
                _record_fuse_failure()

        # 更新决策结果
        update_outcome(decision_id, "success" if all_ok else "fail")

        entry = {
            "ts": datetime.now().isoformat(),
            "reaction_id": uuid.uuid4().hex[:8],
            "decision_id": decision_id,
            "alert_id": alert.get("id", "?"),
            "alert_severity": alert.get("severity", "?"),
            "alert_message": alert.get("message", "")[:100],
            "playbook_id": pb["id"],
            "playbook_name": pb["name"],
            "status": "success" if all_ok else "partial_failure",
            "mode": effective_mode,
            "fuse_tripped": fuse_tripped,
            "pb_success_rate": f"{get_pb_success_rate(pb['id']):.0%}",
            "dynamic_cooldown_min": dynamic_cd,
            "action_results": action_results,
        }
        _log_reaction(entry)
        results.append(entry)

    return results


# ── 批量：扫描所有活跃告警 ──


def scan_and_react(mode="auto"):
    """扫描所有活跃告警，逐条匹配并响应"""
    alerts_file = AIOS_ROOT.parent / "memory" / "alerts_active.json"
    if not alerts_file.exists():
        return []

    with open(alerts_file, "r", encoding="utf-8") as f:
        alerts = json.load(f)

    all_results = []
    for fp, alert in alerts.items():
        if alert.get("status") not in ("OPEN", "ACK"):
            continue
        results = react(alert, mode=mode)
        all_results.extend(results)

    return all_results


# ── Dashboard 指标 ──


def dashboard_metrics():
    """计算 4 个核心指标"""
    if not REACTION_LOG.exists():
        return {
            "auto_exec_rate": 0,
            "verify_pass_rate": 0,
            "auto_close_rate": 0,
            "escalation_rate": 0,
            "total": 0,
        }

    with open(REACTION_LOG, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    if not lines:
        return {
            "auto_exec_rate": 0,
            "verify_pass_rate": 0,
            "auto_close_rate": 0,
            "escalation_rate": 0,
            "total": 0,
        }

    total = len(lines)
    auto_exec = 0
    pending_confirm = 0
    success = 0

    for line in lines:
        try:
            r = json.loads(line)
            if r.get("status") == "success":
                auto_exec += 1
                success += 1
            elif r.get("status") == "pending_confirm":
                pending_confirm += 1
        except:
            continue

    # 验证通过率从 verify_log 读
    verify_log = DATA_DIR / "verify_log.jsonl"
    verify_total = 0
    verify_passed = 0
    if verify_log.exists():
        with open(verify_log, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    v = json.loads(line)
                    verify_total += 1
                    if v.get("passed"):
                        verify_passed += 1
                except:
                    continue

    # 自动关闭率从 alerts_history 读
    history_file = AIOS_ROOT.parent / "memory" / "alerts_history.jsonl"
    auto_closed = 0
    total_resolved = 0
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    h = json.loads(line)
                    if h.get("to") == "RESOLVED":
                        total_resolved += 1
                        reason = h.get("reason", "")
                        if (
                            "auto" in reason.lower()
                            or "reactor" in reason.lower()
                            or "converge" in reason.lower()
                        ):
                            auto_closed += 1
                except:
                    continue

    acted = auto_exec + pending_confirm
    return {
        "total_reactions": total,
        "auto_exec_rate": f"{auto_exec/acted*100:.0f}%" if acted > 0 else "N/A",
        "verify_pass_rate": (
            f"{verify_passed/verify_total*100:.0f}%" if verify_total > 0 else "N/A"
        ),
        "auto_close_rate": (
            f"{auto_closed/total_resolved*100:.0f}%" if total_resolved > 0 else "N/A"
        ),
        "escalation_rate": f"{pending_confirm/acted*100:.0f}%" if acted > 0 else "N/A",
        "fuse_status": "🔴 TRIPPED" if is_fuse_tripped() else "🟢 OK",
    }


# ── CLI ──


def cli():
    if len(sys.argv) < 2:
        print(
            "用法: python reactor.py [scan|dry_run|history|stats|metrics|fuse|playbook_stats]"
        )
        return

    cmd = sys.argv[1]

    if cmd == "scan":
        results = scan_and_react(mode="auto")
        if not results:
            print("✅ 无需响应")
        else:
            for r in results:
                icon = (
                    "✅"
                    if r.get("status") == "success"
                    else "⚠️" if r.get("status") == "pending_confirm" else "❌"
                )
                print(
                    f"{icon} [{r.get('playbook_id','?')}] {r.get('playbook_name','?')} → {r.get('status')}"
                )
                for ar in r.get("action_results", []):
                    ok_icon = "✓" if ar["success"] else "✗"
                    print(f"    {ok_icon} {ar['type']}: {ar['output'][:80]}")

    elif cmd == "dry_run":
        results = scan_and_react(mode="dry_run")
        if not results:
            print("✅ 无匹配剧本")
        else:
            print(f"🔍 DRY RUN — {len(results)} 条响应计划:")
            for r in results:
                print(f"  📋 [{r.get('playbook_id')}] {r.get('playbook_name')}")
                for ar in r.get("action_results", []):
                    print(f"      → {ar['output']}")

    elif cmd == "history":
        if not REACTION_LOG.exists():
            print("无历史记录")
            return
        with open(REACTION_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-10:] if len(lines) > 10 else lines
        for line in recent:
            r = json.loads(line.strip())
            icon = (
                "✅"
                if r.get("status") == "success"
                else "⚠️" if r.get("status") == "pending_confirm" else "❌"
            )
            ts = r.get("ts", "?")[:16]
            did = r.get("decision_id", "")[:8]
            print(
                f"{icon} {ts} [{r.get('playbook_id','?')}] → {r.get('status')} (decision:{did})"
            )

    elif cmd == "stats":
        if not REACTION_LOG.exists():
            print("无历史记录")
            return
        with open(REACTION_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total = len(lines)
        success = sum(
            1 for l in lines if '"success"' in l and '"partial_failure"' not in l
        )
        pending = sum(1 for l in lines if '"pending_confirm"' in l)
        failed = total - success - pending
        print(
            f"📊 响应统计: 总计={total} 成功={success} 待确认={pending} 失败={failed}"
        )

    elif cmd == "metrics":
        m = dashboard_metrics()
        print("📊 Reactor Dashboard 指标:")
        print(f"  总响应数: {m['total_reactions']}")
        print(f"  自动执行率: {m['auto_exec_rate']}")
        print(f"  验证通过率: {m['verify_pass_rate']}")
        print(f"  自动关闭率: {m['auto_close_rate']}")
        print(f"  升级确认率: {m['escalation_rate']}")
        print(f"  熔断状态: {m['fuse_status']}")

    elif cmd == "fuse":
        fuse = _load_fuse()
        if fuse.get("tripped"):
            print(f"🔴 全局熔断中 (触发于 {fuse['tripped_at']})")
            print(f"   窗口内失败: {len(fuse.get('failures', []))} 次")
        else:
            recent = len(fuse.get("failures", []))
            print(f"🟢 熔断未触发 (窗口内失败: {recent}/{FUSE_FAIL_THRESHOLD})")

    elif cmd == "playbook_stats":
        stats = _load_pb_stats()
        if not stats:
            print("无剧本统计")
            return
        print("📊 剧本成功率:")
        for pid, s in stats.items():
            total = s.get("total", 0)
            rate = s.get("success", 0) / total * 100 if total > 0 else 0
            icon = "🟢" if rate >= 80 else "🟡" if rate >= 50 else "🔴"
            print(f"  {icon} [{pid}] {rate:.0f}% ({s.get('success',0)}/{total})")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()

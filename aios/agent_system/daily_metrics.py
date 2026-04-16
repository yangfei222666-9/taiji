#!/usr/bin/env python3
"""
AIOS Observability Blueprint v1 - Daily Metrics Collector

数据流: logs → daily_metrics.json → daily_metrics.md → dashboard

输出:
  reports/daily_metrics_YYYY-MM-DD.json  (数据)
  reports/daily_metrics_YYYY-MM-DD.md    (展示)

数据源:
  task_executions.jsonl   → Task Metrics
  route_log.jsonl         → Router Metrics
  decision_log.jsonl      → Debate Metrics
  lessons.json            → Failure Taxonomy
  experience_library.jsonl → Learning Metrics (Phase 3)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Failure taxonomy
FAILURE_TYPES = {
    "timeout": "任务超时",
    "tool_error": "工具调用失败",
    "logic_error": "逻辑错误",
    "missing_dependency": "依赖缺失",
    "bad_plan": "计划不合理",
    "resource_exhausted": "资源耗尽",
    "unknown": "未知错误",
}

# SLO thresholds
SLO = {
    "success_rate": {"ideal": 85.0, "warn": 80.0},
    "fast_ratio": {"ideal_min": 60.0, "ideal_max": 80.0, "warn_low": 50.0, "warn_high": 90.0},
    "debate_rate": {"ideal_min": 10.0, "ideal_max": 25.0, "warn_high": 40.0},
    "regeneration_rate": {"ideal": 75.0, "warn": 60.0},
    "avg_task_latency": {"ideal": 10.0, "warn": 20.0},
}


def load_jsonl(filename):
    path = os.path.join(BASE_DIR, filename)
    return load_jsonl_path(path)


def load_jsonl_path(path):
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_today(entries, date_str, ts_key="timestamp"):
    """Filter entries for a specific date (YYYY-MM-DD)."""
    today_entries = []
    for e in entries:
        ts = e.get(ts_key)
        if ts is None:
            continue
        # Handle both epoch float and ISO string
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
        elif isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                dt = dt.astimezone(timezone(timedelta(hours=8)))
            except ValueError:
                continue
        else:
            continue
        if dt.strftime("%Y-%m-%d") == date_str:
            today_entries.append(e)
    return today_entries


def classify_failure(error_type, error_message=""):
    """Classify failure into taxonomy, preserving original error_message."""
    error_type = (error_type or "").lower().strip()
    # Map known types
    if error_type in FAILURE_TYPES:
        return error_type
    # Try to infer from error_message
    msg = (error_message or "").lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "dependency" in msg or "import" in msg or "module" in msg:
        return "missing_dependency"
    if "502" in msg or "api" in msg or "connection" in msg:
        return "tool_error"
    if "resource" in msg or "memory" in msg or "disk" in msg:
        return "resource_exhausted"
    if "logic" in msg or "assertion" in msg:
        return "logic_error"
    if "plan" in msg or "decompos" in msg:
        return "bad_plan"
    return "unknown"


def classify_severity(failure_type, error_message=""):
    """Classify failure severity: recoverable / degraded / fatal."""
    recoverable = {"timeout", "tool_error", "resource_exhausted"}
    fatal = {"bad_plan", "logic_error"}
    if failure_type in recoverable:
        return "recoverable"
    if failure_type in fatal:
        return "fatal"
    # Heuristic from message
    msg = (error_message or "").lower()
    if "retry" in msg or "temporary" in msg or "transient" in msg:
        return "recoverable"
    if "crash" in msg or "corrupt" in msg or "fatal" in msg:
        return "fatal"
    return "degraded"


def infer_component(agent, error_message=""):
    """Infer which component failed: tool_layer / model_layer / plan_layer / infra."""
    msg = (error_message or "").lower()
    if "api" in msg or "502" in msg or "connection" in msg or "tool" in msg:
        return "tool_layer"
    if "model" in msg or "token" in msg or "context" in msg:
        return "model_layer"
    if "plan" in msg or "decompos" in msg or "step" in msg:
        return "plan_layer"
    if "timeout" in msg or "resource" in msg or "memory" in msg or "disk" in msg:
        return "infra"
    # Fallback by agent type
    agent = (agent or "").lower()
    if agent in ("coder", "tester"):
        return "model_layer"
    if agent in ("monitor",):
        return "infra"
    return "unknown"


def collect_task_metrics(date_str):
    """Collect task execution metrics for the given date."""
    all_tasks = load_jsonl("task_executions.jsonl")
    tasks = filter_today(all_tasks, date_str)

    total = len(tasks)
    success = sum(1 for t in tasks if t.get("result", {}).get("success", False))
    failed = total - success
    durations = [
        t["result"]["duration"]
        for t in tasks
        if isinstance(t.get("result", {}).get("duration"), (int, float))
        and t["result"]["duration"] >= 0
    ]
    avg_latency = round(sum(durations) / len(durations), 2) if durations else 0.0

    # Pending tasks from queue
    try:
        from paths import TASK_QUEUE as _TQ
        queue = load_jsonl_path(str(_TQ))
    except ImportError:
        queue = load_jsonl("task_queue.jsonl")
    pending = sum(1 for t in queue if t.get("status") == "pending")

    # Model usage breakdown
    model_counts = {}
    for t in tasks:
        model = t.get("model_used") or t.get("result", {}).get("model_used", "unknown")
        model_counts[model] = model_counts.get(model, 0) + 1

    return {
        "tasks_total": total,
        "tasks_success": success,
        "tasks_failed": failed,
        "tasks_pending": pending,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0.0,
        "avg_task_latency_s": avg_latency,
        "model_usage": model_counts,
        "durations": durations,  # raw, for dashboard
    }


def collect_router_metrics(date_str):
    """Collect router metrics. Fast = confidence >= 0.8, Slow = confidence < 0.8."""
    all_routes = load_jsonl("route_log.jsonl")
    routes = filter_today(all_routes, date_str, ts_key="ts")

    total = len(routes)
    # Heuristic: high confidence = fast model, low confidence = slow model (needs deliberation)
    fast = sum(1 for r in routes if r.get("confidence", 0) >= 0.8)
    slow = total - fast

    return {
        "router_total": total,
        "router_fast_count": fast,
        "router_slow_count": slow,
        "fast_ratio": round(fast / total * 100, 1) if total > 0 else 0.0,
        "slow_ratio": round(slow / total * 100, 1) if total > 0 else 0.0,
    }


def collect_debate_metrics(date_str):
    """Collect adversarial debate metrics from decision_log."""
    all_decisions = load_jsonl("decision_log.jsonl")
    decisions = filter_today(all_decisions, date_str)

    # Also check for dedicated debate log
    all_debates = load_jsonl("adversarial_debates.jsonl")
    debates = filter_today(all_debates, date_str)

    # Use whichever has data
    debate_entries = debates if debates else decisions
    debates_triggered = len(debate_entries)

    # Task total for debate_rate
    all_tasks = load_jsonl("task_executions.jsonl")
    tasks_today = filter_today(all_tasks, date_str)
    tasks_total = len(tasks_today)

    debate_rate = round(debates_triggered / tasks_total * 100, 1) if tasks_total > 0 else 0.0

    # Latency and rounds (if available, with type validation)
    latencies = []
    rounds_list = []
    for d in debate_entries:
        lat = d.get("latency")
        if isinstance(lat, (int, float)) and lat >= 0:
            latencies.append(lat)
        rnd = d.get("rounds")
        if isinstance(rnd, (int, float)) and rnd >= 0:
            rounds_list.append(rnd)

    return {
        "debates_triggered": debates_triggered,
        "debate_rate": debate_rate,
        "avg_debate_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "avg_rounds": round(sum(rounds_list) / len(rounds_list), 1) if rounds_list else 0.0,
    }


def collect_debate_effectiveness(date_str):
    """Compare success rate with vs without debate."""
    all_tasks = load_jsonl("task_executions.jsonl")
    tasks = filter_today(all_tasks, date_str)

    all_decisions = load_jsonl("decision_log.jsonl")
    all_debates = load_jsonl("adversarial_debates.jsonl")

    # Build set of task_ids that went through debate
    debate_task_ids = set()
    for d in all_decisions + all_debates:
        if "task_id" in d:
            debate_task_ids.add(d["task_id"])

    with_debate = [t for t in tasks if t.get("task_id") in debate_task_ids]
    without_debate = [t for t in tasks if t.get("task_id") not in debate_task_ids]

    def success_pct(lst):
        if not lst:
            return 0.0
        s = sum(1 for t in lst if t.get("result", {}).get("success", False))
        total = len(lst)
        return round(s / total * 100, 1) if total > 0 else 0.0

    return {
        "tasks_with_debate": len(with_debate),
        "tasks_without_debate": len(without_debate),
        "success_with_debate": success_pct(with_debate),
        "success_without_debate": success_pct(without_debate),
        "debate_delta": round(success_pct(with_debate) - success_pct(without_debate), 1),
    }


def collect_failure_taxonomy(date_str):
    """Classify failures with type + severity + component + error_message."""
    all_tasks = load_jsonl("task_executions.jsonl")
    tasks = filter_today(all_tasks, date_str)
    failed = [t for t in tasks if not t.get("result", {}).get("success", False)]

    # Also include lessons.json
    lessons_data = load_json("lessons.json")
    lessons = lessons_data.get("lessons", []) if isinstance(lessons_data, dict) else []

    taxonomy = {}
    severity_counts = {}
    component_counts = {}
    failure_details = []

    for t in failed:
        result = t.get("result", {})
        error_type = result.get("error_type", "")
        error_message = result.get("error", "")
        agent = result.get("agent", "")
        classified = classify_failure(error_type, error_message)
        severity = classify_severity(classified, error_message)
        component = infer_component(agent, error_message)

        taxonomy[classified] = taxonomy.get(classified, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        component_counts[component] = component_counts.get(component, 0) + 1

        failure_details.append({
            "task_id": t.get("task_id", ""),
            "failure_type": classified,
            "severity": severity,
            "component": component,
            "error_message": error_message,
            "agent": agent,
            "timestamp": t.get("timestamp"),
        })

    return {
        "failure_counts": taxonomy,
        "severity_counts": severity_counts,
        "component_counts": component_counts,
        "failure_total": len(failed),
        "failure_details": failure_details,
    }


def collect_learning_metrics(date_str):
    """Collect Phase 3 regeneration metrics."""
    all_regen = load_jsonl("experience_library.jsonl")
    regen = filter_today(all_regen, date_str)

    attempts = len(regen)
    successes = sum(1 for r in regen if r.get("success", False))

    # Regeneration times (if available, with type validation)
    times = []
    for r in regen:
        dur = r.get("duration")
        if isinstance(dur, (int, float)) and dur >= 0:
            times.append(dur)

    # Max regeneration attempts (from config or default to 3)
    max_attempts = 3  # Default from Phase 3 config

    return {
        "regeneration_attempts": attempts,
        "regeneration_success": successes,
        "regeneration_rate": round(successes / attempts * 100, 1) if attempts > 0 else 0.0,
        "avg_regeneration_time_s": round(sum(times) / len(times), 2) if times else 0.0,
        "max_regeneration_attempts": max_attempts,
    }


def check_slo(metrics):
    """Check metrics against SLO thresholds, return alerts."""
    alerts = []
    sr = metrics["success_rate"]
    if sr < SLO["success_rate"]["warn"]:
        alerts.append(f"⚠️ success_rate {sr}% < {SLO['success_rate']['warn']}% (WARN)")
    elif sr >= SLO["success_rate"]["ideal"]:
        alerts.append(f"✅ success_rate {sr}% (GOOD)")

    fr = metrics["router"]["fast_ratio"]
    if fr < SLO["fast_ratio"]["warn_low"]:
        alerts.append(f"⚠️ fast_ratio {fr}% < {SLO['fast_ratio']['warn_low']}% (WARN)")
    elif fr > SLO["fast_ratio"]["warn_high"]:
        alerts.append(f"⚠️ fast_ratio {fr}% > {SLO['fast_ratio']['warn_high']}% (WARN)")

    dr = metrics["debate"]["rate"]
    if dr > SLO["debate_rate"]["warn_high"]:
        alerts.append(f"⚠️ debate_rate {dr}% > {SLO['debate_rate']['warn_high']}% (WARN)")

    lat = metrics["avg_latency"]
    if lat > SLO["avg_task_latency"]["warn"] and not metrics.get("noise", False):
        alerts.append(f"⚠️ avg_latency {lat}s > {SLO['avg_task_latency']['warn']}s (WARN)")
    elif lat > SLO["avg_task_latency"]["warn"] and metrics.get("noise", False):
        alerts.append(f"ℹ️ avg_latency {lat}s high but noise=true (tasks<10, ignoring)")

    rr = metrics["regeneration"]["rate"]
    if rr > 0 and rr < SLO["regeneration_rate"]["warn"]:
        alerts.append(f"⚠️ regeneration_rate {rr}% < {SLO['regeneration_rate']['warn']}% (WARN)")

    return alerts


def generate_json(metrics, date_str):
    """Save metrics as JSON (data layer). Clean structure for dashboard consumption."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"daily_metrics_{date_str}.json")
    # Strip internal fields
    output = {k: v for k, v in metrics.items() if k != "_raw"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return path


def generate_md(metrics, date_str, alerts):
    """Generate human-readable markdown report (display layer)."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"daily_metrics_{date_str}.md")

    r = metrics["router"]
    d = metrics["debate"]
    de = d["effectiveness"]
    f = metrics["failures"]
    rg = metrics["regeneration"]

    lines = [
        f"# AIOS Daily Report",
        f"Date: {date_str}",
        "",
        "## Task Metrics",
        f"  tasks_total: {metrics['tasks_total']}",
        f"  success_rate: {metrics['success_rate']}%",
        f"  avg_latency: {metrics['avg_latency']}s",
        f"  latency_baseline_3d: {metrics.get('latency_baseline_3d', 0)}s",
        f"  latency_spike: {metrics.get('latency_spike', False)}",
        f"  noise: {metrics.get('noise', False)}",
        f"  tasks_pending: {metrics['tasks_pending']}",
        "",
        "## Router",
        f"  total: {r['total']}",
        f"  fast: {r['fast_count']}  slow: {r['slow_count']}",
        f"  fast_ratio: {r['fast_ratio']}%",
        "",
        "## Debate",
        f"  total: {d['total']}",
        f"  rate: {d['rate']}%",
        f"  avg_latency: {d['avg_latency']}s",
        f"  avg_rounds: {d['avg_rounds']}",
        "",
        "## Debate Effectiveness",
        f"  with_debate: {de['success_with_debate']}%  ({de['tasks_with_debate']} tasks)",
        f"  without_debate: {de['success_without_debate']}%  ({de['tasks_without_debate']} tasks)",
        f"  delta: {de['debate_delta']}%",
        "",
        "## Failures",
        f"  total: {f['total']}",
    ]

    if f["by_type"]:
        lines.append("  by_type:")
        for ftype, count in sorted(f["by_type"].items(), key=lambda x: -x[1]):
            label = FAILURE_TYPES.get(ftype, ftype)
            lines.append(f"    {ftype}: {count} ({label})")

    if f["by_severity"]:
        lines.append("  by_severity:")
        for sev, count in sorted(f["by_severity"].items(), key=lambda x: -x[1]):
            lines.append(f"    {sev}: {count}")

    if f["by_component"]:
        lines.append("  by_component:")
        for comp, count in sorted(f["by_component"].items(), key=lambda x: -x[1]):
            lines.append(f"    {comp}: {count}")

    # Failure details
    if f["details"]:
        lines.append("")
        lines.append("### Failure Details")
        for fd in f["details"]:
            lines.append(f"  - [{fd['failure_type']}|{fd['severity']}|{fd['component']}] {fd['task_id']}: {fd['error_message']}")

    lines.extend([
        "",
        "## Regeneration (Phase 3)",
        f"  attempts: {rg['attempts']}",
        f"  success: {rg['success']}",
        f"  rate: {rg['rate']}%",
        f"  avg_time: {rg['avg_time']}s",
        f"  max_attempts: {rg['max_regeneration_attempts']}",
    ])

    # Model usage
    mu = metrics.get("model_usage", {})
    if mu:
        lines.append("")
        lines.append("## Model Usage")
        for model, count in sorted(mu.items(), key=lambda x: -x[1]):
            lines.append(f"  {model}: {count}")

    lines.extend([
        "",
        "## SLO Alerts",
    ])

    if alerts:
        for a in alerts:
            lines.append(f"  {a}")
    else:
        lines.append("  (no alerts)")

    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone(timedelta(hours=8))).isoformat()}")

    with open(path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(lines))
    return path


def collect_all_metrics(date_str):
    """Collect all metrics for a given date, using nested structure."""
    tm = collect_task_metrics(date_str)
    rm = collect_router_metrics(date_str)
    dm = collect_debate_metrics(date_str)
    de = collect_debate_effectiveness(date_str)
    ft = collect_failure_taxonomy(date_str)
    lm = collect_learning_metrics(date_str)

    # Unified structure per 珊瑚海's review
    # Latency spike detection: compare against 3-day baseline
    baseline_latencies = []
    for i in range(1, 4):
        prev_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
        prev_path = os.path.join(REPORTS_DIR, f"daily_metrics_{prev_date}.json")
        if os.path.exists(prev_path):
            try:
                with open(prev_path, "r", encoding="utf-8") as pf:
                    prev = json.load(pf)
                lat = prev.get("avg_latency", prev.get("task_metrics", {}).get("avg_task_latency_s"))
                if lat is not None:
                    baseline_latencies.append(lat)
            except Exception:
                pass
    baseline_avg = round(sum(baseline_latencies) / len(baseline_latencies), 2) if baseline_latencies else 0.0
    spike_threshold = round(baseline_avg * 1.5, 2)
    current_latency = tm["avg_task_latency_s"]

    # Sample protection: need >= 10 tasks to declare a spike (avoid single slow task → false spike)
    MIN_SAMPLE_FOR_SPIKE = 10
    tasks_today = tm["tasks_total"]
    raw_spike = current_latency > spike_threshold if baseline_avg > 0 else False
    latency_spike = raw_spike and tasks_today >= MIN_SAMPLE_FOR_SPIKE
    # noise flag: spike signal present but sample too small to be meaningful
    noise = raw_spike and tasks_today < MIN_SAMPLE_FOR_SPIKE

    return {
        "date": date_str,
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "tasks_total": tm["tasks_total"],
        "success_rate": tm["success_rate"],
        "avg_latency": tm["avg_task_latency_s"],
        "latency_baseline_3d": baseline_avg,
        "latency_spike_threshold": spike_threshold,
        "latency_spike": latency_spike,
        "noise": noise,
        "tasks_pending": tm["tasks_pending"],
        "router": {
            "total": rm["router_total"],
            "fast_count": rm["router_fast_count"],
            "slow_count": rm["router_slow_count"],
            "fast_ratio": rm["fast_ratio"],
        },
        "debate": {
            "total": dm["debates_triggered"],
            "rate": dm["debate_rate"],
            "avg_latency": dm["avg_debate_latency_s"],
            "avg_rounds": dm["avg_rounds"],
            "effectiveness": de,
        },
        "failures": {
            "total": ft["failure_total"],
            "by_type": ft["failure_counts"],
            "by_severity": ft["severity_counts"],
            "by_component": ft["component_counts"],
            "details": ft["failure_details"],
        },
        "regeneration": {
            "attempts": lm["regeneration_attempts"],
            "success": lm["regeneration_success"],
            "rate": lm["regeneration_rate"],
            "avg_time": lm["avg_regeneration_time_s"],
            "max_regeneration_attempts": lm["max_regeneration_attempts"],
        },
        "model_usage": tm["model_usage"],
        # Keep raw sub-metrics for internal use
        "_raw": {
            "task_metrics": tm,
            "router_metrics": rm,
            "debate_metrics": dm,
            "debate_effectiveness": de,
            "failure_taxonomy": ft,
            "learning_metrics": lm,
        },
    }


def quick_metrics(date_str):
    """Quick metrics for 12:00 check (subset of full)."""
    tm = collect_task_metrics(date_str)
    ft = collect_failure_taxonomy(date_str)
    return {
        "date": date_str,
        "type": "quick",
        "tasks_total": tm["tasks_total"],
        "success_rate": tm["success_rate"],
        "tasks_failed": tm["tasks_failed"],
        "avg_latency": tm["avg_task_latency_s"],
        "failure_counts": ft["failure_counts"],
    }


def observation_line(date_str=None, day_number=None):
    """Generate the one-line observation for 珊瑚海.
    
    Format:
      Day{N} (22:00) obs_id=YYYY-MM-DD tasks=X success=X% debate=X% fast_ratio=X% latency=Xs spike=T/F top_failure=X system_state=X load_state=X sample_state=X regen_rate=X%
    
    Also appends to reports/observation_log.md for historical tracking.
    """
    if date_str is None:
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    metrics = collect_all_metrics(date_str)

    tasks = metrics["tasks_total"]
    success = metrics["success_rate"]
    debate = metrics["debate"]["rate"]
    fast_ratio = metrics["router"]["fast_ratio"]
    latency = metrics["avg_latency"]
    spike = metrics["latency_spike"]
    regen_rate = metrics["regeneration"]["rate"]

    # top_failure: most common failure component, or "none"
    comp = metrics["failures"].get("by_component", {})
    if comp:
        top_failure = max(comp, key=comp.get)
        sev = metrics["failures"].get("by_severity", {})
        top_sev = max(sev, key=sev.get) if sev else ""
        top_failure_str = f"{top_failure}({top_sev})" if top_sev else top_failure
    else:
        top_failure_str = "none"

    # system_state: stable / defensive / abnormal
    if success < 90 or debate > 30 or latency > 15:
        system_state = "abnormal"
    elif (debate > 15 and fast_ratio < 65) or latency > 12:
        system_state = "defensive"
    else:
        system_state = "stable"

    # load_state: low / normal / high
    if tasks < 30:
        load_state = "low"
    elif tasks <= 150:
        load_state = "normal"
    else:
        load_state = "high"

    # sample_state: noise / warmup / valid
    if tasks < 10:
        sample_state = "noise"
    elif tasks <= 50:
        sample_state = "warmup"
    else:
        sample_state = "valid"

    # Day number: auto-detect from freeze start (2026-03-05)
    if day_number is None:
        freeze_start = datetime(2026, 3, 5)
        current = datetime.strptime(date_str, "%Y-%m-%d")
        day_number = (current - freeze_start).days + 1

    line = (
        f"Day{day_number} (22:00) "
        f"obs_id={date_str} "
        f"tasks={tasks} "
        f"success={success}% "
        f"debate={debate}% "
        f"fast_ratio={fast_ratio}% "
        f"latency={latency}s "
        f"spike={str(spike).lower()} "
        f"top_failure={top_failure_str} "
        f"system_state={system_state} "
        f"load_state={load_state} "
        f"sample_state={sample_state} "
        f"regen_rate={regen_rate}%"
    )

    # Append to observation log file
    log_path = os.path.join(REPORTS_DIR, "observation_log.md")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    header_needed = not os.path.exists(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("# AIOS Observation Log\n\n")
        f.write(line + "\n")

    return line


def run(date_str=None, mode="full"):
    """Main entry point."""
    if date_str is None:
        date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    if mode == "quick":
        qm = quick_metrics(date_str)
        print(f"AIOS Quick Metrics ({date_str})")
        print(f"  tasks: {qm['tasks_total']} | success: {qm['success_rate']}% | failed: {qm['tasks_failed']} | latency: {qm['avg_latency']}s")
        if qm["failure_counts"]:
            print(f"  failures: {qm['failure_counts']}")
        return qm

    # Full metrics
    metrics = collect_all_metrics(date_str)
    alerts = check_slo(metrics)

    json_path = generate_json(metrics, date_str)
    md_path = generate_md(metrics, date_str, alerts)

    # Print summary
    r = metrics["router"]
    d = metrics["debate"]
    de = d["effectiveness"]
    rg = metrics["regeneration"]

    print(f"AIOS Daily Report ({date_str})")
    print(f"")
    print(f"Tasks")
    print(f"  total: {metrics['tasks_total']}  success_rate: {metrics['success_rate']}%  avg_latency: {metrics['avg_latency']}s")
    print(f"")
    print(f"Router")
    print(f"  fast: {r['fast_count']}  slow: {r['slow_count']}  fast_ratio: {r['fast_ratio']}%")
    print(f"")
    print(f"Debate")
    print(f"  total: {d['total']}  rate: {d['rate']}%")
    print(f"  effectiveness: with={de['success_with_debate']}%  without={de['success_without_debate']}%  delta={de['debate_delta']}%")
    print(f"")
    print(f"Failures")
    ft = metrics["failures"]
    if ft["by_type"]:
        print(f"  by_type: {ft['by_type']}")
        print(f"  by_severity: {ft['by_severity']}")
        print(f"  by_component: {ft['by_component']}")
    else:
        print(f"  (none)")
    print(f"")
    print(f"Regeneration")
    print(f"  attempts: {rg['attempts']}  success: {rg['success']}  rate: {rg['rate']}%")
    print(f"")
    mu = metrics.get("model_usage", {})
    if mu:
        print(f"Model Usage")
        for model, count in sorted(mu.items(), key=lambda x: -x[1]):
            print(f"  {model}: {count}")
        print(f"")
    print(f"SLO Alerts")
    for a in alerts:
        print(f"  {a}")
    print(f"")
    print(f"Output:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    
    # Generate Skill Memory Dashboard (daily)
    try:
        from skill_memory_dashboard import generate_dashboard
        print(f"\n[SKILL_MEMORY] Generating dashboard...")
        generate_dashboard()
    except Exception as e:
        print(f"[WARN] Skill memory dashboard failed: {e}")

    return metrics


if __name__ == "__main__":
    mode = "full"
    date_str = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ("quick", "observe"):
            mode = sys.argv[1]
        else:
            date_str = sys.argv[1]
    if len(sys.argv) > 2:
        mode = sys.argv[2]

    if mode == "observe":
        line = observation_line(date_str=date_str)
        print(line)
    else:
        run(date_str=date_str, mode=mode)

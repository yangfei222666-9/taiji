# aios/learning/analyze.py - 分析层（纯计算，无 I/O 输出）
"""
从 events.jsonl 分析，产出结构化数据：
  metrics / top_issues / alias_suggestions / tool_suggestions / threshold_warnings

输入层: analyze_extract.py (事件字段提取)
输出层: analyze_report.py (报告生成+写入)
"""

import math
import time
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.engine import load_events
from core.config import get_int, get_float
from learning.analyze_extract import (
    event_name, is_ok, tool_name, latency, payload, classify_layer,
)

AIOS_ROOT = Path(__file__).resolve().parent.parent
LEARNING_DIR = AIOS_ROOT / "learning"
LEARNING_DIR.mkdir(exist_ok=True)

AIOS_VERSION = "0.2.0"
CORRECTION_THRESHOLD = get_int("analysis.correction_threshold", 3)
LOW_SCORE_THRESHOLD = get_float("analysis.low_score_threshold", 0.80)

# 时间衰减: W = e^(-λ * Δt), λ = ln(2)/half_life_hours
DECAY_HALF_LIFE_HOURS = 12
DECAY_LAMBDA = math.log(2) / (DECAY_HALF_LIFE_HOURS * 3600)


def _decay_weight(event_ts: int) -> float:
    """指数衰减权重，越近的事件权重越大"""
    dt = max(0, time.time() - event_ts)
    return math.exp(-DECAY_LAMBDA * dt)


def compute_metrics(days: int = 1) -> dict:
    events = load_events(days)

    by_layer = {"KERNEL": [], "COMMS": [], "TOOL": [], "MEM": [], "SEC": []}
    for e in events:
        layer = classify_layer(e)
        by_layer.setdefault(layer, []).append(e)

    tools = by_layer["TOOL"]
    mem_events = by_layer["MEM"]
    sec_events = by_layer["SEC"]

    matches = [e for e in mem_events if event_name(e) in ("match", "confirm")]
    corrections = [e for e in mem_events if event_name(e) == "correction"]
    total_match = len(matches) + len(corrections)
    correction_rate = len(corrections) / total_match if total_match > 0 else 0

    tool_ok = [t for t in tools if is_ok(t)]
    tool_success_rate = len(tool_ok) / len(tools) if tools else 1.0

    http_errors = [e for e in sec_events if event_name(e) == "http_error"]
    http_codes = Counter(payload(e).get("status_code", "?") for e in http_errors)

    by_tool = defaultdict(list)
    for e in tools:
        name = tool_name(e)
        ms = latency(e)
        if ms > 0:
            by_tool[name].append(ms)

    tool_p95 = {}
    tool_p50 = {}
    for name, times in by_tool.items():
        if len(times) >= 2:
            s = sorted(times)
            tool_p95[name] = s[math.ceil(0.95 * len(s)) - 1]
            tool_p50[name] = s[len(s) // 2]

    return {
        "counts": {
            "events": len(events),
            "matches": len(matches),
            "corrections": len(corrections),
            "tools": len(tools),
            "by_layer": {k: len(v) for k, v in by_layer.items()},
        },
        "quality": {"correction_rate": round(correction_rate, 4)},
        "reliability": {
            "tool_success_rate": round(tool_success_rate, 4),
            "http_502": http_codes.get(502, 0),
            "http_404": http_codes.get(404, 0),
        },
        "performance": {"tool_p95_ms": tool_p95, "tool_p50_ms": tool_p50},
    }


def compute_top_issues(days: int = 7) -> dict:
    events = load_events(days)
    corrections = [e for e in events if event_name(e) == "correction"]
    errors = [
        e for e in events
        if e.get("status") == "err" or event_name(e) in ("runtime_error", "http_error")
    ]
    failed_tools = [
        e for e in events
        if e.get("layer", e.get("type")) in ("TOOL", "tool", "task") and not is_ok(e)
    ]

    return {
        "top_corrected_inputs": dict(
            Counter(
                payload(e).get("query", payload(e).get("input", "?"))
                for e in corrections
            ).most_common(10)
        ),
        "top_failed_tools": dict(
            Counter(tool_name(e) for e in failed_tools).most_common(5)
        ),
        "top_error_types": dict(
            Counter(
                (f"http_{payload(e).get('status_code', '?')}"
                 if event_name(e) == "http_error"
                 else payload(e).get("error", e.get("event", "?"))[:50])
                for e in errors
            ).most_common(5)
        ),
    }


def compute_alias_suggestions(days: int = 7) -> list:
    """L1: alias 建议（可自动应用）"""
    corrections = load_events(days, "correction")
    targets = defaultdict(list)
    examples = defaultdict(list)

    for c in corrections:
        data = c.get("data", {})
        inp = data.get("input", "")
        target = data.get("correct_target", "")
        matched = data.get("matched", "")
        if inp and target:
            targets[inp].append(target)
            if matched:
                ex = f"{matched}->{target}"
                if ex not in examples[inp]:
                    examples[inp].append(ex)

    suggestions = []
    for inp, tlist in targets.items():
        tc = Counter(tlist)
        top, count = tc.most_common(1)[0]
        if count >= CORRECTION_THRESHOLD:
            suggestions.append({
                "level": "L1",
                "input": inp,
                "suggested": top,
                "confidence": round(count / len(tlist), 2),
                "evidence": {"corrections": count, "examples": examples[inp][:3]},
                "reason": f"corrected>={count}",
            })

    return suggestions


def compute_tool_suggestions(days: int = 7) -> list:
    """L2: tool 建议 — 失败驱动 + 性能驱动"""
    events = load_events(days)
    tool_events = [
        e for e in events
        if e.get("layer") == "TOOL" or e.get("type") in ("tool", "task")
    ]
    failed = [
        e for e in events
        if not is_ok(e) and (
            e.get("layer") in ("TOOL", "SEC")
            or e.get("type") in ("tool", "task", "error", "http_error")
        )
    ]

    # Failure Learner
    by_tool_fail = defaultdict(list)
    for e in failed:
        by_tool_fail[tool_name(e)].append(e)

    suggestions = []
    for tool, errs in by_tool_fail.items():
        if len(errs) < 2:
            continue
        err_types = Counter()
        for e in errs:
            p = payload(e)
            code = p.get("status_code", "")
            err = p.get("err", p.get("error", ""))
            err_types[str(code) if code else err[:50] or "unknown"] += 1
        top_err, _ = err_types.most_common(1)[0]
        suggestions.append({
            "level": "L2",
            "name": tool,
            "action": "cooldown_10m" if len(errs) >= 3 else "monitor",
            "confidence": round(min(len(errs) / 5, 1.0), 2),
            "evidence": {"fails": len(errs), "top_err": top_err},
            "reason": f"repeat_fail>={len(errs)}",
        })

    # Perf Learner
    by_tool_perf = defaultdict(list)
    for e in tool_events:
        ms = latency(e)
        if ms > 0:
            by_tool_perf[tool_name(e)].append(ms)

    for tool, times in by_tool_perf.items():
        if len(times) < 3:
            continue
        times_sorted = sorted(times)
        p95 = times_sorted[math.ceil(0.95 * len(times_sorted)) - 1]
        median = times_sorted[len(times_sorted) // 2]
        if p95 > 5000:
            suggestions.append({
                "level": "L2",
                "name": tool,
                "action": "optimize_or_cache",
                "confidence": round(min(p95 / 10000, 1.0), 2),
                "evidence": {"p95_ms": p95, "median_ms": median, "samples": len(times)},
                "reason": f"p95>{p95}ms",
            })

    return suggestions


def compute_threshold_warnings(days: int = 7) -> list:
    """L3: 阈值警告（仅报警）"""
    events = load_events(days)
    matches = [e for e in events if e.get("type") == "match"]
    corrections = [e for e in events if e.get("type") == "correction"]
    warnings = []

    total = len(matches) + len(corrections)
    if total > 0:
        cr = len(corrections) / total
        if cr > 0.15:
            warnings.append({
                "field": "correction_rate",
                "current": round(cr, 2),
                "suggested": 0.10,
                "reason": "high_correction_rate",
            })

    if matches:
        low = [m for m in matches if (m.get("data") or {}).get("score", 1.0) < LOW_SCORE_THRESHOLD]
        lsr = len(low) / len(matches)
        if lsr > 0.15:
            warnings.append({
                "field": "low_score_rate",
                "current": round(lsr, 2),
                "suggested": 0.10,
                "reason": "too_many_low_score_matches",
            })

    return warnings


# 向后兼容：旧代码 `from learning.analyze import generate_daily_report` 仍可用
from learning.analyze_report import generate_full_report, generate_daily_report  # noqa: E402, F401

if __name__ == "__main__":
    import json
    action = sys.argv[1] if len(sys.argv) > 1 else "report"
    if action == "json":
        print(json.dumps(generate_full_report(), ensure_ascii=False, indent=2))
    elif action == "report":
        print(generate_daily_report())
    else:
        print("Usage: analyze.py [json|report]")

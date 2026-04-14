# aios/learning/analyze_report.py - 报告生成（输出层）
"""
从 analyze.py 的计算结果生成结构化报告 + 写入文件。
"""
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning.analyze import (
    compute_metrics,
    compute_top_issues,
    compute_alias_suggestions,
    compute_tool_suggestions,
    compute_threshold_warnings,
    LEARNING_DIR,
    AIOS_VERSION,
)


def _get_git_commit() -> str:
    try:
        import subprocess, os
        git_exe = r"C:\Program Files\Git\cmd\git.exe"
        r = subprocess.run(
            [git_exe, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
            cwd=os.path.join(os.environ.get("USERPROFILE", ""), ".openclaw", "workspace"),
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def generate_full_report(days: int = 7) -> dict:
    """完整结构化报告"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    window_from = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400)
    )
    metrics = compute_metrics(days)

    report = {
        "ts": now,
        "window": {"from": window_from, "to": now},
        **metrics,
        "model": {"default": "claude-sonnet-4-6", "fallback": "claude-opus-4-6"},
        "version": {"aios": AIOS_VERSION, "commit": _get_git_commit()},
        "top_issues": compute_top_issues(days),
        "alias_suggestions": compute_alias_suggestions(days),
        "tool_suggestions": compute_tool_suggestions(days),
        "threshold_warnings": compute_threshold_warnings(days),
    }

    # 写 suggestions.json
    sug = {
        "generated_at": now,
        "alias_suggestions": [
            {"input": s["input"], "suggested": s["suggested"],
             "reason": s["reason"], "confidence": s["confidence"]}
            for s in report["alias_suggestions"]
        ],
        "threshold_warnings": report["threshold_warnings"],
        "route_suggestions": [],
    }
    (LEARNING_DIR / "suggestions.json").write_text(
        json.dumps(sug, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def generate_daily_report(days: int = 1) -> str:
    r = generate_full_report(days)

    # 基线固化
    try:
        from learning.baseline import snapshot
        snapshot(days)
    except Exception:
        pass

    # 门禁检测
    gate_result = None
    try:
        from learning.guardrail import guardrail_from_history
        from learning.baseline import load_history
        from learning.tickets import ingest

        history = load_history(30)
        gate_tickets = guardrail_from_history(history)
        if gate_tickets:
            ingest([{
                "level": t.level, "name": t.title, "action": "investigate",
                "reason": t.evidence.get("rule", ""), "confidence": 0.8,
                "evidence": t.evidence,
            } for t in gate_tickets])
        gate_result = {
            "alerts": [{"title": t.title, "evidence": t.evidence} for t in gate_tickets],
            "status": "regression_detected" if gate_tickets else "gate_passed",
        }
    except Exception:
        pass

    # L2 → 工单
    try:
        from learning.tickets import ingest
        ingest(r.get("tool_suggestions", []))
    except Exception:
        pass

    report_text = _format_report(r, gate_result)
    (LEARNING_DIR / "daily_report.md").write_text(report_text, encoding="utf-8")
    return report_text


def _format_report(r: dict, gate_result: dict = None) -> str:
    """格式化为 Markdown 文本"""
    q = r.get("quality", {})
    rel = r.get("reliability", {})
    perf = r.get("performance", {})
    counts = r.get("counts", {})

    lines = [
        f"# AIOS Daily Report",
        f"Generated: {r['ts']}",
        f"Window: {r['window']['from']} → {r['window']['to']}\n",
        "## A. Metrics",
        f"- events: {counts.get('events', 0)}  matches: {counts.get('matches', 0)}  corrections: {counts.get('corrections', 0)}  tools: {counts.get('tools', 0)}",
        f"- correction_rate: {q.get('correction_rate', 0):.2%}",
        f"- tool_success_rate: {rel.get('tool_success_rate', 0):.2%}",
        f"- http_502: {rel.get('http_502', 0)}  http_404: {rel.get('http_404', 0)}",
    ]
    if perf.get("tool_p95_ms"):
        lines.append("- p95/p50:")
        for t in perf["tool_p95_ms"]:
            p95 = perf["tool_p95_ms"].get(t, "?")
            p50 = perf.get("tool_p50_ms", {}).get(t, "?")
            lines.append(f"  - {t}: p95={p95}ms p50={p50}ms")

    lines.append("\n## B. Top Issues")
    for inp, cnt in r["top_issues"].get("top_corrected_inputs", {}).items():
        lines.append(f'- corrected: "{inp}" x{cnt}')
    for t, cnt in r["top_issues"].get("top_failed_tools", {}).items():
        lines.append(f"- failed: {t} x{cnt}")

    lines.append("\n## C. Alias Suggestions (L1)")
    for s in r["alias_suggestions"]:
        lines.append(f"- \"{s['input']}\" → \"{s['suggested']}\" conf={s['confidence']} ({s['reason']})")

    lines.append("\n## D. Tool Suggestions (L2)")
    for s in r["tool_suggestions"]:
        lines.append(f"- {s['name']}: {s['action']} conf={s['confidence']} ({s['reason']})")

    if r["threshold_warnings"]:
        lines.append("\n## E. Threshold Warnings")
        for w in r["threshold_warnings"]:
            lines.append(f"- {w['field']}: {w['current']} → {w['suggested']}")

    if not any([r["alias_suggestions"], r["tool_suggestions"], r["threshold_warnings"]]):
        lines.append("\n- No suggestions")

    try:
        from learning.baseline import evolution_score
        evo = evolution_score()
        lines.append(f"\n## F. Evolution Score")
        lines.append(f"- score: {evo['score']}  grade: {evo['grade']}")
        for k, v in evo.get("breakdown", {}).items():
            lines.append(f"  - {k}: {v['value']} (w={v['weight']})")
    except Exception:
        pass

    if gate_result and gate_result.get("alerts"):
        lines.append(f"\n## G. Regression Gate")
        for a in gate_result["alerts"]:
            lines.append(f"- {a['title']}: {a['evidence'].get('rule', '')}")
    elif gate_result:
        lines.append(f"\n## G. Regression Gate")
        lines.append(f"- {gate_result['status']}")

    return "\n".join(lines)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "report"
    if action == "json":
        print(json.dumps(generate_full_report(), ensure_ascii=False, indent=2))
    elif action == "report":
        print(generate_daily_report())
    else:
        print("Usage: analyze_report.py [json|report]")

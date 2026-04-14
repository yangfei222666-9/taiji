# aios/learning/baseline.py - 基线固化（metrics_history.jsonl）
"""
每次 analyze 后追加一条基线快照，用于画趋势。
缓存机制: snapshot/score 结果缓存5分钟，减少重复计算开销
"""

import json, time, sys, math, os
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.engine import load_events, append_jsonl
from core.config import get_path

LEARNING_DIR = Path(__file__).resolve().parent
HISTORY_FILE = get_path("paths.metrics_history") or (
    LEARNING_DIR / "metrics_history.jsonl"
)
CACHE_FILE = LEARNING_DIR / "baseline_cache.json"
CACHE_TTL_SECONDS = 300  # 5分钟缓存

# --- Cache Management ---


def load_cache(action):
    """加载缓存，如果未过期则返回结果"""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

        if action not in cache:
            return None

        entry = cache[action]
        cached_at = entry.get("cached_at", 0)
        age = time.time() - cached_at

        if age < CACHE_TTL_SECONDS:
            return entry.get("data")
        else:
            return None
    except Exception:
        return None


def save_cache(action, data):
    """保存结果到缓存"""
    cache = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass

    cache[action] = {"cached_at": time.time(), "data": data}

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _count_severity(events: list) -> dict:
    """统计事件严重度分布，统一 fatal→CRIT 映射"""
    counts = {"CRIT": 0, "WARN": 0, "INFO": 0, "ERR": 0}
    for e in events:
        status = e.get("status", "ok")
        layer = e.get("layer", "")
        event_name = e.get("event", "")
        payload = e.get("payload") or {}

        # fatal 事件 → CRIT
        if any(k in event_name.lower() for k in ("fatal", "circuit_breaker")):
            counts["CRIT"] += 1
        elif status == "err" and layer == "SEC":
            counts["CRIT"] += 1
        elif status == "err":
            counts["ERR"] += 1
        elif layer in ("SEC",) and "hallucination" in event_name:
            counts["WARN"] += 1
        else:
            counts["INFO"] += 1
    return counts


def _inline_evolution_score(record: dict) -> dict:
    """从单条 snapshot record 直接算 evolution_score，不依赖 history"""
    tsr = record.get("tool_success_rate", 1.0)
    cr = record.get("correction_rate", 0)
    h502 = record.get("http_502_rate", 0)

    p95 = record.get("tool_p95_ms", {})
    if p95:
        slow = sum(1 for v in p95.values() if v > 5000)
        p95_slow_ratio = slow / len(p95)
    else:
        p95_slow_ratio = 0
    
    # 资源效率：峰值 CPU/内存超标扣分
    resource = record.get("resource", {})
    peak_cpu = resource.get("peak_cpu_percent", 0)
    peak_mem = resource.get("peak_memory_percent", 0)
    
    # CPU > 80% 或 内存 > 85% 算超标
    resource_penalty = 0
    if peak_cpu > 80:
        resource_penalty += (peak_cpu - 80) / 100  # 最多扣 0.2
    if peak_mem > 85:
        resource_penalty += (peak_mem - 85) / 100  # 最多扣 0.15
    resource_penalty = min(resource_penalty, 0.2)  # 封顶 0.2

    score = round(
        tsr * 0.4           # 系统稳定性（少出错）
        - cr * 0.15         # 学习能力（纠正率下降）
        - h502 * 0.15       # 网络稳定性
        - p95_slow_ratio * 0.15  # 响应速度
        - resource_penalty * 0.15  # 资源效率
    , 4)

    if score >= 0.35:
        grade = "healthy"
    elif score >= 0.25:
        grade = "ok"
    elif score >= 0.15:
        grade = "degraded"
    else:
        grade = "critical"

    return {"score": score, "grade": grade}


def _classify(e: dict) -> str:
    """v0.1/v0.2 兼容分类"""
    # v0.1: type 字段
    if "type" in e:
        return e["type"]
    # v0.2: layer + payload._v1_type
    layer = e.get("layer", "")
    v1 = (e.get("payload") or {}).get("_v1_type", "")
    if v1:
        return v1
    layer_map = {"TOOL": "tool", "MEM": "match", "SEC": "http_error"}
    return layer_map.get(layer, "")


def _tool_name_ms(e: dict) -> tuple:
    """从 v0.1 或 v0.2 事件中提取 (tool_name, ms, ok)"""
    # v0.2: payload.name / payload.ms
    p = e.get("payload") or {}
    name = p.get("name", "")
    ms = p.get("ms", 0)
    ok = p.get("ok", True)
    if name and ms:
        return name, ms, ok
    # v0.1: data.name / data.ms
    data = e.get("data") or {}
    name = name or data.get("name", data.get("tool", e.get("source", "?")))
    ms = ms or data.get("ms", data.get("elapsed_ms", 0))
    ok = data.get("ok", ok)
    # v0.2 latency_ms fallback
    if not ms:
        ms = e.get("latency_ms", 0)
    return name, ms, ok


def snapshot(days: int = 1) -> dict:
    events = load_events(days)

    matches = [e for e in events if _classify(e) in ("match", "memory_recall")]
    corrections = [e for e in events if _classify(e) == "correction"]
    tools = [e for e in events if _classify(e) == "tool" or e.get("layer") == "TOOL"]
    http_errors = [
        e
        for e in events
        if _classify(e) == "http_error"
        or (e.get("layer") == "SEC" and "http" in e.get("event", ""))
    ]
    
    # 资源监控数据（从 KERNEL 层 resource_snapshot 事件提取）
    resource_events = [
        e for e in events 
        if e.get("layer") == "KERNEL" and e.get("event") == "resource_snapshot"
    ]
    
    if resource_events:
        cpu_values = [e.get("payload", {}).get("cpu_percent", 0) for e in resource_events]
        mem_values = [e.get("payload", {}).get("memory_percent", 0) for e in resource_events]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        avg_mem = sum(mem_values) / len(mem_values)
        peak_cpu = max(cpu_values)
        peak_mem = max(mem_values)
    else:
        avg_cpu = avg_mem = peak_cpu = peak_mem = 0

    total_match = len(matches) + len(corrections)
    correction_rate = len(corrections) / total_match if total_match > 0 else 0

    tool_ok = [t for t in tools if _tool_name_ms(t)[2]]
    tool_success_rate = len(tool_ok) / len(tools) if tools else 1.0

    # p95 per tool
    by_tool = defaultdict(list)
    for e in tools:
        name, ms, _ = _tool_name_ms(e)
        if ms > 0:
            by_tool[name].append(ms)

    tool_p95 = {}
    for name, times in by_tool.items():
        if len(times) >= 2:
            s = sorted(times)
            idx = math.ceil(0.95 * len(s)) - 1
            tool_p95[name] = s[idx]

    # http error rates
    http_codes = Counter(
        (e.get("data") or {}).get("status_code", 0) for e in http_errors
    )
    total_http = sum(http_codes.values())

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "period_days": days,
        "correction_rate": round(correction_rate, 4),
        "tool_success_rate": round(tool_success_rate, 4),
        "tool_p95_ms": tool_p95,
        "http_error_count": total_http,
        "http_502_rate": round(http_codes.get(502, 0) / max(total_http, 1), 3),
        "http_404_rate": round(http_codes.get(404, 0) / max(total_http, 1), 3),
        "total_events": len(events),
        # 事件严重度统计（fatal/error/warn 分级）
        "severity_counts": _count_severity(events),
        # 资源效率指标
        "resource": {
            "avg_cpu_percent": round(avg_cpu, 2),
            "avg_memory_percent": round(avg_mem, 2),
            "peak_cpu_percent": round(peak_cpu, 2),
            "peak_memory_percent": round(peak_mem, 2),
        }
    }

    # 强制内联 evolution_score + grade（不缺 key）
    evo = _inline_evolution_score(record)
    record["evolution_score"] = evo["score"]
    record["grade"] = evo["grade"]

    # Schema 校验：必须字段齐全才入正式快照
    REQUIRED_KEYS = {
        "ts",
        "correction_rate",
        "tool_success_rate",
        "evolution_score",
        "grade",
    }
    missing_keys = REQUIRED_KEYS - set(record.keys())
    if missing_keys:
        record["_schema_warning"] = f"missing keys: {sorted(missing_keys)}"
        # 仍然写入但标记，不静默丢失

    append_jsonl(HISTORY_FILE, record)
    return record


def load_history(limit: int = 30) -> list:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def trend_summary(limit: int = 7) -> str:
    history = load_history(limit)
    if len(history) < 2:
        return "Not enough data for trend (need >= 2 snapshots)"

    first, last = history[0], history[-1]
    lines = [f"Trend ({len(history)} snapshots):"]

    cr_delta = last["correction_rate"] - first["correction_rate"]
    lines.append(
        f"  correction_rate: {first['correction_rate']:.2%} → {last['correction_rate']:.2%} ({'+' if cr_delta >= 0 else ''}{cr_delta:.2%})"
    )

    ts_delta = last["tool_success_rate"] - first["tool_success_rate"]
    lines.append(
        f"  tool_success_rate: {first['tool_success_rate']:.2%} → {last['tool_success_rate']:.2%} ({'+' if ts_delta >= 0 else ''}{ts_delta:.2%})"
    )

    # p95 trend per tool
    all_tools = set(
        list(first.get("tool_p95_ms", {}).keys())
        + list(last.get("tool_p95_ms", {}).keys())
    )
    for t in sorted(all_tools):
        p_first = first.get("tool_p95_ms", {}).get(t)
        p_last = last.get("tool_p95_ms", {}).get(t)
        if p_first and p_last:
            lines.append(f"  {t} p95: {p_first}ms → {p_last}ms")

    return "\n".join(lines)


def evolution_score(limit: int = 7) -> dict:
    """
    进化评分：基于最新 baseline 快照直接计算。

    score = tool_success_rate * 0.4        # 系统稳定性
          - correction_rate * 0.15         # 学习能力
          - http_502_rate * 0.15           # 网络稳定性
          - p95_slow_ratio * 0.15          # 响应速度
          - resource_penalty * 0.15        # 资源效率

    resource_penalty: CPU > 80% 或 内存 > 85% 扣分
    score: 0.0 (最差) ~ 1.0 (完美)
    """
    history = load_history(limit)
    if not history:
        return {"score": 0, "grade": "N/A", "reason": "no_data"}

    last = history[-1]

    tsr = last.get("tool_success_rate", 1.0)
    cr = last.get("correction_rate", 0)
    h502 = last.get("http_502_rate", 0)

    # p95_slow_ratio: 超过 5s 的 tool 占比
    p95 = last.get("tool_p95_ms", {})
    if p95:
        slow = sum(1 for v in p95.values() if v > 5000)
        p95_slow_ratio = slow / len(p95)
    else:
        p95_slow_ratio = 0
    
    # 资源效率
    resource = last.get("resource", {})
    peak_cpu = resource.get("peak_cpu_percent", 0)
    peak_mem = resource.get("peak_memory_percent", 0)
    
    resource_penalty = 0
    if peak_cpu > 80:
        resource_penalty += (peak_cpu - 80) / 100
    if peak_mem > 85:
        resource_penalty += (peak_mem - 85) / 100
    resource_penalty = min(resource_penalty, 0.2)

    score = round(
        tsr * 0.4 
        - cr * 0.15 
        - h502 * 0.15 
        - p95_slow_ratio * 0.15 
        - resource_penalty * 0.15
    , 4)

    if score >= 0.35:
        grade = "healthy"
    elif score >= 0.25:
        grade = "ok"
    elif score >= 0.15:
        grade = "degraded"
    else:
        grade = "critical"

    return {
        "score": score,
        "grade": grade,
        "breakdown": {
            "tool_success_rate": {"value": tsr, "weight": 0.4},
            "correction_rate": {"value": cr, "weight": -0.15},
            "http_502_rate": {"value": h502, "weight": -0.15},
            "p95_slow_ratio": {"value": round(p95_slow_ratio, 3), "weight": -0.15},
            "resource_penalty": {"value": round(resource_penalty, 3), "weight": -0.15},
        },
        "snapshot_ts": last.get("ts", "?"),
    }


def regression_gate(limit: int = 5) -> dict:
    """门禁检测：委托给 guardrail.py"""
    from learning.guardrail import run_guardrail

    history = load_history(limit)
    return run_guardrail(history)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "snapshot"

    # 可缓存的操作
    cacheable = ["snapshot", "score"]

    if action in cacheable:
        cached = load_cache(action)
        if cached:
            print(json.dumps(cached, ensure_ascii=False, indent=2))
            sys.exit(0)

    # 缓存未命中，执行实际操作
    if action == "snapshot":
        r = snapshot()
        save_cache(action, r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif action == "trend":
        print(trend_summary())
    elif action == "score":
        r = evolution_score()
        save_cache(action, r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif action == "gate":
        print(json.dumps(regression_gate(), ensure_ascii=False, indent=2))
    elif action == "history":
        for r in load_history():
            print(json.dumps(r, ensure_ascii=False))
    else:
        print("Usage: baseline.py [snapshot|trend|score|gate|history]")

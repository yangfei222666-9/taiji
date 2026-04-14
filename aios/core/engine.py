# aios/core/engine.py - 事件引擎 v0.2（5层架构 + JSONL）
"""
v0.2 Schema:
{
  "ts": "ISO-8601",
  "epoch": unix_seconds,
  "layer": "KERNEL|COMMS|TOOL|MEM|SEC",
  "event": "具体事件名",
  "status": "ok|err",
  "latency_ms": int (可选),
  "payload": {} (动态上下文)
}

向后兼容: 旧的 log_event/log_tool_event 仍可用，自动映射到新 schema。
"""

import json, time, os, sys, threading
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import get_path

# ── 5层架构常量 ──
LAYER_KERNEL = "KERNEL"
LAYER_COMMS = "COMMS"
LAYER_TOOL = "TOOL"
LAYER_MEM = "MEM"
LAYER_SEC = "SEC"
VALID_LAYERS = {LAYER_KERNEL, LAYER_COMMS, LAYER_TOOL, LAYER_MEM, LAYER_SEC}


def _events_path() -> Path:
    return (
        get_path("paths.events")
        or Path(__file__).resolve().parent.parent / "events" / "events.jsonl"
    )


_jsonl_lock = threading.Lock()


def append_jsonl(path: Path, obj: dict):
    """通用 JSONL 追加（线程安全）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _jsonl_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ── 严重度标准化 ──


def _classify_severity(layer: str, event: str, status: str) -> str:
    """
    统一事件严重度映射，确保 fatal→CRIT 不丢失。
    返回: CRIT / WARN / INFO
    """
    ev_lower = event.lower()
    # fatal / circuit_breaker → 一律 CRIT
    if "fatal" in ev_lower or "circuit_breaker" in ev_lower:
        return "CRIT"
    # SEC 层 err → CRIT
    if layer == LAYER_SEC and status == "err":
        return "CRIT"
    # 其他 err → WARN
    if status == "err":
        return "WARN"
    # 正常 → INFO
    return "INFO"


# ── v0.2 核心: emit ──


def emit(
    layer: str,
    event: str,
    status: str = "ok",
    latency_ms: int = None,
    payload: dict = None,
) -> dict:
    """
    v0.2 统一事件发射器。所有事件都走这里。

    layer: KERNEL / COMMS / TOOL / MEM / SEC
    event: 具体事件名 (如 tool_exec, memory_recall, loop_start)
    status: ok / err
    latency_ms: 耗时(可选)
    payload: 动态上下文(可选)
    """
    if layer not in VALID_LAYERS:
        layer = LAYER_TOOL  # fallback

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "epoch": int(time.time()),
        "layer": layer,
        "event": event,
        "status": status,
        "severity": _classify_severity(layer, event, status),
    }
    if latency_ms is not None:
        record["latency_ms"] = latency_ms
    if payload:
        record["payload"] = payload

    append_jsonl(_events_path(), record)
    return record


# ── v0.1 兼容层 (映射到 emit) ──


def log_event(event_type: str, source: str, summary: str, data: dict = None) -> dict:
    """v0.1 兼容: 自动映射 type→layer"""
    layer_map = {
        "tool": LAYER_TOOL,
        "task": LAYER_TOOL,
        "match": LAYER_MEM,
        "correction": LAYER_MEM,
        "error": LAYER_SEC,
        "http_error": LAYER_SEC,
    }
    layer = layer_map.get(event_type, LAYER_TOOL)
    status = "ok"
    if data and not data.get("ok", True):
        status = "err"
    if event_type in ("error", "http_error"):
        status = "err"

    ms = None
    if data:
        ms = data.get("ms", data.get("elapsed_ms"))

    # 保留完整 payload 用于向后兼容
    payload = {"_v1_type": event_type, "_v1_source": source, "_v1_summary": summary}
    if data:
        payload.update(data)

    return emit(
        layer, f"{event_type}_{source}" if source else event_type, status, ms, payload
    )


def log_tool_event(
    name: str, ok: bool, ms: int, err: str = None, meta: dict = None
) -> dict:
    """v0.1 兼容: tool 事件 → emit(TOOL, ...)"""
    payload = {"name": name, "ok": ok, "ms": ms}
    if not ok and err:
        payload["err"] = err[:500]
    if meta:
        payload["meta"] = meta
    return emit(LAYER_TOOL, f"tool_{name}", "ok" if ok else "err", ms, payload)


# ── v0.2 便捷方法: 各层专用 ──


def log_kernel(event: str, status: str = "ok", latency_ms: int = None, **kw) -> dict:
    """内核层事件: loop_start, context_prune, token_usage"""
    return emit(LAYER_KERNEL, event, status, latency_ms, kw or None)


def log_comms(event: str, status: str = "ok", latency_ms: int = None, **kw) -> dict:
    """通信层事件: user_input, plan_generated, reflection"""
    return emit(LAYER_COMMS, event, status, latency_ms, kw or None)


def log_mem(event: str, status: str = "ok", latency_ms: int = None, **kw) -> dict:
    """存储层事件: memory_recall, memory_store, memory_miss"""
    return emit(LAYER_MEM, event, status, latency_ms, kw or None)


def log_sec(event: str, status: str = "ok", latency_ms: int = None, **kw) -> dict:
    """安全层事件: runtime_error, hallucination, ticket_created"""
    return emit(LAYER_SEC, event, status, latency_ms, kw or None)


# ── v0.2 听诊器: trace_span 上下文管理器 ──

from contextlib import contextmanager


@contextmanager
def trace_span(layer: str, event: str, **extra_payload):
    """
    自动计时的事件探针。用法：

        with trace_span("KERNEL", "loop_iteration", loop_id=1):
            do_work()

    自动记录 status(ok/err) + latency_ms，异常会继续抛出。
    yield 一个 dict，可在 with 块内追加 payload：

        with trace_span("MEM", "memory_recall") as ctx:
            results = search(...)
            ctx["hit_count"] = len(results)
    """
    ctx = dict(extra_payload)  # 可变 payload，with 块内可追加
    t0 = time.monotonic()
    status = "ok"
    try:
        yield ctx
    except Exception as e:
        status = "err"
        ctx["error"] = str(e)[:500]
        raise
    finally:
        ms = round((time.monotonic() - t0) * 1000)
        emit(layer, event, status, ms, ctx or None)


def load_events(days: int = 30, event_type: str = None, layer: str = None) -> list:
    """加载事件，支持 v0.1 type 过滤和 v0.2 layer 过滤"""
    p = _events_path()
    if not p.exists():
        return []
    cutoff = time.time() - days * 86400
    out = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:  # 流式逐行读取，避免大文件 OOM
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    raw_ts = ev.get("epoch")
                    if raw_ts is None:
                        raw_ts = ev.get("ts", 0)
                    ts = 0.0
                    if isinstance(raw_ts, (int, float)):
                        ts = float(raw_ts)
                    else:
                        s = str(raw_ts or "").strip()
                        if not s:
                            ts = 0.0
                        else:
                            try:
                                ts = float(s)
                            except Exception:
                                try:
                                    s2 = s.replace("Z", "+00:00")
                                    dt = datetime.fromisoformat(s2)
                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    ts = dt.timestamp()
                                except Exception:
                                    ts = 0.0
                    if ts and ts < cutoff:
                        continue
                    # v0.2 layer 过滤
                    if layer and ev.get("layer") != layer:
                        continue
                    # v0.1 兼容: type 过滤 (查 payload._v1_type 或旧 type 字段)
                    if event_type:
                        old_type = ev.get("type", "")
                        v1_type = (ev.get("payload") or {}).get("_v1_type", "")
                        if event_type not in (old_type, v1_type):
                            continue
                    out.append(ev)
                except Exception:
                    continue
    except IOError:
        pass
    return out


def count_by_type(days: int = 30) -> dict:
    events = load_events(days)
    counts = {}
    for ev in events:
        t = ev.get("layer", ev.get("type", "unknown"))
        counts[t] = counts.get(t, 0) + 1
    return counts


def count_by_layer(days: int = 30) -> dict:
    """v0.2: 按层统计"""
    events = load_events(days)
    counts = {l: 0 for l in VALID_LAYERS}
    for ev in events:
        l = ev.get("layer", "TOOL")
        counts[l] = counts.get(l, 0) + 1
    return counts

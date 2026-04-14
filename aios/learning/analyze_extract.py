# aios/learning/analyze_extract.py - 事件字段提取（输入层）
"""
从 v0.1/v0.2 schema 统一提取事件字段。
所有 compute_* 函数都通过这些辅助函数访问事件数据。
"""


def event_name(e: dict) -> str:
    """提取事件名（兼容 v0.1 type 和 v0.2 event）"""
    name = e.get("event", "")
    if name:
        return name
    return (e.get("payload") or {}).get("_v1_type", e.get("type", ""))


def is_ok(e: dict) -> bool:
    """判断事件是否成功"""
    if e.get("status") == "err":
        return False
    p = e.get("payload", e.get("data", {}))
    return p.get("ok", True)


def tool_name(e: dict) -> str:
    """提取工具名"""
    p = e.get("payload", e.get("data", {}))
    return p.get("name", p.get("tool", e.get("source", e.get("event", "?"))))


def latency(e: dict) -> int:
    """提取延迟 ms"""
    ms = e.get("latency_ms", 0)
    if ms:
        return ms
    p = e.get("payload", e.get("data", {}))
    return p.get("ms", p.get("elapsed_ms", 0))


def payload(e: dict) -> dict:
    """提取 payload（兼容 v0.1 data 和 v0.2 payload）"""
    return e.get("payload", e.get("data", {}))


# 层映射（v0.1 type → v0.2 layer）
LAYER_MAP = {
    "tool": "TOOL",
    "task": "TOOL",
    "match": "MEM",
    "correction": "MEM",
    "confirm": "MEM",
    "lesson": "MEM",
    "error": "SEC",
    "http_error": "SEC",
    "health": "KERNEL",
    "deploy": "KERNEL",
}


def classify_layer(e: dict) -> str:
    """事件分层（兼容 v0.1/v0.2）"""
    layer = e.get("layer")
    if layer:
        return layer if layer in ("KERNEL", "COMMS", "TOOL", "MEM", "SEC") else "TOOL"
    old_type = e.get("type", "")
    v1_type = (e.get("payload") or {}).get("_v1_type", "")
    return LAYER_MAP.get(old_type) or LAYER_MAP.get(v1_type) or "TOOL"

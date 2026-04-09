# aios/core/dispatcher.py - 事件调度协调器 v0.1
"""
把感知事件分发给对应的处理器。

职责：
1. 消费 EventBus 队列中的待处理事件
2. 运行感知探针收集新事件
3. 按优先级排序，分发给注册的处理器
4. 生成行动建议（供心跳或主会话消费）

设计：无状态调度，每次调用 dispatch() 做一轮。
"""

import json, time, uuid
from pathlib import Path
from typing import Callable

from core.event_bus import (
    get_bus,
    Event,
    PRIORITY_NORMAL,
    PRIORITY_HIGH,
    PRIORITY_CRITICAL,
)
from core.sensors import scan_all

ACTIONS_FILE = (
    Path(__file__).resolve().parent.parent / "events" / "pending_actions.jsonl"
)


def _append_action(action: dict):
    ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ACTIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(action, ensure_ascii=False) + "\n")


# 当前 dispatch 轮次的 trace_id（模块级，每次 dispatch() 重置）
_current_trace_id: str = ""


def _default_handlers() -> dict[str, Callable]:
    """默认事件处理器映射"""
    return {
        "sensor.file.modified": _handle_file_change,
        "sensor.file.created": _handle_file_change,
        "sensor.process.stopped": _handle_process_stopped,
        "sensor.system.health": _handle_system_health,
        "sensor.network.unreachable": _handle_network_unreachable,
        "sensor.app.started": _handle_app_event,
        "sensor.app.stopped": _handle_app_event,
        "sensor.lol.version_updated": _handle_lol_update,
        "sensor.gpu.critical": _handle_gpu_critical,
    }


def _handle_file_change(event: Event):
    path = event.payload.get("path", "")
    change_type = event.payload.get("type", "modified")
    critical_files = ["alerts.py", "baseline.py", "lessons.jsonl", "events.jsonl"]
    if any(cf in path for cf in critical_files):
        _append_action(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "trace_id": _current_trace_id,
                "type": "review_change",
                "priority": "normal",
                "summary": f"关键文件{change_type}: {Path(path).name}",
                "detail": path,
            }
        )


def _handle_process_stopped(event: Event):
    proc = event.payload.get("process", "")
    important = ["openclaw", "node"]
    if any(p in proc.lower() for p in important):
        _append_action(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "trace_id": _current_trace_id,
                "type": "process_alert",
                "priority": "high",
                "summary": f"关键进程停止: {proc}",
                "detail": event.payload,
            }
        )


def _handle_system_health(event: Event):
    disk_free = event.payload.get("disk_c_free_gb", 999)
    mem_pct = event.payload.get("memory_pct", 0)

    if disk_free < 10:
        _append_action(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "trace_id": _current_trace_id,
                "type": "resource_warning",
                "priority": "high" if disk_free < 5 else "normal",
                "summary": f"磁盘空间不足: C: 剩余 {disk_free}GB",
            }
        )

    if mem_pct > 90:
        _append_action(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "trace_id": _current_trace_id,
                "type": "resource_warning",
                "priority": "high",
                "summary": f"内存使用率过高: {mem_pct}%",
            }
        )


def _handle_network_unreachable(event: Event):
    target = event.payload.get("target", "")
    _append_action(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trace_id": _current_trace_id,
            "type": "network_alert",
            "priority": "high",
            "summary": f"网络不可达: {target}",
            "detail": event.payload,
        }
    )


def _handle_app_event(event: Event):
    """处理应用启动/关闭事件，记录到习惯追踪器"""
    app = event.payload.get("app", "")
    status = event.payload.get("status", "")

    # 导入习惯追踪器
    try:
        from learning.habits.tracker import track_app_event

        track_app_event(app, status, event.timestamp)
    except Exception as e:
        # 静默失败，不影响主流程
        pass


def _handle_lol_update(event: Event):
    """处理 LOL 版本更新事件"""
    old_ver = event.payload.get("old_version", "")
    new_ver = event.payload.get("new_version", "")
    _append_action(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trace_id": _current_trace_id,
            "type": "lol_update",
            "priority": "high",
            "summary": f"LOL 版本更新: {old_ver} → {new_ver}",
            "detail": "建议运行 ARAM 数据刷新",
        }
    )


def _handle_gpu_critical(event: Event):
    """处理 GPU 严重过热事件"""
    temp = event.payload.get("temp", 0)
    _append_action(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trace_id": _current_trace_id,
            "type": "gpu_critical",
            "priority": "critical",
            "summary": f"GPU 温度严重过热: {temp}°C",
            "detail": "建议立即检查散热系统",
        }
    )


def dispatch(run_sensors: bool = True) -> dict:
    """
    一轮调度：
    1. 生成 trace_id 串联本轮所有事件
    2. 可选：运行探针收集新事件
    3. 消费队列中的待处理事件
    4. 分发给处理器
    5. 返回本轮摘要（含 trace_id）
    """
    global _current_trace_id
    _current_trace_id = uuid.uuid4().hex[:12]

    bus = get_bus()
    handlers = _default_handlers()

    # 注册处理器
    for pattern, handler in handlers.items():
        bus.subscribe(pattern, handler)

    sensor_results = {}
    if run_sensors:
        sensor_results = scan_all()

    # 消费跨会话队列
    queued = bus.drain_queue(limit=20)
    for event in queued:
        bus.publish(event)

    # 清理订阅（避免重复注册）
    for pattern, handler in handlers.items():
        bus.unsubscribe(handler)

    return {
        "trace_id": _current_trace_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sensor_results": {
            "file_changes": len(sensor_results.get("file_changes", [])),
            "process_events": len(sensor_results.get("process_events", [])),
            "system_health": sensor_results.get("system_health", {}),
            "network": sensor_results.get("network", {}),
        },
        "queued_processed": len(queued),
        "bus_pending": bus.pending_count(),
    }


def get_pending_actions(limit: int = 10) -> list[dict]:
    """读取待处理的行动建议"""
    if not ACTIONS_FILE.exists():
        return []
    lines = ACTIONS_FILE.read_text(encoding="utf-8").splitlines()
    actions = []
    for line in lines[-limit:]:
        if line.strip():
            try:
                actions.append(json.loads(line))
            except Exception:
                continue
    return actions


def clear_actions():
    """清空已处理的行动建议"""
    ACTIONS_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    result = dispatch()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    actions = get_pending_actions()
    if actions:
        print(f"\n待处理行动 ({len(actions)}):")
        for a in actions:
            print(f"  [{a.get('priority','?')}] {a.get('summary','')}")

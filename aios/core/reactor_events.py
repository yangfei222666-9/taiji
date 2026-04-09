"""
Reactor 事件发射器
将 Reactor 操作改造为事件驱动模式
"""
from pathlib import Path
import sys

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import create_event, EventType
from core.event_bus import emit


def emit_reactor_matched(playbook_id: str, alert_id: str, confidence: float):
    """发射 reactor 匹配事件"""
    event = create_event(
        EventType.REACTOR_MATCHED,
        source="reactor",
        playbook_id=playbook_id,
        alert_id=alert_id,
        confidence=confidence
    )
    emit(event)


def emit_reactor_executed(playbook_id: str, alert_id: str, action: str):
    """发射 reactor 执行事件"""
    event = create_event(
        EventType.REACTOR_EXECUTED,
        source="reactor",
        playbook_id=playbook_id,
        alert_id=alert_id,
        action=action
    )
    emit(event)


def emit_reactor_success(playbook_id: str, alert_id: str, duration_ms: int):
    """发射 reactor 成功事件"""
    event = create_event(
        EventType.REACTOR_SUCCESS,
        source="reactor",
        playbook_id=playbook_id,
        alert_id=alert_id,
        duration_ms=duration_ms
    )
    emit(event)


def emit_reactor_failed(playbook_id: str, alert_id: str, error: str):
    """发射 reactor 失败事件"""
    event = create_event(
        EventType.REACTOR_FAILED,
        source="reactor",
        playbook_id=playbook_id,
        alert_id=alert_id,
        error=error
    )
    emit(event)

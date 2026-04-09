"""
Resource Monitor 事件发射器
将资源监控改造为事件驱动模式
"""
from pathlib import Path
import sys

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import create_event, EventType
from core.event_bus import emit


def emit_cpu_spike(cpu_percent: float, threshold: float):
    """发射 CPU 峰值事件"""
    event = create_event(
        EventType.RESOURCE_CPU_SPIKE,
        source="resource_monitor",
        cpu_percent=cpu_percent,
        threshold=threshold,
        severity="high" if cpu_percent > 90 else "medium"
    )
    emit(event)


def emit_memory_high(memory_percent: float, threshold: float):
    """发射内存高占用事件"""
    event = create_event(
        EventType.RESOURCE_MEMORY_HIGH,
        source="resource_monitor",
        memory_percent=memory_percent,
        threshold=threshold,
        severity="high" if memory_percent > 90 else "medium"
    )
    emit(event)


def emit_gpu_overload(gpu_percent: float, threshold: float):
    """发射 GPU 过载事件"""
    event = create_event(
        EventType.RESOURCE_GPU_OVERLOAD,
        source="resource_monitor",
        gpu_percent=gpu_percent,
        threshold=threshold,
        severity="high" if gpu_percent > 95 else "medium"
    )
    emit(event)


# 便捷函数：自动检测并发射事件
def check_and_emit_resource_events(
    cpu_percent: float,
    memory_percent: float,
    gpu_percent: float = None,
    cpu_threshold: float = 80.0,
    memory_threshold: float = 85.0,
    gpu_threshold: float = 90.0
):
    """
    检查资源使用情况并自动发射事件
    
    Args:
        cpu_percent: CPU 使用率
        memory_percent: 内存使用率
        gpu_percent: GPU 使用率（可选）
        cpu_threshold: CPU 阈值
        memory_threshold: 内存阈值
        gpu_threshold: GPU 阈值
    """
    if cpu_percent > cpu_threshold:
        emit_cpu_spike(cpu_percent, cpu_threshold)
    
    if memory_percent > memory_threshold:
        emit_memory_high(memory_percent, memory_threshold)
    
    if gpu_percent is not None and gpu_percent > gpu_threshold:
        emit_gpu_overload(gpu_percent, gpu_threshold)

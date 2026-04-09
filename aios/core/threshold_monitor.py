"""
Resource Threshold Monitor - 持续时间判定 + 滞回
"""

import time
from typing import Optional

from .event import EventType, create_event
from .event_bus import EventBus, get_event_bus


class ThresholdMonitor:
    def __init__(
        self,
        bus: Optional[EventBus] = None,
        cpu_trigger_threshold: float = 80.0,
        cpu_recover_threshold: float = 70.0,
        cpu_duration_seconds: int = 10,
        memory_trigger_threshold: float = 85.0,
        memory_recover_threshold: float = 75.0,
        memory_duration_seconds: int = 30,
    ):
        self.bus = bus or get_event_bus()

        self.cpu_trigger_threshold = cpu_trigger_threshold
        self.cpu_recover_threshold = cpu_recover_threshold
        self.cpu_duration_seconds = cpu_duration_seconds

        self.memory_trigger_threshold = memory_trigger_threshold
        self.memory_recover_threshold = memory_recover_threshold
        self.memory_duration_seconds = memory_duration_seconds

        self.cpu_candidate_start: Optional[float] = None
        self.cpu_confirmed = False

        self.memory_candidate_start: Optional[float] = None
        self.memory_confirmed = False

    def check_cpu(self, cpu_percent: float) -> None:
        now = time.time()

        if self.cpu_confirmed:
            if cpu_percent <= self.cpu_recover_threshold:
                self.cpu_confirmed = False
                self.cpu_candidate_start = None
                self.bus.emit(
                    create_event(
                        EventType.RESOURCE_RECOVERED,
                        source="threshold_monitor",
                        resource_type="cpu",
                        value=cpu_percent,
                        threshold=self.cpu_recover_threshold,
                    )
                )
            return

        if self.cpu_candidate_start is not None:
            if cpu_percent > self.cpu_trigger_threshold:
                duration = now - self.cpu_candidate_start
                if duration >= self.cpu_duration_seconds:
                    self.cpu_confirmed = True
                    self.bus.emit(
                        create_event(
                            EventType.RESOURCE_THRESHOLD_CONFIRMED,
                            source="threshold_monitor",
                            resource_type="cpu",
                            value=cpu_percent,
                            threshold=self.cpu_trigger_threshold,
                            duration_seconds=duration,
                        )
                    )
            else:
                self.cpu_candidate_start = None
            return

        if cpu_percent > self.cpu_trigger_threshold:
            self.cpu_candidate_start = now
            self.bus.emit(
                create_event(
                    EventType.RESOURCE_THRESHOLD_CANDIDATE,
                    source="threshold_monitor",
                    resource_type="cpu",
                    value=cpu_percent,
                    threshold=self.cpu_trigger_threshold,
                )
            )

    def check_memory(self, memory_percent: float) -> None:
        now = time.time()

        if self.memory_confirmed:
            if memory_percent <= self.memory_recover_threshold:
                self.memory_confirmed = False
                self.memory_candidate_start = None
                self.bus.emit(
                    create_event(
                        EventType.RESOURCE_RECOVERED,
                        source="threshold_monitor",
                        resource_type="memory",
                        value=memory_percent,
                        threshold=self.memory_recover_threshold,
                    )
                )
            return

        if self.memory_candidate_start is not None:
            if memory_percent > self.memory_trigger_threshold:
                duration = now - self.memory_candidate_start
                if duration >= self.memory_duration_seconds:
                    self.memory_confirmed = True
                    self.bus.emit(
                        create_event(
                            EventType.RESOURCE_THRESHOLD_CONFIRMED,
                            source="threshold_monitor",
                            resource_type="memory",
                            value=memory_percent,
                            threshold=self.memory_trigger_threshold,
                            duration_seconds=duration,
                        )
                    )
            else:
                self.memory_candidate_start = None
            return

        if memory_percent > self.memory_trigger_threshold:
            self.memory_candidate_start = now
            self.bus.emit(
                create_event(
                    EventType.RESOURCE_THRESHOLD_CANDIDATE,
                    source="threshold_monitor",
                    resource_type="memory",
                    value=memory_percent,
                    threshold=self.memory_trigger_threshold,
                )
            )
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "cpu": {
                "confirmed": self.cpu_confirmed,
                "candidate": self.cpu_candidate_start is not None,
                "candidate_duration": time.time() - self.cpu_candidate_start if self.cpu_candidate_start else 0,
                "trigger_threshold": self.cpu_trigger_threshold,
                "recover_threshold": self.cpu_recover_threshold,
                "required_duration": self.cpu_duration_seconds
            },
            "memory": {
                "confirmed": self.memory_confirmed,
                "candidate": self.memory_candidate_start is not None,
                "candidate_duration": time.time() - self.memory_candidate_start if self.memory_candidate_start else 0,
                "trigger_threshold": self.memory_trigger_threshold,
                "recover_threshold": self.memory_recover_threshold,
                "required_duration": self.memory_duration_seconds
            }
        }


# 全局单例
_threshold_monitor: Optional[ThresholdMonitor] = None


def get_threshold_monitor() -> ThresholdMonitor:
    """获取全局阈值监控器实例"""
    global _threshold_monitor
    if _threshold_monitor is None:
        _threshold_monitor = ThresholdMonitor()
    return _threshold_monitor


# CLI 工具
if __name__ == "__main__":
    import sys
    import json
    
    monitor = get_threshold_monitor()
    
    if len(sys.argv) < 2:
        print("用法: python -m aios.core.threshold_monitor status")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status = monitor.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


"""
AIOS v0.5 标准事件模型
所有事件必须符合这个结构
"""
import time
import uuid
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class Event:
    """标准事件模型"""
    id: str
    type: str
    source: str
    timestamp: int
    payload: Dict[str, Any]
    
    @classmethod
    def create(cls, event_type: str, source: str, payload: Optional[Dict[str, Any]] = None) -> "Event":
        """创建事件的便捷方法"""
        return cls(
            id=str(uuid.uuid4()),
            type=event_type,
            source=source,
            timestamp=int(time.time() * 1000),  # 毫秒时间戳
            payload=payload or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建事件（兼容旧格式：额外字段自动归入 payload）"""
        from datetime import datetime as _dt
        known_fields = {"id", "type", "source", "timestamp", "payload"}
        known = {}
        extra = {}
        for k, v in data.items():
            if k in known_fields:
                known[k] = v
            else:
                extra[k] = v
        # 合并额外字段到 payload
        if extra:
            payload = known.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            payload.update(extra)
            known["payload"] = payload
        # 确保必要字段存在
        if "id" not in known:
            known["id"] = str(uuid.uuid4())
        if "source" not in known:
            known["source"] = known.get("payload", {}).get("source", "unknown")
        if "payload" not in known:
            known["payload"] = {}
        # 兼容 ISO 字符串 timestamp → 毫秒整数
        ts = known.get("timestamp")
        if isinstance(ts, str):
            try:
                known["timestamp"] = int(_dt.fromisoformat(ts).timestamp() * 1000)
            except Exception:
                known["timestamp"] = int(time.time() * 1000)
        elif ts is None:
            known["timestamp"] = int(time.time() * 1000)
        return cls(**known)


# 标准事件类型常量
class EventType:
    """标准事件类型"""
    
    # Pipeline 事件
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    
    # Agent 事件
    AGENT_CREATED = "agent.created"
    AGENT_TASK_STARTED = "agent.task_started"
    AGENT_TASK_COMPLETED = "agent.task_completed"
    AGENT_ERROR = "agent.error"
    
    # Resource 事件
    RESOURCE_CPU_SPIKE = "resource.cpu_spike"
    RESOURCE_MEMORY_HIGH = "resource.memory_high"
    RESOURCE_GPU_OVERLOAD = "resource.gpu_overload"
    
    # Reactor 事件
    REACTOR_MATCHED = "reactor.matched"
    REACTOR_EXECUTED = "reactor.executed"
    REACTOR_SUCCESS = "reactor.success"
    REACTOR_FAILED = "reactor.failed"
    REACTOR_SKIPPED = "reactor.skipped"
    
    # Scheduler 事件
    SCHEDULER_DISPATCH = "scheduler.dispatch"
    SCHEDULER_THROTTLE = "scheduler.throttle"
    
    # Score 事件
    SCORE_UPDATED = "score.updated"
    SCORE_DEGRADED = "score.degraded"
    SCORE_RECOVERED = "score.recovered"
    
    # Circuit Breaker 事件
    CIRCUIT_OPENED = "circuit.opened"
    CIRCUIT_HALF_OPEN = "circuit.half_open"
    CIRCUIT_CLOSED = "circuit.closed"
    
    # Resource 阈值事件（持续时间判定）
    RESOURCE_THRESHOLD_CANDIDATE = "resource.threshold_candidate"
    RESOURCE_THRESHOLD_CONFIRMED = "resource.threshold_confirmed"
    RESOURCE_RECOVERED = "resource.recovered"
    
    # Scheduler 扩展事件
    SCHEDULER_TASK_SUBMITTED = "scheduler.task_submitted"
    SCHEDULER_TASK_STARTED = "scheduler.task_started"
    SCHEDULER_TASK_COMPLETED = "scheduler.task_completed"
    SCHEDULER_TASK_FAILED = "scheduler.task_failed"
    SCHEDULER_TASK_RETRYING = "scheduler.task_retrying"
    SCHEDULER_QUEUE_FULL = "scheduler.queue_full"
    SCHEDULER_DECISION = "scheduler.decision"
    
    # Agent 生命周期事件
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_DEGRADED = "agent.degraded"
    AGENT_RECOVERED = "agent.recovered"
    AGENT_FAILED = "agent.failed"
    AGENT_SPAWNED = "agent.spawned"
    AGENT_KILLED = "agent.killed"
    
    # Evolution 事件
    EVOLUTION_CANDIDATE = "evolution.candidate"
    EVOLUTION_APPLIED = "evolution.applied"
    EVOLUTION_ROLLED_BACK = "evolution.rolled_back"
    EVOLUTION_BLOCKED = "evolution.blocked"
    EVOLUTION_EVALUATION = "evolution.evaluation"
    
    # Pipeline 扩展事件
    PIPELINE_STAGE_STARTED = "pipeline.stage_started"
    PIPELINE_STAGE_COMPLETED = "pipeline.stage_completed"
    PIPELINE_STAGE_FAILED = "pipeline.stage_failed"
    
    # Maintenance 事件
    MAINTENANCE_STARTED = "maintenance.started"
    MAINTENANCE_COMPLETED = "maintenance.completed"
    MAINTENANCE_CLEANUP = "maintenance.cleanup"
    
    # Learning 事件
    LEARNING_LESSON_EXTRACTED = "learning.lesson_extracted"
    LEARNING_PATTERN_DETECTED = "learning.pattern_detected"
    LEARNING_KNOWLEDGE_UPDATED = "learning.knowledge_updated"


# 便捷函数
def create_event(event_type: str, source: str, **payload) -> Event:
    """创建事件的便捷函数"""
    return Event.create(event_type, source, payload)

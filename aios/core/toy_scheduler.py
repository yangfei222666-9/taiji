"""
AIOS v0.5 Scheduler - 玩具版
100 行代码证明概念：事件驱动的调度器

职责：
1. 订阅事件
2. 做决策
3. 发事件（不直接调用其他模块）

禁止：
- 直接调用 Reactor
- 直接调用 Agent
- 执行任务
"""
from pathlib import Path
import sys

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType, create_event
from core.event_bus import get_event_bus, subscribe, emit


class ToyScheduler:
    """玩具版调度器 - 证明概念"""
    
    def __init__(self, bus=None):
        self.bus = bus or get_event_bus()
        self.actions = []  # 记录所有决策
        
    def start(self):
        """启动调度器，订阅事件"""
        print("[Scheduler] 启动中...")
        
        # 订阅资源事件
        self.bus.subscribe("resource.*", self._handle_resource_event)
        
        # 订阅 agent 错误
        self.bus.subscribe("agent.error", self._handle_agent_error)
        
        # 订阅 pipeline 完成
        self.bus.subscribe("pipeline.completed", self._handle_pipeline_completed)
        
        print("[Scheduler] 已启动，监听事件中...")
    
    def _handle_resource_event(self, event: Event):
        """处理资源事件"""
        print(f"[Scheduler] 收到资源事件: {event.type}")
        
        # 决策：资源峰值 → 触发 Reactor
        decision = {
            "action": "trigger_reactor",
            "reason": f"资源告警: {event.type}",
            "event_id": event.id
        }
        self.actions.append(decision)
        
        # 发事件（不直接调用 Reactor）
        self.bus.emit(create_event(
            "scheduler.decision",
            source="scheduler",
            action="trigger_reactor",
            target_event=event.id,
            reason=decision["reason"]
        ))
        
        print(f"[Scheduler] 决策: {decision['action']} - {decision['reason']}")
    
    def _handle_agent_error(self, event: Event):
        """处理 agent 错误"""
        print(f"[Scheduler] 收到 agent 错误: {event.payload.get('error', 'unknown')}")
        
        # 决策：agent 错误 → 触发 Reactor
        decision = {
            "action": "trigger_reactor",
            "reason": "Agent 执行失败",
            "event_id": event.id
        }
        self.actions.append(decision)
        
        # 发事件
        self.bus.emit(create_event(
            "scheduler.decision",
            source="scheduler",
            action="trigger_reactor",
            target_event=event.id,
            reason=decision["reason"]
        ))
        
        print(f"[Scheduler] 决策: {decision['action']} - {decision['reason']}")
    
    def _handle_pipeline_completed(self, event: Event):
        """处理 pipeline 完成"""
        print(f"[Scheduler] Pipeline 完成")
        
        # 决策：pipeline 完成 → 记录日志
        decision = {
            "action": "log_completion",
            "reason": "Pipeline 正常完成",
            "event_id": event.id
        }
        self.actions.append(decision)
        
        print(f"[Scheduler] 决策: {decision['action']} - {decision['reason']}")
    
    def get_actions(self):
        """获取所有决策记录"""
        return self.actions


# 便捷函数
def start_scheduler():
    """启动调度器"""
    scheduler = ToyScheduler()
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Scheduler 玩具版测试")
    print("=" * 60)
    
    scheduler = start_scheduler()
    
    # 模拟事件
    print("\n模拟资源峰值事件...")
    emit(create_event(EventType.RESOURCE_CPU_SPIKE, "monitor", cpu_percent=90.0))
    
    print("\n模拟 agent 错误...")
    emit(create_event(EventType.AGENT_ERROR, "agent_system", error="Task failed"))
    
    print("\n模拟 pipeline 完成...")
    emit(create_event(EventType.PIPELINE_COMPLETED, "pipeline", duration_ms=5000))
    
    # 查看决策
    print("\n" + "=" * 60)
    print(f"总决策数: {len(scheduler.get_actions())}")
    for i, action in enumerate(scheduler.get_actions(), 1):
        print(f"{i}. {action['action']} - {action['reason']}")
    print("=" * 60)

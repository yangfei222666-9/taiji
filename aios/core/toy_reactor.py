"""
AIOS v0.5 Reactor - 玩具版
订阅 scheduler.decision 事件，执行修复动作

职责：
1. 订阅 scheduler.decision 事件
2. 匹配 playbook 规则
3. 执行修复动作
4. 发射结果事件

禁止：
- UI 操作
- 直接调用其他模块
"""
from pathlib import Path
import sys
import time

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType, create_event
from core.event_bus import get_event_bus, emit
from core.circuit_breaker import get_circuit_breaker


class ToyReactor:
    """玩具版 Reactor - 证明概念（已集成熔断器）"""
    
    def __init__(self, bus=None):
        self.bus = bus or get_event_bus()
        self.circuit_breaker = get_circuit_breaker()
        self.executions = []  # 记录所有执行
        
        # 简单的 playbook 规则
        self.playbooks = {
            "cpu_spike": {
                "name": "CPU 峰值处理",
                "action": "降低优先级进程",
                "success_rate": 0.8
            },
            "memory_high": {
                "name": "内存高占用处理",
                "action": "清理缓存",
                "success_rate": 0.9
            },
            "agent_error": {
                "name": "Agent 错误处理",
                "action": "重试任务",
                "success_rate": 0.7
            }
        }
    
    def start(self):
        """启动 Reactor，订阅事件"""
        print("[Reactor] 启动中...")
        
        # 订阅 scheduler 决策事件
        self.bus.subscribe("scheduler.decision", self._handle_decision)
        
        # 也可以直接订阅错误事件（备用）
        self.bus.subscribe("*.error", self._handle_error_direct)
        
        print("[Reactor] 已启动，等待修复指令...")
    
    def _handle_decision(self, event: Event):
        """处理 scheduler 决策"""
        action = event.payload.get("action")
        
        if action == "trigger_reactor":
            print(f"[Reactor] 收到修复指令: {event.payload.get('reason')}")
            self._execute_fix(event)
    
    def _handle_error_direct(self, event: Event):
        """直接处理错误事件（备用路径）"""
        # 这是备用路径，优先走 scheduler 决策
        pass
    
    def _execute_fix(self, decision_event: Event):
        """执行修复动作（已集成熔断器）"""
        start_time = time.time()
        
        # 匹配 playbook
        playbook = self._match_playbook(decision_event)
        
        if not playbook:
            print("[Reactor] 未找到匹配的 playbook")
            self.bus.emit(create_event(
                EventType.REACTOR_FAILED,
                source="reactor",
                reason="No matching playbook"
            ))
            return
        
        playbook_id = playbook["name"]
        event_type = decision_event.payload.get("reason", "unknown")
        
        # 检查熔断器
        if not self.circuit_breaker.check(event_type, playbook_id):
            print(f"[Reactor] ⚠️  熔断中，跳过执行: {playbook_id}")
            return  # reactor.skipped 事件已由熔断器发射
        
        # 记录触发
        self.circuit_breaker.record_trigger(event_type, playbook_id)
        
        # 发射匹配事件
        self.bus.emit(create_event(
            EventType.REACTOR_MATCHED,
            source="reactor",
            playbook_id=playbook_id,
            confidence=playbook["success_rate"]
        ))
        
        print(f"[Reactor] 匹配 playbook: {playbook['name']}")
        print(f"[Reactor] 执行动作: {playbook['action']}")
        
        # 模拟执行（实际应该调用真实修复逻辑）
        time.sleep(0.1)  # 模拟执行时间
        
        # 模拟成功/失败（基于 success_rate）
        import random
        success = random.random() < playbook["success_rate"]
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 记录执行
        execution = {
            "playbook": playbook["name"],
            "action": playbook["action"],
            "success": success,
            "duration_ms": duration_ms
        }
        self.executions.append(execution)
        
        # 发射结果事件 + 更新熔断器
        if success:
            self.circuit_breaker.record_success(event_type, playbook_id)
            self.bus.emit(create_event(
                EventType.REACTOR_SUCCESS,
                source="reactor",
                playbook_id=playbook_id,
                duration_ms=duration_ms
            ))
            print(f"[Reactor] ✅ 修复成功 ({duration_ms}ms)")
        else:
            self.circuit_breaker.record_failure(event_type, playbook_id)
            self.bus.emit(create_event(
                EventType.REACTOR_FAILED,
                source="reactor",
                playbook_id=playbook_id,
                error="Execution failed"
            ))
            print(f"[Reactor] ❌ 修复失败")
    
    def _match_playbook(self, decision_event: Event):
        """匹配 playbook 规则"""
        reason = decision_event.payload.get("reason", "")
        
        if "CPU" in reason or "cpu" in reason:
            return self.playbooks["cpu_spike"]
        elif "内存" in reason or "memory" in reason:
            return self.playbooks["memory_high"]
        elif "Agent" in reason or "agent" in reason:
            return self.playbooks["agent_error"]
        
        return None
    
    def get_executions(self):
        """获取所有执行记录"""
        return self.executions


# 便捷函数
def start_reactor():
    """启动 Reactor"""
    reactor = ToyReactor()
    reactor.start()
    return reactor


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Reactor 玩具版测试")
    print("=" * 60)
    
    reactor = start_reactor()
    
    # 模拟 scheduler 决策
    print("\n模拟 scheduler 决策...")
    emit(create_event(
        "scheduler.decision",
        source="scheduler",
        action="trigger_reactor",
        reason="资源告警: CPU 峰值"
    ))
    
    time.sleep(0.2)
    
    # 查看执行记录
    print("\n" + "=" * 60)
    print(f"总执行数: {len(reactor.get_executions())}")
    for i, exec in enumerate(reactor.get_executions(), 1):
        status = "✅" if exec["success"] else "❌"
        print(f"{i}. {status} {exec['playbook']} - {exec['action']} ({exec['duration_ms']}ms)")
    print("=" * 60)

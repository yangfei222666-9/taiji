"""
AIOS v0.5 Agent 状态机
管理 Agent 的生命周期状态

状态：
- idle: 空闲，等待任务
- running: 执行中
- degraded: 出错但还能工作（降级模式）
- learning: 从失败中学习，更新策略

状态转换：
idle → running → idle (成功)
idle → running → degraded → learning → idle (失败后学习)
"""
from pathlib import Path
import sys
import time
from enum import Enum

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType, create_event
from core.event_bus import get_event_bus


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    DEGRADED = "degraded"
    LEARNING = "learning"


class AgentStateMachine:
    """Agent 状态机"""
    
    def __init__(self, agent_id: str, bus=None):
        self.agent_id = agent_id
        self.bus = bus or get_event_bus()
        
        # 当前状态
        self.state = AgentState.IDLE
        self.last_state = AgentState.IDLE
        
        # 统计
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "degraded_count": 0,
            "learning_count": 0,
            "total_runtime_ms": 0
        }
        
        # 状态历史
        self.state_history = []
        
        # 任务开始时间
        self.task_start_time = None
    
    def start_task(self, task: str):
        """开始任务"""
        if self.state != AgentState.IDLE:
            print(f"[Agent {self.agent_id}] ⚠️ 状态错误: {self.state.value} → running")
            return False
        
        self._transition_to(AgentState.RUNNING)
        self.task_start_time = time.time()
        
        # 发射事件
        self.bus.emit(create_event(
            EventType.AGENT_TASK_STARTED,
            source=f"agent_{self.agent_id}",
            agent_id=self.agent_id,
            task=task
        ))
        
        print(f"[Agent {self.agent_id}] 开始任务: {task}")
        return True
    
    def complete_task(self, success: bool):
        """完成任务"""
        if self.state != AgentState.RUNNING:
            print(f"[Agent {self.agent_id}] ⚠️ 状态错误: {self.state.value} → complete")
            return False
        
        # 计算运行时间
        if self.task_start_time:
            duration_ms = int((time.time() - self.task_start_time) * 1000)
            self.stats["total_runtime_ms"] += duration_ms
        else:
            duration_ms = 0
        
        if success:
            # 成功 → idle
            self.stats["tasks_completed"] += 1
            self._transition_to(AgentState.IDLE)
            
            # 发射事件
            self.bus.emit(create_event(
                EventType.AGENT_TASK_COMPLETED,
                source=f"agent_{self.agent_id}",
                agent_id=self.agent_id,
                success=True,
                duration_ms=duration_ms
            ))
            
            print(f"[Agent {self.agent_id}] ✅ 任务完成 ({duration_ms}ms)")
        else:
            # 失败 → degraded
            self.stats["tasks_failed"] += 1
            self.stats["degraded_count"] += 1
            self._transition_to(AgentState.DEGRADED)
            
            # 发射事件
            self.bus.emit(create_event(
                EventType.AGENT_ERROR,
                source=f"agent_{self.agent_id}",
                agent_id=self.agent_id,
                error="Task failed",
                duration_ms=duration_ms
            ))
            
            print(f"[Agent {self.agent_id}] ❌ 任务失败 → 降级模式")
        
        return True
    
    def start_learning(self):
        """开始学习（从失败中学习）"""
        if self.state != AgentState.DEGRADED:
            print(f"[Agent {self.agent_id}] ⚠️ 状态错误: {self.state.value} → learning")
            return False
        
        self.stats["learning_count"] += 1
        self._transition_to(AgentState.LEARNING)
        
        print(f"[Agent {self.agent_id}] 🧠 开始学习...")
        return True
    
    def finish_learning(self):
        """完成学习，恢复到 idle"""
        if self.state != AgentState.LEARNING:
            print(f"[Agent {self.agent_id}] ⚠️ 状态错误: {self.state.value} → idle")
            return False
        
        self._transition_to(AgentState.IDLE)
        
        print(f"[Agent {self.agent_id}] ✅ 学习完成 → 恢复正常")
        return True
    
    def _transition_to(self, new_state: AgentState):
        """状态转换"""
        self.last_state = self.state
        self.state = new_state
        
        # 记录历史
        self.state_history.append({
            "timestamp": int(time.time() * 1000),
            "from": self.last_state.value,
            "to": new_state.value
        })
        
        print(f"[Agent {self.agent_id}] 状态: {self.last_state.value} → {new_state.value}")
    
    def get_state(self):
        """获取当前状态"""
        return self.state
    
    def get_stats(self):
        """获取统计数据"""
        return self.stats
    
    def get_history(self):
        """获取状态历史"""
        return self.state_history
    
    def get_success_rate(self):
        """获取成功率"""
        total = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        if total == 0:
            return 1.0
        return self.stats["tasks_completed"] / total


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Agent 状态机测试")
    print("=" * 60)
    
    agent = AgentStateMachine("test_agent")
    
    # 场景 1: 成功任务
    print("\n场景 1: 成功任务")
    agent.start_task("Task 1")
    time.sleep(0.1)
    agent.complete_task(success=True)
    
    # 场景 2: 失败任务 → 学习
    print("\n场景 2: 失败任务 → 学习")
    agent.start_task("Task 2")
    time.sleep(0.1)
    agent.complete_task(success=False)
    agent.start_learning()
    time.sleep(0.1)
    agent.finish_learning()
    
    # 场景 3: 连续成功
    print("\n场景 3: 连续成功")
    for i in range(3):
        agent.start_task(f"Task {i+3}")
        time.sleep(0.05)
        agent.complete_task(success=True)
    
    # 查看结果
    print("\n" + "=" * 60)
    print(f"当前状态: {agent.get_state().value}")
    print(f"成功率: {agent.get_success_rate():.1%}")
    print(f"统计数据: {agent.get_stats()}")
    print(f"状态历史: {len(agent.get_history())} 次转换")
    print("=" * 60)

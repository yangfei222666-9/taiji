"""
Circuit Breaker - 熔断机制
防止修复循环，保护系统稳定性

状态机：
- CLOSED: 正常工作，允许执行
- OPEN: 熔断中，拒绝执行
- HALF_OPEN: 半开状态，允许 1 次探测

规则：
- N 次失败或触发过密 → OPEN（熔断）
- OPEN 期间只记录 reactor.skipped，不执行修复
- cooldown 结束后进入 HALF_OPEN：只允许 1 次探测
- 成功 → CLOSED；失败 → OPEN
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from collections import defaultdict

from .event import create_event, EventType
from .event_bus import emit


class CircuitBreaker:
    """熔断器"""
    
    # 状态常量
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        max_triggers_in_window: int = 3,
        window_seconds: int = 60,
        max_failures: int = 2,
        failure_window_seconds: int = 300,
        cooldown_seconds: int = 600
    ):
        """
        初始化熔断器
        
        Args:
            max_triggers_in_window: 时间窗口内最大触发次数（过密熔断）
            window_seconds: 触发计数窗口（秒）
            max_failures: 失败窗口内最大失败次数
            failure_window_seconds: 失败计数窗口（秒）
            cooldown_seconds: 熔断冷却时间（秒）
        """
        self.max_triggers_in_window = max_triggers_in_window
        self.window_seconds = window_seconds
        self.max_failures = max_failures
        self.failure_window_seconds = failure_window_seconds
        self.cooldown_seconds = cooldown_seconds
        
        # 状态存储：key = (event_type, playbook_id)
        self.states: Dict[tuple, str] = defaultdict(lambda: self.CLOSED)
        self.trigger_history: Dict[tuple, list] = defaultdict(list)
        self.failure_history: Dict[tuple, list] = defaultdict(list)
        self.open_time: Dict[tuple, float] = {}
        
        # 持久化路径
        self.state_file = Path(__file__).parent.parent / "data" / "circuit_breaker_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载持久化状态
        self._load_state()
    
    def check(self, event_type: str, playbook_id: str) -> bool:
        """
        检查是否允许执行
        
        Args:
            event_type: 事件类型
            playbook_id: Playbook ID
            
        Returns:
            True: 允许执行
            False: 熔断中，拒绝执行
        """
        key = (event_type, playbook_id)
        state = self.states[key]
        now = time.time()
        
        # CLOSED: 正常工作
        if state == self.CLOSED:
            return True
        
        # OPEN: 检查是否可以进入 HALF_OPEN
        if state == self.OPEN:
            open_time = self.open_time.get(key, now)
            if now - open_time >= self.cooldown_seconds:
                # 进入 HALF_OPEN
                self.states[key] = self.HALF_OPEN
                self._emit_state_change(event_type, playbook_id, self.HALF_OPEN)
                self._save_state()
                return True
            else:
                # 仍在冷却期，拒绝执行
                self._emit_skipped(event_type, playbook_id, "circuit_open")
                return False
        
        # HALF_OPEN: 允许 1 次探测
        if state == self.HALF_OPEN:
            return True
        
        return False
    
    def record_trigger(self, event_type: str, playbook_id: str):
        """
        记录触发
        
        Args:
            event_type: 事件类型
            playbook_id: Playbook ID
        """
        key = (event_type, playbook_id)
        now = time.time()
        state = self.states[key]
        
        # HALF_OPEN 状态下不检查触发频率（正在探测恢复）
        if state == self.HALF_OPEN:
            return
        
        # 添加触发记录
        self.trigger_history[key].append(now)
        
        # 清理过期记录
        cutoff = now - self.window_seconds
        self.trigger_history[key] = [t for t in self.trigger_history[key] if t > cutoff]
        
        # 检查是否过密
        if len(self.trigger_history[key]) >= self.max_triggers_in_window:
            self._open_circuit(event_type, playbook_id, "too_frequent")
    
    def record_success(self, event_type: str, playbook_id: str):
        """
        记录成功
        
        Args:
            event_type: 事件类型
            playbook_id: Playbook ID
        """
        key = (event_type, playbook_id)
        state = self.states[key]
        
        # HALF_OPEN 成功 → CLOSED
        if state == self.HALF_OPEN:
            self.states[key] = self.CLOSED
            self._emit_state_change(event_type, playbook_id, self.CLOSED)
            # 清空历史
            self.trigger_history[key] = []
            self.failure_history[key] = []
            if key in self.open_time:
                del self.open_time[key]
            self._save_state()
        
        # CLOSED 状态下成功，也清空失败历史（但保留触发历史用于频率检测）
        elif state == self.CLOSED:
            self.failure_history[key] = []
    
    def record_failure(self, event_type: str, playbook_id: str):
        """
        记录失败
        
        Args:
            event_type: 事件类型
            playbook_id: Playbook ID
        """
        key = (event_type, playbook_id)
        now = time.time()
        state = self.states[key]
        
        # 添加失败记录
        self.failure_history[key].append(now)
        
        # 清理过期记录
        cutoff = now - self.failure_window_seconds
        self.failure_history[key] = [t for t in self.failure_history[key] if t > cutoff]
        
        # HALF_OPEN 失败 → OPEN
        if state == self.HALF_OPEN:
            self._open_circuit(event_type, playbook_id, "half_open_failed")
            return
        
        # CLOSED: 检查失败次数
        if len(self.failure_history[key]) >= self.max_failures:
            self._open_circuit(event_type, playbook_id, "too_many_failures")
    
    def _open_circuit(self, event_type: str, playbook_id: str, reason: str):
        """打开熔断器"""
        key = (event_type, playbook_id)
        self.states[key] = self.OPEN
        self.open_time[key] = time.time()
        self._emit_state_change(event_type, playbook_id, self.OPEN, reason)
        self._save_state()
    
    def _emit_state_change(self, event_type: str, playbook_id: str, new_state: str, reason: str = None):
        """发射状态变化事件"""
        event_type_map = {
            self.OPEN: EventType.CIRCUIT_OPENED,
            self.HALF_OPEN: EventType.CIRCUIT_HALF_OPEN,
            self.CLOSED: EventType.CIRCUIT_CLOSED
        }
        
        event = create_event(
            event_type_map[new_state],
            source="circuit_breaker",
            trigger_event_type=event_type,
            playbook_id=playbook_id,
            new_state=new_state,
            reason=reason,
            cooldown_seconds=self.cooldown_seconds if new_state == self.OPEN else None
        )
        emit(event)
    
    def _emit_skipped(self, event_type: str, playbook_id: str, reason: str):
        """发射跳过事件"""
        event = create_event(
            EventType.REACTOR_SKIPPED,
            source="circuit_breaker",
            trigger_event_type=event_type,
            playbook_id=playbook_id,
            reason=reason
        )
        emit(event)
    
    def _save_state(self):
        """持久化状态"""
        state_data = {
            "states": {f"{k[0]}:{k[1]}": v for k, v in self.states.items()},
            "open_time": {f"{k[0]}:{k[1]}": v for k, v in self.open_time.items()},
            "trigger_history": {f"{k[0]}:{k[1]}": v for k, v in self.trigger_history.items()},
            "failure_history": {f"{k[0]}:{k[1]}": v for k, v in self.failure_history.items()},
            "updated_at": datetime.now().isoformat()
        }
        
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
    
    def _load_state(self):
        """加载持久化状态"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            
            # 恢复状态
            self.states = defaultdict(
                lambda: self.CLOSED,
                {tuple(k.split(":")): v for k, v in state_data.get("states", {}).items()}
            )
            self.open_time = {tuple(k.split(":")): v for k, v in state_data.get("open_time", {}).items()}
            self.trigger_history = defaultdict(
                list,
                {tuple(k.split(":")): v for k, v in state_data.get("trigger_history", {}).items()}
            )
            self.failure_history = defaultdict(
                list,
                {tuple(k.split(":")): v for k, v in state_data.get("failure_history", {}).items()}
            )
        except Exception as e:
            print(f"[CircuitBreaker] 加载状态失败: {e}")
    
    def get_status(self) -> dict:
        """获取当前状态"""
        now = time.time()
        status = {
            "total_circuits": len(self.states),
            "open": 0,
            "half_open": 0,
            "closed": 0,
            "circuits": []
        }
        
        for key, state in self.states.items():
            event_type, playbook_id = key
            
            if state == self.OPEN:
                status["open"] += 1
            elif state == self.HALF_OPEN:
                status["half_open"] += 1
            else:
                status["closed"] += 1
            
            circuit_info = {
                "event_type": event_type,
                "playbook_id": playbook_id,
                "state": state,
                "trigger_count": len(self.trigger_history[key]),
                "failure_count": len(self.failure_history[key])
            }
            
            if state == self.OPEN:
                open_time = self.open_time.get(key, now)
                remaining = max(0, self.cooldown_seconds - (now - open_time))
                circuit_info["cooldown_remaining"] = int(remaining)
            
            status["circuits"].append(circuit_info)
        
        return status


# 全局单例
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """获取全局熔断器实例"""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


# CLI 工具
if __name__ == "__main__":
    import sys
    
    breaker = get_circuit_breaker()
    
    if len(sys.argv) < 2:
        print("用法: python -m aios.core.circuit_breaker [status|reset]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status = breaker.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    
    elif cmd == "reset":
        # 清空状态
        breaker.states.clear()
        breaker.trigger_history.clear()
        breaker.failure_history.clear()
        breaker.open_time.clear()
        breaker._save_state()
        print("✅ 熔断器状态已重置")
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

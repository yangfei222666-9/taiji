"""
AIOS v0.5 Score Engine - 玩具版
实时计算系统健康度评分

职责：
1. 订阅所有事件
2. 实时计算 score
3. 发射 score 事件（updated/degraded/recovered）

公式：
score = success_rate * 0.4 + latency_score * 0.2 + stability * 0.2 + resource_margin * 0.2

禁止：
- 控制流程
- 直接调用其他模块
"""
from pathlib import Path
import sys
import time

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType, create_event
from core.event_bus import get_event_bus


class ToyScoreEngine:
    """玩具版评分引擎 - 证明概念

    改进：使用滑动窗口而非累积统计，避免历史数据稀释当前状态。
    """
    
    WINDOW_SIZE = 100  # 只保留最近 100 个事件的统计

    def __init__(self, bus=None):
        self.bus = bus or get_event_bus()
        
        # 统计数据
        self.stats = {
            "total_events": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_latency_ms": 0,
            "latency_count": 0,
            "resource_alerts": 0,
        }
        
        # 滑动窗口（用于更准确的近期评分）
        self._recent_events = []
        
        # 当前 score
        self.current_score = 1.0
        self.last_score = 1.0
        
        # Score 历史
        self.score_history = []
        
    def start(self):
        """启动评分引擎，订阅所有事件"""
        print("[ScoreEngine] 启动中...")
        
        # 订阅所有事件
        self.bus.subscribe("*", self._handle_event)
        
        print("[ScoreEngine] 已启动，实时计算评分中...")
    
    def _handle_event(self, event: Event):
        """处理所有事件，更新统计"""
        self.stats["total_events"] += 1
        
        # 记录事件类型用于滑动窗口
        event_record = {"type": event.type, "payload": event.payload}
        
        # 统计成功/失败
        if event.type.endswith(".success") or event.type.endswith(".completed"):
            self.stats["success_count"] += 1
            event_record["outcome"] = "success"
        elif event.type.endswith(".failed") or event.type.endswith(".error"):
            self.stats["failure_count"] += 1
            event_record["outcome"] = "failure"
        else:
            event_record["outcome"] = "neutral"
        
        # 统计延迟
        if "duration_ms" in event.payload:
            self.stats["total_latency_ms"] += event.payload["duration_ms"]
            self.stats["latency_count"] += 1
            event_record["latency_ms"] = event.payload["duration_ms"]
        
        # 统计资源告警
        if event.type.startswith("resource."):
            self.stats["resource_alerts"] += 1
            event_record["resource_alert"] = True
        
        # 滑动窗口维护
        self._recent_events.append(event_record)
        if len(self._recent_events) > self.WINDOW_SIZE:
            self._recent_events = self._recent_events[-self.WINDOW_SIZE:]
        
        # 每 5 个事件重新计算一次 score
        if self.stats["total_events"] % 5 == 0:
            self._calculate_score()
    
    def _calculate_score(self):
        """计算系统健康度评分（基于滑动窗口）"""
        window = self._recent_events
        if not window:
            return

        # 1. 成功率（0-1）—— 基于滑动窗口
        successes = sum(1 for e in window if e.get("outcome") == "success")
        failures = sum(1 for e in window if e.get("outcome") == "failure")
        total_ops = successes + failures
        success_rate = successes / total_ops if total_ops > 0 else 1.0
        
        # 2. 延迟评分（0-1，越低越好）—— 基于滑动窗口
        latencies = [e["latency_ms"] for e in window if "latency_ms" in e]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # 100ms 理想，1000ms 最差
            latency_score = max(0, min(1, 1 - (avg_latency - 100) / 900))
        else:
            latency_score = 1.0
        
        # 3. 稳定性（0-1）—— 基于滑动窗口
        resource_alerts = sum(1 for e in window if e.get("resource_alert"))
        if len(window) > 0:
            alert_rate = resource_alerts / len(window)
            stability = max(0, 1 - alert_rate * 10)
        else:
            stability = 1.0
        
        # 4. 资源余量
        resource_margin = 1.0 if resource_alerts == 0 else 0.5
        
        # 计算总分
        self.last_score = self.current_score
        self.current_score = (
            success_rate * 0.4 +
            latency_score * 0.2 +
            stability * 0.2 +
            resource_margin * 0.2
        )
        
        # 记录历史
        self.score_history.append({
            "timestamp": int(time.time() * 1000),
            "score": self.current_score,
            "success_rate": success_rate,
            "latency_score": latency_score,
            "stability": stability,
            "resource_margin": resource_margin
        })
        
        # 发射 score 事件
        self._emit_score_event()
        
        print(f"[ScoreEngine] Score: {self.current_score:.3f} "
              f"(success={success_rate:.2f}, latency={latency_score:.2f}, "
              f"stability={stability:.2f}, resource={resource_margin:.2f})")
    
    def _emit_score_event(self):
        """发射 score 事件"""
        # 判断状态变化
        if self.current_score < 0.5 and self.last_score >= 0.5:
            # 降级
            self.bus.emit(create_event(
                "score.degraded",
                source="score_engine",
                score=self.current_score,
                previous_score=self.last_score
            ))
            print("[ScoreEngine] ⚠️ 系统降级")
        elif self.current_score >= 0.5 and self.last_score < 0.5:
            # 恢复
            self.bus.emit(create_event(
                "score.recovered",
                source="score_engine",
                score=self.current_score,
                previous_score=self.last_score
            ))
            print("[ScoreEngine] ✅ 系统恢复")
        else:
            # 正常更新
            self.bus.emit(create_event(
                "score.updated",
                source="score_engine",
                score=self.current_score,
                previous_score=self.last_score
            ))
    
    def get_score(self):
        """获取当前评分"""
        return self.current_score
    
    def get_stats(self):
        """获取统计数据"""
        return self.stats
    
    def get_history(self):
        """获取评分历史"""
        return self.score_history


# 便捷函数
def start_score_engine(bus=None):
    """启动评分引擎"""
    engine = ToyScoreEngine(bus=bus)
    engine.start()
    return engine


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Score Engine 玩具版测试")
    print("=" * 60)
    
    engine = start_score_engine()
    
    # 模拟事件流
    from core.event_bus import emit
    
    print("\n模拟正常事件流...")
    for i in range(5):
        emit(create_event(EventType.REACTOR_SUCCESS, "reactor", duration_ms=100))
    
    print("\n模拟失败事件...")
    for i in range(3):
        emit(create_event(EventType.REACTOR_FAILED, "reactor", error="test"))
    
    print("\n模拟资源告警...")
    emit(create_event(EventType.RESOURCE_CPU_SPIKE, "monitor"))
    emit(create_event(EventType.RESOURCE_MEMORY_HIGH, "monitor"))
    
    # 触发重新计算
    for i in range(5):
        emit(create_event(EventType.PIPELINE_COMPLETED, "pipeline", duration_ms=200))
    
    # 查看结果
    print("\n" + "=" * 60)
    print(f"最终评分: {engine.get_score():.3f}")
    print(f"统计数据: {engine.get_stats()}")
    print(f"评分历史: {len(engine.get_history())} 条记录")
    print("=" * 60)

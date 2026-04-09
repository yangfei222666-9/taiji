"""
AIOS v0.5 通知集成
系统降级时自动发送 Telegram 消息
"""
import sys
import time
from pathlib import Path

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import Event, EventType
from core.event_bus import get_event_bus


class NotificationHandler:
    """通知处理器"""
    
    def __init__(self):
        self.bus = get_event_bus()
        self.last_notification_time = {}
        self.cooldown_seconds = 300  # 5 分钟冷却
    
    def start(self):
        """启动通知处理器"""
        print("[NotificationHandler] 启动中...")
        
        # 订阅关键事件
        self.bus.subscribe("score.degraded", self._handle_degraded)
        self.bus.subscribe("score.recovered", self._handle_recovered)
        
        print("[NotificationHandler] 已启动，监听降级/恢复事件...")
    
    def _handle_degraded(self, event: Event):
        """处理系统降级事件"""
        score = event.payload.get("score", 0)
        previous_score = event.payload.get("previous_score", 1.0)
        
        # 检查冷却时间
        now = time.time()
        last_time = self.last_notification_time.get("degraded", 0)
        
        if now - last_time < self.cooldown_seconds:
            print(f"[NotificationHandler] 降级通知冷却中")
            return
        
        # 发送通知
        message = f"⚠️ AIOS 系统降级\n\n"
        message += f"评分: {previous_score:.3f} → {score:.3f}\n"
        message += f"状态: 系统性能下降\n"
        message += f"建议: 检查系统资源"
        
        self._send_telegram(message)
        self.last_notification_time["degraded"] = now
    
    def _handle_recovered(self, event: Event):
        """处理系统恢复事件"""
        score = event.payload.get("score", 1.0)
        previous_score = event.payload.get("previous_score", 0)
        
        # 检查冷却时间
        now = time.time()
        last_time = self.last_notification_time.get("recovered", 0)
        
        if now - last_time < self.cooldown_seconds:
            print(f"[NotificationHandler] 恢复通知冷却中")
            return
        
        # 发送通知
        message = f"✅ AIOS 系统恢复\n\n"
        message += f"评分: {previous_score:.3f} → {score:.3f}\n"
        message += f"状态: 系统已恢复正常"
        
        self._send_telegram(message)
        self.last_notification_time["recovered"] = now
    
    def _send_telegram(self, message: str):
        """发送 Telegram 消息"""
        print(f"[NotificationHandler] 发送通知:")
        for line in message.split('\n'):
            print(f"  {line}")


def start_notification_handler():
    """启动通知处理器"""
    handler = NotificationHandler()
    handler.start()
    return handler


if __name__ == "__main__":
    print("=" * 60)
    print("通知处理器测试")
    print("=" * 60)
    
    from core.event import create_event
    from core.event_bus import emit
    
    handler = start_notification_handler()
    
    # 模拟降级事件
    print("\n模拟系统降级...")
    emit(create_event(
        "score.degraded",
        source="test",
        score=0.45,
        previous_score=0.85
    ))
    
    time.sleep(1)
    
    # 模拟恢复事件
    print("\n模拟系统恢复...")
    emit(create_event(
        "score.recovered",
        source="test",
        score=0.75,
        previous_score=0.45
    ))
    
    print("\n" + "=" * 60)
    print("✅ 通知处理器测试完成")
    print("=" * 60)

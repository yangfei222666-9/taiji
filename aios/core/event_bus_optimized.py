"""
EventBus 性能优化
减少事件发布和订阅的开销
"""
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from collections import defaultdict
import fnmatch
import threading
from queue import Queue

from .event import Event
from .event_store import EventStore, get_event_store


class OptimizedEventBus:
    """优化的事件总线"""
    
    def __init__(self, storage_path: Optional[str] = None, batch_size: int = 10):
        """
        初始化优化的 EventBus
        
        Args:
            storage_path: 事件存储路径
            batch_size: 批量写入大小
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.store = get_event_store()
        
        # 批量写入队列
        self.batch_size = batch_size
        self.event_queue = Queue()
        self.batch_thread = None
        self.running = False
        
        # 订阅缓存（加速模式匹配）
        self._pattern_cache: Dict[str, List[str]] = {}
        
        # 兼容旧版
        if storage_path:
            old_file = Path(storage_path)
            if old_file.exists() and old_file.suffix == ".jsonl":
                count = self.store.migrate_from_single_file(old_file)
    
    def start_batch_writer(self):
        """启动批量写入线程"""
        if self.running:
            return
        
        self.running = True
        self.batch_thread = threading.Thread(target=self._batch_write_loop, daemon=True)
        self.batch_thread.start()
    
    def stop_batch_writer(self):
        """停止批量写入线程"""
        self.running = False
        if self.batch_thread:
            self.batch_thread.join(timeout=1)
    
    def _batch_write_loop(self):
        """批量写入循环"""
        batch = []
        
        while self.running:
            try:
                # 收集事件
                while len(batch) < self.batch_size:
                    try:
                        event = self.event_queue.get(timeout=0.1)
                        batch.append(event)
                    except:
                        break
                
                # 批量写入
                if batch:
                    for event in batch:
                        self.store.append(event)
                    batch.clear()
                
                time.sleep(0.01)  # 短暂休息
            
            except Exception as e:
                print(f"[EventBus] 批量写入错误: {e}")
    
    def emit(self, event: Event, async_write: bool = True) -> None:
        """
        发布事件（优化版）
        
        Args:
            event: 事件对象
            async_write: 是否异步写入（默认 True）
        """
        # 1. 持久化（异步）
        if async_write:
            self.event_queue.put(event)
        else:
            self.store.append(event)
        
        # 2. 通知订阅者（使用缓存加速）
        matched_patterns = self._get_matched_patterns(event.type)
        
        for pattern in matched_patterns:
            for handler in self._subscribers[pattern]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"[EventBus] Handler 错误: {e}")
    
    def _get_matched_patterns(self, event_type: str) -> List[str]:
        """获取匹配的模式（使用缓存）"""
        # 检查缓存
        if event_type in self._pattern_cache:
            return self._pattern_cache[event_type]
        
        # 计算匹配
        matched = []
        for pattern in self._subscribers.keys():
            if pattern == "*" or fnmatch.fnmatch(event_type, pattern):
                matched.append(pattern)
        
        # 缓存结果
        self._pattern_cache[event_type] = matched
        
        return matched
    
    def subscribe(self, pattern: str, handler: Callable) -> None:
        """订阅事件"""
        self._subscribers[pattern].append(handler)
        
        # 清除缓存（因为订阅变化了）
        self._pattern_cache.clear()
    
    def unsubscribe(self, pattern: str, handler: Callable) -> None:
        """取消订阅"""
        if pattern in self._subscribers:
            try:
                self._subscribers[pattern].remove(handler)
                
                # 清除缓存
                self._pattern_cache.clear()
            except ValueError:
                pass
    
    def flush(self):
        """强制刷新队列"""
        while not self.event_queue.empty():
            event = self.event_queue.get()
            self.store.append(event)


# 性能对比测试
if __name__ == "__main__":
    from .event import Event
    
    print("EventBus 性能对比测试")
    print("=" * 60)
    
    # 测试原始版本
    from .event_bus import EventBus as OriginalEventBus
    
    original_bus = OriginalEventBus()
    
    start = time.time()
    for i in range(1000):
        event = Event.create(f"test.event{i % 10}", "benchmark", {})
        original_bus.emit(event)
    original_time = time.time() - start
    
    print(f"原始版本: {original_time*1000:.1f}ms (1000 events)")
    
    # 测试优化版本
    optimized_bus = OptimizedEventBus()
    optimized_bus.start_batch_writer()
    
    start = time.time()
    for i in range(1000):
        event = Event.create(f"test.event{i % 10}", "benchmark", {})
        optimized_bus.emit(event)
    optimized_time = time.time() - start
    
    optimized_bus.flush()
    optimized_bus.stop_batch_writer()
    
    print(f"优化版本: {optimized_time*1000:.1f}ms (1000 events)")
    print(f"加速比: {original_time/optimized_time:.2f}x")

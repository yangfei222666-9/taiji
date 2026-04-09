"""
EventStore Adapter for Storage Manager
将 Storage Manager 适配为 EventStore 接口，实现无缝替换

创建时间：2026-02-26
版本：v1.0
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .storage_manager import StorageManager


class EventStoreAdapter:
    """
    EventStore 适配器
    
    将 Storage Manager 的异步接口适配为 EventStore 的同步接口
    用于无缝替换 EventBus 中的 EventStore
    """
    
    def __init__(self, base_dir: Optional[Path] = None, db_path: str = "aios.db"):
        """
        初始化适配器
        
        Args:
            base_dir: 基础目录（兼容 EventStore，实际不使用）
            db_path: SQLite 数据库路径
        """
        self.db_path = db_path
        self.storage = StorageManager(db_path)
        self._loop = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """确保 Storage Manager 已初始化"""
        if not self._initialized:
            # 获取或创建事件循环
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            
            # 初始化 Storage Manager
            self._loop.run_until_complete(self.storage.initialize())
            self._initialized = True
    
    def append(self, event) -> None:
        """
        追加事件（同步接口）
        
        Args:
            event: Event 对象
        """
        self._ensure_initialized()
        
        # 转换为 Storage Manager 格式
        # log_event(event_type, data, agent_id, severity)
        event_data = {
            "event_type": event.type,
            "data": event.payload or {},  # Event 使用 payload
            "agent_id": event.source or "unknown",  # source → agent_id
            "severity": "info"
        }
        
        # 异步调用
        self._loop.run_until_complete(
            self.storage.log_event(**event_data)
        )
    
    def load_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[int] = None,
        until: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List:
        """
        加载事件（同步接口）
        
        Args:
            event_type: 事件类型过滤
            since: 开始时间戳（毫秒）
            until: 结束时间戳（毫秒）
            limit: 最大数量
        
        Returns:
            事件列表（Event 对象）
        """
        self._ensure_initialized()
        
        # 转换时间戳（毫秒 → 秒）
        start_time = since / 1000 if since else None
        end_time = until / 1000 if until else None
        
        # 异步查询
        # list_events(agent_id, event_type, start_time, end_time, limit, offset)
        # 注意：Storage Manager 不支持通配符，需要后过滤
        events = self._loop.run_until_complete(
            self.storage.list_events(
                agent_id=None,  # 不过滤 agent
                event_type=None,  # 先查所有，后过滤
                start_time=start_time,
                end_time=end_time,
                limit=limit or 100,
                offset=0
            )
        )
        
        # 后过滤（支持通配符）
        if event_type:
            import fnmatch
            events = [e for e in events if fnmatch.fnmatch(e["event_type"], event_type)]
        
        # 转换为 Event 对象
        from aios.core.event import Event
        result = []
        for row in events:
            event = Event(
                id=row.get("event_id", str(uuid.uuid4())),
                type=row["event_type"],
                source=row.get("agent_id", "unknown"),  # agent_id → source
                payload=row.get("data_json", {}),  # data_json → payload
                timestamp=int(row["timestamp"] * 1000)  # 秒 → 毫秒
            )
            result.append(event)
        
        return result
    
    def cleanup(self) -> dict:
        """
        清理旧事件（同步接口）
        
        Returns:
            清理统计
        """
        self._ensure_initialized()
        
        # Storage Manager 使用 SQLite，不需要手动清理
        # 可以通过 SQL 删除旧数据
        stats = {
            "archived": 0,
            "deleted": 0,
            "saved_bytes": 0
        }
        
        # TODO: 实现基于时间的自动清理
        # DELETE FROM events WHERE timestamp < ?
        
        return stats
    
    def migrate_from_single_file(self, old_file: Path) -> int:
        """
        从旧的单文件迁移到 SQLite
        
        Args:
            old_file: 旧的 events.jsonl 文件
        
        Returns:
            迁移的事件数量
        """
        self._ensure_initialized()
        
        if not old_file.exists():
            return 0
        
        import json
        count = 0
        
        try:
            with open(old_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        
                        # 提取字段
                        event_type = data.get("type") or data.get("event_type")
                        agent_id = data.get("source", "unknown")
                        event_data = data.get("data", {}) or data.get("payload", {})
                        
                        # 插入到 SQLite
                        self._loop.run_until_complete(
                            self.storage.log_event(
                                event_type=event_type,
                                data=event_data,
                                agent_id=agent_id,
                                severity="info"
                            )
                        )
                        count += 1
                    
                    except Exception as e:
                        print(f"[EventStoreAdapter] Migration error: {e}")
            
            # 备份旧文件
            import shutil
            backup_path = old_file.parent / f"{old_file.name}.bak"
            shutil.move(str(old_file), str(backup_path))
            print(f"[EventStoreAdapter] Migrated {count} events, old file backed up to {backup_path}")
        
        except Exception as e:
            print(f"[EventStoreAdapter] Migration failed: {e}")
        
        return count


def get_event_store_adapter() -> EventStoreAdapter:
    """获取全局 EventStoreAdapter 实例"""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = EventStoreAdapter()
    return _global_adapter


# 全局单例
_global_adapter: Optional[EventStoreAdapter] = None

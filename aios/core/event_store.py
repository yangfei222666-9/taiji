"""
AIOS v0.6 事件存储层
职责：
1. 按日期分文件存储
2. 自动归档压缩
3. 高效查询
"""
import json
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Iterator
from .event import Event


class EventStore:
    """事件存储 - 按日期分文件 + 自动归档"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        初始化事件存储
        
        Args:
            base_dir: 基础目录，默认 workspace/aios/data/events/
        """
        if base_dir is None:
            workspace = Path(__file__).parent.parent.parent
            base_dir = workspace / "aios" / "data" / "events"
        
        self.base_dir = Path(base_dir)
        self.archive_dir = self.base_dir / "archive"
        
        # 创建目录
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置
        self.hot_days = 7        # 保留最近7天原始文件
        self.archive_days = 30   # 7-30天压缩存储
        self.max_age_days = 90   # 90天后删除
    
    def append(self, event: Event) -> None:
        """
        追加事件到今天的文件
        
        Args:
            event: 事件对象
        """
        today_file = self._get_today_file()
        with open(today_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    
    def load_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[int] = None,
        until: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        加载事件（支持日期范围查询）
        
        Args:
            event_type: 事件类型过滤
            since: 开始时间戳（毫秒）
            until: 结束时间戳（毫秒）
            limit: 最大数量
        
        Returns:
            事件列表
        """
        events = []
        
        # 确定日期范围
        date_range = self._get_date_range(since, until)
        
        # 遍历日期文件
        for date_str in date_range:
            file_path = self._get_file_for_date(date_str)
            if not file_path or not file_path.exists():
                continue
            
            # 读取事件
            for event in self._read_file(file_path):
                # 过滤
                if event_type and not self._match_pattern(event.type, event_type):
                    continue
                if since and event.timestamp < since:
                    continue
                if until and event.timestamp > until:
                    continue
                
                events.append(event)
                
                # 限制数量
                if limit and len(events) >= limit:
                    return events
        
        return events
    
    def cleanup(self) -> dict:
        """
        清理旧事件
        
        Returns:
            清理统计
        """
        stats = {
            "archived": 0,
            "deleted": 0,
            "saved_bytes": 0
        }
        
        now = datetime.now()
        
        # 遍历所有日期文件
        for file_path in self.base_dir.glob("*.jsonl"):
            try:
                date_str = file_path.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                age_days = (now - file_date).days
                
                # 超过90天 → 删除
                if age_days > self.max_age_days:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    stats["deleted"] += 1
                    stats["saved_bytes"] += size
                
                # 7-30天 → 压缩归档
                elif age_days > self.hot_days:
                    archive_path = self.archive_dir / f"{date_str}.jsonl.gz"
                    if not archive_path.exists():
                        original_size = file_path.stat().st_size
                        with open(file_path, "rb") as f_in:
                            with gzip.open(archive_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        file_path.unlink()
                        compressed_size = archive_path.stat().st_size
                        stats["archived"] += 1
                        stats["saved_bytes"] += (original_size - compressed_size)
            
            except Exception as e:
                print(f"[EventStore] Cleanup error for {file_path}: {e}")
        
        return stats
    
    def migrate_from_single_file(self, old_file: Path) -> int:
        """
        从旧的单文件迁移到新结构
        
        Args:
            old_file: 旧的 events.jsonl 文件
        
        Returns:
            迁移的事件数量
        """
        if not old_file.exists():
            return 0
        
        count = 0
        date_files = {}  # {date_str: file_handle}
        
        try:
            with open(old_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        event = Event.from_dict(data)
                        
                        # 根据时间戳确定日期
                        date_str = datetime.fromtimestamp(event.timestamp / 1000).strftime("%Y-%m-%d")
                        
                        # 打开对应日期的文件
                        if date_str not in date_files:
                            file_path = self.base_dir / f"{date_str}.jsonl"
                            date_files[date_str] = open(file_path, "a", encoding="utf-8")
                        
                        # 写入
                        date_files[date_str].write(line)
                        count += 1
                    
                    except Exception as e:
                        print(f"[EventStore] Migration error: {e}")
            
            # 关闭所有文件
            for fh in date_files.values():
                fh.close()
            
            # 备份旧文件
            backup_path = old_file.parent / f"{old_file.name}.bak"
            shutil.move(str(old_file), str(backup_path))
            print(f"[EventStore] Migrated {count} events, old file backed up to {backup_path}")
        
        except Exception as e:
            print(f"[EventStore] Migration failed: {e}")
            # 关闭所有文件
            for fh in date_files.values():
                try:
                    fh.close()
                except:
                    pass
        
        return count
    
    # ========== 内部方法 ==========
    
    def _get_today_file(self) -> Path:
        """获取今天的事件文件"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.base_dir / f"{today}.jsonl"
    
    def _get_file_for_date(self, date_str: str) -> Optional[Path]:
        """获取指定日期的文件（可能是原始或压缩）"""
        # 先找原始文件
        raw_file = self.base_dir / f"{date_str}.jsonl"
        if raw_file.exists():
            return raw_file
        
        # 再找压缩文件
        gz_file = self.archive_dir / f"{date_str}.jsonl.gz"
        if gz_file.exists():
            return gz_file
        
        return None
    
    def _read_file(self, file_path: Path) -> Iterator[Event]:
        """读取文件（自动处理压缩）"""
        try:
            if file_path.suffix == ".gz":
                with gzip.open(file_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            yield Event.from_dict(data)
                        except Exception as e:
                            print(f"[EventStore] Parse error: {e}")
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            yield Event.from_dict(data)
                        except Exception as e:
                            print(f"[EventStore] Parse error: {e}")
        except Exception as e:
            print(f"[EventStore] Read error for {file_path}: {e}")
    
    def _get_date_range(self, since: Optional[int], until: Optional[int]) -> List[str]:
        """根据时间戳范围生成日期列表"""
        if since is None and until is None:
            # 默认最近7天
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.fromtimestamp((since or 0) / 1000)
            end_date = datetime.fromtimestamp((until or int(datetime.now().timestamp() * 1000)) / 1000)
        
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        return dates
    
    @staticmethod
    def _match_pattern(event_type: str, pattern: str) -> bool:
        """匹配事件类型（简单通配符）"""
        import fnmatch
        return fnmatch.fnmatch(event_type, pattern)


# 全局单例
_global_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """获取全局 EventStore 实例"""
    global _global_store
    if _global_store is None:
        _global_store = EventStore()
    return _global_store

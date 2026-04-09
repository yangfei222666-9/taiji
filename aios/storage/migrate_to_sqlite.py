"""
AIOS 数据迁移工具
从 events.jsonl 迁移到 SQLite

使用方法：
    python migrate_to_sqlite.py

创建时间：2026-02-26
版本：v1.0
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加 workspace 到路径
workspace = Path(__file__).parent.parent.parent
sys.path.insert(0, str(workspace))

from aios.storage.storage_manager import StorageManager


async def migrate_events(old_file: Path, db_path: str = "aios.db"):
    """
    迁移事件数据
    
    Args:
        old_file: 旧的 events.jsonl 文件
        db_path: SQLite 数据库路径
    """
    if not old_file.exists():
        print(f"❌ 文件不存在: {old_file}")
        return 0
    
    print(f"📂 开始迁移: {old_file}")
    print(f"📊 目标数据库: {db_path}")
    
    # 初始化 Storage Manager
    storage = StorageManager(db_path)
    await storage.initialize()
    
    count = 0
    errors = 0
    
    try:
        with open(old_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    
                    # 提取字段
                    event_type = data.get("type") or data.get("event_type")
                    agent_id = data.get("source", "unknown")
                    event_data = data.get("data", {}) or data.get("payload", {})
                    
                    # 插入到 SQLite
                    await storage.log_event(
                        event_type=event_type,
                        data=event_data,
                        agent_id=agent_id,
                        severity="info"
                    )
                    count += 1
                    
                    # 进度提示
                    if count % 100 == 0:
                        print(f"  已迁移 {count} 条事件...")
                
                except Exception as e:
                    errors += 1
                    print(f"  ⚠️ 第 {line_num} 行错误: {e}")
        
        print(f"\n✅ 迁移完成!")
        print(f"  成功: {count} 条")
        print(f"  失败: {errors} 条")
        
        # 备份旧文件
        import shutil
        backup_path = old_file.parent / f"{old_file.name}.bak"
        shutil.move(str(old_file), str(backup_path))
        print(f"  旧文件已备份到: {backup_path}")
    
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
    
    finally:
        await storage.close()
    
    return count


async def migrate_all():
    """迁移所有数据"""
    workspace = Path(__file__).parent.parent.parent
    
    # 1. 迁移主事件文件
    events_file = workspace / "aios" / "data" / "events.jsonl"
    if events_file.exists():
        print("\n=== 迁移主事件文件 ===")
        await migrate_events(events_file)
    
    # 2. 迁移按日期分文件的事件
    events_dir = workspace / "aios" / "data" / "events"
    if events_dir.exists():
        print("\n=== 迁移日期分文件 ===")
        for jsonl_file in events_dir.glob("*.jsonl"):
            if jsonl_file.name != "events.jsonl":  # 跳过主文件
                await migrate_events(jsonl_file)
    
    print("\n🎉 所有数据迁移完成!")


def main():
    """主函数"""
    print("=" * 60)
    print("AIOS 数据迁移工具 v1.0")
    print("=" * 60)
    
    # 运行迁移
    asyncio.run(migrate_all())


if __name__ == "__main__":
    main()

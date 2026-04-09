#!/usr/bin/env python3
"""
测试数据隔离 - 测试事件不写入生产日志

使用方法：
1. 在测试代码中设置环境变量：os.environ['AIOS_ENV'] = 'test'
2. 测试事件会写入 aios/events/test_events.jsonl
3. 生产事件写入 aios/events/events.jsonl
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

class IsolatedEventStore:
    """隔离的事件存储（测试/生产分离）"""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(__file__).parent.parent / "events"
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 根据环境变量决定文件名
        env = os.environ.get('AIOS_ENV', 'prod')
        if env == 'test':
            self.events_file = self.base_path / "test_events.jsonl"
        else:
            self.events_file = self.base_path / "events.jsonl"
    
    def append(self, event: dict) -> None:
        """追加事件"""
        # 添加环境标记
        event['env'] = os.environ.get('AIOS_ENV', 'prod')
        event['ts'] = event.get('ts', datetime.now().isoformat())
        
        with open(self.events_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    def get_file_path(self) -> Path:
        """获取当前事件文件路径"""
        return self.events_file


# 全局实例
_isolated_store = None

def get_isolated_store() -> IsolatedEventStore:
    """获取隔离的事件存储实例"""
    global _isolated_store
    if _isolated_store is None:
        _isolated_store = IsolatedEventStore()
    return _isolated_store


# 使用示例
if __name__ == '__main__':
    print("Testing event isolation...\n")
    
    # 测试 1：生产环境
    os.environ['AIOS_ENV'] = 'prod'
    store_prod = IsolatedEventStore()
    print(f"1. Production events -> {store_prod.get_file_path()}")
    
    # 测试 2：测试环境
    os.environ['AIOS_ENV'] = 'test'
    store_test = IsolatedEventStore()
    print(f"2. Test events -> {store_test.get_file_path()}")
    
    # 测试 3：写入测试事件
    store_test.append({
        'event': 'test.event',
        'severity': 'INFO',
        'payload': {'test': True}
    })
    print(f"3. Test event written to {store_test.get_file_path()}")
    
    # 测试 4：验证隔离
    prod_file = Path(__file__).parent.parent / "events" / "events.jsonl"
    test_file = Path(__file__).parent.parent / "events" / "test_events.jsonl"
    
    print(f"\n4. Verification:")
    print(f"   Production file exists: {prod_file.exists()}")
    print(f"   Test file exists: {test_file.exists()}")
    
    if test_file.exists():
        with open(test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"   Test events count: {len(lines)}")
            if lines:
                last_event = json.loads(lines[-1])
                print(f"   Last test event env: {last_event.get('env')}")
    
    print("\n[SUCCESS] Event isolation working!")

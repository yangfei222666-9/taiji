"""
AIOS Storage Manager
使用 aiosqlite 实现异步存储
创建时间：2026-02-26
版本：v1.0
"""

import aiosqlite
import json
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any


class StorageManager:
    """
    AIOS 存储管理器
    
    功能：
    1. Agent 状态持久化
    2. 上下文持久化
    3. 事件存储（替代 events.jsonl）
    4. 任务历史记录
    5. 查询和索引
    """
    
    def __init__(self, db_path: str = "aios.db"):
        self.db_path = db_path
        self._db = None
        
    async def initialize(self):
        """初始化数据库"""
        # 创建数据库连接
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        
        # 执行 schema
        sql_dir = Path(__file__).parent / "sql"
        schema_path = sql_dir / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        await self._db.executescript(schema_sql)
        await self._db.commit()
        
    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            
    # ==================== Agent State ====================
    
    async def save_agent_state(self, agent_id: str, role: str, state: str, 
                               goal: Optional[str] = None, 
                               backstory: Optional[str] = None,
                               last_task_id: Optional[str] = None,
                               stats: Optional[Dict] = None):
        """保存 Agent 状态"""
        now = time.time()
        stats_json = json.dumps(stats) if stats else None
        
        await self._db.execute("""
            INSERT INTO agent_states (agent_id, role, goal, backstory, state, created_at, updated_at, last_task_id, stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                role = ?,
                goal = ?,
                backstory = ?,
                state = ?,
                updated_at = ?,
                last_task_id = ?,
                stats_json = ?
        """, (agent_id, role, goal, backstory, state, now, now, last_task_id, stats_json,
              role, goal, backstory, state, now, last_task_id, stats_json))
        await self._db.commit()
        
    async def get_agent_state(self, agent_id: str) -> Optional[Dict]:
        """获取 Agent 状态"""
        async with self._db.execute(
            "SELECT * FROM agent_states WHERE agent_id = ?", (agent_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None
        
    async def list_agent_states(self, active_only: bool = False) -> List[Dict]:
        """列出所有 Agent 状态"""
        if active_only:
            query = "SELECT * FROM agent_states WHERE state != 'archived' ORDER BY updated_at DESC"
        else:
            query = "SELECT * FROM agent_states ORDER BY updated_at DESC"
        
        async with self._db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
    async def delete_agent_state(self, agent_id: str):
        """删除 Agent 状态"""
        await self._db.execute("DELETE FROM agent_states WHERE agent_id = ?", (agent_id,))
        await self._db.commit()
        
    # ==================== Context ====================
    
    async def save_context(self, agent_id: str, context_data: Dict,
                          session_id: Optional[str] = None,
                          expires_at: Optional[float] = None) -> str:
        """保存上下文"""
        context_id = str(uuid.uuid4())
        now = time.time()
        
        await self._db.execute("""
            INSERT INTO contexts (context_id, agent_id, session_id, context_data, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (context_id, agent_id, session_id, json.dumps(context_data), now, expires_at))
        await self._db.commit()
        return context_id
        
    async def get_context(self, context_id: str) -> Optional[Dict]:
        """获取上下文"""
        async with self._db.execute(
            "SELECT * FROM contexts WHERE context_id = ?", (context_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                data['context_data'] = json.loads(data['context_data'])
                return data
        return None
        
    async def list_contexts_by_agent(self, agent_id: str) -> List[Dict]:
        """列出 Agent 的所有上下文"""
        async with self._db.execute(
            "SELECT * FROM contexts WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                data = dict(row)
                data['context_data'] = json.loads(data['context_data'])
                result.append(data)
            return result
        
    async def delete_context(self, context_id: str):
        """删除上下文"""
        await self._db.execute("DELETE FROM contexts WHERE context_id = ?", (context_id,))
        await self._db.commit()
        
    async def cleanup_expired_contexts(self):
        """清理过期上下文"""
        now = time.time()
        await self._db.execute(
            "DELETE FROM contexts WHERE expires_at IS NOT NULL AND expires_at < ?", (now,)
        )
        await self._db.commit()
        
    # ==================== Events ====================
    
    async def log_event(self, event_type: str, data: Dict,
                       agent_id: Optional[str] = None,
                       severity: str = "info"):
        """记录事件"""
        event_id = str(uuid.uuid4())
        now = time.time()
        
        await self._db.execute("""
            INSERT INTO events (event_id, event_type, agent_id, timestamp, data_json, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_id, event_type, agent_id, now, json.dumps(data), severity))
        await self._db.commit()
        
    async def list_events(self, agent_id: Optional[str] = None,
                         event_type: Optional[str] = None,
                         start_time: Optional[float] = None,
                         end_time: Optional[float] = None,
                         limit: int = 100,
                         offset: int = 0) -> List[Dict]:
        """列出事件"""
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                data = dict(row)
                data['data_json'] = json.loads(data['data_json'])
                result.append(data)
            return result
        
    async def count_events(self, agent_id: Optional[str] = None,
                          event_type: Optional[str] = None,
                          start_time: Optional[float] = None,
                          end_time: Optional[float] = None) -> int:
        """统计事件数量"""
        query = "SELECT COUNT(*) as count FROM events WHERE 1=1"
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        async with self._db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row['count']
        
    async def cleanup_old_events(self, days: int = 30):
        """清理旧事件"""
        cutoff_time = time.time() - (days * 86400)
        await self._db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_time,))
        await self._db.commit()
        
    # ==================== Task History ====================
    
    async def log_task(self, task_id: str, agent_id: str, task_type: str,
                      priority: str = "normal", status: str = "pending"):
        """记录任务"""
        now = time.time()
        
        await self._db.execute("""
            INSERT INTO task_history (task_id, agent_id, task_type, priority, status, created_at, started_at, completed_at, duration, result_json, error_message)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)
        """, (task_id, agent_id, task_type, priority, status, now))
        await self._db.commit()
        
    async def update_task_status(self, task_id: str, status: str,
                                started_at: Optional[float] = None,
                                completed_at: Optional[float] = None,
                                duration: Optional[float] = None,
                                result: Optional[Dict] = None,
                                error_message: Optional[str] = None):
        """更新任务状态"""
        result_json = json.dumps(result) if result else None
        
        await self._db.execute("""
            UPDATE task_history SET
                status = ?,
                started_at = ?,
                completed_at = ?,
                duration = ?,
                result_json = ?,
                error_message = ?
            WHERE task_id = ?
        """, (status, started_at, completed_at, duration, result_json, error_message, task_id))
        await self._db.commit()
        
    async def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务"""
        async with self._db.execute(
            "SELECT * FROM task_history WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                if data.get('result_json'):
                    data['result_json'] = json.loads(data['result_json'])
                return data
        return None
        
    async def list_tasks_by_agent(self, agent_id: str, limit: int = 100) -> List[Dict]:
        """列出 Agent 的任务"""
        async with self._db.execute(
            "SELECT * FROM task_history WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                data = dict(row)
                if data.get('result_json'):
                    data['result_json'] = json.loads(data['result_json'])
                result.append(data)
            return result
        
    async def list_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """列出指定状态的任务"""
        async with self._db.execute(
            "SELECT * FROM task_history WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                data = dict(row)
                if data.get('result_json'):
                    data['result_json'] = json.loads(data['result_json'])
                result.append(data)
            return result
        
    async def get_agent_stats(self, agent_id: str) -> Optional[Dict]:
        """获取 Agent 统计"""
        async with self._db.execute("""
            SELECT
                agent_id,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
                AVG(CASE WHEN duration IS NOT NULL THEN duration ELSE NULL END) as avg_duration
            FROM task_history
            WHERE agent_id = ?
            GROUP BY agent_id
        """, (agent_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None


# 全局实例
_storage_manager = None


async def get_storage_manager(db_path: str = "aios.db") -> StorageManager:
    """获取全局 Storage Manager 实例"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager(db_path)
        await _storage_manager.initialize()
    return _storage_manager


async def close_storage_manager():
    """关闭全局 Storage Manager"""
    global _storage_manager
    if _storage_manager:
        await _storage_manager.close()
        _storage_manager = None

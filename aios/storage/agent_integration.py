"""
Agent System Storage Integration
将 Agent System 集成到 Storage Manager，持久化 Agent 状态

创建时间：2026-02-26
版本：v1.0
"""

import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path


class AgentStorage:
    """
    Agent 存储集成
    
    功能：
    1. 保存 Agent 状态
    2. 加载 Agent 状态
    3. 保存 Agent 上下文
    4. 加载 Agent 上下文
    5. 查询 Agent 统计
    """
    
    def __init__(self, storage_manager):
        """
        初始化
        
        Args:
            storage_manager: StorageManager 实例
        """
        self.storage = storage_manager
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
    
    def save_state(self, agent_id: str, state_data: Dict) -> None:
        """
        保存 Agent 状态
        
        Args:
            agent_id: Agent ID
            state_data: 状态数据
        """
        self._ensure_initialized()
        
        # 异步调用
        self._loop.run_until_complete(
            self.storage.save_agent_state(
                agent_id=agent_id,
                state_data=state_data
            )
        )
    
    def load_state(self, agent_id: str) -> Optional[Dict]:
        """
        加载 Agent 状态
        
        Args:
            agent_id: Agent ID
        
        Returns:
            状态数据（如果存在）
        """
        self._ensure_initialized()
        
        # 异步查询
        state = self._loop.run_until_complete(
            self.storage.get_agent_state(agent_id=agent_id)
        )
        
        return state
    
    def save_context(self, agent_id: str, context_data: Dict,
                    session_id: Optional[str] = None,
                    expires_at: Optional[float] = None) -> str:
        """
        保存 Agent 上下文
        
        Args:
            agent_id: Agent ID
            context_data: 上下文数据
            session_id: 会话 ID（可选）
            expires_at: 过期时间（Unix 时间戳，可选）
        
        Returns:
            上下文 ID
        """
        self._ensure_initialized()
        
        # 异步调用
        context_id = self._loop.run_until_complete(
            self.storage.save_context(
                agent_id=agent_id,
                context_data=context_data,
                session_id=session_id,
                expires_at=expires_at
            )
        )
        
        return context_id
    
    def load_context(self, context_id: str) -> Optional[Dict]:
        """
        加载 Agent 上下文
        
        Args:
            context_id: 上下文 ID
        
        Returns:
            上下文数据（如果存在）
        """
        self._ensure_initialized()
        
        # 异步查询
        context = self._loop.run_until_complete(
            self.storage.get_context(context_id=context_id)
        )
        
        return context
    
    def list_contexts(self, agent_id: str, limit: int = 10) -> list:
        """
        列出 Agent 的上下文
        
        Args:
            agent_id: Agent ID
            limit: 最大数量
        
        Returns:
            上下文列表
        """
        self._ensure_initialized()
        
        # 异步查询
        contexts = self._loop.run_until_complete(
            self.storage.list_contexts_by_agent(
                agent_id=agent_id,
                limit=limit
            )
        )
        
        return contexts
    
    def get_stats(self, agent_id: str) -> Dict:
        """
        获取 Agent 统计
        
        Args:
            agent_id: Agent ID
        
        Returns:
            统计数据
        """
        self._ensure_initialized()
        
        # 异步查询
        stats = self._loop.run_until_complete(
            self.storage.get_agent_stats(agent_id=agent_id)
        )
        
        return stats or {}


def integrate_agent_storage(agent_system, storage_manager):
    """
    集成 Agent System 和 Storage Manager
    
    Args:
        agent_system: Agent System 实例
        storage_manager: StorageManager 实例
    
    使用方法：
        from aios.storage.storage_manager import get_storage_manager
        from aios.storage.agent_integration import integrate_agent_storage
        
        # 初始化
        storage = await get_storage_manager()
        integrate_agent_storage(agent_system, storage)
        
        # 使用
        agent_system.storage.save_state("agent_1", {"status": "active"})
        state = agent_system.storage.load_state("agent_1")
    """
    # 创建存储集成
    agent_system.storage = AgentStorage(storage_manager)
    
    print("[AgentStorage] Integration completed")

"""
Agent System Storage Integration (Async Version)
异步版本，避免事件循环冲突

创建时间：2026-02-26
版本：v2.0
"""

from typing import Dict, Any, Optional


class AgentStorageAsync:
    """
    Agent 存储集成（异步版本）
    
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
            storage_manager: StorageManager 实例（已初始化）
        """
        self.storage = storage_manager
    
    async def save_state(self, agent_id: str, state_data: Dict) -> None:
        """
        保存 Agent 状态
        
        Args:
            agent_id: Agent ID
            state_data: 状态数据
        """
        await self.storage.save_agent_state(
            agent_id=agent_id,
            state_data=state_data
        )
    
    async def load_state(self, agent_id: str) -> Optional[Dict]:
        """
        加载 Agent 状态
        
        Args:
            agent_id: Agent ID
        
        Returns:
            状态数据（如果存在）
        """
        state = await self.storage.get_agent_state(agent_id=agent_id)
        
        return state
    
    async def save_context(self, agent_id: str, context_data: Dict,
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
        context_id = await self.storage.save_context(
            agent_id=agent_id,
            context_data=context_data,
            session_id=session_id,
            expires_at=expires_at
        )
        
        return context_id
    
    async def load_context(self, context_id: str) -> Optional[Dict]:
        """
        加载 Agent 上下文
        
        Args:
            context_id: 上下文 ID
        
        Returns:
            上下文数据（如果存在）
        """
        context = await self.storage.get_context(context_id=context_id)
        
        return context
    
    async def list_contexts(self, agent_id: str, limit: int = 10) -> list:
        """
        列出 Agent 的上下文
        
        Args:
            agent_id: Agent ID
            limit: 最大数量
        
        Returns:
            上下文列表
        """
        contexts = await self.storage.list_contexts_by_agent(
            agent_id=agent_id,
            limit=limit
        )
        
        return contexts
    
    async def get_stats(self, agent_id: str) -> Dict:
        """
        获取 Agent 统计
        
        Args:
            agent_id: Agent ID
        
        Returns:
            统计数据
        """
        stats = await self.storage.get_agent_stats(agent_id=agent_id)
        
        return stats or {}

"""
Scheduler Storage Integration (Async Version)
异步版本，避免事件循环冲突

创建时间：2026-02-26
版本：v2.0
"""

from typing import Dict, Any, Optional


class SchedulerStorageAsync:
    """
    Scheduler 存储集成（异步版本）
    
    功能：
    1. 记录任务创建
    2. 记录任务开始
    3. 记录任务完成/失败
    4. 查询任务历史
    5. 统计任务性能
    """
    
    def __init__(self, storage_manager):
        """
        初始化
        
        Args:
            storage_manager: StorageManager 实例（已初始化）
        """
        self.storage = storage_manager
    
    async def log_task_created(self, task_id: str, task_type: str, 
                              description: str, metadata: Optional[Dict] = None) -> str:
        """
        记录任务创建
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型（code/analysis/monitor/etc.）
            description: 任务描述（存储在 metadata 中）
            metadata: 额外元数据
        
        Returns:
            任务 ID
        """
        # log_task(task_id, agent_id, task_type, priority, status)
        await self.storage.log_task(
            task_id=task_id,
            agent_id="scheduler",
            task_type=task_type,
            priority=metadata.get("priority", "normal") if metadata else "normal",
            status="pending"
        )
        
        return task_id
    
    async def log_task_started(self, task_id: str):
        """
        记录任务开始
        
        Args:
            task_id: 任务 ID
        """
        import time
        await self.storage.update_task_status(
            task_id=task_id,
            status="running",
            started_at=time.time()
        )
    
    async def log_task_completed(self, task_id: str, result: Any, duration: float):
        """
        记录任务完成
        
        Args:
            task_id: 任务 ID
            result: 任务结果
            duration: 执行时长（秒）
        """
        import time
        await self.storage.update_task_status(
            task_id=task_id,
            status="completed",
            completed_at=time.time(),
            duration=duration,
            result={"result": str(result)}
        )
    
    async def log_task_failed(self, task_id: str, error: str, duration: float):
        """
        记录任务失败
        
        Args:
            task_id: 任务 ID
            error: 错误信息
            duration: 执行时长（秒）
        """
        import time
        await self.storage.update_task_status(
            task_id=task_id,
            status="failed",
            completed_at=time.time(),
            duration=duration,
            error_message=error
        )
    
    async def get_task_history(self, agent_id: str = "scheduler", limit: int = 100) -> list:
        """
        查询任务历史
        
        Args:
            agent_id: Agent ID
            limit: 最大数量
        
        Returns:
            任务列表
        """
        tasks = await self.storage.list_tasks_by_agent(
            agent_id=agent_id,
            limit=limit
        )
        
        return tasks
    
    async def get_stats(self, agent_id: str = "scheduler") -> Dict:
        """
        获取任务统计
        
        Args:
            agent_id: Agent ID
        
        Returns:
            统计数据
        """
        stats = await self.storage.get_agent_stats(agent_id=agent_id)
        
        return stats or {}

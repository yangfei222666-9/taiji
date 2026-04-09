"""
Scheduler Storage Integration
将 Scheduler 集成到 Storage Manager，记录任务历史

创建时间：2026-02-26
版本：v1.0
"""

import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path


class SchedulerStorage:
    """
    Scheduler 存储集成
    
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
    
    def log_task_created(self, task_id: str, task_type: str, 
                        description: str, metadata: Optional[Dict] = None) -> str:
        """
        记录任务创建
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型（code/analysis/monitor/etc.）
            description: 任务描述
            metadata: 额外元数据
        
        Returns:
            任务记录 ID
        """
        self._ensure_initialized()
        
        # 异步调用
        record_id = self._loop.run_until_complete(
            self.storage.log_task(
                agent_id="scheduler",
                task_type=task_type,
                description=description,
                status="pending",
                result_json=metadata or {}
            )
        )
        
        return record_id
    
    def log_task_started(self, task_id: str):
        """
        记录任务开始
        
        Args:
            task_id: 任务 ID
        """
        self._ensure_initialized()
        
        # 更新状态为 running
        self._loop.run_until_complete(
            self.storage.update_task_status(
                task_id=task_id,
                status="running"
            )
        )
    
    def log_task_completed(self, task_id: str, result: Any, duration: float):
        """
        记录任务完成
        
        Args:
            task_id: 任务 ID
            result: 任务结果
            duration: 执行时长（秒）
        """
        self._ensure_initialized()
        
        # 更新状态为 completed
        self._loop.run_until_complete(
            self.storage.update_task_status(
                task_id=task_id,
                status="completed",
                result_json={"result": str(result)},
                duration=duration
            )
        )
    
    def log_task_failed(self, task_id: str, error: str, duration: float):
        """
        记录任务失败
        
        Args:
            task_id: 任务 ID
            error: 错误信息
            duration: 执行时长（秒）
        """
        self._ensure_initialized()
        
        # 更新状态为 failed
        self._loop.run_until_complete(
            self.storage.update_task_status(
                task_id=task_id,
                status="failed",
                result_json={"error": error},
                duration=duration
            )
        )
    
    def get_task_history(self, agent_id: str = "scheduler", limit: int = 100) -> list:
        """
        查询任务历史
        
        Args:
            agent_id: Agent ID
            limit: 最大数量
        
        Returns:
            任务列表
        """
        self._ensure_initialized()
        
        # 异步查询
        tasks = self._loop.run_until_complete(
            self.storage.list_tasks_by_agent(
                agent_id=agent_id,
                limit=limit
            )
        )
        
        return tasks
    
    def get_task_stats(self, agent_id: str = "scheduler") -> Dict:
        """
        获取任务统计
        
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


def integrate_scheduler_storage(scheduler, storage_manager):
    """
    集成 Scheduler 和 Storage Manager
    
    Args:
        scheduler: Scheduler 实例
        storage_manager: StorageManager 实例
    """
    # 创建存储集成
    scheduler.storage = SchedulerStorage(storage_manager)
    
    # 包装原有的 _start_task 方法
    original_start_task = scheduler._start_task
    
    def wrapped_start_task(task: Dict[str, Any]) -> None:
        """包装的 _start_task，记录任务历史"""
        task_id = task["id"]
        task_type = task.get("type", "unknown")
        description = task.get("description", f"Task {task_id}")
        
        # 记录任务创建
        scheduler.storage.log_task_created(
            task_id=task_id,
            task_type=task_type,
            description=description,
            metadata={"depends_on": task.get("depends_on", [])}
        )
        
        # 记录任务开始
        scheduler.storage.log_task_started(task_id)
        
        # 调用原方法
        original_start_task(task)
    
    # 替换方法
    scheduler._start_task = wrapped_start_task
    
    # 包装原有的 _task_done 方法
    original_task_done = scheduler._task_done
    
    def wrapped_task_done(task_id: str, future, task: Dict[str, Any]) -> None:
        """包装的 _task_done，记录任务完成/失败"""
        start_time = task.get("_start_time", time.time())
        duration = time.time() - start_time
        
        try:
            result = future.result(timeout=0.1)  # 快速获取结果
            # 记录任务完成
            scheduler.storage.log_task_completed(
                task_id=task_id,
                result=result,
                duration=duration
            )
        except Exception as e:
            # 记录任务失败
            scheduler.storage.log_task_failed(
                task_id=task_id,
                error=str(e),
                duration=duration
            )
        
        # 调用原方法
        original_task_done(task_id, future, task)
    
    # 替换方法
    scheduler._task_done = wrapped_task_done
    
    print("[SchedulerStorage] Integration completed")

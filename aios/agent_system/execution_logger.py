#!/usr/bin/env python3
"""
AIOS 执行记录器 - 强制规范化写入
只允许写入符合统一 Schema 的执行记录
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from datetime import datetime


class ExecutionLogger:
    """
    统一的执行记录器
    
    用法:
        logger = ExecutionLogger()
        
        # 开始任务
        task_id = logger.start_task(
            agent_id="coder-dispatcher",
            task_type="code",
            description="重构 scheduler.py",
            source="heartbeat"
        )
        
        # 完成任务
        logger.complete_task(
            task_id=task_id,
            output_summary="成功重构 scheduler.py",
            tokens={"input": 1000, "output": 500}
        )
        
        # 或失败任务
        logger.fail_task(
            task_id=task_id,
            error_type="timeout",
            error_message="执行超时"
        )
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        初始化执行记录器
        
        Args:
            log_file: 日志文件路径，默认为 task_executions_v2.jsonl
        """
        if log_file is None:
            try:
                from .paths import TASK_EXECUTIONS
            except Exception:
                from paths import TASK_EXECUTIONS
            log_file = TASK_EXECUTIONS
        
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存中的任务状态（用于计算 duration）
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
    
    def start_task(
        self,
        agent_id: str,
        task_type: Literal["code", "analysis", "monitor", "learning", "improvement", "cleanup", "other"],
        description: str,
        source: Literal["heartbeat", "user_request", "cron", "self_improving", "learning_agent", "manual", "other"] = "other",
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        开始一个任务
        
        Returns:
            task_id: 任务 ID
        """
        # 生成 task_id
        timestamp = int(time.time() * 1000)
        task_id = f"{task_type}-{agent_id}-{timestamp}"
        
        # 记录任务开始状态
        self._active_tasks[task_id] = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "description": description[:500],  # 限制长度
            "started_at": time.time(),
            "source": source,
            "trace_id": trace_id,
            "metadata": metadata or {},
        }
        
        return task_id
    
    def complete_task(
        self,
        task_id: str,
        output_summary: str,
        output_full: Optional[str] = None,
        tokens: Optional[Dict[str, int]] = None,
        retry_count: int = 0,
    ) -> None:
        """
        标记任务完成
        """
        if task_id not in self._active_tasks:
            raise ValueError(f"Task {task_id} not found in active tasks")
        
        task_info = self._active_tasks.pop(task_id)
        finished_at = time.time()
        started_at = task_info["started_at"]
        duration_ms = int((finished_at - started_at) * 1000)
        
        # 构建完整记录
        record = {
            "task_id": task_id,
            "agent_id": task_info["agent_id"],
            "task_type": task_info["task_type"],
            "status": "completed",
            "description": task_info["description"],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "success": True,
            "error_type": None,
            "error_message": None,
            "output_summary": output_summary[:500] if output_summary else None,
            "output_full": output_full,
            "source": task_info["source"],
            "trace_id": task_info["trace_id"],
            "retry_count": retry_count,
            "total_attempts": retry_count + 1,
            "tokens": self._normalize_tokens(tokens),
            "metadata": task_info["metadata"],
        }
        
        # 写入文件
        self._write_record(record)
        if output_full:
            try:
                try:
                    from .artifact_ledger import append_artifact_event
                except Exception:
                    from artifact_ledger import append_artifact_event

                p = Path(str(output_full))
                if p.exists():
                    append_artifact_event(
                        task_id=task_id,
                        artifact_path=str(p),
                        artifact_type="output_full",
                        producer="execution_logger",
                        status="completed",
                        reason_code="ok",
                        created_at=str(datetime.utcnow().isoformat() + "Z"),
                        agent_id=str(task_info.get("agent_id") or ""),
                        trace_id=str(task_info.get("trace_id") or ""),
                        metadata={"source": str(task_info.get("source") or "")},
                    )
            except Exception:
                pass
    
    def fail_task(
        self,
        task_id: str,
        error_type: Literal["timeout", "network_error", "model_error", "validation_error", "resource_exhausted", "unknown"],
        error_message: str,
        output_full: Optional[str] = None,
        retry_count: int = 0,
    ) -> None:
        """
        标记任务失败
        """
        if task_id not in self._active_tasks:
            raise ValueError(f"Task {task_id} not found in active tasks")
        
        task_info = self._active_tasks.pop(task_id)
        finished_at = time.time()
        started_at = task_info["started_at"]
        duration_ms = int((finished_at - started_at) * 1000)
        
        # 构建完整记录
        record = {
            "task_id": task_id,
            "agent_id": task_info["agent_id"],
            "task_type": task_info["task_type"],
            "status": "failed",
            "description": task_info["description"],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "success": False,
            "error_type": error_type,
            "error_message": error_message[:1000] if error_message else None,
            "output_summary": None,
            "output_full": output_full,
            "source": task_info["source"],
            "trace_id": task_info["trace_id"],
            "retry_count": retry_count,
            "total_attempts": retry_count + 1,
            "tokens": None,
            "metadata": task_info["metadata"],
        }
        
        # 写入文件
        self._write_record(record)
        if output_full:
            try:
                try:
                    from .artifact_ledger import append_artifact_event
                except Exception:
                    from artifact_ledger import append_artifact_event

                p = Path(str(output_full))
                if p.exists():
                    append_artifact_event(
                        task_id=task_id,
                        artifact_path=str(p),
                        artifact_type="output_full",
                        producer="execution_logger",
                        status="failed",
                        reason_code=str(error_type),
                        created_at=str(datetime.utcnow().isoformat() + "Z"),
                        agent_id=str(task_info.get("agent_id") or ""),
                        trace_id=str(task_info.get("trace_id") or ""),
                        metadata={"source": str(task_info.get("source") or "")},
                    )
            except Exception:
                pass
    
    def timeout_task(
        self,
        task_id: str,
        timeout_seconds: int,
        output_full: Optional[str] = None,
        retry_count: int = 0,
    ) -> None:
        """
        标记任务超时
        """
        self.fail_task(
            task_id=task_id,
            error_type="timeout",
            error_message=f"Task timed out after {timeout_seconds} seconds",
            output_full=output_full,
            retry_count=retry_count,
        )
    
    def _normalize_tokens(self, tokens: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        """
        规范化 tokens 字段
        """
        if not tokens:
            return None
        
        input_tokens = tokens.get("input", 0)
        output_tokens = tokens.get("output", 0)
        
        return {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }
    
    def _write_record(self, record: Dict[str, Any]) -> None:
        """
        写入记录到文件（追加模式）
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    def get_recent_executions(self, limit: int = 10) -> list[Dict[str, Any]]:
        """
        获取最近的执行记录
        """
        if not self.log_file.exists():
            return []
        
        records = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # 按 finished_at 倒序排序
        records.sort(key=lambda x: x.get("finished_at", 0), reverse=True)
        return records[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取执行统计
        """
        if not self.log_file.exists():
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "success_rate": 0.0,
            }
        
        total = 0
        completed = 0
        failed = 0
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        total += 1
                        if record.get("status") == "completed":
                            completed += 1
                        elif record.get("status") == "failed":
                            failed += 1
                    except json.JSONDecodeError:
                        continue
        
        success_rate = (completed / total * 100) if total > 0 else 0.0
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "success_rate": success_rate,
        }


# 全局单例
_global_logger: Optional[ExecutionLogger] = None


def get_logger() -> ExecutionLogger:
    """
    获取全局执行记录器单例
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ExecutionLogger()
    return _global_logger


# 便捷函数
def start_task(*args, **kwargs) -> str:
    """便捷函数：开始任务"""
    return get_logger().start_task(*args, **kwargs)


def complete_task(*args, **kwargs) -> None:
    """便捷函数：完成任务"""
    get_logger().complete_task(*args, **kwargs)


def fail_task(*args, **kwargs) -> None:
    """便捷函数：失败任务"""
    get_logger().fail_task(*args, **kwargs)


def timeout_task(*args, **kwargs) -> None:
    """便捷函数：超时任务"""
    get_logger().timeout_task(*args, **kwargs)


def get_recent_executions(limit: int = 10) -> list[Dict[str, Any]]:
    """便捷函数：获取最近执行"""
    return get_logger().get_recent_executions(limit)


def get_stats() -> Dict[str, Any]:
    """便捷函数：获取统计"""
    return get_logger().get_stats()


if __name__ == "__main__":
    # 测试代码
    logger = ExecutionLogger()
    
    # 测试成功任务
    task_id = logger.start_task(
        agent_id="test-agent",
        task_type="code",
        description="测试任务",
        source="manual",
    )
    
    time.sleep(0.1)  # 模拟执行
    
    logger.complete_task(
        task_id=task_id,
        output_summary="测试成功",
        tokens={"input": 100, "output": 50},
    )
    
    # 测试失败任务
    task_id2 = logger.start_task(
        agent_id="test-agent",
        task_type="analysis",
        description="测试失败任务",
        source="manual",
    )
    
    time.sleep(0.1)
    
    logger.fail_task(
        task_id=task_id2,
        error_type="timeout",
        error_message="测试超时",
    )
    
    # 打印统计
    stats = logger.get_stats()
    print(f"统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    
    # 打印最近记录
    recent = logger.get_recent_executions(limit=2)
    print(f"\n最近记录:")
    for record in recent:
        print(f"  - {record['task_id']}: {record['status']}")

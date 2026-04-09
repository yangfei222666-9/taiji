"""
AIOS v0.6 Provider Manager - 容灾三件套
职责：
1. Provider Failover（故障转移）
2. 重试机制（指数退避）
3. DLQ（死信队列）
"""
import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ProviderConfig:
    """Provider 配置"""
    name: str
    priority: int  # 优先级（越小越优先）
    max_retries: int = 3
    timeout_sec: int = 30
    enabled: bool = True


@dataclass
class FailedTask:
    """失败任务"""
    id: str
    task_type: str
    payload: Dict[str, Any]
    error: str
    failed_at: str
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[str] = None


class ProviderManager:
    """Provider 管理器 - 容灾三件套"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化 Provider Manager
        
        Args:
            config_path: 配置文件路径
        """
        if config_path is None:
            workspace = Path(__file__).parent.parent.parent
            config_path = workspace / "aios" / "data" / "provider_config.json"
        
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # DLQ 路径
        self.dlq_path = self.config_path.parent / "dlq.jsonl"
        
        # 加载配置
        self.providers = self._load_config()
        
        # 熔断器状态
        self.circuit_breakers: Dict[str, Dict] = {}
    
    def execute_with_failover(
        self,
        task_type: str,
        task_payload: Dict[str, Any],
        execute_fn: callable
    ) -> Dict[str, Any]:
        """
        执行任务（带 Failover + 重试 + DLQ）
        
        Args:
            task_type: 任务类型（如 "llm_call", "agent_spawn"）
            task_payload: 任务参数
            execute_fn: 执行函数（接收 provider_name 和 payload，返回结果）
        
        Returns:
            执行结果
        """
        task_id = f"{task_type}_{int(time.time() * 1000)}"
        errors = []
        
        # 按优先级排序 provider
        sorted_providers = sorted(
            [p for p in self.providers if p.enabled],
            key=lambda x: x.priority
        )
        
        if not sorted_providers:
            return self._handle_all_failed(task_id, task_type, task_payload, "No enabled providers")
        
        # 尝试每个 provider
        for provider in sorted_providers:
            # 检查熔断器
            if self._is_circuit_open(provider.name):
                print(f"[ProviderManager] ⚠️  {provider.name} 熔断中，跳过")
                errors.append(f"{provider.name}: circuit open")
                continue
            
            # 重试机制（指数退避）
            for attempt in range(provider.max_retries):
                try:
                    print(f"[ProviderManager] 尝试 {provider.name} (attempt {attempt + 1}/{provider.max_retries})")
                    
                    # 执行任务
                    result = execute_fn(provider.name, task_payload)
                    
                    # 成功 → 重置熔断器
                    self._record_success(provider.name)
                    
                    return {
                        "success": True,
                        "provider": provider.name,
                        "attempt": attempt + 1,
                        "result": result
                    }
                
                except Exception as e:
                    error_msg = str(e)
                    print(f"[ProviderManager] ❌ {provider.name} 失败: {error_msg}")
                    
                    # 记录失败
                    self._record_failure(provider.name)
                    errors.append(f"{provider.name} (attempt {attempt + 1}): {error_msg}")
                    
                    # 判断是否可重试
                    if not self._is_retryable_error(error_msg):
                        print(f"[ProviderManager] 不可重试错误，跳过剩余尝试")
                        break
                    
                    # 指数退避
                    if attempt < provider.max_retries - 1:
                        backoff_sec = 2 ** attempt  # 1s, 2s, 4s
                        print(f"[ProviderManager] 等待 {backoff_sec}s 后重试...")
                        time.sleep(backoff_sec)
        
        # 所有 provider 都失败 → DLQ
        return self._handle_all_failed(task_id, task_type, task_payload, "; ".join(errors))
    
    def _handle_all_failed(
        self,
        task_id: str,
        task_type: str,
        task_payload: Dict[str, Any],
        error: str
    ) -> Dict[str, Any]:
        """
        所有 provider 都失败 → 进入 DLQ
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型
            task_payload: 任务参数
            error: 错误信息
        
        Returns:
            失败结果
        """
        print(f"[ProviderManager] 🔴 所有 provider 都失败，任务进入 DLQ")
        
        # 创建失败任务
        failed_task = FailedTask(
            id=task_id,
            task_type=task_type,
            payload=task_payload,
            error=error,
            failed_at=datetime.now().isoformat(),
            retry_count=0,
            max_retries=3
        )
        
        # 写入 DLQ
        self._write_to_dlq(failed_task)
        
        return {
            "success": False,
            "error": error,
            "task_id": task_id,
            "dlq": True
        }
    
    def _write_to_dlq(self, failed_task: FailedTask):
        """写入 DLQ"""
        with open(self.dlq_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(failed_task), ensure_ascii=False) + "\n")
    
    def get_dlq_tasks(self, limit: int = 100) -> List[FailedTask]:
        """获取 DLQ 中的任务"""
        if not self.dlq_path.exists():
            return []
        
        tasks = []
        with open(self.dlq_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    tasks.append(FailedTask(**data))
                    if len(tasks) >= limit:
                        break
                except Exception as e:
                    print(f"[ProviderManager] DLQ 解析错误: {e}")
        
        return tasks
    
    def retry_dlq_task(self, task_id: str, execute_fn: callable) -> Dict[str, Any]:
        """重试 DLQ 中的任务"""
        tasks = self.get_dlq_tasks()
        
        for task in tasks:
            if task.id == task_id:
                if task.retry_count >= task.max_retries:
                    return {
                        "success": False,
                        "error": "Max retries exceeded"
                    }
                
                # 更新重试次数
                task.retry_count += 1
                
                # 重新执行
                result = self.execute_with_failover(
                    task.task_type,
                    task.payload,
                    execute_fn
                )
                
                if result["success"]:
                    # 成功 → 从 DLQ 移除
                    self._remove_from_dlq(task_id)
                
                return result
        
        return {
            "success": False,
            "error": f"Task {task_id} not found in DLQ"
        }
    
    def _remove_from_dlq(self, task_id: str):
        """从 DLQ 移除任务"""
        if not self.dlq_path.exists():
            return
        
        # 读取所有任务
        tasks = []
        with open(self.dlq_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data["id"] != task_id:
                        tasks.append(line)
                except:
                    pass
        
        # 写回
        with open(self.dlq_path, "w", encoding="utf-8") as f:
            f.writelines(tasks)
    
    # ========== 熔断器 ==========
    
    def _is_circuit_open(self, provider_name: str) -> bool:
        """检查熔断器是否打开"""
        if provider_name not in self.circuit_breakers:
            return False
        
        cb = self.circuit_breakers[provider_name]
        
        # 检查是否在熔断期
        if cb["state"] == "open":
            if time.time() < cb["open_until"]:
                return True
            else:
                # 熔断期结束 → 半开状态
                cb["state"] = "half_open"
                print(f"[ProviderManager] {provider_name} 进入半开状态")
        
        return False
    
    def _record_success(self, provider_name: str):
        """记录成功"""
        if provider_name in self.circuit_breakers:
            cb = self.circuit_breakers[provider_name]
            
            if cb["state"] == "half_open":
                # 半开状态成功 → 关闭熔断器
                cb["state"] = "closed"
                cb["failure_count"] = 0
                print(f"[ProviderManager] {provider_name} 熔断器关闭")
            else:
                # 重置失败计数
                cb["failure_count"] = 0
    
    def _record_failure(self, provider_name: str):
        """记录失败"""
        if provider_name not in self.circuit_breakers:
            self.circuit_breakers[provider_name] = {
                "state": "closed",
                "failure_count": 0,
                "open_until": 0
            }
        
        cb = self.circuit_breakers[provider_name]
        cb["failure_count"] += 1
        
        # 连续失败 3 次 → 打开熔断器
        if cb["failure_count"] >= 3:
            cb["state"] = "open"
            cb["open_until"] = time.time() + 300  # 5 分钟
            print(f"[ProviderManager] 🔴 {provider_name} 熔断器打开（5 分钟）")
    
    @staticmethod
    def _is_retryable_error(error_msg: str) -> bool:
        """判断错误是否可重试"""
        retryable_codes = ["502", "503", "429", "timeout", "temporarily unavailable"]
        error_lower = error_msg.lower()
        
        return any(code in error_lower for code in retryable_codes)
    
    # ========== 配置管理 ==========
    
    def _load_config(self) -> List[ProviderConfig]:
        """加载配置"""
        if not self.config_path.exists():
            # 默认配置
            default_config = [
                ProviderConfig(name="claude-sonnet-4-6", priority=1),
                ProviderConfig(name="claude-opus-4-6", priority=2),
                ProviderConfig(name="claude-haiku-4-5", priority=3),
            ]
            self._save_config(default_config)
            return default_config
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [ProviderConfig(**p) for p in data]
    
    def _save_config(self, providers: List[ProviderConfig]):
        """保存配置"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump([asdict(p) for p in providers], f, indent=2, ensure_ascii=False)


# 全局单例
_global_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """获取全局 ProviderManager 实例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ProviderManager()
    return _global_manager

"""
AIOS Production Scheduler v3 - 支持配置文件的兼容层

新增特性：
1. 支持配置文件（scheduler_config.py）
2. 可以轻松切换调度策略
3. 可以启用/禁用 CPU 绑定
4. 保持与旧版 API 完全兼容
"""

from typing import Dict, Any, Optional
from enum import IntEnum
from dataclasses import dataclass, field
import time
import logging
import sys
from pathlib import Path

# 添加 core 目录到路径
CORE_DIR = Path(__file__).parent
sys.path.insert(0, str(CORE_DIR))

# 导入新版 Scheduler 和配置
from scheduler_v2_3 import Scheduler as SchedulerV23
from scheduling_policies import (
    PriorityPolicy, FIFOPolicy, SJFPolicy, 
    RoundRobinPolicy, EDFPolicy, HybridPolicy
)
from scheduler_config import SchedulerConfig, PresetConfigs

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """任务优先级（兼容旧版）"""
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


@dataclass
class Task:
    """调度任务（兼容旧版）"""
    priority: int
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    timeout_sec: int = 60
    retry_count: int = 0
    max_retries: int = 3


class ProductionScheduler:
    """生产级调度器 v3 - 支持配置文件"""
    
    def __init__(
        self,
        max_concurrent: int = None,
        enable_cpu_binding: bool = None,
        cpu_pool: Optional[list] = None,
        config: Optional[SchedulerConfig] = None,
        preset: str = None
    ):
        """初始化调度器。
        
        Args:
            max_concurrent: 最大并发任务数（None = 使用配置文件）
            enable_cpu_binding: 是否启用 CPU 绑定（None = 使用配置文件）
            cpu_pool: CPU 池（None = 使用配置文件）
            config: 配置对象（None = 使用默认配置）
            preset: 预设配置名称（"default"/"high_performance"/"real_time"/"fair"/"interactive"）
        """
        # 加载配置
        if preset:
            if preset == "default":
                self.config = PresetConfigs.default()
            elif preset == "high_performance":
                self.config = PresetConfigs.high_performance()
            elif preset == "real_time":
                self.config = PresetConfigs.real_time()
            elif preset == "fair":
                self.config = PresetConfigs.fair()
            elif preset == "interactive":
                self.config = PresetConfigs.interactive()
            else:
                logger.warning(f"Unknown preset: {preset}, using default")
                self.config = PresetConfigs.default()
        elif config:
            self.config = config
        else:
            self.config = SchedulerConfig()
        
        # 参数覆盖配置
        if max_concurrent is not None:
            self.config.MAX_CONCURRENT = max_concurrent
        if enable_cpu_binding is not None:
            self.config.ENABLE_CPU_BINDING = enable_cpu_binding
        if cpu_pool is not None:
            self.config.CPU_POOL = cpu_pool
        
        # 创建调度策略
        policy = self._create_policy()
        
        # 创建 Scheduler
        self.scheduler = SchedulerV23(
            max_concurrent=self.config.MAX_CONCURRENT,
            default_timeout=self.config.DEFAULT_TIMEOUT,
            policy=policy,
            enable_cpu_binding=self.config.ENABLE_CPU_BINDING,
            cpu_pool=self.config.CPU_POOL
        )
        
        self.running = True
        
        logger.info(
            f"ProductionScheduler v3 initialized: "
            f"policy={self.config.CURRENT_POLICY.value}, "
            f"cpu_binding={self.config.ENABLE_CPU_BINDING}, "
            f"max_concurrent={self.config.MAX_CONCURRENT}"
        )
    
    def _create_policy(self):
        """根据配置创建调度策略"""
        policy_type = self.config.CURRENT_POLICY
        
        if policy_type == SchedulerConfig.Policy.PRIORITY:
            return PriorityPolicy()
        elif policy_type == SchedulerConfig.Policy.FIFO:
            return FIFOPolicy()
        elif policy_type == SchedulerConfig.Policy.SJF:
            return SJFPolicy()
        elif policy_type == SchedulerConfig.Policy.RR:
            return RoundRobinPolicy(time_slice=self.config.RR_TIME_SLICE)
        elif policy_type == SchedulerConfig.Policy.EDF:
            return EDFPolicy()
        elif policy_type == SchedulerConfig.Policy.HYBRID:
            fallback = self._create_fallback_policy()
            return HybridPolicy(fallback_policy=fallback)
        else:
            logger.warning(f"Unknown policy: {policy_type}, using Priority")
            return PriorityPolicy()
    
    def _create_fallback_policy(self):
        """创建 Hybrid 的 fallback 策略"""
        fallback_type = self.config.HYBRID_FALLBACK
        
        if fallback_type == SchedulerConfig.Policy.FIFO:
            return FIFOPolicy()
        elif fallback_type == SchedulerConfig.Policy.SJF:
            return SJFPolicy()
        elif fallback_type == SchedulerConfig.Policy.RR:
            return RoundRobinPolicy(time_slice=self.config.RR_TIME_SLICE)
        elif fallback_type == SchedulerConfig.Policy.EDF:
            return EDFPolicy()
        else:
            return SJFPolicy()  # 默认 SJF
    
    def submit(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: Priority = Priority.P3_LOW,
        timeout_sec: int = 60
    ) -> str:
        """提交任务到队列（兼容旧版 API）。"""
        def task_func():
            return payload
        
        task_id = self.scheduler.schedule({
            "func": task_func,
            "priority": priority.value,
            "timeout_sec": timeout_sec,
            "task_type": task_type,
            "payload": payload,
        })
        
        return task_id
    
    def start(self):
        """启动调度器（兼容旧版 API）。"""
        self.running = True
        logger.info("ProductionScheduler started")
    
    def stop(self):
        """停止调度器（兼容旧版 API）。"""
        self.running = False
        self.scheduler.shutdown(wait=True)
        logger.info("ProductionScheduler stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（兼容旧版 API）。"""
        stats = self.scheduler.get_stats()
        stats["config"] = {
            "policy": self.config.CURRENT_POLICY.value,
            "cpu_binding": self.config.ENABLE_CPU_BINDING,
            "max_concurrent": self.config.MAX_CONCURRENT,
        }
        return stats


# 全局单例（兼容旧版 API）
_scheduler_instance: Optional[ProductionScheduler] = None


def get_scheduler(
    max_concurrent: int = None,
    enable_cpu_binding: bool = None,
    cpu_pool: Optional[list] = None,
    preset: str = None
) -> ProductionScheduler:
    """获取全局调度器实例（兼容旧版 API）。
    
    Args:
        max_concurrent: 最大并发任务数
        enable_cpu_binding: 是否启用 CPU 绑定
        cpu_pool: CPU 池
        preset: 预设配置（"default"/"high_performance"/"real_time"/"fair"/"interactive"）
    
    Returns:
        调度器实例
    """
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = ProductionScheduler(
            max_concurrent=max_concurrent,
            enable_cpu_binding=enable_cpu_binding,
            cpu_pool=cpu_pool,
            preset=preset
        )
    
    return _scheduler_instance


# ==================== 测试示例 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("Production Scheduler v3 - 配置测试")
    print("=" * 80)
    
    # 测试 1：默认配置
    print("\n=== Test 1: Default Config ===")
    scheduler = get_scheduler()
    stats = scheduler.get_stats()
    print(f"Config: {stats['config']}")
    
    # 测试 2：高性能配置
    print("\n=== Test 2: High Performance Preset ===")
    _scheduler_instance = None  # 重置单例
    scheduler = get_scheduler(preset="high_performance")
    stats = scheduler.get_stats()
    print(f"Config: {stats['config']}")
    
    # 测试 3：实时配置
    print("\n=== Test 3: Real-time Preset ===")
    _scheduler_instance = None
    scheduler = get_scheduler(preset="real_time")
    stats = scheduler.get_stats()
    print(f"Config: {stats['config']}")
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

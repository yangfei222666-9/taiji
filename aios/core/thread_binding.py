"""
AIOS Thread Binding - CPU 亲和性管理

功能：
1. 将任务绑定到特定 CPU 核心
2. 支持 CPU 池（多个核心）
3. 自动负载均衡
4. 跨平台支持（Windows/Linux/macOS）
"""

import os
import sys
import threading
import psutil
from typing import List, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CPUAffinity:
    """CPU 亲和性配置"""
    cpu_ids: List[int]  # CPU 核心 ID 列表
    exclusive: bool = False  # 是否独占（不与其他任务共享）


class ThreadBinder:
    """线程绑定管理器"""
    
    def __init__(self):
        """初始化线程绑定管理器"""
        self.total_cpus = psutil.cpu_count(logical=True)
        self.physical_cpus = psutil.cpu_count(logical=False)
        
        # 跟踪每个 CPU 的使用情况
        self.cpu_usage: dict[int, Set[int]] = {i: set() for i in range(self.total_cpus)}
        self.lock = threading.Lock()
        
        logger.info(f"ThreadBinder initialized: {self.total_cpus} logical CPUs, {self.physical_cpus} physical CPUs")
    
    def get_available_cpus(self) -> List[int]:
        """获取所有可用的 CPU 核心 ID。
        
        Returns:
            CPU 核心 ID 列表
        """
        return list(range(self.total_cpus))
    
    def get_least_loaded_cpu(self) -> int:
        """获取负载最低的 CPU 核心。
        
        Returns:
            CPU 核心 ID
        """
        with self.lock:
            # 找到使用最少的 CPU
            return min(self.cpu_usage.items(), key=lambda x: len(x[1]))[0]
    
    def bind_current_thread(self, cpu_ids: List[int]) -> bool:
        """将当前线程绑定到指定的 CPU 核心。
        
        Args:
            cpu_ids: CPU 核心 ID 列表
        
        Returns:
            是否成功绑定
        """
        try:
            # 验证 CPU ID
            for cpu_id in cpu_ids:
                if cpu_id < 0 or cpu_id >= self.total_cpus:
                    logger.error(f"Invalid CPU ID: {cpu_id} (total: {self.total_cpus})")
                    return False
            
            # 获取当前进程
            process = psutil.Process()
            
            # 设置 CPU 亲和性
            if sys.platform == "win32":
                # Windows: 使用位掩码
                mask = sum(1 << cpu_id for cpu_id in cpu_ids)
                process.cpu_affinity([cpu_id for cpu_id in cpu_ids])
            else:
                # Linux/macOS: 直接设置 CPU 列表
                process.cpu_affinity(cpu_ids)
            
            # 记录绑定
            thread_id = threading.get_ident()
            with self.lock:
                for cpu_id in cpu_ids:
                    self.cpu_usage[cpu_id].add(thread_id)
            
            logger.info(f"Thread {thread_id} bound to CPUs {cpu_ids}")
            return True
        
        except (AttributeError, OSError) as e:
            logger.warning(f"CPU affinity not supported on this platform: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to bind thread to CPUs {cpu_ids}: {e}")
            return False
    
    def unbind_current_thread(self) -> bool:
        """解除当前线程的 CPU 绑定。
        
        Returns:
            是否成功解除
        """
        try:
            process = psutil.Process()
            
            # 重置为所有 CPU
            all_cpus = list(range(self.total_cpus))
            process.cpu_affinity(all_cpus)
            
            # 清除记录
            thread_id = threading.get_ident()
            with self.lock:
                for cpu_set in self.cpu_usage.values():
                    cpu_set.discard(thread_id)
            
            logger.info(f"Thread {thread_id} unbound from CPUs")
            return True
        
        except Exception as e:
            logger.error(f"Failed to unbind thread: {e}")
            return False
    
    def get_current_affinity(self) -> Optional[List[int]]:
        """获取当前线程的 CPU 亲和性。
        
        Returns:
            CPU 核心 ID 列表，如果不支持返回 None
        """
        try:
            process = psutil.Process()
            return process.cpu_affinity()
        except (AttributeError, OSError):
            return None
    
    def allocate_cpus(self, count: int, exclusive: bool = False) -> Optional[List[int]]:
        """分配指定数量的 CPU 核心。
        
        Args:
            count: 需要的 CPU 核心数量
            exclusive: 是否独占（不与其他任务共享）
        
        Returns:
            分配的 CPU 核心 ID 列表，如果无法分配返回 None
        """
        with self.lock:
            if count > self.total_cpus:
                logger.error(f"Requested {count} CPUs, but only {self.total_cpus} available")
                return None
            
            if exclusive:
                # 独占模式：找到完全空闲的 CPU
                idle_cpus = [cpu_id for cpu_id, threads in self.cpu_usage.items() if len(threads) == 0]
                if len(idle_cpus) < count:
                    logger.warning(f"Not enough idle CPUs for exclusive allocation (need {count}, have {len(idle_cpus)})")
                    return None
                return idle_cpus[:count]
            else:
                # 共享模式：选择负载最低的 CPU
                sorted_cpus = sorted(self.cpu_usage.items(), key=lambda x: len(x[1]))
                return [cpu_id for cpu_id, _ in sorted_cpus[:count]]
    
    def get_cpu_stats(self) -> dict:
        """获取 CPU 使用统计。
        
        Returns:
            统计信息字典
        """
        with self.lock:
            return {
                "total_cpus": self.total_cpus,
                "physical_cpus": self.physical_cpus,
                "cpu_usage": {cpu_id: len(threads) for cpu_id, threads in self.cpu_usage.items()},
                "total_threads": sum(len(threads) for threads in self.cpu_usage.values()),
            }


class CPUPool:
    """CPU 池管理器（用于任务调度）"""
    
    def __init__(self, cpu_ids: Optional[List[int]] = None):
        """初始化 CPU 池。
        
        Args:
            cpu_ids: CPU 核心 ID 列表，如果为 None 则使用所有 CPU
        """
        self.binder = ThreadBinder()
        
        if cpu_ids is None:
            self.cpu_ids = self.binder.get_available_cpus()
        else:
            self.cpu_ids = cpu_ids
        
        self.current_index = 0
        self.lock = threading.Lock()
        
        logger.info(f"CPUPool initialized with CPUs: {self.cpu_ids}")
    
    def get_next_cpu(self) -> int:
        """获取下一个 CPU（轮转）。
        
        Returns:
            CPU 核心 ID
        """
        with self.lock:
            cpu_id = self.cpu_ids[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.cpu_ids)
            return cpu_id
    
    def bind_to_next_cpu(self) -> bool:
        """将当前线程绑定到下一个 CPU。
        
        Returns:
            是否成功绑定
        """
        cpu_id = self.get_next_cpu()
        return self.binder.bind_current_thread([cpu_id])
    
    def bind_to_least_loaded(self) -> bool:
        """将当前线程绑定到负载最低的 CPU。
        
        Returns:
            是否成功绑定
        """
        cpu_id = self.binder.get_least_loaded_cpu()
        return self.binder.bind_current_thread([cpu_id])


# ==================== 测试示例 ====================
if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("Thread Binding 测试")
    print("=" * 80)
    
    binder = ThreadBinder()
    
    # 测试 1：获取 CPU 信息
    print(f"\n=== Test 1: CPU Info ===")
    print(f"Total CPUs: {binder.total_cpus}")
    print(f"Physical CPUs: {binder.physical_cpus}")
    print(f"Available CPUs: {binder.get_available_cpus()}")
    
    # 测试 2：绑定当前线程
    print(f"\n=== Test 2: Bind Current Thread ===")
    current_affinity = binder.get_current_affinity()
    print(f"Current affinity: {current_affinity}")
    
    if binder.total_cpus >= 2:
        success = binder.bind_current_thread([0, 1])
        print(f"Bind to CPUs [0, 1]: {success}")
        
        new_affinity = binder.get_current_affinity()
        print(f"New affinity: {new_affinity}")
        
        # 解除绑定
        binder.unbind_current_thread()
        print(f"Unbound, affinity: {binder.get_current_affinity()}")
    else:
        print("Not enough CPUs for binding test")
    
    # 测试 3：分配 CPU
    print(f"\n=== Test 3: Allocate CPUs ===")
    allocated = binder.allocate_cpus(2, exclusive=False)
    print(f"Allocated CPUs (shared): {allocated}")
    
    allocated_exclusive = binder.allocate_cpus(1, exclusive=True)
    print(f"Allocated CPUs (exclusive): {allocated_exclusive}")
    
    # 测试 4：CPU 池
    print(f"\n=== Test 4: CPU Pool ===")
    pool = CPUPool(cpu_ids=[0, 1] if binder.total_cpus >= 2 else [0])
    
    for i in range(5):
        cpu_id = pool.get_next_cpu()
        print(f"Round {i+1}: CPU {cpu_id}")
    
    # 测试 5：多线程绑定
    print(f"\n=== Test 5: Multi-threaded Binding ===")
    
    def worker(worker_id, cpu_id):
        binder.bind_current_thread([cpu_id])
        print(f"Worker {worker_id} bound to CPU {cpu_id}")
        time.sleep(0.5)
        binder.unbind_current_thread()
    
    if binder.total_cpus >= 2:
        threads = []
        for i in range(4):
            cpu_id = i % 2  # 轮流绑定到 CPU 0 和 1
            t = threading.Thread(target=worker, args=(i, cpu_id))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
    
    # 测试 6：统计信息
    print(f"\n=== Test 6: CPU Stats ===")
    stats = binder.get_cpu_stats()
    print(f"Total CPUs: {stats['total_cpus']}")
    print(f"Physical CPUs: {stats['physical_cpus']}")
    print(f"CPU Usage: {stats['cpu_usage']}")
    print(f"Total Threads: {stats['total_threads']}")
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

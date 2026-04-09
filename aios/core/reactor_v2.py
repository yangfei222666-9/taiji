#!/usr/bin/env python3
"""
AIOS Reactor v2.0 - 生产级自动响应引擎

核心改进：
1. 线程安全 - threading.Lock 全覆盖
2. 熔断器自动恢复 - half-open + 30s 重试窗口
3. 超时保护 - ThreadPoolExecutor + timeout=10s
4. 类型提示 + Google docstring
5. 快速失败 - 高风险操作失败立即停止

Critical Fixes:
- ✅ 并发安全：playbooks/failure_count/circuit_breaker 全部加锁
- ✅ 熔断器恢复：opened_at 用于 half-open 状态转换
- ✅ 超时保护：所有 action 执行都有 timeout
- ✅ 异常处理：替换 bare except 为具体异常类型
"""

import json
import time
import threading
import subprocess
import uuid
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断（拒绝请求）
    HALF_OPEN = "half_open"  # 半开（尝试恢复）


@dataclass
class CircuitBreaker:
    """熔断器"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    opened_at: Optional[float] = None
    last_attempt: Optional[float] = None
    
    # 配置
    failure_threshold: int = 3  # 连续失败3次触发熔断
    success_threshold: int = 2  # 半开状态成功2次恢复
    timeout_seconds: int = 30   # 熔断后30秒进入半开


@dataclass
class Playbook:
    """剧本"""
    id: str
    name: str
    actions: List[Dict[str, Any]]
    error_pattern: str = ""
    cooldown_min: int = 60
    require_confirm: bool = False
    risk_level: str = "low"


class Reactor:
    """生产级自动响应引擎"""
    
    def __init__(self, max_workers: int = 3, action_timeout: int = 10):
        """初始化 Reactor。
        
        Args:
            max_workers: 最大并发执行数
            action_timeout: 单个 action 超时时间（秒）
        """
        self.max_workers = max_workers
        self.action_timeout = action_timeout
        
        # 线程安全的数据结构
        self.lock = threading.Lock()
        self.playbooks: Dict[str, Playbook] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.failure_count: Dict[str, int] = {}
        
        # 执行器
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        
        # 统计
        self.stats = {
            "total_executed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_timeout": 0,
            "total_circuit_open": 0,
        }
    
    def register_playbook(self, playbook: Playbook) -> None:
        """注册剧本（线程安全）。
        
        Args:
            playbook: 剧本对象
        """
        with self.lock:
            # 验证 playbook
            if not playbook.id:
                raise ValueError("Playbook must have an id")
            if not playbook.actions:
                raise ValueError(f"Playbook {playbook.id} must have actions")
            
            # 验证每个 action
            for action in playbook.actions:
                if "type" not in action:
                    raise ValueError(f"Action in playbook {playbook.id} must have 'type'")
                if "target" not in action:
                    raise ValueError(f"Action in playbook {playbook.id} must have 'target'")
            
            self.playbooks[playbook.id] = playbook
            self.circuit_breakers[playbook.id] = CircuitBreaker()
            self.failure_count[playbook.id] = 0
            
            logger.info(f"📥 Playbook registered: {playbook.id} ({playbook.name})")
    
    def _check_circuit_breaker(self, playbook_id: str) -> bool:
        """检查熔断器状态（线程安全）。
        
        Args:
            playbook_id: 剧本 ID
        
        Returns:
            True 如果可以执行，False 如果熔断
        """
        with self.lock:
            if playbook_id not in self.circuit_breakers:
                return True
            
            cb = self.circuit_breakers[playbook_id]
            now = time.time()
            
            if cb.state == CircuitState.CLOSED:
                return True
            
            elif cb.state == CircuitState.OPEN:
                # 检查是否可以进入 half-open
                if cb.opened_at and (now - cb.opened_at) > cb.timeout_seconds:
                    cb.state = CircuitState.HALF_OPEN
                    cb.success_count = 0
                    cb.failure_count = 0
                    logger.info(f"🔄 Circuit breaker {playbook_id} → HALF_OPEN")
                    return True
                else:
                    self.stats["total_circuit_open"] += 1
                    logger.warning(f"🚫 Circuit breaker {playbook_id} is OPEN")
                    return False
            
            elif cb.state == CircuitState.HALF_OPEN:
                # 半开状态允许尝试
                return True
        
        return False
    
    def _record_success(self, playbook_id: str) -> None:
        """记录成功（线程安全）。
        
        Args:
            playbook_id: 剧本 ID
        """
        with self.lock:
            if playbook_id not in self.circuit_breakers:
                return
            
            cb = self.circuit_breakers[playbook_id]
            self.failure_count[playbook_id] = 0
            
            if cb.state == CircuitState.HALF_OPEN:
                cb.success_count += 1
                if cb.success_count >= cb.success_threshold:
                    cb.state = CircuitState.CLOSED
                    cb.failure_count = 0
                    cb.opened_at = None
                    logger.info(f"✅ Circuit breaker {playbook_id} → CLOSED (recovered)")
    
    def _record_failure(self, playbook_id: str) -> None:
        """记录失败（线程安全）。
        
        Args:
            playbook_id: 剧本 ID
        """
        with self.lock:
            if playbook_id not in self.circuit_breakers:
                return
            
            cb = self.circuit_breakers[playbook_id]
            self.failure_count[playbook_id] = self.failure_count.get(playbook_id, 0) + 1
            
            if cb.state == CircuitState.CLOSED:
                cb.failure_count += 1
                if cb.failure_count >= cb.failure_threshold:
                    cb.state = CircuitState.OPEN
                    cb.opened_at = time.time()
                    logger.warning(f"🔴 Circuit breaker {playbook_id} → OPEN (threshold reached)")
            
            elif cb.state == CircuitState.HALF_OPEN:
                # 半开状态失败，立即回到 open
                cb.state = CircuitState.OPEN
                cb.opened_at = time.time()
                cb.failure_count = 0
                cb.success_count = 0
                logger.warning(f"🔴 Circuit breaker {playbook_id} → OPEN (half-open failed)")
    
    def _execute_action(self, action: Dict[str, Any]) -> Tuple[bool, str]:
        """执行单个 action（带超时保护）。
        
        Args:
            action: action 配置
        
        Returns:
            (success, output)
        """
        action_type = action.get("type", "shell")
        target = action.get("target", "")
        timeout = min(action.get("timeout", self.action_timeout), 120)  # 最大120秒
        
        if action_type == "shell":
            try:
                result = subprocess.run(
                    ["powershell", "-Command", target],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                ok = result.returncode == 0
                output = result.stdout.strip() if ok else f"EXIT {result.returncode}: {result.stderr.strip()[:200]}"
                return ok, output
            
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT after {timeout}s"
            except FileNotFoundError as e:
                return False, f"Command not found: {e}"
            except Exception as e:
                return False, f"ERROR: {str(e)[:200]}"
        
        elif action_type == "python":
            try:
                result = subprocess.run(
                    [r"sys.executable", "-X", "utf8", "-c", target],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                ok = result.returncode == 0
                output = result.stdout.strip() if ok else result.stderr.strip()[:200]
                return ok, output
            
            except subprocess.TimeoutExpired:
                return False, f"TIMEOUT after {timeout}s"
            except FileNotFoundError as e:
                return False, f"Python not found: {e}"
            except Exception as e:
                return False, f"ERROR: {str(e)[:200]}"
        
        else:
            return False, f"Unknown action type: {action_type}"
    
    def execute_playbook(self, playbook_id: str, dry_run: bool = False) -> Dict[str, Any]:
        """执行剧本（线程安全 + 熔断保护 + 超时保护）。
        
        Args:
            playbook_id: 剧本 ID
            dry_run: 是否为演练模式
        
        Returns:
            执行结果
        """
        # 检查剧本是否存在
        with self.lock:
            if playbook_id not in self.playbooks:
                return {
                    "playbook_id": playbook_id,
                    "status": "error",
                    "message": f"Playbook {playbook_id} not found",
                }
            
            playbook = self.playbooks[playbook_id]
        
        # 检查熔断器
        if not self._check_circuit_breaker(playbook_id):
            return {
                "playbook_id": playbook_id,
                "status": "circuit_open",
                "message": f"Circuit breaker is OPEN for {playbook_id}",
            }
        
        # 执行所有 actions
        action_results = []
        all_success = True
        fast_fail = False
        
        for i, action in enumerate(playbook.actions):
            # 快速失败：如果前一个高风险操作失败，跳过后续
            if fast_fail:
                action_results.append({
                    "action_index": i,
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": False,
                    "output": "SKIPPED: 前置高风险操作失败",
                })
                continue
            
            if dry_run:
                action_results.append({
                    "action_index": i,
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": True,
                    "output": f"[DRY_RUN] would execute: {action.get('type')} → {action.get('target', '')[:50]}",
                })
                continue
            
            # 使用 ThreadPoolExecutor 执行（带超时）
            try:
                future = self.executor.submit(self._execute_action, action)
                success, output = future.result(timeout=self.action_timeout)
                
                action_results.append({
                    "action_index": i,
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": success,
                    "output": output[:500],
                })
                
                if not success:
                    all_success = False
                    # 如果是高风险操作失败，启用快速失败
                    if action.get("risk", "low") in ("medium", "high"):
                        fast_fail = True
                        logger.warning(f"⚠️ High-risk action failed in {playbook_id}, fast-failing")
            
            except concurrent.futures.TimeoutError:
                all_success = False
                action_results.append({
                    "action_index": i,
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": False,
                    "output": f"TIMEOUT after {self.action_timeout}s",
                })
                with self.lock:
                    self.stats["total_timeout"] += 1
                
                # 超时也触发快速失败
                if action.get("risk", "low") in ("medium", "high"):
                    fast_fail = True
            
            except Exception as e:
                all_success = False
                action_results.append({
                    "action_index": i,
                    "type": action.get("type"),
                    "target": action.get("target", "")[:80],
                    "risk": action.get("risk", "low"),
                    "success": False,
                    "output": f"EXCEPTION: {str(e)[:200]}",
                })
        
        # 更新统计和熔断器
        with self.lock:
            self.stats["total_executed"] += 1
            if all_success:
                self.stats["total_success"] += 1
            else:
                self.stats["total_failed"] += 1
        
        if not dry_run:
            if all_success:
                self._record_success(playbook_id)
            else:
                self._record_failure(playbook_id)
        
        return {
            "playbook_id": playbook_id,
            "playbook_name": playbook.name,
            "status": "success" if all_success else "partial_failure",
            "dry_run": dry_run,
            "action_results": action_results,
            "executed_at": datetime.now().isoformat(),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（线程安全）。
        
        Returns:
            统计信息
        """
        with self.lock:
            return {
                **self.stats,
                "playbooks_registered": len(self.playbooks),
                "circuit_breakers": {
                    pb_id: {
                        "state": cb.state.value,
                        "failure_count": cb.failure_count,
                        "success_count": cb.success_count,
                        "opened_at": datetime.fromtimestamp(cb.opened_at).isoformat() if cb.opened_at else None,
                    }
                    for pb_id, cb in self.circuit_breakers.items()
                },
            }
    
    def get_circuit_breaker_status(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        """获取熔断器状态（线程安全）。
        
        Args:
            playbook_id: 剧本 ID
        
        Returns:
            熔断器状态，如果不存在返回 None
        """
        with self.lock:
            if playbook_id not in self.circuit_breakers:
                return None
            
            cb = self.circuit_breakers[playbook_id]
            return {
                "playbook_id": playbook_id,
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "opened_at": datetime.fromtimestamp(cb.opened_at).isoformat() if cb.opened_at else None,
                "can_execute": self._check_circuit_breaker(playbook_id),
            }
    
    def reset_circuit_breaker(self, playbook_id: str) -> bool:
        """手动重置熔断器（线程安全）。
        
        Args:
            playbook_id: 剧本 ID
        
        Returns:
            是否成功重置
        """
        with self.lock:
            if playbook_id not in self.circuit_breakers:
                return False
            
            cb = self.circuit_breakers[playbook_id]
            cb.state = CircuitState.CLOSED
            cb.failure_count = 0
            cb.success_count = 0
            cb.opened_at = None
            self.failure_count[playbook_id] = 0
            
            logger.info(f"🔄 Circuit breaker {playbook_id} manually reset")
            return True
    
    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭（线程安全）。
        
        Args:
            wait: 是否等待所有任务完成
        """
        self.executor.shutdown(wait=wait)
        logger.info("Reactor shutdown complete.")


# ==================== 测试示例 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    reactor = Reactor(max_workers=3, action_timeout=5)
    
    # 注册测试剧本
    playbook1 = Playbook(
        id="test_success",
        name="测试成功剧本",
        actions=[
            {"type": "shell", "target": "echo 'Hello from Reactor v2.0'", "risk": "low"},
            {"type": "python", "target": "print('Python action works!')", "risk": "low"},
        ]
    )
    
    playbook2 = Playbook(
        id="test_failure",
        name="测试失败剧本",
        actions=[
            {"type": "shell", "target": "exit 1", "risk": "low"},
        ]
    )
    
    reactor.register_playbook(playbook1)
    reactor.register_playbook(playbook2)
    
    # 测试成功剧本
    print("\n=== Test 1: Success Playbook ===")
    result = reactor.execute_playbook("test_success")
    print(f"Status: {result['status']}")
    for ar in result['action_results']:
        print(f"  [{ar['action_index']}] {ar['type']}: {ar['output']}")
    
    # 测试失败剧本（触发熔断器）
    print("\n=== Test 2: Failure Playbook (trigger circuit breaker) ===")
    for i in range(4):
        result = reactor.execute_playbook("test_failure")
        print(f"Attempt {i+1}: {result['status']}")
        time.sleep(0.1)
    
    # 检查熔断器状态
    print("\n=== Test 3: Circuit Breaker Status ===")
    cb_status = reactor.get_circuit_breaker_status("test_failure")
    print(f"State: {cb_status['state']}")
    print(f"Can execute: {cb_status['can_execute']}")
    
    # 等待熔断器恢复
    print("\n=== Test 4: Wait for circuit breaker recovery ===")
    print("Waiting 31 seconds for half-open...")
    time.sleep(31)
    
    cb_status = reactor.get_circuit_breaker_status("test_failure")
    print(f"State after 31s: {cb_status['state']}")
    print(f"Can execute: {cb_status['can_execute']}")
    
    # 统计
    print("\n=== Stats ===")
    stats = reactor.get_stats()
    print(f"Total executed: {stats['total_executed']}")
    print(f"Total success: {stats['total_success']}")
    print(f"Total failed: {stats['total_failed']}")
    print(f"Total circuit open: {stats['total_circuit_open']}")
    
    reactor.shutdown()
    print("\n✅ All tests completed!")

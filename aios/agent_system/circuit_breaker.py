"""
AIOS Circuit Breaker - 熔断器模式
防止失败任务拖垮整个系统
"""

import json
import time
from pathlib import Path
from typing import Dict, Tuple, Optional


class CircuitBreaker:
    """熔断器：自动隔离频繁失败的任务类型"""

    def __init__(
        self,
        threshold: int = 3,  # 失败次数阈值
        timeout: int = 300,  # 熔断时长（秒）
        state_file: Optional[Path] = None,
    ):
        self.threshold = threshold
        self.timeout = timeout
        self.state_file = (
            state_file or Path(__file__).parent / "circuit_breaker_state.json"
        )
        self.failures: Dict[str, Tuple[int, float]] = (
            {}
        )  # {task_type: (count, last_fail_time)}

        # 加载持久化状态
        self._load_state()

    def should_execute(self, task_type: str) -> bool:
        """判断任务是否应该执行（未熔断）"""
        if task_type not in self.failures:
            return True

        count, last_fail = self.failures[task_type]

        # 熔断中
        if count >= self.threshold:
            elapsed = time.time() - last_fail

            if elapsed < self.timeout:
                # 仍在熔断窗口内
                return False
            else:
                # 超时恢复，重置计数
                del self.failures[task_type]
                self._save_state()
                return True

        return True

    def record_failure(self, task_type: str):
        """记录失败"""
        if task_type not in self.failures:
            self.failures[task_type] = (0, 0)

        count, _ = self.failures[task_type]
        self.failures[task_type] = (count + 1, time.time())
        self._save_state()

    def record_success(self, task_type: str):
        """记录成功（重置计数）"""
        if task_type in self.failures:
            del self.failures[task_type]
            self._save_state()

    def get_status(self) -> Dict:
        """获取熔断器状态"""
        now = time.time()
        status = {}

        for task_type, (count, last_fail) in self.failures.items():
            elapsed = now - last_fail
            is_open = count >= self.threshold and elapsed < self.timeout

            status[task_type] = {
                "failure_count": count,
                "last_failure": last_fail,
                "elapsed_seconds": int(elapsed),
                "circuit_open": is_open,
                "retry_after": max(0, int(self.timeout - elapsed)) if is_open else 0,
            }

        return status

    def reset(self, task_type: Optional[str] = None):
        """手动重置熔断器"""
        if task_type:
            if task_type in self.failures:
                del self.failures[task_type]
        else:
            self.failures.clear()

        self._save_state()

    def _load_state(self):
        """从文件加载状态"""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

                # 转换为内存格式
                for task_type, info in data.items():
                    self.failures[task_type] = (info["count"], info["last_fail"])
        except Exception:
            # 损坏的状态文件，忽略
            pass

    def _save_state(self):
        """保存状态到文件"""
        data = {}
        for task_type, (count, last_fail) in self.failures.items():
            data[task_type] = {"count": count, "last_fail": last_fail}

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """CLI 测试"""
    import sys

    breaker = CircuitBreaker(threshold=3, timeout=60)

    if len(sys.argv) < 2:
        print("Usage: python circuit_breaker.py [status|test|reset]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        status = breaker.get_status()
        if not status:
            print("All circuits closed (healthy)")
        else:
            print("Circuit Breaker Status:")
            for task_type, info in status.items():
                state = "🔴 OPEN" if info["circuit_open"] else "🟡 DEGRADED"
                print(f"  {task_type}: {state}")
                print(f"    Failures: {info['failure_count']}")
                print(f"    Retry after: {info['retry_after']}s")

    elif cmd == "test":
        # 模拟失败
        print("Simulating failures...")
        for i in range(5):
            if breaker.should_execute("test_task"):
                print(f"  Attempt {i+1}: ALLOWED")
                breaker.record_failure("test_task")
            else:
                print(f"  Attempt {i+1}: BLOCKED (circuit open)")

        print("\nStatus after test:")
        status = breaker.get_status()
        print(json.dumps(status, indent=2))

    elif cmd == "reset":
        task_type = sys.argv[2] if len(sys.argv) > 2 else None
        breaker.reset(task_type)
        print(f"Reset {'all circuits' if not task_type else task_type}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Test 1: Basic"""
import time
from scheduler_v2_1 import Scheduler

scheduler = Scheduler(max_concurrent=2)

result = []
def task():
    result.append("done")
    return "success"

scheduler.schedule({"id": "test1", "func": task})
time.sleep(0.5)

print(f"Completed: {scheduler.completed}")
print(f"Result: {result}")

assert "test1" in scheduler.completed
assert result == ["done"]

scheduler.shutdown(wait=False)
print("✅ Test 1 PASS")

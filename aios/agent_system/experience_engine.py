"""
Experience Engine - 从真实失败中学习

核心功能：
1. harvest_real_failures() - 从 task_executions.jsonl 提取真实失败
2. 自动过滤模拟数据（source=simulated / error=Simulated）
3. 写入 lessons.json（去重）
"""

import json
import os
import hashlib
from datetime import datetime

EXECUTIONS_PATH = "task_executions.jsonl"
LESSONS_PATH = "lessons.json"


def harvest_real_failures():
    """从 task_executions.jsonl 提取真实失败，写入 lessons.json"""
    
    # 加载已有 lessons（去重）
    existing_ids = set()
    if os.path.exists(LESSONS_PATH):
        with open(LESSONS_PATH, "r", encoding="utf-8") as f:
            for lesson in json.load(f):
                existing_ids.add(lesson.get("source_task_id"))
    
    # 扫描 task_executions.jsonl
    new_lessons = []
    if not os.path.exists(EXECUTIONS_PATH):
        print(f"[WARN] {EXECUTIONS_PATH} not found")
        return 0
    
    with open(EXECUTIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            
            # 门禁 1：跳过模拟数据
            if rec.get("source") == "simulated":
                continue
            if rec.get("error", "").startswith("Simulated"):
                continue
            
            # 门禁 2：只要失败任务
            if rec.get("status") != "failed":
                continue
            
            # 门禁 3：去重
            task_id = rec.get("task_id")
            if not task_id or task_id in existing_ids:
                continue
            
            # 提取失败信息（含 stderr）
            result = rec.get("result", {})
            error_msg = result.get("error", "") or rec.get("error", "")
            stderr = result.get("stderr", "") or rec.get("stderr", "")
            # 合并 error + stderr，保留完整根因
            full_error = error_msg
            if stderr and stderr not in full_error:
                full_error = f"{error_msg}\n[stderr] {stderr}".strip()
            error_type = classify_error(full_error, stderr)
            
            lesson = {
                "lesson_id": f"lesson-{hashlib.sha256(task_id.encode()).hexdigest()[:8]}",
                "source_task_id": task_id,
                "source": "real",
                "task_description": rec.get("description", ""),
                "task_type": rec.get("task_type", "unknown"),
                "error_type": error_type,
                "error_message": full_error,
                "stderr": stderr,  # 单独保留，方便后续分析
                "context": {
                    "timestamp": rec.get("start_time", rec.get("timestamp")),
                    "agent": rec.get("agent_id", "unknown"),  # 新格式用 agent_id
                    "retry_count": rec.get("retry_count", 0),
                    "total_attempts": rec.get("retry_count", 0) + 1,
                },
                "harvested_at": datetime.utcnow().isoformat() + "Z",
                "regeneration_status": "pending"
            }
            
            new_lessons.append(lesson)
            existing_ids.add(task_id)
    
    # 合并并保存
    if new_lessons:
        all_lessons = []
        if os.path.exists(LESSONS_PATH):
            with open(LESSONS_PATH, "r", encoding="utf-8") as f:
                all_lessons = json.load(f)
        
        all_lessons.extend(new_lessons)
        
        with open(LESSONS_PATH, "w", encoding="utf-8") as f:
            json.dump(all_lessons, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Harvested {len(new_lessons)} real failures → {LESSONS_PATH}")
    else:
        print(f"[OK] No new failures to harvest")
    
    return len(new_lessons)


def classify_error(error_msg: str, stderr: str = "") -> str:
    """
    错误分类，stderr 优先于 error_msg（stderr 更接近真实根因）。
    匹配顺序：资源 > 超时 > 网络 > 权限 > 依赖 > unknown
    """
    # stderr 优先检查
    for text in (stderr, error_msg):
        t = text.lower()
        if not t:
            continue
        if any(k in t for k in ("oomkilled", "memoryerror", "out of memory", "killed")):
            return "resource_exhausted"
        if any(k in t for k in ("timeouterror", "deadline exceeded", "timed out", "timeout")):
            return "timeout"
        if any(k in t for k in ("connectionrefused", "econnreset", "connection refused",
                                 "network", "unreachable", "no route to host")):
            return "network_error"
        if any(k in t for k in ("permissionerror", "eacces", "permission denied",
                                 "access denied", "forbidden")):
            return "permission_error"
        if any(k in t for k in ("modulenotfounderror", "importerror", "no module named",
                                 "dependency", "module", "import")):
            return "dependency_error"
    return "unknown"


if __name__ == "__main__":
    print("Experience Engine - Harvesting Real Failures")
    print("=" * 60)
    count = harvest_real_failures()
    print(f"\n[DONE] Harvested {count} new lessons")

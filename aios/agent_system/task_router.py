#!/usr/bin/env python3
"""
AIOS Task Router v2.0 - 智能任务路由系统 + Planning 集成
接收任务 → 自动拆解 → 匹配 Agent → 分发执行

用法:
  python task_router.py route "写一个排序算法"
  python task_router.py route "检查系统健康度" --dry-run
  python task_router.py submit "分析最近的错误日志" --priority high
  python task_router.py plan "搜索GitHub项目，然后分析架构，最后写报告"
  python task_router.py queue                    # 查看队列
  python task_router.py stats                    # 查看统计
"""

import json
import sys
import time
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from core.status_adapter import get_agent_status

BASE_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = BASE_DIR / "unified_registry.json"
try:
    from paths import TASK_QUEUE as QUEUE_PATH
except ImportError:
    QUEUE_PATH = BASE_DIR / "data" / "task_queue.jsonl"
ROUTE_LOG_PATH = BASE_DIR / "route_log.jsonl"
STATS_PATH = BASE_DIR / "router_stats.json"


# ========== 关键词映射表 ==========

# 中文关键词 → task_type 映射
KEYWORD_MAP = {
    # code 类
    "写代码": "code", "编程": "code", "实现": "code", "开发": "code",
    "写一个": "code", "创建": "code", "生成代码": "code", "函数": "code",
    "脚本": "code", "程序": "code", "算法": "code", "写个": "code",
    # debug 类
    "调试": "debug", "修bug": "debug", "修复": "debug", "排错": "debug",
    "报错": "debug", "错误": "debug", "异常": "debug", "崩溃": "debug",
    # refactor 类
    "重构": "refactor", "优化代码": "refactor", "整理代码": "refactor",
    "代码质量": "refactor", "清理代码": "refactor",
    # test 类
    "测试": "test", "单元测试": "test", "写测试": "test", "验证": "test",
    "回归测试": "test", "qa": "test",
    # analysis 类
    "分析": "analysis", "统计": "analysis", "报告": "analysis",
    "数据分析": "analysis", "根因分析": "analysis", "趋势": "analysis",
    # monitor 类
    "监控": "monitor", "健康检查": "monitor", "系统状态": "monitor",
    "资源": "monitor", "cpu": "monitor", "内存": "monitor", "磁盘": "monitor",
    # health-check 类
    "健康度": "health-check", "系统健康": "health-check",
    # research 类
    "研究": "research", "调研": "research", "搜索": "research",
    "学习": "research", "github": "research", "论文": "research",
    # design 类
    "设计": "design", "架构": "design", "方案": "design", "选型": "design",
    # fix 类
    "修复": "fix", "恢复": "fix", "回滚": "fix",
    # automation 类
    "自动化": "automation", "批量": "automation", "清理": "automation",
    "备份": "automation", "整理": "automation",
    # document 类
    "文档": "document", "摘要": "document", "总结": "document",
    "提取": "document", "关键词": "document",
    # game 类
    "游戏": "game", "小游戏": "game",
    # security 类
    "安全": "security", "审计": "audit", "权限": "security",
    # evolution 类
    "进化": "evolution", "改进": "evolution", "自我改进": "evolution",
    "优化系统": "optimize",
    # alert 类
    "告警": "alert", "通知": "alert", "预警": "alert",
}

# 英文关键词
KEYWORD_MAP_EN = {
    "code": "code", "write": "code", "implement": "code", "create": "code",
    "debug": "debug", "fix": "fix", "bug": "debug",
    "test": "test", "unittest": "test",
    "analyze": "analysis", "report": "analysis", "insight": "analysis",
    "monitor": "monitor", "health": "health-check", "status": "monitor",
    "research": "research", "search": "research",
    "design": "design", "architect": "design",
    "automate": "automation", "cleanup": "automation", "backup": "automation",
    "document": "document", "summary": "document",
    "game": "game",
    "security": "security", "audit": "audit",
    "evolve": "evolution", "optimize": "optimize",
}


@dataclass
class RouteResult:
    """路由结果"""
    agent_id: str
    agent_name: str
    task_type: str
    confidence: float  # 0.0 ~ 1.0
    reason: str
    alternatives: List[Dict]  # 备选 Agent


@dataclass
class Task:
    """任务"""
    id: str
    description: str
    task_type: str
    agent_id: str
    priority: str  # critical / high / normal / low
    status: str  # pending / running / done / failed
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[str] = None
    confidence: float = 0.0


class TaskRouter:
    """智能任务路由器 + Planning 集成"""

    def __init__(self):
        self.registry = self._load_registry()
        self.agents = {a["id"]: a for a in self.registry.get("agents", [])}
        self.stats = self._load_stats()
        self._planner = None

    @property
    def planner(self):
        """懒加载 Planner"""
        if self._planner is None:
            try:
                sys.path.insert(0, str(BASE_DIR.parent / "core"))
                from planner import Planner
                workspace = BASE_DIR.parent.parent
                self._planner = Planner(workspace)
            except ImportError:
                self._planner = False  # 标记为不可用
        return self._planner if self._planner is not False else None

    def plan_and_submit(self, description: str, priority: str = "normal") -> List[Task]:
        """
        复杂任务：先拆解再逐个提交
        返回所有子任务
        """
        if not self.planner:
            # Planner 不可用，直接提交
            return [self.submit(description, priority)]

        plan = self.planner.plan(description)

        if len(plan.subtasks) <= 1:
            # 简单任务，不拆解
            return [self.submit(description, priority)]

        tasks = []
        for st in plan.subtasks:
            task = self.submit(
                st.description,
                priority=st.priority if st.priority != "normal" else priority
            )
            tasks.append(task)

        # 记录计划
        self._log_route(description, RouteResult(
            agent_id="planner",
            agent_name="Planner",
            task_type="plan",
            confidence=0.9,
            reason=f"拆解为 {len(plan.subtasks)} 个子任务 (strategy={plan.strategy})",
            alternatives=[]
        ))

        return tasks

    # ========== 核心路由 ==========

    def route(self, description: str) -> RouteResult:
        """
        核心路由：任务描述 → 最佳 Agent
        
        匹配策略（按优先级）：
        1. 精确匹配 task_type
        2. 关键词匹配
        3. 模糊匹配（Jaccard 相似度）
        """
        # Step 1: 识别 task_type
        task_type, kw_confidence = self._identify_task_type(description)

        # Step 2: 找到匹配的 Agent
        candidates = self._find_agents_for_type(task_type)

        if not candidates:
            # 降级：尝试模糊匹配
            task_type, candidates, kw_confidence = self._fuzzy_match(description)

        if not candidates:
            # 最终降级：用 coder（万能选手）
            fallback = self.agents.get("coder", {})
            return RouteResult(
                agent_id="coder",
                agent_name=fallback.get("name", "代码开发专家"),
                task_type=task_type or "code",
                confidence=0.2,
                reason=f"无精确匹配，降级到 coder（万能选手）",
                alternatives=[]
            )

        # Step 3: 从候选中选最佳
        best = self._rank_candidates(candidates, task_type, description)

        # 备选列表（排除最佳）
        alternatives = [
            {"agent_id": c["id"], "agent_name": c["name"], "score": c.get("_score", 0)}
            for c in candidates if c["id"] != best["id"]
        ][:3]

        confidence = min(kw_confidence * best.get("_score", 0.5) * 2, 1.0)

        return RouteResult(
            agent_id=best["id"],
            agent_name=best["name"],
            task_type=task_type,
            confidence=round(confidence, 2),
            reason=f"task_type={task_type} → {best['name']}（{best['role']}）",
            alternatives=alternatives
        )

    def _identify_task_type(self, description: str) -> Tuple[str, float]:
        """识别任务类型"""
        desc_lower = description.lower().strip()

        # 1. 精确中文关键词匹配
        best_type = None
        best_len = 0
        for keyword, task_type in KEYWORD_MAP.items():
            if keyword in desc_lower and len(keyword) > best_len:
                best_type = task_type
                best_len = len(keyword)

        if best_type:
            return best_type, 0.9

        # 2. 英文关键词匹配
        words = set(re.findall(r'[a-zA-Z]+', desc_lower))
        for word, task_type in KEYWORD_MAP_EN.items():
            if word in words:
                return task_type, 0.8

        # 3. 默认 code
        return "code", 0.3

    def _find_agents_for_type(self, task_type: str) -> List[Dict]:
        """找到支持该 task_type 的 Agent"""
        result = []
        for agent in self.agents.values():
            if get_agent_status(agent) == "standby":
                continue
            if task_type in agent.get("task_types", []):
                agent_copy = dict(agent)
                # 精确匹配得分高
                agent_copy["_score"] = 1.0
                result.append(agent_copy)
        return result

    def _fuzzy_match(self, description: str) -> Tuple[str, List[Dict], float]:
        """模糊匹配：用 Jaccard 相似度"""
        desc_words = set(description.lower().split())
        best_type = "code"
        best_score = 0
        best_agents = []

        for agent in self.agents.values():
            if get_agent_status(agent) == "standby":
                continue
            role_words = set(agent.get("role", "").lower().split())
            name_words = set(agent.get("name", "").lower().split())
            all_words = role_words | name_words

            # Jaccard
            intersection = desc_words & all_words
            union = desc_words | all_words
            score = len(intersection) / max(len(union), 1)

            if score > best_score:
                best_score = score
                best_type = agent.get("task_types", ["code"])[0]
                best_agents = [dict(agent, _score=score)]
            elif score == best_score and score > 0:
                best_agents.append(dict(agent, _score=score))

        return best_type, best_agents, max(best_score, 0.3)

    def _rank_candidates(self, candidates: List[Dict], task_type: str, description: str) -> Dict:
        """对候选 Agent 排名"""
        for c in candidates:
            score = c.get("_score", 0.5)

            # 优先级加分
            priority_bonus = {"critical": 0.3, "high": 0.2, "normal": 0.1, "low": 0.0}
            score += priority_bonus.get(c.get("priority", "normal"), 0)

            # 成功率加分
            stats = c.get("stats", {})
            sr = stats.get("success_rate", 0)
            if sr > 0:
                score += sr * 0.2

            # 任务经验加分
            completed = stats.get("tasks_completed", 0)
            if completed > 0:
                score += min(completed * 0.05, 0.2)

            c["_score"] = score

        candidates.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return candidates[0]

    # ========== 任务队列 ==========

    def submit(self, description: str, priority: str = "normal") -> Task:
        """提交任务到队列"""
        route = self.route(description)

        task = Task(
            id=f"task-{int(time.time()*1000)}",
            description=description,
            task_type=route.task_type,
            agent_id=route.agent_id,
            priority=priority,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            confidence=route.confidence
        )

        # 写入队列
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(task), ensure_ascii=False) + "\n")

        # 记录路由日志
        self._log_route(description, route)

        # 更新统计
        self.stats["total_routed"] = self.stats.get("total_routed", 0) + 1
        agent_stats = self.stats.setdefault("by_agent", {})
        agent_stats[route.agent_id] = agent_stats.get(route.agent_id, 0) + 1
        self._save_stats()

        return task

    def get_queue(self) -> List[Dict]:
        """获取待处理队列"""
        if not QUEUE_PATH.exists():
            return []
        tasks = []
        for line in QUEUE_PATH.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    tasks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        # 按优先级排序
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        tasks.sort(key=lambda t: priority_order.get(t.get("priority", "normal"), 2))
        return [t for t in tasks if t.get("status") == "pending"]

    def get_stats(self) -> Dict:
        """获取路由统计"""
        stats = dict(self.stats)
        stats["agents_total"] = len(self.agents)
        stats["agents_active"] = sum(1 for a in self.agents.values() if a.get("status") == "active")
        stats["queue_pending"] = len(self.get_queue())
        return stats

    # ========== 内部方法 ==========

    def _load_registry(self) -> Dict:
        if not REGISTRY_PATH.exists():
            return {"agents": [], "skills": {}}
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def _load_stats(self) -> Dict:
        if not STATS_PATH.exists():
            return {"total_routed": 0, "by_agent": {}, "by_type": {}}
        try:
            return json.loads(STATS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"total_routed": 0, "by_agent": {}, "by_type": {}}

    def _save_stats(self):
        STATS_PATH.write_text(
            json.dumps(self.stats, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _log_route(self, description: str, route: RouteResult):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "input": description,
            "agent": route.agent_id,
            "type": route.task_type,
            "confidence": route.confidence,
            "reason": route.reason
        }
        with open(ROUTE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ========== CLI ==========

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    router = TaskRouter()

    if cmd == "route":
        if len(sys.argv) < 3:
            print("Usage: python task_router.py route <description>")
            sys.exit(1)
        desc = " ".join(sys.argv[2:]).replace("--dry-run", "").strip()
        dry_run = "--dry-run" in sys.argv

        result = router.route(desc)
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Route Result:")
        print(f"  Task:       {desc}")
        print(f"  Agent:      {result.agent_id} ({result.agent_name})")
        print(f"  Type:       {result.task_type}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Reason:     {result.reason}")
        if result.alternatives:
            print(f"  Alternatives:")
            for alt in result.alternatives:
                print(f"    - {alt['agent_id']} ({alt['agent_name']})")

    elif cmd == "submit":
        if len(sys.argv) < 3:
            print("Usage: python task_router.py submit <description> [--priority high]")
            sys.exit(1)
        priority = "normal"
        args = sys.argv[2:]
        if "--priority" in args:
            idx = args.index("--priority")
            if idx + 1 < len(args):
                priority = args[idx + 1]
                args = args[:idx] + args[idx+2:]
        desc = " ".join(args).strip()

        task = router.submit(desc, priority)
        print(f"\nTask Submitted:")
        print(f"  ID:       {task.id}")
        print(f"  Agent:    {task.agent_id}")
        print(f"  Type:     {task.task_type}")
        print(f"  Priority: {task.priority}")
        print(f"  Status:   {task.status}")

    elif cmd == "queue":
        queue = router.get_queue()
        if not queue:
            print("\nQueue is empty.")
        else:
            print(f"\nPending Tasks ({len(queue)}):")
            for t in queue:
                print(f"  [{t['priority']:>8}] {t['agent_id']:>12} | {t['description'][:60]}")

    elif cmd == "stats":
        stats = router.get_stats()
        print(f"\nRouter Stats:")
        print(f"  Total Routed:  {stats.get('total_routed', 0)}")
        print(f"  Agents Active: {stats.get('agents_active', 0)}/{stats.get('agents_total', 0)}")
        print(f"  Queue Pending: {stats.get('queue_pending', 0)}")
        by_agent = stats.get("by_agent", {})
        if by_agent:
            print(f"  By Agent:")
            for agent_id, count in sorted(by_agent.items(), key=lambda x: -x[1]):
                print(f"    {agent_id:>12}: {count}")

    elif cmd == "plan":
        if len(sys.argv) < 3:
            print("Usage: python task_router.py plan <complex task description>")
            sys.exit(1)
        desc = " ".join(sys.argv[2:]).strip()
        tasks = router.plan_and_submit(desc)
        print(f"\nPlan & Submit ({len(tasks)} tasks):")
        for t in tasks:
            print(f"  [{t.priority:>8}] {t.agent_id:>12} | {t.description[:60]}")

    elif cmd == "test":
        # 快速测试
        test_cases = [
            "写一个排序算法",
            "检查系统健康度",
            "分析最近的错误日志",
            "研究 GitHub 上最新的 Agent 框架",
            "设计一个新的调度系统",
            "清理临时文件",
            "写个弹球小游戏",
            "检查安全漏洞",
            "生成项目文档",
            "写单元测试",
        ]
        print(f"\nRouting Test ({len(test_cases)} cases):\n")
        for desc in test_cases:
            r = router.route(desc)
            print(f"  {desc:30s} -> {r.agent_id:>12} ({r.task_type:>12}, {r.confidence:.0%})")
        print(f"\nAll {len(test_cases)} cases routed successfully.")

        # Planning 测试
        print(f"\n--- Planning Test ---\n")
        plan_cases = [
            "搜索 GitHub 上的 AIOS 项目，然后分析架构，最后写报告",
            "实现一个新的调度算法",
        ]
        for desc in plan_cases:
            tasks = router.plan_and_submit(desc)
            print(f"  {desc[:50]:50s} -> {len(tasks)} subtasks")
            for t in tasks:
                print(f"    [{t.priority:>8}] {t.agent_id:>12} | {t.description[:50]}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: route, submit, plan, queue, stats, test")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Adaptive Threshold - 自适应阈值

根据 Agent 特性动态调整失败阈值，让系统更智能。

核心逻辑：
1. 分析 Agent 的任务频率（高频/中频/低频）
2. 分析 Agent 的任务类型（关键/普通）
3. 动态计算失败阈值
4. 动态计算分析窗口

阈值策略：
- 高频任务 Agent（>10 次/天）：阈值 5 次，窗口 48 小时
- 中频任务 Agent（3-10 次/天）：阈值 3 次，窗口 24 小时
- 低频任务 Agent（<3 次/天）：阈值 2 次，窗口 72 小时
- 关键任务 Agent：阈值 1 次，窗口 24 小时

冷却期策略：
- 高频 Agent：冷却期 3 小时
- 中频 Agent：冷却期 6 小时
- 低频 Agent：冷却期 12 小时
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Tuple


class AdaptiveThreshold:
    """自适应阈值管理器"""

    # 默认阈值（中频 Agent）
    DEFAULT_FAILURE_THRESHOLD = 3
    DEFAULT_ANALYSIS_WINDOW_HOURS = 24
    DEFAULT_COOLDOWN_HOURS = 6

    # 任务频率分类（次/天）
    HIGH_FREQUENCY_THRESHOLD = 10  # >10 次/天
    LOW_FREQUENCY_THRESHOLD = 3    # <3 次/天

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path.home() / ".self-improving-loop"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.data_dir / "adaptive_thresholds.json"
        self.config = self._load_config()

    def get_threshold(self, agent_id: str, task_history: list) -> Tuple[int, int, int]:
        """
        获取 Agent 的自适应阈值

        Args:
            agent_id: Agent ID
            task_history: 任务历史（最近的追踪记录）

        Returns:
            (失败阈值, 分析窗口小时数, 冷却期小时数)
        """
        # 检查是否有手动配置
        if agent_id in self.config:
            manual_config = self.config[agent_id]
            return (
                manual_config.get("failure_threshold", self.DEFAULT_FAILURE_THRESHOLD),
                manual_config.get("analysis_window_hours", self.DEFAULT_ANALYSIS_WINDOW_HOURS),
                manual_config.get("cooldown_hours", self.DEFAULT_COOLDOWN_HOURS)
            )

        # 自动计算
        frequency = self._calculate_frequency(task_history)
        is_critical = self._is_critical_agent(agent_id)

        if is_critical:
            # 关键任务：低阈值，快速响应
            return (1, 24, 6)

        elif frequency == "high":
            # 高频任务：高阈值，避免误触发
            return (5, 48, 3)

        elif frequency == "low":
            # 低频任务：低阈值，长窗口
            return (2, 72, 12)

        else:
            # 中频任务：默认值
            return (
                self.DEFAULT_FAILURE_THRESHOLD,
                self.DEFAULT_ANALYSIS_WINDOW_HOURS,
                self.DEFAULT_COOLDOWN_HOURS
            )

    def _calculate_frequency(self, task_history: list) -> str:
        """
        计算任务频率

        Returns:
            "high" | "medium" | "low"
        """
        if not task_history:
            return "medium"

        # 计算最近 24 小时的任务数
        now = datetime.now()
        cutoff = now - timedelta(hours=24)

        recent_tasks = [
            t for t in task_history
            if datetime.fromisoformat(t.get("start_time", "")) > cutoff
        ]

        tasks_per_day = len(recent_tasks)

        if tasks_per_day > self.HIGH_FREQUENCY_THRESHOLD:
            return "high"
        elif tasks_per_day < self.LOW_FREQUENCY_THRESHOLD:
            return "low"
        else:
            return "medium"

    def _is_critical_agent(self, agent_id: str) -> bool:
        """
        判断是否是关键任务 Agent

        关键任务特征：
        - 名称包含 "critical", "prod", "production"
        - 手动标记为关键
        """
        critical_keywords = ["critical", "prod", "production", "monitor"]

        # 检查名称
        if any(keyword in agent_id.lower() for keyword in critical_keywords):
            return True

        # 检查手动配置
        if agent_id in self.config:
            return self.config[agent_id].get("is_critical", False)

        return False

    def set_manual_threshold(
        self,
        agent_id: str,
        failure_threshold: int = None,
        analysis_window_hours: int = None,
        cooldown_hours: int = None,
        is_critical: bool = None
    ):
        """
        手动设置 Agent 阈值

        Args:
            agent_id: Agent ID
            failure_threshold: 失败阈值
            analysis_window_hours: 分析窗口（小时）
            cooldown_hours: 冷却期（小时）
            is_critical: 是否关键任务
        """
        if agent_id not in self.config:
            self.config[agent_id] = {}

        if failure_threshold is not None:
            self.config[agent_id]["failure_threshold"] = failure_threshold

        if analysis_window_hours is not None:
            self.config[agent_id]["analysis_window_hours"] = analysis_window_hours

        if cooldown_hours is not None:
            self.config[agent_id]["cooldown_hours"] = cooldown_hours

        if is_critical is not None:
            self.config[agent_id]["is_critical"] = is_critical

        self._save_config()

    def get_agent_profile(self, agent_id: str, task_history: list) -> Dict:
        """
        获取 Agent 的完整配置文件

        Returns:
            {
                "agent_id": str,
                "frequency": "high" | "medium" | "low",
                "is_critical": bool,
                "failure_threshold": int,
                "analysis_window_hours": int,
                "cooldown_hours": int,
                "tasks_per_day": int,
                "source": "manual" | "auto"
            }
        """
        frequency = self._calculate_frequency(task_history)
        is_critical = self._is_critical_agent(agent_id)
        threshold, window, cooldown = self.get_threshold(agent_id, task_history)

        # 计算任务频率
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        recent_tasks = [
            t for t in task_history
            if datetime.fromisoformat(t.get("start_time", "")) > cutoff
        ]
        tasks_per_day = len(recent_tasks)

        return {
            "agent_id": agent_id,
            "frequency": frequency,
            "is_critical": is_critical,
            "failure_threshold": threshold,
            "analysis_window_hours": window,
            "cooldown_hours": cooldown,
            "tasks_per_day": tasks_per_day,
            "source": "manual" if agent_id in self.config else "auto"
        }

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if THRESHOLD_CONFIG_FILE.exists():
            with open(THRESHOLD_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_config(self):
        """保存配置文件"""
        THRESHOLD_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(THRESHOLD_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)


# ============================================================================
# 使用示例
# ============================================================================

def example_usage():
    """使用示例"""
    adaptive = AdaptiveThreshold()

    # 模拟任务历史
    now = datetime.now()

    # 1. 高频 Agent（15 次/天）
    high_freq_history = [
        {"start_time": (now - timedelta(hours=i)).isoformat()}
        for i in range(15)
    ]

    threshold, window, cooldown = adaptive.get_threshold("agent-high-freq", high_freq_history)
    print(f"高频 Agent:")
    print(f"  失败阈值: {threshold}")
    print(f"  分析窗口: {window} 小时")
    print(f"  冷却期: {cooldown} 小时")

    # 2. 低频 Agent（2 次/天）
    low_freq_history = [
        {"start_time": (now - timedelta(hours=i*12)).isoformat()}
        for i in range(2)
    ]

    threshold, window, cooldown = adaptive.get_threshold("agent-low-freq", low_freq_history)
    print(f"\n低频 Agent:")
    print(f"  失败阈值: {threshold}")
    print(f"  分析窗口: {window} 小时")
    print(f"  冷却期: {cooldown} 小时")

    # 3. 关键 Agent
    threshold, window, cooldown = adaptive.get_threshold("agent-critical-monitor", [])
    print(f"\n关键 Agent:")
    print(f"  失败阈值: {threshold}")
    print(f"  分析窗口: {window} 小时")
    print(f"  冷却期: {cooldown} 小时")

    # 4. 手动配置
    adaptive.set_manual_threshold(
        "agent-custom",
        failure_threshold=10,
        analysis_window_hours=12,
        cooldown_hours=1,
        is_critical=True
    )

    threshold, window, cooldown = adaptive.get_threshold("agent-custom", [])
    print(f"\n手动配置 Agent:")
    print(f"  失败阈值: {threshold}")
    print(f"  分析窗口: {window} 小时")
    print(f"  冷却期: {cooldown} 小时")

    # 5. 查看完整配置
    profile = adaptive.get_agent_profile("agent-high-freq", high_freq_history)
    print(f"\nAgent 配置文件:")
    print(f"  频率: {profile['frequency']}")
    print(f"  任务数/天: {profile['tasks_per_day']}")
    print(f"  是否关键: {profile['is_critical']}")
    print(f"  配置来源: {profile['source']}")


if __name__ == "__main__":
    example_usage()

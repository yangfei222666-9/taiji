# aios/agent_system/self_evolution_agent.py - 自我进化 Agent
"""
Self-Evolution Agent
一个能够自我进化的 Agent

核心能力：
1. 自我观察 - 分析自己的执行历史
2. 自我诊断 - 识别自己的问题
3. 自我优化 - 生成改进方案
4. 自我验证 - 测试改进效果
5. 自我学习 - 从经验中学习
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aios.agent_system.config_center import agent_system_root


class SelfEvolutionAgent:
    """自我进化 Agent"""

    def __init__(self):
        self.workspace = agent_system_root()
        self.data_dir = self.workspace / "data"
        self.evolution_dir = self.data_dir / "evolution"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)

        # 自我状态
        self.agent_id = "self_evolution_agent"
        self.version = "1.0.0"
        self.evolution_count = 0
        self.performance_history = []

        # 进化配置
        self.config = {
            "min_samples": 10,  # 最少样本数
            "success_rate_threshold": 0.7,  # 成功率阈值
            "evolution_cooldown_hours": 6,  # 进化冷却时间
            "max_evolutions_per_day": 3,  # 每天最多进化次数
        }

        self.log_file = self.workspace / "self_evolution.log"

    def log(self, message, level="INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

        try:
            print(log_entry.strip())
        except UnicodeEncodeError:
            print(log_entry.encode("ascii", "ignore").decode("ascii").strip())

    def observe_self(self) -> Dict:
        """自我观察 - 分析自己的执行历史"""
        self.log("=== 自我观察 ===")

        # 读取自己的执行记录
        traces_dir = self.data_dir / "traces"
        if not traces_dir.exists():
            self.log("没有执行记录", "WARN")
            return {"samples": 0}

        # 分析最近的执行
        recent_traces = []
        cutoff = datetime.now() - timedelta(days=7)

        for trace_file in traces_dir.glob("*.json"):
            try:
                with open(trace_file, "r", encoding="utf-8") as f:
                    trace = json.load(f)

                # 只分析自己的记录
                if trace.get("agent_id") == self.agent_id:
                    trace_time = datetime.fromisoformat(trace.get("timestamp", "2000-01-01"))
                    if trace_time > cutoff:
                        recent_traces.append(trace)
            except:
                continue

        # 统计
        total = len(recent_traces)
        success = sum(1 for t in recent_traces if t.get("success", False))
        success_rate = success / total if total > 0 else 0

        avg_duration = (
            sum(t.get("duration", 0) for t in recent_traces) / total if total > 0 else 0
        )

        # 错误分析
        errors = [t.get("error") for t in recent_traces if t.get("error")]
        error_patterns = {}
        for error in errors:
            error_type = error.split(":")[0] if error else "unknown"
            error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

        observation = {
            "samples": total,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "error_patterns": error_patterns,
            "recent_traces": recent_traces[-10:],  # 最近10条
        }

        self.log(f"观察结果: {total} 个样本, 成功率 {success_rate:.2%}")
        return observation

    def diagnose_self(self, observation: Dict) -> List[Dict]:
        """自我诊断 - 识别问题"""
        self.log("=== 自我诊断 ===")

        issues = []

        # 1. 样本数不足
        if observation["samples"] < self.config["min_samples"]:
            issues.append(
                {
                    "type": "insufficient_data",
                    "severity": "low",
                    "description": f"样本数不足: {observation['samples']} < {self.config['min_samples']}",
                    "recommendation": "继续收集数据",
                }
            )

        # 2. 成功率低
        if observation["success_rate"] < self.config["success_rate_threshold"]:
            issues.append(
                {
                    "type": "low_success_rate",
                    "severity": "high",
                    "description": f"成功率过低: {observation['success_rate']:.2%}",
                    "recommendation": "需要优化策略",
                }
            )

        # 3. 执行时间长
        if observation["avg_duration"] > 60:
            issues.append(
                {
                    "type": "high_latency",
                    "severity": "medium",
                    "description": f"平均耗时过长: {observation['avg_duration']:.1f}s",
                    "recommendation": "优化性能",
                }
            )

        # 4. 频繁错误
        for error_type, count in observation["error_patterns"].items():
            if count >= 3:
                issues.append(
                    {
                        "type": "frequent_error",
                        "severity": "high",
                        "description": f"频繁错误: {error_type} ({count}次)",
                        "recommendation": f"修复 {error_type} 错误",
                    }
                )

        self.log(f"诊断结果: 发现 {len(issues)} 个问题")
        for issue in issues:
            self.log(f"  - [{issue['severity']}] {issue['description']}")

        return issues

    def generate_evolution_plan(self, issues: List[Dict]) -> Optional[Dict]:
        """生成进化方案"""
        self.log("=== 生成进化方案 ===")

        if not issues:
            self.log("没有需要改进的问题")
            return None

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        issues.sort(key=lambda x: severity_order[x["severity"]])

        # 选择最严重的问题
        primary_issue = issues[0]

        # 生成方案
        plan = {
            "version": f"{self.version} → {self._next_version()}",
            "target_issue": primary_issue,
            "changes": [],
            "expected_improvement": {},
            "risk": "low",
        }

        # 根据问题类型生成具体改进
        if primary_issue["type"] == "low_success_rate":
            plan["changes"].append(
                {
                    "type": "increase_thinking",
                    "description": "提升思考深度",
                    "from": "off",
                    "to": "medium",
                }
            )
            plan["expected_improvement"] = {"success_rate": "+10%"}

        elif primary_issue["type"] == "high_latency":
            plan["changes"].append(
                {
                    "type": "optimize_performance",
                    "description": "优化执行流程",
                    "details": "减少不必要的步骤",
                }
            )
            plan["expected_improvement"] = {"avg_duration": "-20%"}

        elif primary_issue["type"] == "frequent_error":
            plan["changes"].append(
                {
                    "type": "add_error_handling",
                    "description": "添加错误处理",
                    "error_type": primary_issue["description"].split(":")[1].strip(),
                }
            )
            plan["expected_improvement"] = {"error_rate": "-50%"}

        self.log(f"生成方案: {len(plan['changes'])} 个改进")
        return plan

    def apply_evolution(self, plan: Dict) -> bool:
        """应用进化方案"""
        self.log("=== 应用进化 ===")

        try:
            # 记录进化历史
            evolution_record = {
                "timestamp": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "version_from": self.version,
                "version_to": self._next_version(),
                "plan": plan,
                "status": "applied",
            }

            history_file = self.evolution_dir / "evolution_history.jsonl"
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(evolution_record, ensure_ascii=False) + "\n")

            # 更新版本
            self.version = self._next_version()
            self.evolution_count += 1

            self.log(f"进化成功: {evolution_record['version_from']} → {evolution_record['version_to']}")
            return True

        except Exception as e:
            self.log(f"进化失败: {e}", "ERROR")
            return False

    def verify_evolution(self) -> Dict:
        """验证进化效果"""
        self.log("=== 验证进化 ===")

        # 等待新数据
        self.log("等待新数据收集...")

        # 重新观察
        new_observation = self.observe_self()

        # 对比改进
        improvement = {
            "success_rate_change": 0,  # 需要对比历史数据
            "duration_change": 0,
            "error_reduction": 0,
        }

        self.log(f"验证完成: 成功率 {new_observation['success_rate']:.2%}")
        return improvement

    def learn_from_experience(self):
        """从经验中学习"""
        self.log("=== 从经验中学习 ===")

        # 分析进化历史
        history_file = self.evolution_dir / "evolution_history.jsonl"
        if not history_file.exists():
            self.log("没有进化历史")
            return

        # 读取历史
        evolutions = []
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    evolutions.append(json.loads(line))

        # 分析哪些进化有效
        successful_patterns = []
        failed_patterns = []

        for evo in evolutions:
            if evo.get("status") == "applied":
                # 这里需要对比进化前后的效果
                # 简化版：假设都成功
                successful_patterns.append(evo["plan"]["changes"])

        self.log(f"学习完成: {len(successful_patterns)} 个成功模式")

    def run_evolution_cycle(self):
        """运行一个完整的进化周期"""
        self.log("=" * 60)
        self.log("开始自我进化周期")
        self.log("=" * 60)

        # 1. 自我观察
        observation = self.observe_self()

        # 2. 自我诊断
        issues = self.diagnose_self(observation)

        # 3. 生成方案
        plan = self.generate_evolution_plan(issues)

        if plan:
            # 4. 应用进化
            success = self.apply_evolution(plan)

            if success:
                # 5. 验证效果
                improvement = self.verify_evolution()

                # 6. 学习经验
                self.learn_from_experience()

                self.log("=" * 60)
                self.log("进化周期完成")
                self.log("=" * 60)
                return True
        else:
            self.log("无需进化")
            return False

    def _next_version(self) -> str:
        """计算下一个版本号"""
        major, minor, patch = map(int, self.version.split("."))
        return f"{major}.{minor}.{patch + 1}"


def main():
    agent = SelfEvolutionAgent()
    agent.run_evolution_cycle()


if __name__ == "__main__":
    main()

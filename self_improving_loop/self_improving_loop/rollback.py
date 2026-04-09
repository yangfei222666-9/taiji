"""
Auto Rollback - 自动回滚机制

当改进后效果变差时，自动回滚到上一个配置。

核心逻辑：
1. 改进前：备份当前配置
2. 改进后：记录基线指标（成功率、平均耗时）
3. 持续监控：对比改进前后的表现
4. 效果变差：自动回滚 + 标记改进失败
5. 效果变好：确认改进成功

判断标准：
- 成功率下降 >10%
- 平均耗时增加 >20%
- 连续失败 ≥5 次

验证窗口：改进后 10 次任务
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class AutoRollback:
    """自动回滚管理器"""

    # 回滚阈值
    SUCCESS_RATE_DROP_THRESHOLD = 0.10  # 成功率下降 >10%
    LATENCY_INCREASE_THRESHOLD = 0.20   # 耗时增加 >20%
    CONSECUTIVE_FAILURES_THRESHOLD = 5  # 连续失败 ≥5 次

    # 验证窗口
    VERIFICATION_WINDOW = 10  # 改进后 10 次任务

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path.home() / ".self-improving-loop" / "rollback"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.backup_file = self.data_dir / "config_backups.jsonl"
        self.rollback_log = self.data_dir / "rollback_history.jsonl"

    def backup_config(self, agent_id: str, config: Dict, improvement_id: str) -> str:
        """
        备份配置

        Args:
            agent_id: Agent ID
            config: 当前配置
            improvement_id: 改进 ID

        Returns:
            备份 ID
        """
        backup_id = f"{agent_id}_{int(time.time())}"

        backup = {
            "backup_id": backup_id,
            "agent_id": agent_id,
            "improvement_id": improvement_id,
            "config": config,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.backup_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(backup, ensure_ascii=False) + "\n")

        return backup_id

    def should_rollback(
        self,
        agent_id: str,
        improvement_id: str,
        before_metrics: Dict,
        after_metrics: Dict
    ) -> tuple[bool, str]:
        """
        判断是否应该回滚

        Args:
            agent_id: Agent ID
            improvement_id: 改进 ID
            before_metrics: 改进前指标
            after_metrics: 改进后指标

        Returns:
            (是否回滚, 原因)
        """
        # 检查成功率
        before_success_rate = before_metrics.get("success_rate", 0)
        after_success_rate = after_metrics.get("success_rate", 0)

        if before_success_rate > 0:
            success_rate_drop = before_success_rate - after_success_rate
            if success_rate_drop > self.SUCCESS_RATE_DROP_THRESHOLD:
                return (
                    True,
                    f"成功率下降 {success_rate_drop:.1%} (从 {before_success_rate:.1%} 到 {after_success_rate:.1%})"
                )

        # 检查平均耗时
        before_latency = before_metrics.get("avg_duration_sec", 0)
        after_latency = after_metrics.get("avg_duration_sec", 0)

        if before_latency > 0:
            latency_increase = (after_latency - before_latency) / before_latency
            if latency_increase > self.LATENCY_INCREASE_THRESHOLD:
                return (
                    True,
                    f"平均耗时增加 {latency_increase:.1%} (从 {before_latency:.1f}s 到 {after_latency:.1f}s)"
                )

        # 检查连续失败
        consecutive_failures = after_metrics.get("consecutive_failures", 0)
        if consecutive_failures >= self.CONSECUTIVE_FAILURES_THRESHOLD:
            return (
                True,
                f"连续失败 {consecutive_failures} 次"
            )

        return (False, "")

    def rollback(self, agent_id: str, backup_id: str) -> Dict:
        """
        执行回滚

        Args:
            agent_id: Agent ID
            backup_id: 备份 ID

        Returns:
            回滚结果
        """
        # 查找备份
        backup = self._find_backup(backup_id)
        if not backup:
            return {
                "success": False,
                "error": f"Backup not found: {backup_id}"
            }

        # 恢复配置
        config = backup["config"]
        improvement_id = backup["improvement_id"]

        try:
            # 这里应该调用 AgentManager 恢复配置
            # 简化版：只记录回滚日志
            rollback_entry = {
                "rollback_id": f"rollback_{int(time.time())}",
                "agent_id": agent_id,
                "backup_id": backup_id,
                "improvement_id": improvement_id,
                "timestamp": datetime.now().isoformat(),
                "config_restored": config,
            }

            with open(self.rollback_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(rollback_entry, ensure_ascii=False) + "\n")

            return {
                "success": True,
                "backup_id": backup_id,
                "improvement_id": improvement_id,
                "config": config,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _find_backup(self, backup_id: str) -> Optional[Dict]:
        """查找备份"""
        if not self.backup_file.exists():
            return None

        with open(self.backup_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    backup = json.loads(line)
                    if backup["backup_id"] == backup_id:
                        return backup

        return None

    def get_rollback_history(self, agent_id: str = None) -> List[Dict]:
        """获取回滚历史"""
        if not self.rollback_log.exists():
            return []

        history = []
        with open(self.rollback_log, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if agent_id is None or entry["agent_id"] == agent_id:
                        history.append(entry)

        return history

    def get_stats(self) -> Dict:
        """获取回滚统计"""
        history = self.get_rollback_history()

        agents_rolled_back = set(entry["agent_id"] for entry in history)

        return {
            "total_rollbacks": len(history),
            "agents_rolled_back": len(agents_rolled_back),
            "agents": list(agents_rolled_back),
        }


# ============================================================================
# 使用示例
# ============================================================================

def example_usage():
    """使用示例"""
    rollback = AutoRollback()

    # 1. 改进前备份配置
    agent_id = "coder-001"
    config = {
        "timeout": 30,
        "retry": 3,
        "priority": 1.0,
    }
    improvement_id = "improvement_001"

    backup_id = rollback.backup_config(agent_id, config, improvement_id)
    print(f"备份配置: {backup_id}")

    # 2. 改进后监控指标
    before_metrics = {
        "success_rate": 0.80,
        "avg_duration_sec": 10.0,
    }

    after_metrics = {
        "success_rate": 0.65,  # 下降 15%
        "avg_duration_sec": 12.0,
    }

    # 3. 判断是否回滚
    should_rollback, reason = rollback.should_rollback(
        agent_id, improvement_id, before_metrics, after_metrics
    )

    if should_rollback:
        print(f"需要回滚: {reason}")

        # 4. 执行回滚
        result = rollback.rollback(agent_id, backup_id)
        if result["success"]:
            print(f"回滚成功: {result['backup_id']}")
        else:
            print(f"回滚失败: {result['error']}")
    else:
        print("改进效果良好，无需回滚")

    # 5. 查看统计
    stats = rollback.get_stats()
    print(f"\n回滚统计:")
    print(f"  总回滚次数: {stats['total_rollbacks']}")
    print(f"  回滚 Agent 数: {stats['agents_rolled_back']}")


if __name__ == "__main__":
    example_usage()

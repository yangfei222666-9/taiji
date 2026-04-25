"""
AIOS Agent Evolution System - Phase 1
Agent 鑷富杩涘寲绯荤粺

鏍稿績鍔熻兘锛?
1. 浠诲姟鎵ц杩借釜
2. 澶辫触鍒嗘瀽鍜屾敼杩涘缓璁?
3. Prompt 鑷姩浼樺寲
4. 杩涘寲鍘嗗彶璁板綍
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


class AgentEvolution:
    """Agent 杩涘寲寮曟搸"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path.home() / ".openclaw" / "workspace" / "aios" / "agent_system" / "data"
        
        self.data_dir = Path(data_dir)
        self.evolution_dir = self.data_dir / "evolution"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)

        # 鏁版嵁鏂囦欢
        self.task_log_file = self.evolution_dir / "task_executions_v2.jsonl"
        self.evolution_log_file = self.evolution_dir / "evolution_history.jsonl"
        self.suggestions_file = self.evolution_dir / "improvement_suggestions.jsonl"

    def log_task_execution(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
        duration_sec: float,
        error_msg: str = None,
        context: Dict = None
    ):
        """
        璁板綍浠诲姟鎵ц缁撴灉

        Args:
            agent_id: Agent ID
            task_type: 浠诲姟绫诲瀷锛坈ode/analysis/monitor/research锛?
            success: 鏄惁鎴愬姛
            duration_sec: 鎵ц鏃堕暱
            error_msg: 閿欒淇℃伅锛堝鏋滃け璐ワ級
            context: 棰濆涓婁笅鏂囷紙宸ュ叿浣跨敤銆佹ā鍨嬭皟鐢ㄧ瓑锛?
        """
        record = {
            "timestamp": int(time.time()),
            "agent_id": agent_id,
            "task_type": task_type,
            "success": success,
            "duration_sec": duration_sec,
            "error_msg": error_msg,
            "context": context or {}
        }

        with open(self.task_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def analyze_failures(self, agent_id: str, lookback_hours: int = 24) -> Dict:
        """
        鍒嗘瀽 Agent 鐨勫け璐ユā寮?

        Args:
            agent_id: Agent ID
            lookback_hours: 鍥炴函鏃堕棿锛堝皬鏃讹級

        Returns:
            {
                'total_tasks': int,
                'failed_tasks': int,
                'failure_rate': float,
                'failure_patterns': {
                    'task_type': {'count': int, 'errors': [str]},
                    ...
                },
                'suggestions': [str]
            }
        """
        if not self.task_log_file.exists():
            return {
                "total_tasks": 0,
                "failed_tasks": 0,
                "failure_rate": 0.0,
                "failure_patterns": {},
                "suggestions": [],
            }

        cutoff_time = int(time.time()) - (lookback_hours * 3600)
        
        total_tasks = 0
        failed_tasks = 0
        failure_patterns = defaultdict(lambda: {"count": 0, "errors": []})

        with open(self.task_log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                record = json.loads(line)
                
                if record["agent_id"] != agent_id:
                    continue
                
                if record["timestamp"] < cutoff_time:
                    continue
                
                total_tasks += 1
                
                if not record["success"]:
                    failed_tasks += 1
                    task_type = record["task_type"]
                    failure_patterns[task_type]["count"] += 1
                    if record.get("error_msg"):
                        failure_patterns[task_type]["errors"].append(record["error_msg"])

        failure_rate = failed_tasks / total_tasks if total_tasks > 0 else 0.0

        # 鐢熸垚鏀硅繘寤鸿
        suggestions = self._generate_suggestions(failure_patterns, failure_rate)

        return {
            "total_tasks": total_tasks,
            "failed_tasks": failed_tasks,
            "failure_rate": failure_rate,
            "failure_patterns": dict(failure_patterns),
            "suggestions": suggestions
        }

    def _generate_suggestions(self, failure_patterns: Dict, failure_rate: float) -> List[str]:
        """鐢熸垚鏀硅繘寤鸿"""
        suggestions = []

        # High failure rate -> raise reasoning depth.
        if failure_rate > 0.3:
            suggestions.append("失败率超过 30%，建议将 thinking level 提升到 'medium' 或 'high'")

        # Repeated failures in one task type -> suggest skill or permission changes.
        for task_type, data in failure_patterns.items():
            if data["count"] >= 3:
                suggestions.append(f"{task_type} 任务失败 {data['count']} 次，建议：")
                
                if task_type == "code":
                    suggestions.append("  - 添加 'coding-agent' 技能")
                    suggestions.append("  - 确保 'exec', 'read', 'write', 'edit' 工具权限")
                
                elif task_type == "analysis":
                    suggestions.append("  - 添加数据分析相关技能")
                    suggestions.append("  - 确保 'web_search', 'web_fetch' 工具权限")
                
                elif task_type == "monitor":
                    suggestions.append("  - 添加 'system-resource-monitor' 技能")
                    suggestions.append("  - 确保 'exec' 工具权限")

        # Common error pattern analysis.
        all_errors = []
        for data in failure_patterns.values():
            all_errors.extend(data["errors"])
        
        if any("timeout" in err.lower() for err in all_errors):
            suggestions.append("检测到超时错误，建议增加任务超时时间")
        
        if any("permission" in err.lower() for err in all_errors):
            suggestions.append("检测到权限错误，建议检查工具权限配置")
        
        if any("502" in err or "rate limit" in err.lower() for err in all_errors):
            suggestions.append("检测到 API 限流，建议添加重试机制或降低请求频率")

        return suggestions

    def save_suggestion(self, agent_id: str, suggestion: Dict):
        """
        淇濆瓨鏀硅繘寤鸿

        Args:
            agent_id: Agent ID
            suggestion: {
                'type': 'prompt_update' | 'tool_permission' | 'skill_install' | 'parameter_tune',
                'description': str,
                'changes': Dict,
                'status': 'pending' | 'approved' | 'rejected' | 'applied'
            }
        """
        record = {
            "timestamp": int(time.time()),
            "agent_id": agent_id,
            **suggestion
        }

        with open(self.suggestions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_pending_suggestions(self, agent_id: str = None) -> List[Dict]:
        """鑾峰彇寰呭鏍哥殑鏀硅繘寤鸿"""
        if not self.suggestions_file.exists():
            return []

        suggestions = []
        with open(self.suggestions_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                record = json.loads(line)
                
                if agent_id and record["agent_id"] != agent_id:
                    continue
                
                if record.get("status") == "pending":
                    suggestions.append(record)

        return suggestions

    def apply_evolution(self, agent_id: str, evolution: Dict) -> bool:
        """
        搴旂敤杩涘寲鏀硅繘

        Args:
            agent_id: Agent ID
            evolution: {
                'type': str,
                'changes': Dict,
                'reason': str
            }

        Returns:
            鏄惁鎴愬姛
        """
        # 璁板綍杩涘寲鍘嗗彶
        record = {
            "timestamp": int(time.time()),
            "agent_id": agent_id,
            "evolution_type": evolution["type"],
            "changes": evolution["changes"],
            "reason": evolution.get("reason", ""),
            "applied_at": datetime.now().isoformat()
        }

        with open(self.evolution_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return True

    def get_evolution_history(self, agent_id: str, limit: int = 10) -> List[Dict]:
        """获取 Agent 的进化历史"""
        if not self.evolution_log_file.exists():
            return []

        history = []
        with open(self.evolution_log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                record = json.loads(line)
                
                if record["agent_id"] == agent_id:
                    history.append(record)

        # Sort newest first.
        history.sort(key=lambda x: x["timestamp"], reverse=True)
        return history[:limit]

    def generate_evolution_report(self, agent_id: str) -> str:
        """生成 Agent 进化报告"""
        analysis = self.analyze_failures(agent_id, lookback_hours=24)
        history = self.get_evolution_history(agent_id, limit=5)
        pending = self.get_pending_suggestions(agent_id)

        report = f"# Agent {agent_id} 进化报告\n\n"
        report += f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        report += "## [REPORT] 性能分析（最近 24 小时）\n\n"
        report += f"- 总任务数: {analysis['total_tasks']}\n"
        report += f"- 失败任务数: {analysis['failed_tasks']}\n"
        report += f"- 失败率: {analysis['failure_rate']:.1%}\n\n"

        if analysis['failure_patterns']:
            report += "## [WARN] 失败模式\n\n"
            for task_type, data in analysis['failure_patterns'].items():
                report += f"- **{task_type}**: 失败 {data['count']} 次\n"
            report += "\n"

        if analysis['suggestions']:
            report += "## [IDEA] 改进建议\n\n"
            for i, suggestion in enumerate(analysis['suggestions'], 1):
                report += f"{i}. {suggestion}\n"
            report += "\n"

        if pending:
            report += "## 待审核建议\n\n"
            for suggestion in pending:
                report += f"- **{suggestion['type']}**: {suggestion['description']}\n"
            report += "\n"

        if history:
            report += "## 进化历史（最近 5 次）\n\n"
            for record in history:
                time_str = datetime.fromtimestamp(record['timestamp']).strftime('%Y-%m-%d %H:%M')
                report += f"- **{time_str}** - {record['evolution_type']}\n"
                report += f"  原因: {record.get('reason', '')}\n"
            report += "\n"

        return report


# CLI interface.
def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m aios.agent_system.evolution <command> [args]")
        print("\nCommands:")
        print("  analyze <agent_id>     - analyze agent failure patterns")
        print("  report <agent_id>      - generate evolution report")
        print("  suggestions [agent_id] - list pending suggestions")
        print("  history <agent_id>     - list evolution history")
        return

    evolution = AgentEvolution()
    command = sys.argv[1]

    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: agent_id is required")
            return
        
        agent_id = sys.argv[2]
        analysis = evolution.analyze_failures(agent_id)
        print(json.dumps(analysis, ensure_ascii=False, indent=2))

    elif command == "report":
        if len(sys.argv) < 3:
            print("Error: agent_id is required")
            return
        
        agent_id = sys.argv[2]
        report = evolution.generate_evolution_report(agent_id)
        print(report)

    elif command == "suggestions":
        agent_id = sys.argv[2] if len(sys.argv) > 2 else None
        suggestions = evolution.get_pending_suggestions(agent_id)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))

    elif command == "history":
        if len(sys.argv) < 3:
            print("Error: agent_id is required")
            return
        
        agent_id = sys.argv[2]
        history = evolution.get_evolution_history(agent_id)
        print(json.dumps(history, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()

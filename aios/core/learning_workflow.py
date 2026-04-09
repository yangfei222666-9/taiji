"""
AIOS 自学习工作流
从每次执行中学习，持续改进系统性能

学习内容：
1. Provider 性能（哪个模型成功率高）
2. Playbook 效果（哪些规则有效）
3. 任务路由（哪种任务适合哪个 Agent）
4. 资源阈值（什么时候该触发告警）
5. 用户偏好（用户喜欢什么样的响应）
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict


class LearningWorkflow:
    """自学习工作流"""
    
    def __init__(self, workspace: Path = None):
        """
        初始化
        
        Args:
            workspace: 工作目录
        """
        if workspace is None:
            workspace = Path(__file__).parent.parent.parent
        
        self.workspace = Path(workspace)
        self.learning_dir = self.workspace / "aios" / "learning"
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        
        # 学习数据文件
        self.provider_stats_file = self.learning_dir / "provider_stats.json"
        self.playbook_stats_file = self.learning_dir / "playbook_stats.json"
        self.task_routing_file = self.learning_dir / "task_routing.json"
        self.threshold_history_file = self.learning_dir / "threshold_history.jsonl"
        self.user_feedback_file = self.learning_dir / "user_feedback.jsonl"
    
    # ========== 1. Provider 性能学习 ==========
    
    def record_provider_execution(
        self,
        provider: str,
        success: bool,
        duration: float,
        task_type: str,
        error: str = None
    ):
        """
        记录 Provider 执行结果
        
        Args:
            provider: Provider 名称
            success: 是否成功
            duration: 执行时长（秒）
            task_type: 任务类型
            error: 错误信息
        """
        stats = self._load_provider_stats()
        
        if provider not in stats:
            stats[provider] = {
                "total_executions": 0,
                "success_count": 0,
                "fail_count": 0,
                "total_duration": 0,
                "avg_duration": 0,
                "success_rate": 0,
                "by_task_type": {}
            }
        
        p = stats[provider]
        p["total_executions"] += 1
        
        if success:
            p["success_count"] += 1
        else:
            p["fail_count"] += 1
        
        p["total_duration"] += duration
        p["avg_duration"] = p["total_duration"] / p["total_executions"]
        p["success_rate"] = p["success_count"] / p["total_executions"]
        
        # 按任务类型统计
        if task_type not in p["by_task_type"]:
            p["by_task_type"][task_type] = {
                "count": 0,
                "success": 0,
                "fail": 0
            }
        
        p["by_task_type"][task_type]["count"] += 1
        if success:
            p["by_task_type"][task_type]["success"] += 1
        else:
            p["by_task_type"][task_type]["fail"] += 1
        
        self._save_provider_stats(stats)
    
    def get_best_provider(self, task_type: str = None) -> str:
        """
        获取最佳 Provider
        
        Args:
            task_type: 任务类型（可选）
        
        Returns:
            最佳 Provider 名称
        """
        stats = self._load_provider_stats()
        
        if not stats:
            return "claude-sonnet-4-6"  # 默认
        
        # 如果指定了任务类型，按任务类型选择
        if task_type:
            best_provider = None
            best_score = 0
            
            for provider, p_stats in stats.items():
                if task_type in p_stats["by_task_type"]:
                    task_stats = p_stats["by_task_type"][task_type]
                    success_rate = task_stats["success"] / task_stats["count"]
                    
                    # 综合评分：成功率 * 0.7 + 速度 * 0.3
                    speed_score = 1 / (p_stats["avg_duration"] + 1)
                    score = success_rate * 0.7 + speed_score * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_provider = provider
            
            if best_provider:
                return best_provider
        
        # 否则按整体成功率选择
        best_provider = max(stats.items(), key=lambda x: x[1]["success_rate"])
        return best_provider[0]
    
    # ========== 2. Playbook 效果学习 ==========
    
    def record_playbook_execution(
        self,
        playbook_id: str,
        success: bool,
        duration: float,
        event_type: str
    ):
        """
        记录 Playbook 执行结果
        
        Args:
            playbook_id: Playbook ID
            success: 是否成功
            duration: 执行时长
            event_type: 事件类型
        """
        stats = self._load_playbook_stats()
        
        if playbook_id not in stats:
            stats[playbook_id] = {
                "total_executions": 0,
                "success_count": 0,
                "fail_count": 0,
                "avg_duration": 0,
                "success_rate": 0,
                "last_success": None,
                "last_fail": None
            }
        
        p = stats[playbook_id]
        p["total_executions"] += 1
        
        if success:
            p["success_count"] += 1
            p["last_success"] = datetime.now().isoformat()
        else:
            p["fail_count"] += 1
            p["last_fail"] = datetime.now().isoformat()
        
        # 更新平均时长（指数移动平均）
        alpha = 0.3
        if p["avg_duration"] == 0:
            p["avg_duration"] = duration
        else:
            p["avg_duration"] = alpha * duration + (1 - alpha) * p["avg_duration"]
        
        p["success_rate"] = p["success_count"] / p["total_executions"]
        
        self._save_playbook_stats(stats)
    
    def get_playbook_recommendations(self, min_executions: int = 5) -> List[Dict]:
        """
        获取 Playbook 推荐（哪些该启用/禁用）
        
        Args:
            min_executions: 最小执行次数
        
        Returns:
            推荐列表
        """
        stats = self._load_playbook_stats()
        recommendations = []
        
        for playbook_id, p_stats in stats.items():
            if p_stats["total_executions"] < min_executions:
                continue
            
            # 成功率低于 30% → 建议禁用
            if p_stats["success_rate"] < 0.3:
                recommendations.append({
                    "playbook_id": playbook_id,
                    "action": "disable",
                    "reason": f"Low success rate: {p_stats['success_rate']:.1%}",
                    "stats": p_stats
                })
            
            # 成功率高于 80% → 建议保持启用
            elif p_stats["success_rate"] > 0.8:
                recommendations.append({
                    "playbook_id": playbook_id,
                    "action": "keep_enabled",
                    "reason": f"High success rate: {p_stats['success_rate']:.1%}",
                    "stats": p_stats
                })
        
        return recommendations
    
    # ========== 3. 任务路由学习 ==========
    
    def record_task_routing(
        self,
        task_type: str,
        agent_template: str,
        success: bool,
        duration: float
    ):
        """
        记录任务路由结果
        
        Args:
            task_type: 任务类型
            agent_template: Agent 模板
            success: 是否成功
            duration: 执行时长
        """
        routing = self._load_task_routing()
        
        if task_type not in routing:
            routing[task_type] = {}
        
        if agent_template not in routing[task_type]:
            routing[task_type][agent_template] = {
                "count": 0,
                "success": 0,
                "fail": 0,
                "avg_duration": 0
            }
        
        r = routing[task_type][agent_template]
        r["count"] += 1
        
        if success:
            r["success"] += 1
        else:
            r["fail"] += 1
        
        # 更新平均时长
        alpha = 0.3
        if r["avg_duration"] == 0:
            r["avg_duration"] = duration
        else:
            r["avg_duration"] = alpha * duration + (1 - alpha) * r["avg_duration"]
        
        self._save_task_routing(routing)
    
    def get_best_agent_template(self, task_type: str) -> str:
        """
        获取最佳 Agent 模板
        
        Args:
            task_type: 任务类型
        
        Returns:
            最佳 Agent 模板
        """
        routing = self._load_task_routing()
        
        if task_type not in routing:
            return "monitor"  # 默认
        
        # 选择成功率最高的
        best_template = max(
            routing[task_type].items(),
            key=lambda x: x[1]["success"] / x[1]["count"] if x[1]["count"] > 0 else 0
        )
        
        return best_template[0]
    
    # ========== 4. 资源阈值学习 ==========
    
    def record_threshold_event(
        self,
        resource_type: str,
        value: float,
        threshold: float,
        triggered_action: bool,
        was_necessary: bool = None
    ):
        """
        记录阈值事件
        
        Args:
            resource_type: 资源类型（cpu/memory/gpu）
            value: 实际值
            threshold: 阈值
            triggered_action: 是否触发了动作
            was_necessary: 动作是否必要（用户反馈）
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "resource_type": resource_type,
            "value": value,
            "threshold": threshold,
            "triggered_action": triggered_action,
            "was_necessary": was_necessary
        }
        
        with open(self.threshold_history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def suggest_threshold_adjustment(self, resource_type: str) -> Dict:
        """
        建议阈值调整
        
        Args:
            resource_type: 资源类型
        
        Returns:
            调整建议
        """
        if not self.threshold_history_file.exists():
            return {"suggestion": "no_data"}
        
        # 读取最近 30 天的数据
        cutoff = datetime.now() - timedelta(days=30)
        events = []
        
        with open(self.threshold_history_file, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if event["resource_type"] == resource_type:
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time >= cutoff:
                        events.append(event)
        
        if len(events) < 10:
            return {"suggestion": "insufficient_data"}
        
        # 分析误报率
        false_positives = sum(
            1 for e in events
            if e["triggered_action"] and e.get("was_necessary") == False
        )
        
        false_positive_rate = false_positives / len(events) if events else 0
        
        # 如果误报率高，建议提高阈值
        if false_positive_rate > 0.3:
            avg_value = sum(e["value"] for e in events) / len(events)
            current_threshold = events[0]["threshold"]
            suggested_threshold = avg_value * 1.1
            
            return {
                "suggestion": "increase_threshold",
                "current": current_threshold,
                "suggested": suggested_threshold,
                "reason": f"High false positive rate: {false_positive_rate:.1%}"
            }
        
        return {"suggestion": "keep_current"}
    
    # ========== 5. 用户反馈学习 ==========
    
    def record_user_feedback(
        self,
        action_id: str,
        feedback: str,
        rating: int = None,
        comment: str = None
    ):
        """
        记录用户反馈
        
        Args:
            action_id: 动作 ID
            feedback: 反馈类型（helpful/not_helpful/wrong）
            rating: 评分（1-5）
            comment: 评论
        """
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_id": action_id,
            "feedback": feedback,
            "rating": rating,
            "comment": comment
        }
        
        with open(self.user_feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
    
    # ========== 辅助方法 ==========
    
    def _load_provider_stats(self) -> Dict:
        """加载 Provider 统计"""
        if not self.provider_stats_file.exists():
            return {}
        
        with open(self.provider_stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_provider_stats(self, stats: Dict):
        """保存 Provider 统计"""
        with open(self.provider_stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    
    def _load_playbook_stats(self) -> Dict:
        """加载 Playbook 统计"""
        if not self.playbook_stats_file.exists():
            return {}
        
        with open(self.playbook_stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_playbook_stats(self, stats: Dict):
        """保存 Playbook 统计"""
        with open(self.playbook_stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    
    def _load_task_routing(self) -> Dict:
        """加载任务路由"""
        if not self.task_routing_file.exists():
            return {}
        
        with open(self.task_routing_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_task_routing(self, routing: Dict):
        """保存任务路由"""
        with open(self.task_routing_file, "w", encoding="utf-8") as f:
            json.dump(routing, f, indent=2, ensure_ascii=False)
    
    def generate_learning_report(self) -> str:
        """生成学习报告"""
        report = []
        report.append("=" * 60)
        report.append("AIOS 自学习报告")
        report.append("=" * 60)
        
        # Provider 性能
        provider_stats = self._load_provider_stats()
        if provider_stats:
            report.append("\n📊 Provider 性能:")
            for provider, stats in sorted(
                provider_stats.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True
            ):
                report.append(
                    f"  {provider}: "
                    f"成功率 {stats['success_rate']:.1%}, "
                    f"平均时长 {stats['avg_duration']:.2f}s, "
                    f"执行 {stats['total_executions']} 次"
                )
        
        # Playbook 推荐
        recommendations = self.get_playbook_recommendations()
        if recommendations:
            report.append("\n💡 Playbook 推荐:")
            for rec in recommendations[:5]:
                report.append(f"  {rec['playbook_id']}: {rec['action']} - {rec['reason']}")
        
        # 任务路由
        routing = self._load_task_routing()
        if routing:
            report.append("\n🎯 任务路由学习:")
            for task_type, agents in routing.items():
                best = max(agents.items(), key=lambda x: x[1]["success"] / x[1]["count"])
                report.append(
                    f"  {task_type} → {best[0]} "
                    f"(成功率 {best[1]['success'] / best[1]['count']:.1%})"
                )
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


# 全局单例
_global_workflow: LearningWorkflow = None


def get_learning_workflow() -> LearningWorkflow:
    """获取全局学习工作流实例"""
    global _global_workflow
    if _global_workflow is None:
        _global_workflow = LearningWorkflow()
    return _global_workflow

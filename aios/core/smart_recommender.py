"""
AIOS Smart Recommender - 智能推荐系统

基于学习数据，为用户推荐最佳操作方案。

功能：
1. 推荐最佳执行路径
2. 预测任务耗时
3. 警告潜在风险
4. 建议参数优化
"""
from typing import Dict, List, Optional, Tuple
from adaptive_learning import get_adaptive_learning, ExecutionPattern


class SmartRecommender:
    """智能推荐系统"""
    
    def __init__(self):
        self.al = get_adaptive_learning()
    
    def recommend_execution_path(
        self,
        task_type: str,
        intent_action: str,
        intent_target: str
    ) -> Optional[Dict]:
        """推荐最佳执行路径"""
        # 查找历史最佳模式
        best_pattern = self.al.get_best_pattern(task_type, intent_action, intent_target)
        
        if not best_pattern:
            return None
        
        return {
            "pattern_id": best_pattern.pattern_id,
            "agent_sequence": best_pattern.agent_sequence,
            "confidence": best_pattern.confidence,
            "avg_duration": best_pattern.avg_duration,
            "success_count": best_pattern.success_count,
            "recommendation": f"建议使用历史最佳路径（成功率 {best_pattern.confidence*100:.1f}%）",
        }
    
    def predict_duration(
        self,
        task_type: str,
        intent_action: str,
        intent_target: str,
        default_duration: float = 60.0
    ) -> Tuple[float, str]:
        """预测任务耗时"""
        best_pattern = self.al.get_best_pattern(task_type, intent_action, intent_target)
        
        if best_pattern and best_pattern.success_count >= 3:
            # 使用历史平均值
            predicted = best_pattern.avg_duration
            confidence = "高"
            reason = f"基于 {best_pattern.success_count} 次历史数据"
        else:
            # 使用默认值
            predicted = default_duration
            confidence = "低"
            reason = "历史数据不足，使用默认值"
        
        return predicted, f"预计耗时: {predicted:.1f}秒 (置信度: {confidence}, {reason})"
    
    def check_risks(self, context: Dict) -> List[Dict]:
        """检查潜在风险"""
        risks = []
        
        # 检查失败模式
        failure_pattern = self.al.should_avoid(context)
        if failure_pattern:
            risks.append({
                "level": "high" if failure_pattern.occurrence_count >= 5 else "medium",
                "type": "known_failure",
                "message": f"此操作曾失败 {failure_pattern.occurrence_count} 次",
                "error_type": failure_pattern.error_type,
                "suggestion": failure_pattern.suggested_fix or "建议谨慎操作",
            })
        
        # 检查高风险操作
        if context.get("action") == "delete":
            risks.append({
                "level": "high",
                "type": "destructive_operation",
                "message": "删除操作不可逆",
                "suggestion": "建议先备份数据",
            })
        
        # 检查资源密集型操作
        if context.get("target") == "system" and context.get("action") == "modify":
            risks.append({
                "level": "medium",
                "type": "system_modification",
                "message": "系统级修改可能影响稳定性",
                "suggestion": "建议在测试环境先验证",
            })
        
        return risks
    
    def suggest_parameters(
        self,
        task_type: str,
        current_params: Dict
    ) -> Dict[str, any]:
        """建议参数优化"""
        suggestions = {}
        
        # 基于用户偏好
        output_format = self.al.get_preference("output_format", "default")
        if output_format and "format" not in current_params:
            suggestions["format"] = output_format
        
        # 基于任务类型
        if task_type in ["analysis", "monitor"]:
            if "limit" not in current_params:
                suggestions["limit"] = 10  # 默认限制
        
        if task_type == "code":
            if "timeout" not in current_params:
                suggestions["timeout"] = 120  # 代码任务默认2分钟超时
        
        return suggestions
    
    def generate_recommendation_report(
        self,
        task_type: str,
        intent_action: str,
        intent_target: str,
        context: Dict,
        default_duration: float = 60.0
    ) -> str:
        """生成完整推荐报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("智能推荐报告")
        lines.append("=" * 60)
        lines.append("")
        
        # 1. 执行路径推荐
        lines.append("📍 执行路径推荐")
        lines.append("-" * 60)
        path_rec = self.recommend_execution_path(task_type, intent_action, intent_target)
        if path_rec:
            lines.append(f"  ✅ {path_rec['recommendation']}")
            lines.append(f"  Agent 序列: {' → '.join(path_rec['agent_sequence'])}")
            lines.append(f"  历史成功: {path_rec['success_count']}次")
        else:
            lines.append("  ℹ️ 暂无历史最佳路径，将使用默认方案")
        lines.append("")
        
        # 2. 耗时预测
        lines.append("⏱️ 耗时预测")
        lines.append("-" * 60)
        predicted_duration, duration_msg = self.predict_duration(
            task_type, intent_action, intent_target, default_duration
        )
        lines.append(f"  {duration_msg}")
        lines.append("")
        
        # 3. 风险检查
        lines.append("⚠️ 风险检查")
        lines.append("-" * 60)
        risks = self.check_risks(context)
        if risks:
            for i, risk in enumerate(risks, 1):
                level_emoji = "🔴" if risk["level"] == "high" else "🟡"
                lines.append(f"  {level_emoji} 风险 {i}: {risk['message']}")
                lines.append(f"     建议: {risk['suggestion']}")
        else:
            lines.append("  ✅ 未发现潜在风险")
        lines.append("")
        
        # 4. 参数建议
        lines.append("🔧 参数建议")
        lines.append("-" * 60)
        param_suggestions = self.suggest_parameters(task_type, context)
        if param_suggestions:
            lines.append("  建议添加以下参数:")
            for key, value in param_suggestions.items():
                lines.append(f"    {key} = {value}")
        else:
            lines.append("  ✅ 当前参数配置合理")
        lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# 测试代码
if __name__ == "__main__":
    recommender = SmartRecommender()
    
    # 测试推荐
    print("测试智能推荐系统\n")
    
    report = recommender.generate_recommendation_report(
        task_type="simple",
        intent_action="view",
        intent_target="agent",
        context={"action": "view", "target": "agent"},
        default_duration=10.0
    )
    
    print(report)

"""
AIOS Learning Analyzer - 学习数据分析器

分析学习数据，生成洞察和建议。

功能：
1. 分析成功模式趋势
2. 识别高频失败原因
3. 生成优化建议
4. 可视化学习曲线
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta

from adaptive_learning import get_adaptive_learning, ExecutionPattern, FailurePattern


class LearningAnalyzer:
    """学习数据分析器"""
    
    def __init__(self):
        self.al = get_adaptive_learning()
    
    def analyze_success_patterns(self) -> Dict:
        """分析成功模式"""
        patterns = list(self.al.success_patterns.values())
        
        if not patterns:
            return {
                "total": 0,
                "message": "暂无成功模式数据"
            }
        
        # 按成功率排序
        patterns_sorted = sorted(patterns, key=lambda p: p.confidence, reverse=True)
        
        # 统计
        total_successes = sum(p.success_count for p in patterns)
        avg_confidence = sum(p.confidence for p in patterns) / len(patterns)
        avg_duration = sum(p.avg_duration for p in patterns) / len(patterns)
        
        # 最佳模式（Top 5）
        top_patterns = patterns_sorted[:5]
        
        # 最常用模式
        most_used = max(patterns, key=lambda p: p.success_count)
        
        # 最快模式
        fastest = min(patterns, key=lambda p: p.avg_duration)
        
        return {
            "total": len(patterns),
            "total_successes": total_successes,
            "avg_confidence": avg_confidence,
            "avg_duration": avg_duration,
            "top_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "task_type": p.task_type,
                    "confidence": p.confidence,
                    "success_count": p.success_count,
                    "avg_duration": p.avg_duration,
                }
                for p in top_patterns
            ],
            "most_used": {
                "pattern_id": most_used.pattern_id,
                "success_count": most_used.success_count,
            },
            "fastest": {
                "pattern_id": fastest.pattern_id,
                "avg_duration": fastest.avg_duration,
            },
        }
    
    def analyze_failure_patterns(self) -> Dict:
        """分析失败模式"""
        patterns = list(self.al.failure_patterns.values())
        
        if not patterns:
            return {
                "total": 0,
                "message": "暂无失败模式数据"
            }
        
        # 统计错误类型
        error_types = Counter(p.error_type for p in patterns)
        
        # 高频失败（>= 3次）
        high_freq_failures = [p for p in patterns if p.occurrence_count >= 3]
        
        # 最近失败（24小时内）
        now = datetime.now().timestamp()
        recent_failures = [
            p for p in patterns
            if now - p.last_seen < 86400  # 24小时
        ]
        
        # 需要关注的失败（高频 + 最近）
        critical_failures = [
            p for p in patterns
            if p.occurrence_count >= 3 and now - p.last_seen < 86400
        ]
        
        return {
            "total": len(patterns),
            "total_failures": sum(p.occurrence_count for p in patterns),
            "error_types": dict(error_types),
            "high_freq_count": len(high_freq_failures),
            "recent_count": len(recent_failures),
            "critical_count": len(critical_failures),
            "critical_failures": [
                {
                    "pattern_id": p.pattern_id,
                    "error_type": p.error_type,
                    "error_message": p.error_message,
                    "occurrence_count": p.occurrence_count,
                    "task_description": p.task_description,
                }
                for p in critical_failures
            ],
        }
    
    def analyze_user_preferences(self) -> Dict:
        """分析用户偏好"""
        prefs = list(self.al.user_preferences.values())
        
        if not prefs:
            return {
                "total": 0,
                "message": "暂无用户偏好数据"
            }
        
        # 按类型分组
        by_type = defaultdict(list)
        for pref in prefs:
            by_type[pref.preference_type].append(pref)
        
        # 高置信度偏好（>= 0.7）
        high_confidence = [p for p in prefs if p.confidence >= 0.7]
        
        return {
            "total": len(prefs),
            "by_type": {
                ptype: len(plist)
                for ptype, plist in by_type.items()
            },
            "high_confidence_count": len(high_confidence),
            "preferences": [
                {
                    "type": p.preference_type,
                    "key": p.key,
                    "value": p.value,
                    "confidence": p.confidence,
                    "sample_count": p.sample_count,
                }
                for p in high_confidence
            ],
        }
    
    def generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 分析成功模式
        success_analysis = self.analyze_success_patterns()
        if success_analysis["total"] > 0:
            if success_analysis["avg_confidence"] < 0.8:
                recommendations.append(
                    f"💡 建议：当前平均成功率 {success_analysis['avg_confidence']*100:.1f}%，"
                    f"可以通过增加测试覆盖率来提升"
                )
        
        # 分析失败模式
        failure_analysis = self.analyze_failure_patterns()
        if failure_analysis["total"] > 0:
            if failure_analysis["critical_count"] > 0:
                recommendations.append(
                    f"⚠️ 警告：发现 {failure_analysis['critical_count']} 个高频失败模式，"
                    f"建议优先修复"
                )
            
            # 针对具体错误类型给建议
            error_types = failure_analysis.get("error_types", {})
            if "PermissionError" in error_types:
                recommendations.append(
                    "🔒 建议：检查文件权限设置，避免 PermissionError"
                )
            if "TimeoutError" in error_types:
                recommendations.append(
                    "⏱️ 建议：增加超时时间或优化任务执行效率"
                )
            if "ValueError" in error_types:
                recommendations.append(
                    "🔍 建议：加强参数验证，避免 ValueError"
                )
        
        # 分析用户偏好
        pref_analysis = self.analyze_user_preferences()
        if pref_analysis["total"] > 0:
            if pref_analysis["high_confidence_count"] > 0:
                recommendations.append(
                    f"✅ 已学习 {pref_analysis['high_confidence_count']} 个用户偏好，"
                    f"系统会自动应用"
                )
        
        # 通用建议
        if success_analysis["total"] < 10:
            recommendations.append(
                "📊 建议：继续使用系统积累更多数据，提升学习效果"
            )
        
        return recommendations
    
    def generate_report(self) -> str:
        """生成完整报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("AIOS 学习数据分析报告")
        lines.append("=" * 60)
        lines.append("")
        
        # 成功模式分析
        lines.append("📊 成功模式分析")
        lines.append("-" * 60)
        success = self.analyze_success_patterns()
        if success["total"] > 0:
            lines.append(f"  总模式数: {success['total']}")
            lines.append(f"  总成功次数: {success['total_successes']}")
            lines.append(f"  平均成功率: {success['avg_confidence']*100:.1f}%")
            lines.append(f"  平均耗时: {success['avg_duration']:.2f}秒")
            lines.append("")
            lines.append("  Top 5 最佳模式:")
            for i, p in enumerate(success['top_patterns'], 1):
                lines.append(f"    {i}. {p['pattern_id']}")
                lines.append(f"       成功率: {p['confidence']*100:.1f}% | "
                           f"使用: {p['success_count']}次 | "
                           f"耗时: {p['avg_duration']:.2f}秒")
        else:
            lines.append(f"  {success['message']}")
        lines.append("")
        
        # 失败模式分析
        lines.append("⚠️ 失败模式分析")
        lines.append("-" * 60)
        failure = self.analyze_failure_patterns()
        if failure["total"] > 0:
            lines.append(f"  总模式数: {failure['total']}")
            lines.append(f"  总失败次数: {failure['total_failures']}")
            lines.append(f"  高频失败: {failure['high_freq_count']} 个")
            lines.append(f"  最近失败: {failure['recent_count']} 个")
            lines.append(f"  需要关注: {failure['critical_count']} 个")
            lines.append("")
            if failure['critical_count'] > 0:
                lines.append("  关键失败模式:")
                for i, p in enumerate(failure['critical_failures'], 1):
                    lines.append(f"    {i}. {p['error_type']}: {p['error_message']}")
                    lines.append(f"       任务: {p['task_description']}")
                    lines.append(f"       发生: {p['occurrence_count']}次")
        else:
            lines.append(f"  {failure['message']}")
        lines.append("")
        
        # 用户偏好分析
        lines.append("👤 用户偏好分析")
        lines.append("-" * 60)
        pref = self.analyze_user_preferences()
        if pref["total"] > 0:
            lines.append(f"  总偏好数: {pref['total']}")
            lines.append(f"  高置信度: {pref['high_confidence_count']} 个")
            lines.append("")
            if pref['high_confidence_count'] > 0:
                lines.append("  已学习的偏好:")
                for i, p in enumerate(pref['preferences'], 1):
                    lines.append(f"    {i}. {p['type']}.{p['key']} = {p['value']}")
                    lines.append(f"       置信度: {p['confidence']*100:.1f}% | "
                               f"样本: {p['sample_count']}次")
        else:
            lines.append(f"  {pref['message']}")
        lines.append("")
        
        # 优化建议
        lines.append("💡 优化建议")
        lines.append("-" * 60)
        recommendations = self.generate_recommendations()
        if recommendations:
            for rec in recommendations:
                lines.append(f"  {rec}")
        else:
            lines.append("  暂无建议")
        lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# 命令行工具
if __name__ == "__main__":
    analyzer = LearningAnalyzer()
    report = analyzer.generate_report()
    print(report)

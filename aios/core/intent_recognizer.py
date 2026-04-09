"""
AIOS Intent Recognizer - 意图识别与风险评估

自动识别用户意图，评估风险等级，决定是否需要确认。

风险等级：
- low: 只读操作，无副作用，自动执行
- medium: 有副作用但可回滚，自动执行
- high: 不可逆操作，需要确认

示例：
- "查看日志" → low, 自动执行
- "清理临时文件" → medium, 自动执行
- "删除数据库" → high, 需要确认
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Intent:
    """意图识别结果"""
    action: str  # 动作类型（view/execute/modify/delete）
    target: str  # 目标对象（file/agent/task/system）
    risk: str  # 风险等级（low/medium/high）
    confidence: float  # 置信度（0-1）
    params: Dict  # 推断的参数
    auto_execute: bool  # 是否自动执行


class IntentRecognizer:
    """意图识别器"""
    
    # 动作关键词映射（扩展版）
    ACTION_KEYWORDS = {
        "view": [
            "查看", "看", "显示", "列出", "检查", "分析", "统计",
            "查询", "获取", "读取", "浏览", "预览", "监控"
        ],
        "execute": [
            "执行", "运行", "启动", "开始", "触发", "调用",
            "处理", "操作", "进行", "实施", "完成"
        ],
        "modify": [
            "修改", "更新", "优化", "调整", "配置", "设置",
            "改进", "提升", "增强", "变更", "编辑", "重构"
        ],
        "delete": [
            "删除", "清理", "移除", "卸载", "关闭", "停止",
            "清除", "擦除", "取消", "终止"
        ],
    }
    
    # 目标对象关键词（扩展版）
    TARGET_KEYWORDS = {
        "file": [
            "文件", "日志", "配置", "代码", "脚本",
            "文档", "数据", "备份", "临时文件"
        ],
        "agent": [
            "agent", "代理", "任务", "工作", "job",
            "队列", "执行", "进程"
        ],
        "task": [
            "任务", "队列", "job", "工作流", "流程"
        ],
        "system": [
            "系统", "服务器", "资源", "性能", "健康",
            "cpu", "内存", "磁盘", "网络", "环境"
        ],
    }
    
    # 风险评估规则
    RISK_RULES = {
        ("view", "*"): "low",
        ("execute", "agent"): "low",
        ("execute", "task"): "low",
        ("modify", "file"): "medium",
        ("modify", "agent"): "medium",
        ("modify", "system"): "medium",
        ("delete", "file"): "high",
        ("delete", "agent"): "high",
        ("delete", "task"): "medium",
        ("delete", "system"): "high",
    }
    
    def recognize(self, text: str) -> Intent:
        """
        识别用户意图
        
        Args:
            text: 用户输入文本
            
        Returns:
            Intent 对象
        """
        text = text.lower().strip()
        
        # 1. 识别动作
        action, action_confidence = self._recognize_action(text)
        
        # 2. 识别目标
        target, target_confidence = self._recognize_target(text)
        
        # 3. 评估风险
        risk = self._assess_risk(action, target)
        
        # 4. 推断参数
        params = self._infer_params(text, action, target)
        
        # 5. 决定是否自动执行
        confidence = (action_confidence + target_confidence) / 2
        # 低风险：置信度 > 0.3 即可自动执行
        # 中等风险：置信度 > 0.6 才自动执行
        # 高风险：永远需要确认
        if risk == "low":
            auto_execute = confidence > 0.3
        elif risk == "medium":
            auto_execute = confidence > 0.6
        else:
            auto_execute = False
        
        return Intent(
            action=action,
            target=target,
            risk=risk,
            confidence=confidence,
            params=params,
            auto_execute=auto_execute,
        )
    
    def _recognize_action(self, text: str) -> Tuple[str, float]:
        """识别动作类型"""
        scores = {}
        
        for action, keywords in self.ACTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[action] = score
        
        if not scores:
            return "execute", 0.5  # 默认为执行
        
        # 选择得分最高的动作
        action = max(scores, key=scores.get)
        confidence = min(scores[action] / 3, 1.0)  # 归一化到 0-1
        
        return action, confidence
    
    def _recognize_target(self, text: str) -> Tuple[str, float]:
        """识别目标对象"""
        scores = {}
        
        for target, keywords in self.TARGET_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[target] = score
        
        if not scores:
            return "system", 0.5  # 默认为系统
        
        # 选择得分最高的目标
        target = max(scores, key=scores.get)
        confidence = min(scores[target] / 2, 1.0)
        
        return target, confidence
    
    def _assess_risk(self, action: str, target: str) -> str:
        """评估风险等级"""
        # 精确匹配
        key = (action, target)
        if key in self.RISK_RULES:
            return self.RISK_RULES[key]
        
        # 通配符匹配
        wildcard_key = (action, "*")
        if wildcard_key in self.RISK_RULES:
            return self.RISK_RULES[wildcard_key]
        
        # 默认中等风险
        return "medium"
    
    def _infer_params(self, text: str, action: str, target: str) -> Dict:
        """推断参数（增强版）"""
        params = {}
        
        # 1. 推断时间范围
        if "最近" in text or "今天" in text or "24小时" in text or "24h" in text:
            params["time_range"] = "today"
        elif "昨天" in text:
            params["time_range"] = "yesterday"
        elif "本周" in text or "这周" in text or "7天" in text:
            params["time_range"] = "week"
        elif "本月" in text or "这个月" in text or "30天" in text:
            params["time_range"] = "month"
        elif "最近一小时" in text or "1小时" in text or "1h" in text:
            params["time_range"] = "hour"
        
        # 2. 推断数量限制
        limit_match = re.search(r'(\d+)\s*(个|条|项|次)', text)
        if limit_match:
            params["limit"] = int(limit_match.group(1))
        elif "所有" in text or "全部" in text:
            params["limit"] = None  # 无限制
        elif "前" in text and "个" in text:
            # "前5个" 这种格式
            limit_match2 = re.search(r'前\s*(\d+)\s*个', text)
            if limit_match2:
                params["limit"] = int(limit_match2.group(1))
        
        # 3. 推断优先级
        if "重要" in text or "紧急" in text or "高优先级" in text or "urgent" in text:
            params["priority"] = "high"
        elif "低优先级" in text or "不急" in text:
            params["priority"] = "low"
        else:
            params["priority"] = "normal"
        
        # 4. 推断状态
        if "失败" in text or "错误" in text or "failed" in text:
            params["status"] = "failed"
        elif "成功" in text or "完成" in text or "completed" in text:
            params["status"] = "completed"
        elif "待处理" in text or "等待" in text or "pending" in text:
            params["status"] = "pending"
        elif "运行中" in text or "执行中" in text or "running" in text:
            params["status"] = "running"
        
        # 5. 推断排序方式
        if "最新" in text or "最近" in text:
            params["sort"] = "desc"
        elif "最旧" in text or "最早" in text:
            params["sort"] = "asc"
        
        # 6. 推断输出格式
        if "详细" in text or "完整" in text:
            params["format"] = "detailed"
        elif "简洁" in text or "简单" in text:
            params["format"] = "brief"
        
        # 7. 推断目标范围
        if "所有" in text or "全部" in text:
            params["scope"] = "all"
        elif "当前" in text or "这个" in text:
            params["scope"] = "current"
        
        # 8. 推断操作模式
        if "强制" in text or "force" in text:
            params["force"] = True
        if "递归" in text or "recursive" in text:
            params["recursive"] = True
        if "备份" in text or "backup" in text:
            params["backup"] = True
        
        return params


# 全局实例
_recognizer = IntentRecognizer()


def recognize_intent(text: str) -> Intent:
    """便捷函数：识别意图"""
    return _recognizer.recognize(text)


# 测试代码
if __name__ == "__main__":
    test_cases = [
        "查看 Agent 执行情况",
        "清理临时文件",
        "删除失败的任务",
        "执行最近 5 个任务",
        "优化系统性能",
        "分析最近 24 小时的日志",
    ]
    
    print("Intent Recognition Test\n" + "=" * 60)
    
    for text in test_cases:
        intent = recognize_intent(text)
        print(f"\n输入: {text}")
        print(f"  动作: {intent.action}")
        print(f"  目标: {intent.target}")
        print(f"  风险: {intent.risk}")
        print(f"  置信度: {intent.confidence:.2f}")
        print(f"  参数: {intent.params}")
        print(f"  自动执行: {'✅ 是' if intent.auto_execute else '❌ 否（需确认）'}")

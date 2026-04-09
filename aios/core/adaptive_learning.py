"""
AIOS Adaptive Learning - 自适应学习系统

Phase 2: 让系统根据历史数据自动调整策略

功能：
1. 成功模式学习 - 记录高成功率的执行路径
2. 失败模式避免 - 自动避免重复错误
3. 用户偏好学习 - 学习用户习惯

数据结构：
- success_patterns.jsonl - 成功模式
- failure_patterns.jsonl - 失败模式
- user_preferences.json - 用户偏好
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ExecutionPattern:
    """执行模式"""
    pattern_id: str
    task_type: str  # 任务类型
    intent_action: str  # 意图动作
    intent_target: str  # 意图目标
    agent_sequence: List[str]  # Agent 执行序列
    success_count: int  # 成功次数
    failure_count: int  # 失败次数
    avg_duration: float  # 平均耗时
    last_used: float  # 最后使用时间
    confidence: float  # 置信度（成功率）


@dataclass
class FailurePattern:
    """失败模式"""
    pattern_id: str
    task_description: str
    error_type: str  # 错误类型
    error_message: str  # 错误信息
    context: Dict  # 上下文（参数、环境等）
    occurrence_count: int  # 发生次数
    first_seen: float  # 首次发现
    last_seen: float  # 最后发现
    suggested_fix: Optional[str]  # 建议修复


@dataclass
class UserPreference:
    """用户偏好"""
    preference_type: str  # 偏好类型
    key: str  # 偏好键
    value: any  # 偏好值
    confidence: float  # 置信度
    sample_count: int  # 样本数量
    last_updated: float  # 最后更新


class AdaptiveLearning:
    """自适应学习系统"""
    
    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent.parent / "agent_system" / "learning_data"
        
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.success_patterns_file = self.data_dir / "success_patterns.jsonl"
        self.failure_patterns_file = self.data_dir / "failure_patterns.jsonl"
        self.user_preferences_file = self.data_dir / "user_preferences.json"
        
        # 内存缓存
        self.success_patterns: Dict[str, ExecutionPattern] = {}
        self.failure_patterns: Dict[str, FailurePattern] = {}
        self.user_preferences: Dict[str, UserPreference] = {}
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载学习数据"""
        # 加载成功模式（只保留最新的）
        if self.success_patterns_file.exists():
            with open(self.success_patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        pattern = ExecutionPattern(**data)
                        # 覆盖旧数据，保留最新
                        self.success_patterns[pattern.pattern_id] = pattern
        
        # 加载失败模式（只保留最新的）
        if self.failure_patterns_file.exists():
            with open(self.failure_patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        pattern = FailurePattern(**data)
                        # 覆盖旧数据，保留最新
                        self.failure_patterns[pattern.pattern_id] = pattern
        
        # 加载用户偏好
        if self.user_preferences_file.exists():
            with open(self.user_preferences_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key, value in data.items():
                    pref = UserPreference(**value)
                    self.user_preferences[key] = pref
    
    def record_success(
        self,
        task_type: str,
        intent_action: str,
        intent_target: str,
        agent_sequence: List[str],
        duration: float
    ):
        """记录成功执行"""
        # 🔧 补丁 1：设置最小统计粒度（1ms），避免 0.0秒误导
        duration = max(duration, 0.001)
        
        # 生成模式 ID
        pattern_id = f"{task_type}_{intent_action}_{intent_target}"
        
        if pattern_id in self.success_patterns:
            # 更新现有模式
            pattern = self.success_patterns[pattern_id]
            pattern.success_count += 1
            # 更新平均耗时（移动平均）
            pattern.avg_duration = (
                pattern.avg_duration * (pattern.success_count - 1) + duration
            ) / pattern.success_count
            pattern.last_used = time.time()
            # 🔧 补丁 4：安全的置信度计算
            pattern.confidence = self._calculate_confidence(
                pattern.success_count, pattern.failure_count
            )
        else:
            # 创建新模式
            pattern = ExecutionPattern(
                pattern_id=pattern_id,
                task_type=task_type,
                intent_action=intent_action,
                intent_target=intent_target,
                agent_sequence=agent_sequence,
                success_count=1,
                failure_count=0,
                avg_duration=duration,
                last_used=time.time(),
                confidence=1.0,
            )
            self.success_patterns[pattern_id] = pattern
        
        # 保存到文件
        self._save_success_pattern(pattern)
    
    def record_failure(
        self,
        task_description: str,
        error_type: str,
        error_message: str,
        context: Dict
    ):
        """记录失败执行"""
        # 生成模式 ID（基于错误类型和上下文）
        context_key = "_".join(sorted(f"{k}={v}" for k, v in context.items()))
        pattern_id = f"{error_type}_{hash(context_key) % 10000}"
        
        if pattern_id in self.failure_patterns:
            # 更新现有模式
            pattern = self.failure_patterns[pattern_id]
            pattern.occurrence_count += 1
            pattern.last_seen = time.time()
        else:
            # 创建新模式
            pattern = FailurePattern(
                pattern_id=pattern_id,
                task_description=task_description,
                error_type=error_type,
                error_message=error_message,
                context=context,
                occurrence_count=1,
                first_seen=time.time(),
                last_seen=time.time(),
                suggested_fix=None,
            )
            self.failure_patterns[pattern_id] = pattern
        
        # 保存到文件
        self._save_failure_pattern(pattern)
    
    def learn_preference(
        self,
        preference_type: str,
        key: str,
        value: any
    ):
        """学习用户偏好"""
        pref_key = f"{preference_type}_{key}"
        
        if pref_key in self.user_preferences:
            # 更新现有偏好
            pref = self.user_preferences[pref_key]
            pref.sample_count += 1
            pref.value = value  # 使用最新值
            pref.confidence = min(pref.sample_count / 10, 1.0)  # 10次后达到100%置信度
            pref.last_updated = time.time()
        else:
            # 创建新偏好
            pref = UserPreference(
                preference_type=preference_type,
                key=key,
                value=value,
                confidence=0.1,
                sample_count=1,
                last_updated=time.time(),
            )
            self.user_preferences[pref_key] = pref
        
        # 保存到文件
        self._save_user_preferences()
    
    def get_best_pattern(
        self,
        task_type: str,
        intent_action: str,
        intent_target: str
    ) -> Optional[ExecutionPattern]:
        """获取最佳执行模式"""
        pattern_id = f"{task_type}_{intent_action}_{intent_target}"
        
        if pattern_id in self.success_patterns:
            pattern = self.success_patterns[pattern_id]
            # 只返回高置信度的模式
            if pattern.confidence >= 0.7 and pattern.success_count >= 3:
                return pattern
        
        return None
    
    def should_avoid(self, context: Dict) -> Optional[FailurePattern]:
        """检查是否应该避免（匹配失败模式）"""
        for pattern in self.failure_patterns.values():
            # 简单匹配：检查上下文是否包含失败模式的关键字段
            if all(
                pattern.context.get(k) == v
                for k, v in context.items()
                if k in pattern.context
            ):
                # 高频失败模式（>= 3次）
                if pattern.occurrence_count >= 3:
                    return pattern
        
        return None
    
    def get_preference(
        self,
        preference_type: str,
        key: str,
        default: any = None
    ) -> any:
        """获取用户偏好"""
        pref_key = f"{preference_type}_{key}"
        
        if pref_key in self.user_preferences:
            pref = self.user_preferences[pref_key]
            # 只返回高置信度的偏好
            if pref.confidence >= 0.5:
                return pref.value
        
        return default
    
    def _save_success_pattern(self, pattern: ExecutionPattern):
        """保存成功模式（🔧 补丁 3：去重压缩）"""
        # 1. 读取所有现有模式
        existing = {}
        if self.success_patterns_file.exists():
            with open(self.success_patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing[data['pattern_id']] = data
                        except json.JSONDecodeError:
                            # 跳过损坏的行
                            continue
        
        # 2. 更新当前模式
        existing[pattern.pattern_id] = asdict(pattern)
        
        # 3. 重写文件（去重）
        with open(self.success_patterns_file, 'w', encoding='utf-8') as f:
            for data in existing.values():
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def _save_failure_pattern(self, pattern: FailurePattern):
        """保存失败模式（🔧 补丁 3：去重压缩）"""
        # 1. 读取所有现有模式
        existing = {}
        if self.failure_patterns_file.exists():
            with open(self.failure_patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing[data['pattern_id']] = data
                        except json.JSONDecodeError:
                            # 跳过损坏的行
                            continue
        
        # 2. 更新当前模式
        existing[pattern.pattern_id] = asdict(pattern)
        
        # 3. 重写文件（去重）
        with open(self.failure_patterns_file, 'w', encoding='utf-8') as f:
            for data in existing.values():
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def _save_user_preferences(self):
        """保存用户偏好"""
        data = {
            key: asdict(pref)
            for key, pref in self.user_preferences.items()
        }
        with open(self.user_preferences_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _calculate_confidence(self, success: int, failure: int) -> float:
        """🔧 补丁 4：安全的置信度计算"""
        total = success + failure
        if total == 0:
            return 0.0
        
        confidence = success / total
        # 限制在 [0, 1] 范围
        return max(0.0, min(1.0, confidence))
    
    def get_stats(self) -> Dict:
        """获取学习统计"""
        return {
            "success_patterns": len(self.success_patterns),
            "failure_patterns": len(self.failure_patterns),
            "user_preferences": len(self.user_preferences),
            "total_successes": sum(p.success_count for p in self.success_patterns.values()),
            "total_failures": sum(p.occurrence_count for p in self.failure_patterns.values()),
        }


# 全局实例
_adaptive_learning = AdaptiveLearning()


def get_adaptive_learning() -> AdaptiveLearning:
    """获取全局实例"""
    return _adaptive_learning


# 测试代码
if __name__ == "__main__":
    al = AdaptiveLearning()
    
    # 测试成功模式学习
    print("测试成功模式学习...")
    al.record_success(
        task_type="analysis",
        intent_action="view",
        intent_target="agent",
        agent_sequence=["monitor", "analysis"],
        duration=45.0
    )
    
    # 测试失败模式学习
    print("测试失败模式学习...")
    al.record_failure(
        task_description="删除文件",
        error_type="PermissionError",
        error_message="Permission denied",
        context={"file_path": "/tmp/test.txt", "user": "test"}
    )
    
    # 测试用户偏好学习
    print("测试用户偏好学习...")
    al.learn_preference("output_format", "default", "brief")
    
    # 获取统计
    stats = al.get_stats()
    print(f"\n学习统计:")
    print(f"  成功模式: {stats['success_patterns']}")
    print(f"  失败模式: {stats['failure_patterns']}")
    print(f"  用户偏好: {stats['user_preferences']}")
    print(f"  总成功次数: {stats['total_successes']}")
    print(f"  总失败次数: {stats['total_failures']}")

"""
AIOS Predictive Engine - 主动预测引擎

Phase 3: 预测用户需求，提前准备，主动服务

功能：
1. 时间模式识别 - 识别用户的时间习惯
2. 关联任务预测 - 预测下一步操作
3. 异常预警 - 提前发现潜在问题

数据结构：
- time_patterns.jsonl - 时间模式
- task_sequences.jsonl - 任务序列
- predictions.jsonl - 预测记录
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from datetime import datetime, timedelta


@dataclass
class TimePattern:
    """时间模式"""
    pattern_id: str
    task_type: str
    hour_of_day: int  # 0-23
    day_of_week: int  # 0-6 (Monday=0)
    occurrence_count: int
    last_occurred: float
    confidence: float  # 置信度


@dataclass
class TaskSequence:
    """任务序列"""
    sequence_id: str
    task_sequence: List[str]  # 任务序列
    occurrence_count: int
    avg_interval: float  # 平均间隔（秒）
    confidence: float


@dataclass
class Prediction:
    """预测记录"""
    prediction_id: str
    prediction_type: str  # time/sequence/anomaly
    predicted_task: str
    predicted_time: float
    confidence: float
    actual_occurred: Optional[bool]
    actual_time: Optional[float]


class PredictiveEngine:
    """主动预测引擎"""
    
    # 🔧 补丁 2：异常检测配置（防误报）
    RAPID_EXECUTION_THRESHOLD = 5.0  # 5秒阈值
    RAPID_EXECUTION_WHITELIST = {
        "simple",   # 简单任务
        "monitor",  # 监控任务
    }
    
    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent.parent / "agent_system" / "prediction_data"
        
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.time_patterns_file = self.data_dir / "time_patterns.jsonl"
        self.task_sequences_file = self.data_dir / "task_sequences.jsonl"
        self.predictions_file = self.data_dir / "predictions.jsonl"
        self.task_history_file = self.data_dir / "task_history.jsonl"
        
        # 内存缓存
        self.time_patterns: Dict[str, TimePattern] = {}
        self.task_sequences: Dict[str, TaskSequence] = {}
        self.predictions: List[Prediction] = []
        self.task_history: List[Dict] = []
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载预测数据"""
        # 加载时间模式
        if self.time_patterns_file.exists():
            with open(self.time_patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        pattern = TimePattern(**data)
                        self.time_patterns[pattern.pattern_id] = pattern
        
        # 加载任务序列
        if self.task_sequences_file.exists():
            with open(self.task_sequences_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        sequence = TaskSequence(**data)
                        self.task_sequences[sequence.sequence_id] = sequence
        
        # 加载任务历史（最近100条）
        if self.task_history_file.exists():
            with open(self.task_history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-100:]:  # 只加载最近100条
                    if line.strip():
                        self.task_history.append(json.loads(line))
    
    def record_task(self, task_type: str, task_description: str):
        """记录任务执行"""
        now = time.time()
        dt = datetime.fromtimestamp(now)
        
        task_record = {
            "task_type": task_type,
            "task_description": task_description,
            "timestamp": now,
            "hour": dt.hour,
            "day_of_week": dt.weekday(),
        }
        
        # 添加到历史
        self.task_history.append(task_record)
        
        # 保存到文件
        with open(self.task_history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(task_record, ensure_ascii=False) + '\n')
        
        # 更新时间模式
        self._update_time_pattern(task_type, dt.hour, dt.weekday())
        
        # 更新任务序列
        self._update_task_sequence()
    
    def _update_time_pattern(self, task_type: str, hour: int, day_of_week: int):
        """更新时间模式"""
        pattern_id = f"{task_type}_h{hour}_d{day_of_week}"
        
        if pattern_id in self.time_patterns:
            pattern = self.time_patterns[pattern_id]
            pattern.occurrence_count += 1
            pattern.last_occurred = time.time()
            # 置信度：出现次数越多，置信度越高（最高0.95）
            pattern.confidence = min(pattern.occurrence_count / 10, 0.95)
        else:
            pattern = TimePattern(
                pattern_id=pattern_id,
                task_type=task_type,
                hour_of_day=hour,
                day_of_week=day_of_week,
                occurrence_count=1,
                last_occurred=time.time(),
                confidence=0.1,
            )
            self.time_patterns[pattern_id] = pattern
        
        # 保存
        with open(self.time_patterns_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(pattern), ensure_ascii=False) + '\n')
    
    def _update_task_sequence(self):
        """更新任务序列"""
        if len(self.task_history) < 2:
            return
        
        # 获取最近的任务序列（窗口大小=3）
        window_size = 3
        if len(self.task_history) >= window_size:
            recent_tasks = [
                t["task_type"]
                for t in self.task_history[-window_size:]
            ]
            
            sequence_id = "_".join(recent_tasks)
            
            # 计算平均间隔
            intervals = []
            for i in range(len(self.task_history) - 1, max(len(self.task_history) - window_size, 0), -1):
                if i > 0:
                    interval = self.task_history[i]["timestamp"] - self.task_history[i-1]["timestamp"]
                    intervals.append(interval)
            
            avg_interval = sum(intervals) / len(intervals) if intervals else 60.0
            
            if sequence_id in self.task_sequences:
                seq = self.task_sequences[sequence_id]
                seq.occurrence_count += 1
                seq.avg_interval = (seq.avg_interval * (seq.occurrence_count - 1) + avg_interval) / seq.occurrence_count
                seq.confidence = min(seq.occurrence_count / 5, 0.9)
            else:
                seq = TaskSequence(
                    sequence_id=sequence_id,
                    task_sequence=recent_tasks,
                    occurrence_count=1,
                    avg_interval=avg_interval,
                    confidence=0.2,
                )
                self.task_sequences[sequence_id] = seq
            
            # 保存
            with open(self.task_sequences_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(seq), ensure_ascii=False) + '\n')
    
    def predict_next_task(self) -> Optional[Dict]:
        """预测下一个任务（基于序列）"""
        if len(self.task_history) < 2:
            return None
        
        # 获取最近的任务
        recent_tasks = [t["task_type"] for t in self.task_history[-2:]]
        
        # 查找匹配的序列
        best_match = None
        best_confidence = 0.0
        
        for seq in self.task_sequences.values():
            # 检查序列前缀是否匹配
            if len(seq.task_sequence) >= 3:
                if seq.task_sequence[:2] == recent_tasks:
                    if seq.confidence > best_confidence:
                        best_match = seq
                        best_confidence = seq.confidence
        
        if best_match and best_confidence >= 0.5:
            predicted_task = best_match.task_sequence[-1]
            predicted_time = time.time() + best_match.avg_interval
            
            return {
                "predicted_task": predicted_task,
                "predicted_time": predicted_time,
                "confidence": best_confidence,
                "reason": f"基于历史序列（{' → '.join(best_match.task_sequence)}）",
                "avg_interval": best_match.avg_interval,
            }
        
        return None
    
    def predict_by_time(self) -> List[Dict]:
        """预测即将到来的任务（基于时间模式）"""
        now = datetime.now()
        current_hour = now.hour
        current_day = now.weekday()
        
        predictions = []
        
        # 查找当前时间的模式
        for pattern in self.time_patterns.values():
            if pattern.hour_of_day == current_hour and pattern.day_of_week == current_day:
                if pattern.confidence >= 0.5:
                    predictions.append({
                        "predicted_task": pattern.task_type,
                        "confidence": pattern.confidence,
                        "reason": f"每周{['一','二','三','四','五','六','日'][current_day]} {current_hour}:00 通常执行此任务",
                        "occurrence_count": pattern.occurrence_count,
                    })
        
        # 按置信度排序
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return predictions
    
    def detect_anomalies(self) -> List[Dict]:
        """检测异常（简化版）"""
        anomalies = []
        
        # 检测任务频率异常
        if len(self.task_history) >= 10:
            recent_10 = self.task_history[-10:]
            task_types = [t["task_type"] for t in recent_10]
            type_counts = Counter(task_types)
            
            # 如果某个任务类型占比超过70%，可能异常
            for task_type, count in type_counts.items():
                if count >= 7:
                    anomalies.append({
                        "type": "high_frequency",
                        "task_type": task_type,
                        "count": count,
                        "message": f"任务 '{task_type}' 在最近10次中出现{count}次，频率异常",
                        "suggestion": "检查是否有重复执行或死循环",
                    })
        
        # 检测时间间隔异常（🔧 补丁 2：添加去抖和白名单）
        if len(self.task_history) >= 2:
            last_task = self.task_history[-1]
            prev_task = self.task_history[-2]
            
            last_interval = last_task["timestamp"] - prev_task["timestamp"]
            
            # 白名单检查
            is_whitelisted = (
                last_task["task_type"] in self.RAPID_EXECUTION_WHITELIST or
                prev_task["task_type"] in self.RAPID_EXECUTION_WHITELIST
            )
            
            # 只有非白名单 + 间隔过短才报警
            if not is_whitelisted and last_interval < self.RAPID_EXECUTION_THRESHOLD:
                anomalies.append({
                    "type": "rapid_execution",
                    "interval": last_interval,
                    "message": f"任务执行间隔过短（{last_interval:.1f}秒）",
                    "suggestion": "检查是否有重复触发",
                })
        
        return anomalies
    
    def get_stats(self) -> Dict:
        """获取预测统计"""
        return {
            "time_patterns": len(self.time_patterns),
            "task_sequences": len(self.task_sequences),
            "task_history_count": len(self.task_history),
            "high_confidence_patterns": sum(
                1 for p in self.time_patterns.values() if p.confidence >= 0.7
            ),
            "high_confidence_sequences": sum(
                1 for s in self.task_sequences.values() if s.confidence >= 0.7
            ),
        }


# 全局实例
_predictive_engine = PredictiveEngine()


def get_predictive_engine() -> PredictiveEngine:
    """获取全局实例"""
    return _predictive_engine


# 测试代码
if __name__ == "__main__":
    pe = PredictiveEngine()
    
    # 模拟任务记录
    print("模拟任务记录...")
    pe.record_task("monitor", "查看系统状态")
    time.sleep(0.1)
    pe.record_task("analysis", "分析数据")
    time.sleep(0.1)
    pe.record_task("code", "执行代码")
    
    # 预测下一个任务
    print("\n预测下一个任务:")
    next_task = pe.predict_next_task()
    if next_task:
        print(f"  预测: {next_task['predicted_task']}")
        print(f"  置信度: {next_task['confidence']*100:.1f}%")
        print(f"  原因: {next_task['reason']}")
    else:
        print("  暂无预测")
    
    # 基于时间预测
    print("\n基于时间预测:")
    time_predictions = pe.predict_by_time()
    if time_predictions:
        for pred in time_predictions:
            print(f"  {pred['predicted_task']} (置信度: {pred['confidence']*100:.1f}%)")
    else:
        print("  暂无预测")
    
    # 异常检测
    print("\n异常检测:")
    anomalies = pe.detect_anomalies()
    if anomalies:
        for anomaly in anomalies:
            print(f"  ⚠️ {anomaly['message']}")
    else:
        print("  未发现异常")
    
    # 统计
    stats = pe.get_stats()
    print(f"\n统计:")
    print(f"  时间模式: {stats['time_patterns']}")
    print(f"  任务序列: {stats['task_sequences']}")
    print(f"  任务历史: {stats['task_history_count']}")

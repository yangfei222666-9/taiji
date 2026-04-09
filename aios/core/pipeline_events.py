"""
Pipeline 事件发射器
将 pipeline.py 改造为事件驱动模式
"""
from pathlib import Path
import sys

# 添加路径
AIOS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AIOS_ROOT))

from core.event import create_event, EventType
from core.event_bus import emit


def emit_pipeline_started(pipeline_id: str, stages: list):
    """发射 pipeline 开始事件"""
    event = create_event(
        EventType.PIPELINE_STARTED,
        source="pipeline",
        pipeline_id=pipeline_id,
        stages=stages,
        stage_count=len(stages)
    )
    emit(event)


def emit_pipeline_completed(pipeline_id: str, duration_ms: int, results: dict):
    """发射 pipeline 完成事件"""
    event = create_event(
        EventType.PIPELINE_COMPLETED,
        source="pipeline",
        pipeline_id=pipeline_id,
        duration_ms=duration_ms,
        results=results,
        success_count=sum(1 for r in results.values() if r.get("ok")),
        total_count=len(results)
    )
    emit(event)


def emit_pipeline_failed(pipeline_id: str, stage: str, error: str):
    """发射 pipeline 失败事件"""
    event = create_event(
        EventType.PIPELINE_FAILED,
        source="pipeline",
        pipeline_id=pipeline_id,
        failed_stage=stage,
        error=error
    )
    emit(event)


# 便捷函数：包装现有 pipeline 执行
def run_pipeline_with_events(pipeline_fn, pipeline_id: str = "daily"):
    """
    包装 pipeline 执行，自动发射事件
    
    Args:
        pipeline_fn: pipeline 执行函数
        pipeline_id: pipeline ID
    
    Returns:
        pipeline 执行结果
    """
    import time
    
    # 发射开始事件
    emit_pipeline_started(pipeline_id, ["sensors", "alerts", "reactor", "verifier", "feedback", "evolution"])
    
    start_time = time.time()
    
    try:
        # 执行 pipeline
        result = pipeline_fn()
        
        # 发射完成事件
        duration_ms = int((time.time() - start_time) * 1000)
        emit_pipeline_completed(pipeline_id, duration_ms, result)
        
        return result
        
    except Exception as e:
        # 发射失败事件
        emit_pipeline_failed(pipeline_id, "unknown", str(e))
        raise

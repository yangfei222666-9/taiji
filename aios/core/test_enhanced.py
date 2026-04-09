"""
测试增强后的全自动智能化功能
"""
import sys
from pathlib import Path

AIOS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.auto_intelligence import process_user_request, format_result

# 测试用例（覆盖新增的模板和参数推断）
test_cases = [
    # 基础功能
    "查看 Agent 执行情况",
    "分析最近 24 小时的任务执行情况",
    
    # 新增模板
    "重构 scheduler.py 代码",
    "排查系统故障",
    "执行性能测试",
    "部署应用到生产环境",
    "搜索 GitHub 上最新的 Agent 框架",
    "清理临时文件",
    "备份数据库",
    
    # 参数推断
    "查看前 10 个失败的任务",
    "分析最近 1 小时的错误日志",
    "执行所有待处理的高优先级任务",
    "删除最近 7 天的临时文件（需要备份）",
]

print("=" * 70)
print("全自动智能化 Phase 1 增强版测试")
print("=" * 70)

for i, test_input in enumerate(test_cases, 1):
    print(f"\n{'=' * 70}")
    print(f"测试 {i}/{len(test_cases)}")
    print(f"{'=' * 70}")
    
    result = process_user_request(test_input)
    print(format_result(result))
    
    # 简要总结
    print(f"\n📊 总结:")
    print(f"   意图: {result.intent.action} {result.intent.target} ({result.intent.risk})")
    print(f"   模板: {result.plan.task_type.value}")
    print(f"   步骤: {len(result.plan.subtasks)} 个")
    print(f"   耗时: {result.plan.total_estimated_duration}秒")
    print(f"   决策: {'✅ 自动执行' if result.auto_execute else '❌ 需要确认'}")
    if result.intent.params:
        print(f"   参数: {result.intent.params}")

print(f"\n{'=' * 70}")
print(f"测试完成！共 {len(test_cases)} 个用例")
print(f"{'=' * 70}")

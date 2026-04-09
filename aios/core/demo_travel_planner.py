"""
AIOS v1.3 演示 - 旅行规划助手
展示 Planning + Memory + Tools 三大模块协同工作
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from planner import Planner, SubTask
from memory import MemoryManager
from tools import ToolManager

print("\n" + "=" * 70)
print(" " * 20 + "AIOS v1.3 旅行规划助手")
print("=" * 70)

workspace = Path(__file__).parent.parent

# 初始化三大模块
planner = Planner(workspace)
memory = MemoryManager(workspace)
tools = ToolManager(workspace)

print("\n✅ 系统已启动")
print("   • Planning 模块: 任务拆解")
print("   • Memory 模块: 记忆检索")
print("   • Tools 模块: 工具执行")

# 用户输入
print("\n" + "-" * 70)
print("👤 用户: 帮我规划一次周末去京都的旅行，预算5000元")
print("-" * 70)

# Step 1: Planning（任务拆解）
print("\n🤖 AIOS: 正在分析任务...")
print("\n[Step 1] Planning - 任务拆解")

# 手动创建子任务（模拟 Planner 的输出）
subtasks = [
    SubTask(
        id="task-1",
        description="搜索北京到京都的机票价格",
        type="research",
        priority="high",
        dependencies=[],
        estimated_time=10
    ),
    SubTask(
        id="task-2",
        description="搜索京都的酒店信息",
        type="research",
        priority="high",
        dependencies=[],
        estimated_time=10
    ),
    SubTask(
        id="task-3",
        description="计算总预算（机票1800 + 酒店1200 + 景点500）",
        type="code",
        priority="normal",
        dependencies=["task-1", "task-2"],
        estimated_time=5
    ),
    SubTask(
        id="task-4",
        description="生成旅行计划报告 kyoto_travel_plan.txt",
        type="code",
        priority="normal",
        dependencies=["task-3"],
        estimated_time=5
    )
]

print(f"   ✅ 任务已拆解为 {len(subtasks)} 个子任务:")
for i, st in enumerate(subtasks, 1):
    deps = f" (依赖: {', '.join(st.dependencies)})" if st.dependencies else ""
    print(f"      {i}. {st.description}{deps}")

# Step 2: Memory（检索相关记忆）
print(f"\n[Step 2] Memory - 检索相关记忆")
memory.store("之前规划过去京都的旅行，预算是5000元", importance=0.8)
memory.store("京都的主要景点有清水寺和金阁寺", importance=0.7)

results = memory.retrieve("京都旅行", k=2)
print(f"   ✅ 检索到 {len(results)} 条相关记忆:")
for i, mem in enumerate(results, 1):
    print(f"      {i}. {mem.content}")

# Step 3: Tools（执行任务）
print(f"\n[Step 3] Tools - 执行任务")

# 执行子任务
task_results = {}

for i, subtask in enumerate(subtasks, 1):
    print(f"\n   [{i}/{len(subtasks)}] {subtask.description}")
    
    # 自动选择工具
    tool = tools.select(subtask.description)
    if tool:
        print(f"      → 选择工具: {tool.name}")
        
        # 执行工具
        if tool.name == "web_search":
            result = tools.execute(tool.name, query=subtask.description)
            task_results[subtask.id] = result.output
            print(f"      ✅ {result.output}")
        
        elif tool.name == "calculator":
            result = tools.execute(tool.name, expression="1800 + 1200 + 500")
            task_results[subtask.id] = result.output
            print(f"      ✅ 总预算: {result.output}元")
        
        elif tool.name == "file_writer":
            # 生成报告内容
            report = f"""
京都周末旅行计划
================

目的地：京都
预算：5000元

行程安排：
- 第1天：清水寺
- 第2天：金阁寺

费用明细：
- 机票：1800元
- 酒店：1200元
- 景点：500元
- 总计：{task_results.get('task-3', 3500)}元

备注：
- 建议提前预订机票和酒店
- 清水寺和金阁寺是京都必去景点
"""
            result = tools.execute(tool.name, 
                                  file_path="kyoto_travel_plan.txt",
                                  content=report)
            task_results[subtask.id] = result.output
            print(f"      ✅ {result.output}")
    else:
        print(f"      ❌ 未找到合适的工具")

# Step 4: 结果汇总
print(f"\n" + "=" * 70)
print("📊 执行结果")
print("=" * 70)

tool_stats = tools.get_tool_stats()
print(f"\n工具使用统计:")
print(f"   • 总执行次数: {tool_stats['total_executions']}")
print(f"   • 成功率: {tool_stats['total_successes'] / max(tool_stats['total_executions'], 1) * 100:.1f}%")

print(f"\n各工具统计:")
for tool_stat in tool_stats['tools']:
    if tool_stat['usage_count'] > 0:
        print(f"   • {tool_stat['name']}: {tool_stat['usage_count']} 次, "
              f"成功率 {tool_stat['success_rate']:.1%}")

print(f"\n记忆统计:")
memory_stats = memory.get_stats()
print(f"   • 短期记忆: {memory_stats['short_term_count']} 条")
print(f"   • 长期记忆: {memory_stats['long_term_count']} 条")

print(f"\n" + "=" * 70)
print("✅ 旅行计划已生成！")
print("📄 查看完整计划: kyoto_travel_plan.txt")
print("=" * 70 + "\n")

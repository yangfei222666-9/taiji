"""
AIOS v1.3 实战演示 - 仙本那旅行规划
用户：珊瑚海
预算：10,000 马币/人
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from planner import Planner, SubTask
from memory import MemoryManager
from tools import ToolManager

print("\n" + "=" * 70)
print(" " * 15 + "AIOS v1.3 - 仙本那旅行规划助手")
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
print("👤 珊瑚海: 帮我规划一次去仙本那旅行，预算1万马币一个人")
print("-" * 70)

# Step 1: Planning（任务拆解）
print("\n🤖 AIOS: 正在分析任务...")
print("\n[Step 1] Planning - 任务拆解")

# 手动创建子任务
subtasks = [
    SubTask(
        id="task-1",
        description="搜索新山到仙本那的交通方式和费用",
        type="research",
        priority="high",
        dependencies=[],
        estimated_time=10
    ),
    SubTask(
        id="task-2",
        description="搜索仙本那的住宿选择（度假村/民宿）",
        type="research",
        priority="high",
        dependencies=[],
        estimated_time=10
    ),
    SubTask(
        id="task-3",
        description="搜索仙本那的潜水和跳岛游活动",
        type="research",
        priority="high",
        dependencies=[],
        estimated_time=10
    ),
    SubTask(
        id="task-4",
        description="计算总预算（交通2000 + 住宿3000 + 活动3000 + 餐饮1500 + 其他500）",
        type="code",
        priority="normal",
        dependencies=["task-1", "task-2", "task-3"],
        estimated_time=5
    ),
    SubTask(
        id="task-5",
        description="生成仙本那旅行计划 semporna_travel_plan.txt",
        type="code",
        priority="normal",
        dependencies=["task-4"],
        estimated_time=5
    )
]

print(f"   ✅ 任务已拆解为 {len(subtasks)} 个子任务:")
for i, st in enumerate(subtasks, 1):
    deps = f" (依赖: {', '.join(st.dependencies)})" if st.dependencies else ""
    print(f"      {i}. {st.description}{deps}")

# Step 2: Memory（检索相关记忆）
print(f"\n[Step 2] Memory - 检索相关记忆")
memory.store("珊瑚海住在马来西亚新山，靠近新加坡", importance=0.9)
memory.store("仙本那是马来西亚著名的潜水胜地，有美丽的海岛", importance=0.8)
memory.store("仙本那的主要活动：潜水、跳岛游、海鲜大餐", importance=0.7)

results = memory.retrieve("仙本那旅行", k=3)
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
            result = tools.execute(tool.name, expression="2000 + 3000 + 3000 + 1500 + 500")
            task_results[subtask.id] = result.output
            print(f"      ✅ 总预算: {result.output} 马币")
        
        elif tool.name == "file_writer":
            # 生成报告内容
            report = f"""
仙本那旅行计划
==============

目的地：仙本那（Semporna），马来西亚沙巴州
预算：10,000 马币/人

行程建议（5天4夜）：
--------------------
第1天：新山 → 斗湖机场 → 仙本那镇
  - 交通：飞机（新山→斗湖）约 300-500 马币
  - 住宿：仙本那镇酒店/民宿 约 150-300 马币/晚

第2-3天：跳岛游 + 浮潜/潜水
  - 推荐岛屿：
    * 马布岛（Mabul Island）- 潜水天堂
    * 卡帕莱岛（Kapalai Island）- 水上屋度假村
    * 邦邦岛（Pom Pom Island）- 海龟保护区
  - 活动费用：
    * 跳岛游套餐：200-400 马币/天
    * 潜水（持证）：150-250 马币/次
    * 浮潜：包含在跳岛游中

第4天：敦沙卡兰海洋公园（Tun Sakaran Marine Park）
  - 珍珠岛（Bohey Dulang）- 登山看全景
  - 军舰岛（Sibuan Island）- 白沙滩
  - 费用：300-500 马币（含午餐）

第5天：仙本那镇 → 斗湖机场 → 新山
  - 早上逛海鲜市场
  - 下午返程

费用明细：
----------
1. 交通费用：
   - 往返机票（新山-斗湖）：1,000-1,500 马币
   - 机场接送 + 镇内交通：200-300 马币
   - 小计：约 1,500 马币

2. 住宿费用：
   - 仙本那镇酒店（4晚）：600-1,200 马币
   - 或选择水上屋度假村（2晚）：2,000-4,000 马币
   - 小计：约 2,000-3,000 马币

3. 活动费用：
   - 跳岛游（2天）：600-800 马币
   - 潜水/浮潜：500-1,000 马币
   - 海洋公园门票：300-500 马币
   - 小计：约 2,000-3,000 马币

4. 餐饮费用：
   - 海鲜大餐：50-100 马币/餐
   - 普通餐饮：20-40 马币/餐
   - 5天约：1,000-1,500 马币

5. 其他费用：
   - 防晒霜、浮潜装备租赁等：300-500 马币

总预算：约 7,000-10,000 马币
实际花费：{task_results.get('task-4', 10000)} 马币

重要提示：
----------
1. 最佳旅行时间：3-10月（避开雨季）
2. 必备物品：
   - 防晒霜（SPF50+）
   - 浮潜装备（可租赁）
   - 防水相机/手机壳
   - 轻便衣物 + 长袖防晒衣
3. 签证：马来西亚公民无需签证
4. 货币：马币（MYR），镇上有ATM
5. 语言：马来语、英语、华语都通用
6. 网络：镇上有WiFi，海岛信号较弱

推荐住宿：
----------
1. 经济型：
   - Seafest Hotel（海丰酒店）：150-250 马币/晚
   - Dragon Inn（龙门客栈）：100-200 马币/晚

2. 中档型：
   - Sipadan Inn（诗巴丹客栈）：250-400 马币/晚
   - Scuba Junkie（潜水狂人度假村）：300-500 马币/晚

3. 豪华型：
   - Singamata Reef Resort（水上屋）：800-1,500 马币/晚
   - Mabul Water Bungalows（马布水上屋）：1,000-2,000 马币/晚

推荐餐厅：
----------
1. 海丰茶餐室 - 本地美食
2. 肥妈海鲜楼 - 海鲜大餐
3. Floating Seafood Market - 海上海鲜市场

注意事项：
----------
1. 仙本那镇较小，步行即可
2. 跳岛游需提前一天预订
3. 潜水需持证（OW/AOW），可在当地考证
4. 海岛上无ATM，需提前准备现金
5. 尊重当地文化（部分岛屿为穆斯林社区）

联系方式：
----------
- 仙本那旅游局：+60 89-782 009
- 紧急救援：999（马来西亚）

祝你旅途愉快！🏝️🤿
"""
            result = tools.execute(tool.name, 
                                  file_path="semporna_travel_plan.txt",
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
print("✅ 仙本那旅行计划已生成！")
print("📄 查看完整计划: semporna_travel_plan.txt")
print("=" * 70 + "\n")

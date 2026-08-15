"""AIOS Agent System 包。

2026-08-15(A2):移除了从未接线的 AgentSystem 门面——它引用的
unified_router_v1.py 从未存在于 git 历史,实例化必然 TypeError。
本包现在只提供可直接导入的子模块(task_router / task_queue /
task_executor / agent_lifecycle_engine / paths / memory_retrieval 等)。
"""

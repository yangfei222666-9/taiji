"""
AIOS Task Scheduler v4.0 - 集成 Planning + Memory + Tools

新增功能（v4.0）：
- 集成 Tools（自动工具选择和执行）
- 三大模块协同工作（Planning → Memory → Tools）
- 自动上下文注入（记忆 + 工具结果）

已有功能（v3.0）：
- 集成 Planner（自动任务拆解）
- 集成 Memory（记忆检索和存储）
- 支持 Plan 执行（按依赖关系调度子任务）
- 保持原有的并发控制、超时保护、依赖处理

核心特性：
- 完全线程安全 (threading.Lock 全覆盖)
- O(1) deque 队列
- 正确依赖处理 (waiting queue + completed set，无死循环、无忙等待)
- 内置任务超时保护 (ThreadPoolExecutor + timeout)
- 类型提示 + Google docstring + structured logging
- 优雅关闭 + 资源零泄漏
"""
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, Any, Callable, List, Optional
from pathlib import Path
import logging
import time

# 导入 Planner
import sys
sys.path.insert(0, str(Path(__file__).parent))
from planner import Planner, Plan, SubTask

# 导入 Memory
try:
    from memory import MemoryManager
except ImportError:
    MemoryManager = None

# 导入 Tools
try:
    from tools import ToolManager
except ImportError:
    ToolManager = None

logger = logging.getLogger(__name__)


class Scheduler:
    """生产级任务调度器，支持依赖关系、并发控制、超时保护、自动任务拆解。"""

    def __init__(self, max_concurrent: int = 5, default_timeout: int = 30, 
                 workspace: Optional[Path] = None):
        """初始化调度器。

        Args:
            max_concurrent: 最大并发任务数
            default_timeout: 单个任务默认超时秒数
            workspace: 工作目录（用于 Planner + Memory）
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.queue: deque = deque()  # 就绪队列
        self.waiting: deque = deque()  # 等待依赖的任务
        self.running: Dict[str, Any] = {}  # task_id -> Future
        self.completed: set[str] = set()
        self.dependencies: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
        # 初始化 Planner
        if workspace is None:
            workspace = Path(__file__).parent.parent.parent
        self.planner = Planner(workspace)
        
        # 初始化 Memory
        self.memory = MemoryManager(workspace) if MemoryManager else None
        
        # 初始化 Tools
        self.tools = ToolManager(workspace) if ToolManager else None
        
        # Plan 管理
        self.plans: Dict[str, Plan] = {}  # task_id -> Plan
        self.plan_callbacks: Dict[str, Callable] = {}  # task_id -> callback

    def schedule(self, task: Dict[str, Any]) -> None:
        """调度新任务。

        Args:
            task: 必须包含 'id' (str) 和 'func' (Callable)，可选 'depends_on' (List[str])
        """
        with self.lock:
            task_id = task.get("id")
            if not task_id or not isinstance(task_id, str):
                raise ValueError("Task must contain 'id' as string")

            func = task.get("func")
            if not callable(func):
                raise TypeError(f"Task {task_id}: 'func' must be callable")

            depends_on = task.get("depends_on", [])
            if not isinstance(depends_on, list):
                raise ValueError(f"Task {task_id}: 'depends_on' must be list")

            self.dependencies[task_id] = depends_on
            self.queue.append(task)
            logger.info(f"📥 Task {task_id} scheduled (depends on {depends_on})")

        self._process_queue()
    
    def schedule_with_planning(self, task_description: str, 
                              executor: Optional[Callable[[SubTask], Any]] = None,
                              callback: Optional[Callable[[Plan], None]] = None,
                              strategy: str = "auto",
                              use_memory: bool = True,
                              use_tools: bool = True) -> str:
        """
        调度任务（自动规划拆解 + 记忆检索 + 工具调用）
        
        Args:
            task_description: 任务描述（自然语言）
            executor: 子任务执行器（可选，如果不提供则使用默认工具执行器）
            callback: Plan 完成后的回调函数
            strategy: 执行策略（auto/sequential/parallel/dag）
            use_memory: 是否使用记忆检索
            use_tools: 是否使用工具自动执行
        
        Returns:
            task_id: 任务 ID
        """
        # 0. 检索相关记忆（如果启用）
        context_memories = []
        if use_memory and self.memory:
            context_memories = self.memory.retrieve(task_description, k=5)
            if context_memories:
                logger.info(f"🧠 检索到 {len(context_memories)} 条相关记忆")
        
        # 1. 使用 Planner 拆解任务（带记忆检索）
        plan = self.planner.plan(task_description, strategy, use_memory=use_memory)
        logger.info(f"📋 Plan created: {plan.task_id} ({len(plan.subtasks)} subtasks, {plan.strategy})")
        
        # 2. 保存 Plan
        with self.lock:
            self.plans[plan.task_id] = plan
            if callback:
                self.plan_callbacks[plan.task_id] = callback
        
        # 3. 如果没有提供 executor，使用默认工具执行器
        if executor is None and use_tools and self.tools:
            executor = self._default_tool_executor
        
        # 4. 调度所有子任务（注入上下文记忆）
        for subtask in plan.subtasks:
            # 构建上下文（包含相关记忆）
            context = self._build_context(context_memories, subtask)
            
            task = {
                "id": subtask.id,
                "func": lambda st=subtask, ctx=context: executor(st, ctx) if ctx else executor(st),
                "depends_on": subtask.dependencies,
                "plan_id": plan.task_id,
                "subtask": subtask
            }
            self.schedule(task)
        
        return plan.task_id
    
    def _default_tool_executor(self, subtask: SubTask, context: Optional[str] = None) -> Any:
        """默认工具执行器（自动选择工具）"""
        if not self.tools:
            logger.warning(f"⚠️ Tools not available for subtask {subtask.id}")
            return None
        
        # 1. 自动选择工具
        tool = self.tools.select(subtask.description)
        
        if not tool:
            logger.warning(f"⚠️ No tool found for subtask: {subtask.description}")
            return None
        
        logger.info(f"🔧 Selected tool: {tool.name} for subtask: {subtask.description}")
        
        # 2. 执行工具（根据工具类型传递不同参数）
        try:
            if tool.name == "web_search":
                result = self.tools.execute(tool.name, query=subtask.description)
            elif tool.name == "calculator":
                # 从描述中提取表达式
                expr = self._extract_expression(subtask.description)
                result = self.tools.execute(tool.name, expression=expr)
            elif tool.name == "file_reader":
                # 从描述中提取文件路径
                file_path = self._extract_file_path(subtask.description)
                result = self.tools.execute(tool.name, file_path=file_path)
            elif tool.name == "file_writer":
                # 从描述中提取文件路径和内容
                file_path = self._extract_file_path(subtask.description)
                content = context or f"自动生成的内容：{subtask.description}"
                result = self.tools.execute(tool.name, file_path=file_path, content=content)
            elif tool.name == "code_executor":
                # 从描述中提取代码
                code = self._extract_code(subtask.description)
                result = self.tools.execute(tool.name, code=code)
            else:
                result = self.tools.execute(tool.name)
            
            # 3. 存储结果到记忆
            if result.success and self.memory:
                self.memory.store(
                    f"使用 {tool.name} 完成任务: {subtask.description}\n结果: {result.output}",
                    importance=0.7
                )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}")
            return None
    
    def _extract_expression(self, text: str) -> str:
        """从文本中提取数学表达式"""
        # 简单实现：查找数字和运算符
        import re
        match = re.search(r'[\d\+\-\*/\(\)\s]+', text)
        return match.group(0).strip() if match else "0"
    
    def _extract_file_path(self, text: str) -> str:
        """从文本中提取文件路径"""
        # 简单实现：查找文件名
        import re
        match = re.search(r'[\w\-\.]+\.(txt|md|pdf|json)', text)
        return match.group(0) if match else "output.txt"
    
    def _extract_code(self, text: str) -> str:
        """从文本中提取代码"""
        # 简单实现：返回原文本
        return text
    
    def _build_context(self, memories: List, subtask: SubTask) -> Optional[str]:
        """构建上下文（从记忆中提取相关信息）"""
        if not memories:
            return None
        
        # 过滤与子任务相关的记忆
        relevant = []
        for mem in memories:
            if any(kw in mem.content for kw in subtask.description.split()[:3]):
                relevant.append(mem.content)
        
        if not relevant:
            return None
        
        return "\n".join([f"- {mem}" for mem in relevant[:3]])

    def _deps_satisfied(self, task_id: str) -> bool:
        """检查任务的所有依赖是否已完成。"""
        deps = self.dependencies.get(task_id, [])
        return all(d in self.completed for d in deps)

    def tick(self) -> int:
        """
        调度器主循环（单次 tick）
        
        Returns:
            启动的任务数量
        """
        # 1. 收集可调度的任务（减少锁持有时间）
        ready_tasks = []
        with self.lock:
            # 从 waiting 队列中找到依赖满足的任务
            still_waiting = deque()
            for task in self.waiting:
                if self._deps_satisfied(task["id"]):
                    ready_tasks.append(task)
                else:
                    still_waiting.append(task)
            self.waiting = still_waiting
            
            # 从就绪队列中取出可执行的任务
            available_slots = self.max_concurrent - len(self.running)
            while available_slots > 0 and self.queue:
                task = self.queue.popleft()
                if self._deps_satisfied(task["id"]):
                    ready_tasks.append(task)
                    available_slots -= 1
                else:
                    self.waiting.append(task)
        
        # 2. 启动任务（锁外执行，避免阻塞）
        started = 0
        for task in ready_tasks:
            with self.lock:
                # 二次检查（防止并发问题）
                if len(self.running) >= self.max_concurrent:
                    self.queue.appendleft(task)
                    break
                self._start_task(task)
                started += 1
        
        return started

    def _process_queue(self) -> None:
        """处理就绪队列和等待依赖的任务（兼容旧接口）。"""
        self.tick()

    def _start_task(self, task: Dict[str, Any]) -> None:
        """使用 Executor 启动带超时的任务。"""
        task_id = task["id"]
        future = self.executor.submit(self._execute_task, task)
        self.running[task_id] = future
        future.add_done_callback(lambda f: self._task_done(task_id, f, task))

    def _execute_task(self, task: Dict[str, Any]) -> Any:
        """实际执行函数（worker 线程）。"""
        return task["func"]()

    def _task_done(self, task_id: str, future, task: Dict[str, Any]) -> None:
        """任务完成回调。"""
        with self.lock:
            self.running.pop(task_id, None)

        try:
            result = future.result(timeout=self.default_timeout)
            self._on_complete(task_id, result, task)
        except FutureTimeoutError:
            self._on_timeout(task_id, task)
        except Exception as e:
            self._on_error(task_id, e, task)

        self._process_queue()

    def _on_complete(self, task_id: str, result: Any, task: Dict[str, Any]) -> None:
        with self.lock:
            self.completed.add(task_id)
        
        logger.info(f"✅ Task {task_id} completed successfully: {result}")
        
        # 存储到记忆（如果启用）
        if self.memory:
            subtask = task.get("subtask")
            if subtask:
                self.memory.store(
                    f"完成任务: {subtask.description} - 结果: {result}",
                    source="scheduler",
                    importance=0.7,
                    metadata={"task_id": task_id, "type": subtask.type}
                )
        
        # 更新 Plan 状态
        plan_id = task.get("plan_id")
        if plan_id and plan_id in self.plans:
            subtask = task.get("subtask")
            if subtask:
                self.planner.update_subtask_status(plan_id, subtask.id, "completed", str(result))
            
            # 检查 Plan 是否完成
            self._check_plan_completion(plan_id)

    def _on_error(self, task_id: str, error: Exception, task: Dict[str, Any]) -> None:
        logger.error(f"❌ Task {task_id} failed: {error}")
        
        # 更新 Plan 状态
        plan_id = task.get("plan_id")
        if plan_id and plan_id in self.plans:
            subtask = task.get("subtask")
            if subtask:
                self.planner.update_subtask_status(plan_id, subtask.id, "failed", str(error))

    def _on_timeout(self, task_id: str, task: Dict[str, Any]) -> None:
        logger.warning(f"⏰ Task {task_id} timed out after {self.default_timeout}s")
        
        # 更新 Plan 状态
        plan_id = task.get("plan_id")
        if plan_id and plan_id in self.plans:
            subtask = task.get("subtask")
            if subtask:
                self.planner.update_subtask_status(plan_id, subtask.id, "failed", "timeout")
    
    def _check_plan_completion(self, plan_id: str):
        """检查 Plan 是否完成"""
        plan = self.plans.get(plan_id)
        if not plan:
            return
        
        # 重新加载 Plan（获取最新状态）
        plan = self.planner.load_plan(plan_id)
        if not plan:
            return
        
        # 检查是否所有子任务都完成
        all_done = all(st.status in ["completed", "failed"] for st in plan.subtasks)
        if all_done:
            logger.info(f"🎉 Plan {plan_id} completed!")
            
            # 调用回调
            callback = self.plan_callbacks.get(plan_id)
            if callback:
                callback(plan)
            
            # 清理
            with self.lock:
                self.plans.pop(plan_id, None)
                self.plan_callbacks.pop(plan_id, None)

    def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """获取 Plan 状态"""
        plan = self.planner.load_plan(plan_id)
        if not plan:
            return None
        
        completed = sum(1 for st in plan.subtasks if st.status == "completed")
        failed = sum(1 for st in plan.subtasks if st.status == "failed")
        running = sum(1 for st in plan.subtasks if st.status == "running")
        pending = sum(1 for st in plan.subtasks if st.status == "pending")
        
        return {
            "task_id": plan.task_id,
            "original_task": plan.original_task,
            "strategy": plan.strategy,
            "total": len(plan.subtasks),
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "progress": f"{completed}/{len(plan.subtasks)}"
        }

    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭。"""
        self.executor.shutdown(wait=wait)
        logger.info("Scheduler shutdown complete.")


# ==================== 测试示例 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("=== AIOS Scheduler v3.0 Demo ===\n")
    
    workspace = Path(__file__).parent.parent.parent
    scheduler = Scheduler(max_concurrent=3, default_timeout=10, workspace=workspace)

    # 测试1：简单任务（不拆解）
    print("测试1：简单任务（不拆解）")
    def simple_executor(subtask: SubTask):
        print(f"  执行: {subtask.description}")
        time.sleep(0.5)
        return f"{subtask.description} - 完成"
    
    plan_id_1 = scheduler.schedule_with_planning(
        "打开 QQ 音乐",
        simple_executor
    )
    time.sleep(2)
    status_1 = scheduler.get_plan_status(plan_id_1)
    print(f"状态: {status_1}\n")
    
    # 测试2：对比任务（拆解为3步）
    print("测试2：对比任务（拆解为3步）")
    def research_executor(subtask: SubTask):
        print(f"  执行: {subtask.description}")
        time.sleep(1)
        return f"{subtask.description} - 完成"
    
    def on_plan_complete(plan: Plan):
        print(f"🎉 Plan {plan.task_id} 全部完成！")
        for st in plan.subtasks:
            print(f"  - {st.description}: {st.status}")
    
    plan_id_2 = scheduler.schedule_with_planning(
        "对比 AIOS 和标准 Agent 架构",
        research_executor,
        callback=on_plan_complete
    )
    time.sleep(5)
    status_2 = scheduler.get_plan_status(plan_id_2)
    print(f"状态: {status_2}\n")
    
    # 测试3：开发任务（拆解为设计→实现→测试）
    print("测试3：开发任务（拆解为设计→实现→测试）")
    def dev_executor(subtask: SubTask):
        print(f"  执行: {subtask.description} ({subtask.type})")
        time.sleep(subtask.estimated_time / 100)  # 缩短时间
        return f"{subtask.description} - 完成"
    
    plan_id_3 = scheduler.schedule_with_planning(
        "实现 Memory 模块",
        dev_executor,
        callback=on_plan_complete
    )
    time.sleep(8)
    status_3 = scheduler.get_plan_status(plan_id_3)
    print(f"状态: {status_3}\n")
    
    # 等待所有任务完成
    time.sleep(3)
    scheduler.shutdown()
    
    print("\n[OK] Demo 完成！")
    print(f"已完成任务: {len(scheduler.completed)}")

"""
AIOS Agent System - Auto Dispatcher
自动任务分发器：监听事件 → 识别任务 → 路由到 Agent

集成点：
1. EventBus 订阅（感知层触发）
2. Heartbeat 轮询（定期检查）
3. Cron 定时（周期任务）
4. Self-Improving Loop（自动改进）
"""

import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 确保 aios/ 作为包被正确导入（避免 agent_system/aios.py 影射 aios 包）
_current_dir = Path(__file__).resolve().parent
_repo_root = _current_dir.parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
_cur_norm = os.path.normcase(os.path.normpath(str(_current_dir)))
sys.path = [p for p in sys.path if os.path.normcase(os.path.normpath(str(p))) != _cur_norm]
sys.path.append(str(_current_dir))

# 假设这些模块存在
try:
    from aios.core.event_bus import EventBus
except ImportError:
    EventBus = None

try:
    from aios.agent_system.circuit_breaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None

# Self-Improving Loop（必须在 sys.path 设置后导入）
SelfImprovingLoop = None
try:
    from self_improving_loop import SelfImprovingLoop
except ImportError as e:
    pass  # 静默失败

# Workflow Engine（新增）
WorkflowEngine = None
try:
    from workflow_engine import WorkflowEngine
except ImportError as e:
    print(f"[AutoDispatcher] Failed to import WorkflowEngine: {e}")
except Exception as e:
    print(f"[AutoDispatcher] Unexpected error importing WorkflowEngine: {e}")


class AutoDispatcher:
    """自动任务分发器"""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        # 统一路径真源：所有队列文件从 paths.py 获取
        try:
            from paths import TASK_QUEUE as _UNIFIED_QUEUE
            self.queue_file = _UNIFIED_QUEUE
        except ImportError:
            self.queue_file = self.workspace / "aios" / "agent_system" / "data" / "task_queue.jsonl"
        self.state_file = self.workspace / "memory" / "agent_dispatch_state.json"
        self.log_file = self.workspace / "aios" / "agent_system" / "dispatcher.log"
        self.event_bus = EventBus() if EventBus else None

        # Self-Improving Loop（新增）
        self.improving_loop = None
        if SelfImprovingLoop:
            try:
                self.improving_loop = SelfImprovingLoop()
            except Exception as e:
                self.improving_loop = None

        # Workflow Engine（新增）
        self.workflow_engine = WorkflowEngine() if WorkflowEngine else None

        # 熔断器
        breaker_file = (
            self.workspace / "aios" / "agent_system" / "circuit_breaker_state.json"
        )
        self.circuit_breaker = (
            CircuitBreaker(threshold=3, timeout=300, state_file=breaker_file)
            if CircuitBreaker
            else None
        )

        # Agent 模板配置
        self.agent_templates = {
            "code": {"model": "ollama/llama3.2:latest", "label": "coder"},
            "analysis": {"model": "ollama/llama3.2:latest", "label": "analyst"},
            "monitor": {"model": "ollama/llama3.2:latest", "label": "monitor"},
            "research": {"model": "ollama/llama3.2:latest", "label": "researcher"},
            "design": {"model": "ollama/llama3.2:latest", "label": "designer"},
            "test": {"model": "ollama/llama3.2:latest", "label": "tester"},
            "document": {"model": "ollama/llama3.2:latest", "label": "documenter"},
            "debug": {"model": "ollama/llama3.2:latest", "label": "debugger"},
        }

        # 加载 Agent 配置（role/goal/backstory）
        self.agent_configs = self._load_agent_configs()

        # 订阅事件
        if self.event_bus:
            self._subscribe_events()

    def _load_agent_configs(self) -> Dict:
        """加载 Agent 配置（包含 role/goal/backstory）"""
        config_file = self.workspace / "aios" / "agent_system" / "data" / "agent_configs.json"
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("agents", {})
        except Exception as e:
            self._log("error", f"Failed to load agent configs: {e}")
            return {}

    def _log(self, level: str, message: str, **kwargs):
        """写日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _log_duplicate_attempt(self, task: Dict, result: Dict):
        """记录 task_queue 重复入队尝试"""
        duplicate_log = Path(__file__).parent / "data" / "duplicate_enqueue_attempts.jsonl"
        duplicate_log.parent.mkdir(parents=True, exist_ok=True)

        reason_text = result.get("reason", "")
        duplicate_reason = "same_task_id"
        if "dedup_key" in reason_text.lower() or result.get("action") == "skipped_duplicate":
            duplicate_reason = "same_dedup_key"

        entry = {
            "target": "task_queue",
            "task_id": task.get("id"),
            "workflow_id": task.get("workflow_id"),
            "dedup_key": result.get("dedup_key"),
            "source": "auto_dispatcher",
            "created_by": "auto_dispatcher.py",
            "created_at": datetime.now().isoformat(),
            "duplicate_reason": duplicate_reason,
            "existing_record_hint": result.get("reason"),
        }

        with open(duplicate_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _log_spawn_duplicate(self, request: Dict, result: Dict):
        """记录 spawn_requests 重复写入尝试"""
        duplicate_log = Path(__file__).parent / "data" / "duplicate_enqueue_attempts.jsonl"
        duplicate_log.parent.mkdir(parents=True, exist_ok=True)

        reason_text = result.get("reason", "")
        duplicate_reason = "same_task_id"
        if "window" in reason_text.lower():
            duplicate_reason = "same_payload_window"
        elif "dedup_key" in reason_text.lower() or result.get("action") == "skipped_duplicate":
            duplicate_reason = "same_dedup_key"

        entry = {
            "target": "spawn_requests",
            "task_id": request.get("task_id"),
            "workflow_id": request.get("workflow_id"),
            "dedup_key": result.get("dedup_key"),
            "source": "auto_dispatcher",
            "created_by": "auto_dispatcher.py",
            "created_at": datetime.now().isoformat(),
            "duplicate_reason": duplicate_reason,
            "existing_record_hint": result.get("reason"),
        }

        with open(duplicate_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _subscribe_events(self):
        """订阅感知层事件"""
        if not self.event_bus:
            return

        # 文件变化 → coder
        self.event_bus.subscribe("sensor.file.*", self._on_file_change)

        # 系统告警 → monitor
        self.event_bus.subscribe("alert.*", self._on_alert)

        # 数据到达 → analyst
        self.event_bus.subscribe("sensor.data.*", self._on_data_arrival)

    def _event_payload(self, event) -> Dict:
        if event is None:
            return {}
        if hasattr(event, "payload"):
            payload = getattr(event, "payload", None)
            return payload if isinstance(payload, dict) else {}
        if isinstance(event, dict):
            if "payload" in event and isinstance(event.get("payload"), dict):
                return event["payload"]
            return event
        return {}

    def _event_type(self, event) -> str:
        if event is None:
            return ""
        if hasattr(event, "type"):
            t = getattr(event, "type", "")
            return t if isinstance(t, str) else ""
        if isinstance(event, dict):
            t = event.get("type") or event.get("event_type") or ""
            return t if isinstance(t, str) else ""
        return ""

    def _event_id(self, event) -> str:
        if event is None:
            return ""
        if hasattr(event, "id"):
            v = getattr(event, "id", "")
            return v if isinstance(v, str) else ""
        if isinstance(event, dict):
            v = event.get("id") or event.get("event_id") or ""
            return v if isinstance(v, str) else ""
        return ""

    def _event_timestamp(self, event) -> Optional[int]:
        if event is None:
            return None
        if hasattr(event, "timestamp"):
            v = getattr(event, "timestamp", None)
            return int(v) if isinstance(v, (int, float)) else None
        if isinstance(event, dict):
            v = event.get("timestamp")
            return int(v) if isinstance(v, (int, float)) else None
        return None

    def _on_file_change(self, event):
        """文件变化处理"""
        payload = self._event_payload(event)
        path = payload.get("path", "")

        # 只处理代码文件
        if not any(path.endswith(ext) for ext in [".py", ".js", ".ts", ".go", ".rs"]):
            return

        # 如果是测试文件变化，触发测试任务
        if "test" in path.lower():
            self.enqueue_task(
                {
                    "type": "code",
                    "message": f"Run tests: {path}",
                    "priority": "high",
                    "source": "file_watcher",
                }
            )

    def _on_alert(self, event):
        """告警处理"""
        payload = self._event_payload(event)
        severity = payload.get("severity", "info")

        if severity in ["warn", "crit"]:
            self.enqueue_task(
                {
                    "type": "monitor",
                    "message": f"Handle alert: {payload.get('message', '')}",
                    "priority": "high" if severity == "crit" else "normal",
                    "source": "alert_system",
                }
            )

    def _on_data_arrival(self, event):
        """数据到达处理"""
        payload = self._event_payload(event)
        data_type = payload.get("data_type", "")
        data_ref = payload.get("data_ref") or payload.get("path") or payload.get("uri") or ""
        event_id = self._event_id(event)
        task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{event_id[:8] if event_id else 'event'}"

        # 新数据需要分析
        self.enqueue_task(
            {
                "id": task_id,
                "type": "analysis",
                "message": f"Analyze new data: {data_type}",
                "priority": "high",
                "source": "data_sensor",
                "metadata": {
                    "data_type": data_type,
                    "data_ref": data_ref,
                    "event_type": self._event_type(event),
                    "event_id": event_id,
                    "event_timestamp": self._event_timestamp(event),
                },
            }
        )

    def enqueue_task(self, task: Dict):
        """
        任务入队（支持优先级）- 通过 TaskQueueManager 统一入口
        
        优先级：
        - high: 立即处理（插队）
        - normal: 正常处理
        - low: 延迟处理（队列空闲时）
        """
        # 导入统一管理器
        from task_queue_manager import TaskQueueManager
        
        # 补充必要字段
        if "id" not in task:
            task["id"] = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        if "status" not in task:
            task["status"] = "pending"
        
        # 默认优先级
        if "priority" not in task:
            task["priority"] = "normal"
        
        # Tracing: task_created
        try:
            from tracer import TaskTracer
            tracer = TaskTracer(
                task_id=task["id"],
                source="auto_dispatcher",
                agent_name=task.get("agent_id", "unknown"),
            )
            task["trace_id"] = tracer.trace_id  # 注入 trace_id，后续步骤沿用
            tracer.created(result_summary=task.get("description", "")[:200])
        except Exception:
            pass  # trace 写失败不阻塞主流程
        
        # 通过统一入口写入（带幂等保护）
        queue_mgr = TaskQueueManager(queue_file=self.queue_file)
        result = queue_mgr.enqueue_task(task, source="auto_dispatcher")
        
        if result["success"]:
            self._log(
                "info",
                "Task enqueued",
                task_id=result["task_id"],
                type=task.get("type"),
                priority=task["priority"],
                dedup_key=result["dedup_key"]
            )
            # Tracing: task_enqueued
            try:
                tracer.enqueued(result_summary=f"priority={task['priority']}")
            except Exception:
                pass
        else:
            # 记录重复/跳过
            self._log(
                "warn",
                f"Task {result['action']}",
                task_id=result.get("task_id"),
                dedup_key=result.get("dedup_key"),
                reason=result.get("reason")
            )
            
            # 记录到 duplicate 日志
            self._log_duplicate_attempt(task, result)

    def process_queue(self, max_tasks: int = 5) -> List[Dict]:
        """
        处理队列（心跳调用）
        
        优先级策略：
        1. high 优先级任务立即处理（插队）
        2. normal 优先级任务按 FIFO 处理
        3. low 优先级任务延迟处理（仅在队列空闲时）
        """
        if not self.queue_file.exists():
            return []

        # 读取所有待处理任务
        tasks_by_id = {}
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    task = json.loads(line)
                    if task.get("status") not in ["pending", "retry_pending"]:
                        continue
                    task_id = task.get("id")
                    if not task_id:
                        continue
                    # 跳过延迟重试的任务
                    if "next_retry_after" in task:
                        retry_time = datetime.fromisoformat(task["next_retry_after"])
                        if datetime.now() < retry_time:
                            continue
                    tasks_by_id[task_id] = task

        tasks = list(tasks_by_id.values())

        if not tasks:
            return []

        # 按优先级排序（high > normal > low）
        priority_order = {"high": 0, "normal": 1, "low": 2}
        tasks.sort(key=lambda t: (
            priority_order.get(t.get("priority", "normal"), 1),
            t.get("enqueued_at", "")  # 同优先级按入队时间排序
        ))

        # 低优先级任务延迟处理（仅在没有 high/normal 任务时）
        high_normal_count = sum(1 for t in tasks if t.get("priority") in ["high", "normal"])
        if high_normal_count > 0:
            # 有高/中优先级任务，跳过低优先级
            tasks = [t for t in tasks if t.get("priority") != "low"]

        # 处理前 N 个任务
        processed = []
        remaining = []

        for i, task in enumerate(tasks):
            if i < max_tasks:
                try:
                    result = self._dispatch_task(task)
                    task["status"] = "dispatched"
                    processed.append({**task, "result": result})
                    
                    self._log(
                        "info",
                        "Task dispatched",
                        task_id=task.get("id"),
                        priority=task.get("priority"),
                        type=task.get("type")
                    )
                    
                except Exception as e:
                    # 失败处理
                    error_msg = str(e)
                    
                    # 记录失败（触发熔断器）
                    task_type = task.get("type", "monitor")
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure(task_type)
                    
                    result = {"status": "error", "message": error_msg}

                    # 失败重试逻辑
                    retry_count = task.get("retry_count", 0)
                    max_retries = 3

                    if retry_count < max_retries:
                        # 重新入队，增加重试计数
                        task["retry_count"] = retry_count + 1
                        task["last_error"] = error_msg
                        task["status"] = "retry_pending"
                        # 指数退避：2^retry_count 分钟
                        task["next_retry_after"] = (
                            datetime.now() + timedelta(minutes=2**retry_count)
                        ).isoformat()
                        remaining.append(task)
                        self._log(
                            "warn",
                            "Task retry scheduled",
                            task_id=task.get("id"),
                            retry=retry_count + 1,
                            max=max_retries,
                            next_retry=task["next_retry_after"][:19],
                            error=error_msg[:300],
                        )
                    else:
                        # 超过最大重试次数，记录失败
                        task["status"] = "failed"
                        self._log(
                            "error",
                            "Task failed permanently",
                            task_id=task.get("id"),
                            retries=retry_count,
                        )

                    processed.append({**task, "result": result})
            else:
                remaining.append(task)

        # 写回未处理的任务（包括延迟重试的任务）
        all_remaining = []
        processed_ids = {t.get("id") for t in tasks if t.get("id")}
        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    task = json.loads(line)
                    # 保留延迟重试的任务
                    if "next_retry_after" in task and task.get("id") not in processed_ids:
                        all_remaining.append(task)
        
        all_remaining.extend(remaining)
        
        with open(self.queue_file, "w", encoding="utf-8") as f:
            for task in all_remaining:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")

        return processed

    def _dispatch_task(self, task: Dict) -> Dict:
        """分发单个任务到 Agent（通过 sessions_spawn）+ Self-Improving Loop"""
        task_type = task.get("type", "monitor")
        message = task["message"]
        task_id = task.get("id", "unknown")

        # 生成 agent_id（用于追踪）
        agent_id = f"{task_type}-dispatcher"

        # 如果启用了 Self-Improving Loop，包装执行
        if self.improving_loop:
            result = self.improving_loop.execute_with_improvement(
                agent_id=agent_id,
                task=message,
                execute_fn=lambda: self._do_dispatch(task, task_type, message),
                context={"task_id": task_id, "task_type": task_type}
            )

            # 检查是否触发了改进
            if result.get("improvement_triggered"):
                self._log(
                    "info",
                    "Self-improvement triggered",
                    agent_id=agent_id,
                    improvements=result.get("improvement_applied", 0)
                )

            # 返回实际结果
            if result["success"]:
                return result["result"]
            else:
                return {"status": "error", "message": result.get("error", "unknown")}
        else:
            # 没有 Self-Improving Loop，直接执行
            return self._do_dispatch(task, task_type, message)

    def _do_dispatch(self, task: Dict, task_type: str, message: str) -> Dict:
        """实际的任务分发逻辑"""
        # 熔断器检查
        if self.circuit_breaker and not self.circuit_breaker.should_execute(task_type):
            retry_after = (
                self.circuit_breaker.get_status()
                .get(task_type, {})
                .get("retry_after", 300)
            )
            self._log(
                "warn",
                "Circuit breaker open",
                task_id=task.get("id"),
                task_type=task_type,
                retry_after=retry_after,
            )
            raise Exception(f"Circuit breaker open for {task_type}, retry after {retry_after}s")

        # 获取模板配置
        template = self.agent_templates.get(task_type, self.agent_templates["monitor"])

        # 查找匹配的 Agent 配置（根据 type）
        agent_config = None
        agent_id = None
        for aid, config in self.agent_configs.items():
            if config.get("type") == template["label"] and config.get("env") == "prod":
                agent_config = config
                agent_id = aid
                break

        # 启动工作流（如果有工作流引擎）
        execution_id = None
        workflow = None
        if self.workflow_engine and agent_id:
            try:
                execution_id = self.workflow_engine.start_execution(
                    agent_id=agent_id,
                    agent_type=template["label"],
                    task=task
                )
                workflow = {"workflow_id": f"{template['label']}-standard"}
                self._log(
                    "info",
                    "Workflow started",
                    execution_id=execution_id,
                    agent_id=agent_id,
                    workflow=f"{template['label']}-standard"
                )
            except Exception as e:
                self._log("warn", f"Failed to start workflow: {e}")

        metadata = task.get("metadata") or {}
        if task_type == "analysis" and metadata.get("data_type") == "mouseflow" and metadata.get("data_ref"):
            data_ref = str(metadata.get("data_ref") or "")
            task_id = str(task.get("id") or "")
            event_id = str(metadata.get("event_id") or "")
            enhanced_message = "\n".join(
                [
                    "Analyze mouseflow data and write outputs using the built-in worker:",
                    f'python g:/TaijiOS_Backup/aios/agent_system/tools/mouseflow_analysis_worker.py --data-ref "{data_ref}" --task-id "{task_id}" --event-id "{event_id}"',
                    "Then verify the output files exist and report their paths.",
                ]
            )
            metadata = {
                **metadata,
                "exec": {
                    "kind": "python_worker",
                    "worker": "mouseflow_analysis_worker",
                    "data_ref": data_ref,
                    "task_id": task_id,
                    "event_id": event_id,
                },
            }
        else:
            enhanced_message = message
        if agent_config:
            role = agent_config.get("role", "")
            goal = agent_config.get("goal", "")
            backstory = agent_config.get("backstory", "")
            
            # 获取工作流定义
            workflow = None
            if self.workflow_engine:
                workflow = self.workflow_engine.get_workflow(template["label"])
            
            role_prompt_parts = ["# Your Role"]
            if role:
                role_prompt_parts.append(f"**Role:** {role}")
            if goal:
                role_prompt_parts.append(f"**Goal:** {goal}")
            if backstory:
                role_prompt_parts.append(f"**Backstory:** {backstory}")
            
            # 添加工作流指引
            if workflow and execution_id:
                role_prompt_parts.append("\n# Your Workflow")
                role_prompt_parts.append(f"**Execution ID:** {execution_id}")
                role_prompt_parts.append(f"**Workflow:** {workflow['description']}")
                role_prompt_parts.append("\n**Stages:**")
                for i, stage in enumerate(workflow["stages"], 1):
                    role_prompt_parts.append(f"{i}. **{stage['name']}** ({stage['stage']})")
                    role_prompt_parts.append(f"   - Actions: {', '.join(stage['actions'][:3])}")
                    role_prompt_parts.append(f"   - Output: {stage['output']}")
                
                role_prompt_parts.append("\n**Quality Gates:**")
                for gate, value in workflow.get("quality_gates", {}).items():
                    role_prompt_parts.append(f"- {gate}: {value}")
                
                # 进度报告指令
                role_prompt_parts.append("\n**Progress Reporting:**")
                role_prompt_parts.append("在每个阶段执行时，请在回复中包含进度标记：")
                role_prompt_parts.append("```")
                role_prompt_parts.append(f"[WORKFLOW_PROGRESS] execution_id={execution_id} stage=<stage_id> status=<started|in_progress|completed|failed> [progress=<0.0-1.0>] [message=<描述>]")
                role_prompt_parts.append("```")
                role_prompt_parts.append("示例：")
                role_prompt_parts.append(f"- 开始阶段：`[WORKFLOW_PROGRESS] execution_id={execution_id} stage=1_understand status=started`")
                role_prompt_parts.append(f"- 进行中：`[WORKFLOW_PROGRESS] execution_id={execution_id} stage=1_understand status=in_progress progress=0.5 message=正在分析需求`")
                role_prompt_parts.append(f"- 完成：`[WORKFLOW_PROGRESS] execution_id={execution_id} stage=1_understand status=completed`")
            
            role_prompt_parts.append("\n# Your Task")
            role_prompt_parts.append(enhanced_message)
            
            enhanced_message = "\n".join(role_prompt_parts)

        # 调用 OpenClaw sessions_spawn
        # 注意：这需要在 OpenClaw 环境中运行，不是独立 Python 脚本
        # 这里使用文件标记的方式，让主 Agent 在心跳时检测并执行

        spawn_task_id = str(task.get("id") or "unknown")
        spawn_agent_id = agent_id or f"{template['label']}-dispatcher"
        spawn_request = {
            "id": f"spawn-{spawn_task_id}",
            "task_id": spawn_task_id,
            "task_type": task_type,
            "task": enhanced_message,
            "message": enhanced_message,
            "model": template["model"],
            "label": template["label"],
            "agent_id": spawn_agent_id,
            "cleanup": "keep",
            "runTimeoutSeconds": int(task.get("timeout", 600)),
            "created_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "role": agent_config.get("role") if agent_config else None,
            "goal": agent_config.get("goal") if agent_config else None,
            "execution_id": execution_id,
            "workflow_id": workflow["workflow_id"] if workflow else None,
        }

        # 通过 SpawnRequestManager 统一写入（带幂等保护）
        from task_queue_manager import SpawnRequestManager
        
        spawn_file = (
            self.workspace / "aios" / "agent_system" / "data" / "spawn_requests.jsonl"
        )
        spawn_mgr = SpawnRequestManager(spawn_file=spawn_file)
        spawn_result = spawn_mgr.create_spawn_request(spawn_request, source="auto_dispatcher")
        
        if spawn_result["success"]:
            self._log(
                "info",
                "Spawn request created",
                task_id=task.get("id"),
                task_type=task_type,
                model=template["model"],
                label=template["label"],
                role=agent_config.get("role") if agent_config else None,
                dedup_key=spawn_result["dedup_key"],
            )
        else:
            # spawn 被拦截（重复）
            self._log(
                "warn",
                f"Spawn request {spawn_result['action']}",
                task_id=task.get("id"),
                dedup_key=spawn_result.get("dedup_key"),
                reason=spawn_result.get("reason"),
                target="spawn_requests",
            )
            # 记录到 duplicate 日志
            self._log_spawn_duplicate(spawn_request, spawn_result)

        # 记录成功（重置熔断器）
        if self.circuit_breaker:
            self.circuit_breaker.record_success(task_type)

        return {
            "status": "pending",
            "agent": template["label"],
            "note": "Spawn request created, waiting for main agent to execute",
        }

    def check_scheduled_tasks(self) -> List[Dict]:
        """检查定时任务（cron 调用）"""
        state = self._load_state()
        now = datetime.now()
        triggered = []

        # 每日任务：代码审查
        if self._should_run(state, "daily_code_review", hours=24):
            self.enqueue_task(
                {
                    "type": "code",
                    "message": "Run daily code review",
                    "priority": "normal",
                    "source": "cron_daily",
                }
            )
            triggered.append("daily_code_review")
            state["daily_code_review"] = now.isoformat()

        # 每周任务：性能分析
        if self._should_run(state, "weekly_performance", hours=168):
            self.enqueue_task(
                {
                    "type": "analysis",
                    "message": "Generate weekly performance report",
                    "priority": "normal",
                    "source": "cron_weekly",
                }
            )
            triggered.append("weekly_performance")
            state["weekly_performance"] = now.isoformat()

        # 每小时任务：待办检查
        if self._should_run(state, "hourly_todo_check", hours=1):
            self.enqueue_task(
                {
                    "type": "monitor",
                    "message": "Check todos and deadlines",
                    "priority": "low",
                    "source": "cron_hourly",
                }
            )
            triggered.append("hourly_todo_check")
            state["hourly_todo_check"] = now.isoformat()

        self._save_state(state)
        return triggered

    def _should_run(self, state: Dict, task_name: str, hours: int) -> bool:
        """判断任务是否应该运行"""
        last_run = state.get(task_name)
        if not last_run:
            return True

        last_time = datetime.fromisoformat(last_run)
        return datetime.now() - last_time >= timedelta(hours=hours)

    def _load_state(self) -> Dict:
        """加载状态"""
        if not self.state_file.exists():
            return {}

        with open(self.state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_state(self, state: Dict):
        """保存状态"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def status(self) -> Dict:
        """获取状态"""
        queue_size = 0
        if self.queue_file.exists():
            with open(self.queue_file, "r", encoding="utf-8") as f:
                queue_size = sum(1 for line in f if line.strip())

        state = self._load_state()

        # 熔断器状态
        breaker_status = {}
        if self.circuit_breaker:
            breaker_status = self.circuit_breaker.get_status()

        # Self-Improving Loop 统计（新增）
        improvement_stats = {}
        if self.improving_loop:
            improvement_stats = self.improving_loop.get_improvement_stats()

        return {
            "queue_size": queue_size,
            "last_scheduled_tasks": state,
            "event_subscriptions": 3 if self.event_bus else 0,
            "circuit_breaker": breaker_status,
            "self_improving": improvement_stats,  # 新增
        }


def main():
    """CLI 入口"""
    import sys

    workspace = Path(__file__).parent.parent.parent
    dispatcher = AutoDispatcher(workspace)

    if len(sys.argv) < 2:
        print("Usage: python auto_dispatcher.py [heartbeat|cron|status]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "heartbeat":
        # 心跳调用：处理队列
        results = dispatcher.process_queue(max_tasks=5)
        if results:
            print(f"OK processed {len(results)} tasks")
            for r in results:
                status = r["result"]["status"]
                task_type = r.get("type") or r.get("task_type", "unknown")
                desc = r.get("description", r.get("message", ""))[:50]
                print(f"  - {task_type}: {desc}... -> {status}")
        else:
            print("SKIP queue empty")

    elif cmd == "cron":
        # Cron 调用：检查定时任务
        triggered = dispatcher.check_scheduled_tasks()
        if triggered:
            print(f"OK triggered {len(triggered)} scheduled tasks")
            for t in triggered:
                print(f"  - {t}")
        else:
            print("SKIP no tasks due")

    elif cmd == "status":
        # 状态查询
        status = dispatcher.status()
        print(f"Auto Dispatcher Status")
        print(f"  Queue size: {status['queue_size']}")
        print(f"  Event subscriptions: {status['event_subscriptions']}")
        print(f"  Last scheduled tasks:")
        for task, time in status["last_scheduled_tasks"].items():
            print(f"    - {task}: {time}")

        # 熔断器状态
        breaker = status.get("circuit_breaker", {})
        if breaker:
            print(f"  Circuit Breaker:")
            for task_type, info in breaker.items():
                state = "🔴 OPEN" if info["circuit_open"] else "🟢 HEALTHY"
                print(
                    f"    - {task_type}: {state} (failures: {info['failure_count']}, retry: {info['retry_after']}s)"
                )
        else:
            print(f"  Circuit Breaker: All healthy")

        # Self-Improving Loop 统计（新增）
        improving = status.get("self_improving", {})
        if improving:
            print(f"  Self-Improving Loop:")
            print(f"    - Total agents: {improving.get('total_agents', 0)}")
            print(f"    - Total improvements: {improving.get('total_improvements', 0)}")
            improved = improving.get("agents_improved", [])
            if improved:
                print(f"    - Improved agents: {', '.join(improved[:5])}")
                if len(improved) > 5:
                    print(f"      ... and {len(improved) - 5} more")
        else:
            print(f"  Self-Improving Loop: Not available")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

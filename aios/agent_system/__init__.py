"""
AIOS Agent System - 自主 Agent 管理系统主入口

统一接口，整合 AgentManager 和 TaskRouter
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    from .core.agent_manager import AgentManager
except ImportError:
    AgentManager = None

try:
    from .unified_router_v1 import UnifiedRouter, TaskContext, TaskType, RiskLevel, Decision, ExecutionMode
except ImportError:
    UnifiedRouter = None
    TaskContext = None
    TaskType = None
    RiskLevel = None
    Decision = None
    ExecutionMode = None

# from .evolution import AgentEvolution  # 临时注释，evolution.py 有语法错误


class AgentSystem:
    """自主 Agent 管理系统"""

    def __init__(self, data_dir: str = None, config_dir: str = None):
        self.manager = AgentManager(data_dir)
        self.router = UnifiedRouter(enable_guardrails=True)  # 使用统一路由 v1.0（解释性 + 防抖滞回）
        # self.evolution = AgentEvolution(data_dir)  # 临时注释，evolution.py 有语法错误

        self.log_file = self.manager.data_dir / "system.log"
        
        # 系统状态（用于路由决策）
        self.system_state = {
            "error_rate": 0.0,
            "performance_drop": 0.0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0
        }

    def _log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def handle_task(self, message: str, auto_create: bool = True,
                   task_type: TaskType = None, complexity: int = 5,
                   risk_level=None) -> Dict:
        """
        处理任务（主入口）- 使用智能路由

        Args:
            message: 用户消息
            auto_create: 是否自动创建 Agent
            task_type: 任务类型（可选，会自动推断）
            complexity: 复杂度 1-10（可选）
            risk_level: 风险等级（可选）

        Returns:
            {
                'status': 'success' | 'error',
                'action': 'assigned' | 'created' | 'failed',
                'agent_id': str,
                'agent_name': str,
                'decision': Dict,
                'message': str
            }
        """
        start_time = time.time()

        try:
            # 1. 推断任务类型（如果未指定）
            if task_type is None:
                task_type = self._infer_task_type(message)
            
            # 2. 更新系统状态
            self._update_system_state()
            
            # 3. 构建任务上下文
            context = TaskContext(
                description=message,
                task_type=task_type,
                complexity=complexity,
                risk_level=risk_level,
                error_rate=self.system_state["error_rate"],
                performance_drop=self.system_state["performance_drop"],
                cpu_usage=self.system_state["cpu_usage"],
                memory_usage=self.system_state["memory_usage"]
            )
            
            # 4. 智能路由决策
            decision = self.router.route(context)
            
            self._log(f"路由决策: {decision.agent} - {decision.reason_codes} (confidence={decision.confidence:.2f})")
            
            # 5. 查找或创建 Agent
            agent = self._get_or_create_agent(
                template=decision.agent,
                auto_create=auto_create
            )
            
            if not agent:
                return {
                    "status": "error",
                    "action": "failed",
                    "decision": decision.__dict__,
                    "message": f"无法创建 Agent: {decision.agent}"
                }
            
            # 6. 返回结果
            action = "created" if agent.get("_just_created") else "assigned"
            
            # 构建向后兼容的 reason 字符串
            reason_str = ", ".join(decision.reason_codes) if decision.reason_codes else "default"
            
            return {
                "status": "success",
                "action": action,
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "agent_template": agent["template"],
                "decision": {
                    "agent": decision.agent,
                    "model": decision.model,
                    "thinking": decision.thinking,
                    "timeout": decision.timeout,
                    "reason": reason_str,  # 向后兼容
                    "reason_codes": decision.reason_codes,
                    "confidence": decision.confidence,
                    "execution_mode": decision.execution_mode.value,
                    "input_snapshot": decision.input_snapshot
                },
                "message": f"{'已创建' if action == 'created' else '已分配给'} {agent['name']} ({agent['id']})"
            }

        except Exception as e:
            self._log(f"Error handling task: {str(e)}", level="ERROR")
            return {
                "status": "error",
                "action": "failed",
                "message": f"处理任务时出错: {str(e)}",
            }

        finally:
            duration = time.time() - start_time
            self._log(f"Task handled in {duration:.2f}s")

    def report_task_result(
        self,
        agent_id: str,
        success: bool,
        duration_sec: float,
        task_type: str = None,
        error_msg: str = None,
        context: Dict = None
    ):
        """
        报告任务执行结果（集成进化系统）

        Args:
            agent_id: Agent ID
            success: 是否成功
            duration_sec: 耗时（秒）
            task_type: 任务类型（code/analysis/monitor/research）
            error_msg: 错误信息（如果失败）
            context: 额外上下文
        """
        # 更新 Agent 统计
        self.manager.update_stats(agent_id, success, duration_sec)
        
        # 记录到进化系统（临时注释）
        # if task_type:
        #     self.evolution.log_task_execution(
        #         agent_id=agent_id,
        #         task_type=task_type,
        #         success=success,
        #         duration_sec=duration_sec,
        #         error_msg=error_msg,
        #         context=context
        #     )
        
        self._log(
            f"Task result: agent={agent_id}, success={success}, duration={duration_sec:.2f}s"
        )
        
        # 如果失败，检查是否需要生成改进建议（临时注释）
        # if not success:
        #     analysis = self.evolution.analyze_failures(agent_id, lookback_hours=24)
        #     
        #     # 失败率过高，自动生成建议
        #     if analysis['failure_rate'] > 0.3:
        #         self._log(
        #             f"High failure rate detected for {agent_id}: {analysis['failure_rate']:.1%}",
        #             level="WARN"
        #         )
        #         
        #         # 保存改进建议
        #         for suggestion in analysis['suggestions']:
        #             self.evolution.save_suggestion(
        #                 agent_id=agent_id,
        #                 suggestion={
        #                     "type": "auto_generated",
        #                     "description": suggestion,
        #                     "changes": {},
        #                     "status": "pending"
        #                 }
        #             )

    def cleanup_idle_agents(self, idle_hours: int = 24) -> List[str]:
        """
        清理闲置 Agent

        Args:
            idle_hours: 闲置时长阈值（小时）

        Returns:
            归档的 Agent ID 列表
        """
        idle_agents = self.manager.find_idle_agents(idle_hours)

        for agent_id in idle_agents:
            self.manager.archive_agent(agent_id, f"Idle for {idle_hours}+ hours")
            self._log(f"Archived idle agent: {agent_id}")

        return idle_agents

    def get_status(self) -> Dict:
        """获取系统状态"""
        summary = self.manager.get_agent_summary()
        active_agents = self.manager.list_agents(status="active")

        # 按模板分组
        by_template = {}
        for agent in active_agents:
            template = agent["template"]
            if template not in by_template:
                by_template[template] = []
            by_template[template].append(
                {
                    "id": agent["id"],
                    "name": agent["name"],
                    "tasks_completed": agent["stats"]["tasks_completed"],
                    "success_rate": agent["stats"]["success_rate"],
                    "last_active": agent["stats"].get("last_active"),
                }
            )

        return {
            "summary": summary,
            "active_agents_by_template": by_template,
            "total_active": len(active_agents),
        }

    def list_agents(self, template: str = None, status: str = "active") -> List[Dict]:
        """列出 Agent"""
        return self.manager.list_agents(status=status, template=template)

    def get_agent_detail(self, agent_id: str) -> Optional[Dict]:
        """获取 Agent 详情"""
        return self.manager.get_agent(agent_id)
    
    def _infer_task_type(self, message: str) -> TaskType:
        """从消息推断任务类型"""
        msg_lower = message.lower()
        
        # 关键词映射
        if any(kw in msg_lower for kw in ["重构", "refactor"]):
            return TaskType.REFACTOR
        elif any(kw in msg_lower for kw in ["调试", "修复", "bug", "debug", "fix"]):
            return TaskType.DEBUG
        elif any(kw in msg_lower for kw in ["测试", "test"]):
            return TaskType.TEST
        elif any(kw in msg_lower for kw in ["优化", "性能", "optimize", "performance"]):
            return TaskType.OPTIMIZE
        elif any(kw in msg_lower for kw in ["监控", "检查", "monitor", "check"]):
            return TaskType.MONITOR
        elif any(kw in msg_lower for kw in ["部署", "发布", "deploy", "release"]):
            return TaskType.DEPLOY
        elif any(kw in msg_lower for kw in ["分析", "统计", "analyze", "data"]):
            return TaskType.ANALYZE
        elif any(kw in msg_lower for kw in ["搜索", "调研", "research", "search"]):
            return TaskType.RESEARCH
        elif any(kw in msg_lower for kw in ["审查", "review"]):
            return TaskType.REVIEW
        elif any(kw in msg_lower for kw in ["文档", "doc"]):
            return TaskType.DOCUMENT
        else:
            return TaskType.CODING  # 默认编码任务
    
    def _update_system_state(self):
        """更新系统状态（从事件日志计算）"""
        try:
            from .paths import EVENTS_LOG
            # 读取最近的事件
            events_file = EVENTS_LOG
            if not events_file.exists():
                return
            
            # 流式读取末尾 100 行（不加载整个文件）
            recent_events = []
            tail = _tail_lines(events_file, 100)
            for line in tail:
                try:
                    recent_events.append(json.loads(line))
                except Exception:
                    pass
            
            if not recent_events:
                return
            
            # 计算错误率
            error_count = sum(1 for e in recent_events if e.get("layer") == "KERNEL" and "error" in e.get("type", ""))
            self.system_state["error_rate"] = error_count / len(recent_events)
            
            # 计算性能（简化版，实际应该对比历史基线）
            tool_events = [e for e in recent_events if e.get("layer") == "TOOL"]
            if tool_events:
                avg_ms = sum(e.get("ms", 0) for e in tool_events) / len(tool_events)
                # 假设基线是 500ms，超过则认为性能下降
                if avg_ms > 500:
                    self.system_state["performance_drop"] = (avg_ms - 500) / 500
            
            # CPU/内存使用率（需要实际监控，这里用占位值）
            # 实际应该从 system-resource-monitor 获取
            self.system_state["cpu_usage"] = 0.4  # 占位
            self.system_state["memory_usage"] = 0.5  # 占位
            
        except Exception as e:
            self._log(f"Error updating system state: {str(e)}", level="ERROR")
    
    def _get_or_create_agent(self, template: str, auto_create: bool = True) -> Optional[Dict]:
        """获取或创建 Agent"""
        # 1. 查找现有的同类型 Agent
        agents = self.manager.list_agents(status="active", template=template)
        
        if agents:
            # 返回最近活跃的
            agents.sort(key=lambda a: a["stats"].get("last_active") or "", reverse=True)
            return agents[0]
        
        # 2. 如果没有，创建新的
        if auto_create:
            agent = self.manager.create_agent(template, f"Auto-created for {template} task")
            agent["_just_created"] = True
            self._log(f"Created new agent: {agent['id']} (template: {template})")
            return agent
        
        return None


# CLI 接口
def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m aios.agent_system <command> [args]")
        print("\nCommands:")
        print("  status              - Show system status")
        print("  list [template]     - List agents")
        print("  create <template>   - Create agent")
        print("  route <message>     - Test task routing")
        print("  cleanup [hours]     - Cleanup idle agents")
        sys.exit(1)

    system = AgentSystem()
    command = sys.argv[1]

    if command == "status":
        status = system.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif command == "list":
        template = sys.argv[2] if len(sys.argv) > 2 else None
        agents = system.list_agents(template=template)
        print(json.dumps(agents, indent=2, ensure_ascii=False))

    elif command == "create":
        if len(sys.argv) < 3:
            print("Usage: create <template>")
            sys.exit(1)
        template = sys.argv[2]
        agent = system.manager.create_agent(template)
        print(f"Created: {agent['id']}")
        print(json.dumps(agent, indent=2, ensure_ascii=False))

    elif command == "route":
        if len(sys.argv) < 3:
            print("Usage: route <message>")
            sys.exit(1)
        message = " ".join(sys.argv[2:])
        result = system.handle_task(message, auto_create=False)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "cleanup":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        archived = system.cleanup_idle_agents(hours)
        print(f"Archived {len(archived)} agents: {', '.join(archived)}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

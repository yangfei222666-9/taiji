"""
Meta-Agent - AIOS 的 Agent 工厂

核心能力：
1. 缺口检测 - 分析系统能力，发现缺失的 Agent 类型
2. Agent 设计 - 基于模板库自动设计新 Agent
3. 沙盒测试 - 在安全环境中验证新 Agent
4. 人工确认 - 所有创建操作需要人工确认（初期）
5. 动态注册 - 通过 DynamicRegistry 注册到运行时

工作流程：
  缺口检测 → 匹配模板 → 设计 Agent → 沙盒测试 → 人工确认 → 注册上线

心跳集成：
  每天检查一次缺口 → META_AGENT_SUGGESTION:N 或 META_AGENT_OK
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# 路径设置
_current_dir = Path(__file__).resolve().parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from dynamic_registry import DynamicRegistry
from aios.agent_system.config_center import openclaw_workspace_root


class MetaAgent:
    """Meta-Agent: 自动检测缺口并设计新 Agent"""

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = Path(workspace or openclaw_workspace_root())
        self.data_dir = self.workspace / "aios" / "agent_system" / "data"
        self.meta_dir = self.data_dir / "meta_agent"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

        self.registry = DynamicRegistry(self.workspace)
        self.templates = self._load_templates()
        self.state = self._load_state()

    # ─── 数据加载 ───

    def _load_templates(self) -> Dict:
        """加载模板库"""
        tpl_file = self.workspace / "aios" / "agent_system" / "agent_templates.json"
        if tpl_file.exists():
            try:
                with open(tpl_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"templates": {}}

    def _load_state(self) -> Dict:
        """加载 Meta-Agent 状态"""
        state_file = self.meta_dir / "meta_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "last_scan": None,
            "suggestions_pending": [],
            "suggestions_history": [],
            "agents_created": 0,
            "agents_rejected": 0
        }

    def _save_state(self):
        """保存状态"""
        state_file = self.meta_dir / "meta_state.json"
        self.state["updated_at"] = datetime.now().isoformat()
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    # ─── Phase 1: 缺口检测 ───

    def detect_gaps(self) -> List[Dict]:
        """
        检测系统能力缺口
        
        分析维度：
        1. 模板覆盖 - 哪些模板类型没有活跃 Agent
        2. 失败模式 - 哪些任务类型频繁失败
        3. 未处理任务 - 队列中长期未处理的任务类型
        4. 事件分析 - 哪些事件没有对应的处理 Agent
        """
        gaps = []

        # 1. 模板覆盖检查
        template_gaps = self._check_template_coverage()
        gaps.extend(template_gaps)

        # 2. 失败模式分析
        failure_gaps = self._check_failure_patterns()
        gaps.extend(failure_gaps)

        # 3. 未处理任务检查
        queue_gaps = self._check_unhandled_tasks()
        gaps.extend(queue_gaps)

        # 4. 事件分析
        event_gaps = self._check_event_coverage()
        gaps.extend(event_gaps)

        # 去重（按 gap_type + agent_type）
        seen = set()
        unique_gaps = []
        for gap in gaps:
            key = f"{gap['gap_type']}:{gap.get('agent_type', gap.get('description', ''))}"
            if key not in seen:
                seen.add(key)
                unique_gaps.append(gap)

        return unique_gaps

    def _check_template_coverage(self) -> List[Dict]:
        """检查模板覆盖率 - 哪些模板没有活跃 Agent"""
        gaps = []
        templates = self.templates.get("templates", {})
        active_agents = self.registry.list_agents(status="active")
        active_types = {a.get("config", {}).get("type") for a in active_agents}

        for tpl_name, tpl in templates.items():
            tpl_type = tpl.get("type", tpl_name)
            if tpl_type not in active_types:
                gaps.append({
                    "gap_type": "template_uncovered",
                    "agent_type": tpl_type,
                    "template": tpl_name,
                    "description": f"模板 '{tpl_name}' ({tpl.get('name', '')}) 没有活跃 Agent",
                    "severity": "low",
                    "suggestion": f"从模板 '{tpl_name}' 创建 Agent"
                })

        return gaps

    def _check_failure_patterns(self) -> List[Dict]:
        """分析失败模式 - 哪些任务类型频繁失败"""
        gaps = []
        traces_file = self.data_dir / "traces" / "agent_traces.jsonl"

        if not traces_file.exists():
            return gaps

        # 统计最近 7 天的失败
        cutoff = datetime.now() - timedelta(days=7)
        type_failures = {}

        try:
            with open(traces_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        trace = json.loads(line)
                        ts = trace.get("timestamp", "")
                        if ts and datetime.fromisoformat(ts) < cutoff:
                            continue
                        if trace.get("status") == "failed":
                            task_type = trace.get("task_type", "unknown")
                            if task_type not in type_failures:
                                type_failures[task_type] = {"count": 0, "errors": []}
                            type_failures[task_type]["count"] += 1
                            err = trace.get("error", "")
                            if err and len(type_failures[task_type]["errors"]) < 3:
                                type_failures[task_type]["errors"].append(err[:100])
                    except (json.JSONDecodeError, ValueError):
                        continue
        except IOError:
            return gaps

        # 频繁失败（≥3次）的类型
        for task_type, info in type_failures.items():
            if info["count"] >= 3:
                gaps.append({
                    "gap_type": "frequent_failure",
                    "agent_type": task_type,
                    "failure_count": info["count"],
                    "sample_errors": info["errors"],
                    "description": f"任务类型 '{task_type}' 最近 7 天失败 {info['count']} 次",
                    "severity": "medium" if info["count"] < 10 else "high",
                    "suggestion": f"创建专门的 '{task_type}' Agent 或优化现有 Agent"
                })

        return gaps

    def _check_unhandled_tasks(self) -> List[Dict]:
        """检查未处理任务"""
        gaps = []
        try:
            from paths import TASK_QUEUE as queue_file
        except ImportError:
            queue_file = self.workspace / "aios" / "agent_system" / "data" / "task_queue.jsonl"

        if not queue_file.exists():
            return gaps

        # 统计 pending 超过 1 小时的任务
        cutoff = datetime.now() - timedelta(hours=1)
        stale_types = {}

        try:
            with open(queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        task = json.loads(line)
                        if task.get("status") != "pending":
                            continue
                        enqueued = task.get("enqueued_at", "")
                        if enqueued and datetime.fromisoformat(enqueued) < cutoff:
                            task_type = task.get("type", "unknown")
                            stale_types[task_type] = stale_types.get(task_type, 0) + 1
                    except (json.JSONDecodeError, ValueError):
                        continue
        except IOError:
            return gaps

        for task_type, count in stale_types.items():
            if count >= 2:
                gaps.append({
                    "gap_type": "unhandled_tasks",
                    "agent_type": task_type,
                    "pending_count": count,
                    "description": f"任务类型 '{task_type}' 有 {count} 个任务积压超过 1 小时",
                    "severity": "medium",
                    "suggestion": f"增加 '{task_type}' 类型的 Agent 或提升处理能力"
                })

        return gaps

    def _check_event_coverage(self) -> List[Dict]:
        """检查事件覆盖 - 哪些事件类型没有处理"""
        gaps = []
        events_file = self.workspace / "aios" / "events.jsonl"

        if not events_file.exists():
            return gaps

        # 统计最近 3 天的事件类型
        cutoff = datetime.now() - timedelta(days=3)
        event_types = {}

        try:
            with open(events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        ts = event.get("timestamp", event.get("ts", ""))
                        if ts:
                            try:
                                if isinstance(ts, (int, float)):
                                    event_time = datetime.fromtimestamp(ts if ts < 1e12 else ts / 1000)
                                else:
                                    event_time = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                                if event_time.replace(tzinfo=None) < cutoff:
                                    continue
                            except (ValueError, OSError):
                                continue

                        etype = event.get("type", event.get("event_type", "unknown"))
                        handled = event.get("handled", event.get("processed", False))
                        if etype not in event_types:
                            event_types[etype] = {"total": 0, "unhandled": 0}
                        event_types[etype]["total"] += 1
                        if not handled:
                            event_types[etype]["unhandled"] += 1
                    except (json.JSONDecodeError, ValueError):
                        continue
        except IOError:
            return gaps

        # 未处理率 > 50% 且数量 ≥ 5 的事件类型
        for etype, info in event_types.items():
            if info["total"] >= 5 and info["unhandled"] / info["total"] > 0.5:
                gaps.append({
                    "gap_type": "event_uncovered",
                    "event_type": etype,
                    "total_events": info["total"],
                    "unhandled": info["unhandled"],
                    "description": f"事件类型 '{etype}' 未处理率 {info['unhandled']}/{info['total']}",
                    "severity": "medium",
                    "suggestion": f"创建处理 '{etype}' 事件的 Agent"
                })

        return gaps

    # ─── Phase 1: Agent 设计 ───

    def design_agent(self, gap: Dict) -> Optional[Dict]:
        """
        根据缺口设计新 Agent
        
        优先匹配模板，无匹配则基于缺口信息生成设计
        """
        agent_type = gap.get("agent_type", "")
        templates = self.templates.get("templates", {})

        # 1. 精确匹配模板
        if agent_type in templates:
            return self._design_from_template(agent_type, templates[agent_type], gap)

        # 2. 模糊匹配（trigger 关键词）
        for tpl_name, tpl in templates.items():
            triggers = [t.lower() for t in tpl.get("triggers", [])]
            if agent_type.lower() in triggers:
                return self._design_from_template(tpl_name, tpl, gap)

        # 3. 无匹配 → 生成基础设计（需要人工审核）
        return self._design_custom(gap)

    def _design_from_template(self, tpl_name: str, template: Dict, gap: Dict) -> Dict:
        """从模板创建 Agent 设计"""
        agent_id = f"{template.get('type', tpl_name)}-{int(time.time()) % 100000:05d}"

        return {
            "agent_id": agent_id,
            "source": "template",
            "template_name": tpl_name,
            "gap": gap,
            "config": {
                "type": template.get("type", tpl_name),
                "name": template.get("name", f"{tpl_name} Agent"),
                "description": template.get("description", ""),
                "model": template.get("model", "claude-sonnet-4-5"),
                "thinking": template.get("thinking", "low"),
                "role": template.get("role", ""),
                "goal": template.get("goal", ""),
                "backstory": template.get("backstory", ""),
                "skills": template.get("skills", []),
                "tools_allow": template.get("tools_allow", []),
                "tools_deny": template.get("tools_deny", []),
                "timeout": template.get("timeout", 100),
                "triggers": template.get("triggers", []),
                "created_by": "meta_agent",
                "env": "prod"
            },
            "designed_at": datetime.now().isoformat(),
            "status": "pending_approval",
            "risk_level": "low"  # 模板创建风险低
        }

    def _design_custom(self, gap: Dict) -> Dict:
        """自定义设计（无模板匹配）"""
        agent_type = gap.get("agent_type", "custom")
        agent_id = f"{agent_type}-{int(time.time()) % 100000:05d}"

        return {
            "agent_id": agent_id,
            "source": "custom",
            "template_name": None,
            "gap": gap,
            "config": {
                "type": agent_type,
                "name": f"{agent_type} Agent",
                "description": gap.get("description", ""),
                "model": "claude-sonnet-4-5",
                "thinking": "low",
                "role": f"{agent_type} Specialist",
                "goal": f"Handle {agent_type} tasks effectively",
                "backstory": f"Specialized agent created to address: {gap.get('description', '')}",
                "skills": [],
                "tools_allow": ["exec", "read"],
                "tools_deny": ["message", "cron", "gateway"],
                "timeout": 100,
                "triggers": [agent_type],
                "created_by": "meta_agent",
                "env": "sandbox"  # 自定义 Agent 先在沙盒
            },
            "designed_at": datetime.now().isoformat(),
            "status": "pending_approval",
            "risk_level": "medium"  # 自定义设计风险中等
        }

    # ─── Phase 2: 沙盒测试 ───

    def sandbox_test(self, design: Dict) -> Dict:
        """
        沙盒测试新 Agent 设计
        
        检查项：
        1. 配置完整性
        2. 模板合法性
        3. 资源限制
        4. 权限安全
        """
        results = {
            "agent_id": design["agent_id"],
            "tests": [],
            "passed": True,
            "tested_at": datetime.now().isoformat()
        }

        config = design.get("config", {})

        # 1. 配置完整性
        required_fields = ["type", "name", "model", "timeout"]
        missing = [f for f in required_fields if not config.get(f)]
        results["tests"].append({
            "name": "config_completeness",
            "passed": len(missing) == 0,
            "detail": f"Missing: {missing}" if missing else "All required fields present"
        })
        if missing:
            results["passed"] = False

        # 2. 模型合法性
        valid_models = [
            "claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5",
            "claude-sonnet-4-6", "claude-opus-4-6"
        ]
        model_ok = config.get("model", "") in valid_models
        results["tests"].append({
            "name": "model_validity",
            "passed": model_ok,
            "detail": f"Model: {config.get('model', 'none')}"
        })
        if not model_ok:
            results["passed"] = False

        # 3. 超时限制（不超过 300s）
        timeout = config.get("timeout", 100)
        timeout_ok = 10 <= timeout <= 300
        results["tests"].append({
            "name": "timeout_range",
            "passed": timeout_ok,
            "detail": f"Timeout: {timeout}s (range: 10-300)"
        })
        if not timeout_ok:
            results["passed"] = False

        # 4. 权限安全（不能有危险工具）
        dangerous_tools = {"gateway", "cron"}
        allowed = set(config.get("tools_allow", []))
        denied = set(config.get("tools_deny", []))
        has_dangerous = allowed & dangerous_tools
        results["tests"].append({
            "name": "permission_safety",
            "passed": len(has_dangerous) == 0,
            "detail": f"Dangerous tools in allow list: {has_dangerous}" if has_dangerous else "Safe"
        })
        if has_dangerous:
            results["passed"] = False

        # 5. Agent 数量上限
        can_register = self.registry.can_register()
        results["tests"].append({
            "name": "capacity_check",
            "passed": can_register,
            "detail": f"Active: {self.registry.active_count()}/{DynamicRegistry.MAX_AGENTS}"
        })
        if not can_register:
            results["passed"] = False

        return results

    # ─── Phase 2: 人工确认 ───

    def submit_for_approval(self, design: Dict, test_result: Dict) -> Dict:
        """
        提交设计等待人工确认
        
        保存到 pending 列表，等待 approve() 或 reject()
        """
        suggestion = {
            "id": f"suggestion-{int(time.time() * 1000)}",
            "design": design,
            "test_result": test_result,
            "submitted_at": datetime.now().isoformat(),
            "status": "pending"
        }

        self.state["suggestions_pending"].append(suggestion)
        self._save_state()

        return suggestion

    def list_pending(self) -> List[Dict]:
        """列出待确认的建议"""
        return [s for s in self.state.get("suggestions_pending", []) if s.get("status") == "pending"]

    def approve(self, suggestion_id: str) -> Dict:
        """批准建议，创建 Agent"""
        for suggestion in self.state["suggestions_pending"]:
            if suggestion["id"] == suggestion_id and suggestion["status"] == "pending":
                design = suggestion["design"]

                # 注册到 DynamicRegistry
                result = self.registry.register(
                    design["agent_id"],
                    design["config"]
                )

                if result["ok"]:
                    suggestion["status"] = "approved"
                    suggestion["approved_at"] = datetime.now().isoformat()
                    self.state["agents_created"] = self.state.get("agents_created", 0) + 1

                    # 移到历史
                    self.state["suggestions_history"].append(suggestion)
                    self.state["suggestions_pending"] = [
                        s for s in self.state["suggestions_pending"]
                        if s["id"] != suggestion_id
                    ]
                    self._save_state()

                    return {"ok": True, "agent_id": design["agent_id"], "message": f"Agent '{design['config']['name']}' 已创建"}
                else:
                    return {"ok": False, "error": result.get("error", "Registration failed")}

        return {"ok": False, "error": f"Suggestion {suggestion_id} not found or not pending"}

    def reject(self, suggestion_id: str, reason: str = "") -> Dict:
        """拒绝建议"""
        for suggestion in self.state["suggestions_pending"]:
            if suggestion["id"] == suggestion_id and suggestion["status"] == "pending":
                suggestion["status"] = "rejected"
                suggestion["rejected_at"] = datetime.now().isoformat()
                suggestion["reject_reason"] = reason
                self.state["agents_rejected"] = self.state.get("agents_rejected", 0) + 1

                self.state["suggestions_history"].append(suggestion)
                self.state["suggestions_pending"] = [
                    s for s in self.state["suggestions_pending"]
                    if s["id"] != suggestion_id
                ]
                self._save_state()

                return {"ok": True, "message": f"Suggestion {suggestion_id} rejected"}

        return {"ok": False, "error": f"Suggestion {suggestion_id} not found or not pending"}

    # ─── Phase 3: 心跳集成 ───

    def heartbeat(self) -> str:
        """
        心跳入口 - 每天检查一次缺口
        
        Returns:
            "META_AGENT_OK" - 无缺口
            "META_AGENT_SUGGESTION:N" - 发现 N 个缺口建议
        """
        # 频率控制：每天最多一次
        last_scan = self.state.get("last_scan")
        if last_scan:
            try:
                last_time = datetime.fromisoformat(last_scan)
                if datetime.now() - last_time < timedelta(hours=24):
                    # 检查是否有待处理的建议
                    pending = self.list_pending()
                    if pending:
                        return f"META_AGENT_PENDING:{len(pending)}"
                    return "META_AGENT_OK"
            except ValueError:
                pass

        # 执行缺口检测
        gaps = self.detect_gaps()
        self.state["last_scan"] = datetime.now().isoformat()

        if not gaps:
            self._save_state()
            return "META_AGENT_OK"

        # 为每个缺口设计 Agent
        suggestions_count = 0
        for gap in gaps:
            # 只处理 medium/high 严重度的缺口
            if gap.get("severity", "low") == "low":
                continue

            design = self.design_agent(gap)
            if not design:
                continue

            # 沙盒测试
            test_result = self.sandbox_test(design)
            if not test_result["passed"]:
                continue

            # 提交审批
            self.submit_for_approval(design, test_result)
            suggestions_count += 1

        self._save_state()

        if suggestions_count > 0:
            return f"META_AGENT_SUGGESTION:{suggestions_count}"
        return "META_AGENT_OK"

    def format_pending_report(self) -> str:
        """格式化待审批报告（给人看的）"""
        pending = self.list_pending()
        if not pending:
            return "没有待审批的 Agent 建议。"

        lines = [f"📋 Meta-Agent 建议 ({len(pending)} 个待审批)：\n"]

        for i, s in enumerate(pending, 1):
            design = s["design"]
            config = design["config"]
            gap = design.get("gap", {})

            lines.append(f"{i}. [{s['id']}]")
            lines.append(f"   类型: {config.get('type', '?')}")
            lines.append(f"   名称: {config.get('name', '?')}")
            lines.append(f"   原因: {gap.get('description', '?')}")
            lines.append(f"   来源: {design.get('source', '?')}")
            lines.append(f"   风险: {design.get('risk_level', '?')}")
            lines.append(f"   模型: {config.get('model', '?')}")
            lines.append("")

        lines.append("回复 'approve <id>' 批准，'reject <id>' 拒绝")
        return "\n".join(lines)

    def get_status(self) -> Dict:
        """获取 Meta-Agent 状态"""
        return {
            "last_scan": self.state.get("last_scan"),
            "pending_suggestions": len(self.list_pending()),
            "agents_created": self.state.get("agents_created", 0),
            "agents_rejected": self.state.get("agents_rejected", 0),
            "total_suggestions": len(self.state.get("suggestions_history", [])),
            "registry_stats": self.registry.get_stats()
        }


# ─── CLI 入口 ───

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Meta-Agent - AIOS Agent Factory")
    parser.add_argument("action", choices=["scan", "heartbeat", "pending", "approve", "reject", "status", "cleanup"],
                        help="Action to perform")
    parser.add_argument("--id", help="Suggestion ID (for approve/reject)")
    parser.add_argument("--reason", default="", help="Rejection reason")
    parser.add_argument("--idle-hours", type=int, default=24, help="Idle hours for cleanup")

    args = parser.parse_args()
    meta = MetaAgent()

    if args.action == "scan":
        gaps = meta.detect_gaps()
        if gaps:
            print(f"发现 {len(gaps)} 个缺口：")
            for g in gaps:
                print(f"  [{g['severity']}] {g['description']}")
        else:
            print("没有发现缺口。")

    elif args.action == "heartbeat":
        result = meta.heartbeat()
        print(result)

    elif args.action == "pending":
        print(meta.format_pending_report())

    elif args.action == "approve":
        if not args.id:
            print("需要 --id 参数")
            return
        result = meta.approve(args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "reject":
        if not args.id:
            print("需要 --id 参数")
            return
        result = meta.reject(args.id, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "status":
        status = meta.get_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))

    elif args.action == "cleanup":
        cleaned = meta.registry.cleanup_idle(args.idle_hours)
        if cleaned:
            print(f"清理了 {len(cleaned)} 个闲置 Agent: {cleaned}")
        else:
            print("没有需要清理的 Agent。")


if __name__ == "__main__":
    main()

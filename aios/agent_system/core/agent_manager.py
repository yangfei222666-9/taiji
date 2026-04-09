"""
AIOS Agent Manager - 自主 Agent 管理系统

负责 Agent 的创建、监控、优化和清理
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from .status_adapter import get_agent_status
from datetime import datetime, timedelta


class AgentManager:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # 优先使用相对路径，支持 TaijiOS 独立运行
            data_dir = (
                Path(__file__).parent.parent
                / "data"
            )
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.agents_file = self.data_dir / "agents.jsonl"
        self.templates_file = (
            Path(__file__).parent.parent / "templates" / "templates.json"
        )

        self.agents: Dict[str, Dict] = {}
        self.templates: Dict[str, Dict] = {}

        self._load_templates()
        self._load_agents()

    def _load_templates(self):
        """加载 Agent 模板"""
        if self.templates_file.exists():
            with open(self.templates_file, "r", encoding="utf-8") as f:
                self.templates = json.load(f)

    def _load_agents(self):
        """从 JSONL 加载现有 Agent"""
        if not self.agents_file.exists():
            return

        with open(self.agents_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    agent = json.loads(line)
                    self.agents[agent["id"]] = agent

    def _save_agent(self, agent: Dict):
        """保存 Agent 到 JSONL"""
        with open(self.agents_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(agent, ensure_ascii=False) + "\n")

    def _update_agent(self, agent_id: str, updates: Dict):
        """更新 Agent 配置"""
        if agent_id in self.agents:
            self.agents[agent_id].update(updates)
            self.agents[agent_id]["updated_at"] = datetime.now().isoformat()

            # 重写整个文件
            with open(self.agents_file, "w", encoding="utf-8") as f:
                for agent in self.agents.values():
                    f.write(json.dumps(agent, ensure_ascii=False) + "\n")

    def create_agent(self, template_name: str, task_description: str = None) -> Dict:
        """
        根据模板创建新 Agent

        Args:
            template_name: 模板名称 (coder/analyst/monitor/researcher)
            task_description: 任务描述（可选，用于定制化）

        Returns:
            创建的 Agent 配置
        """
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = self.templates[template_name]

        # 生成唯一 ID
        agent_id = f"{template_name}-{int(time.time() * 1000) % 1000000:06d}"

        # 创建 Agent 配置
        agent = {
            "id": agent_id,
            "template": template_name,
            "name": template["name"],
            "description": template["description"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "active",
            "workspace": f"agents/{agent_id}",
            "skills": template.get("skills", []),
            "tools": template.get("tools", {}),
            "system_prompt": template["system_prompt"],
            "model": template.get("model", "claude-sonnet-4-5"),
            "thinking": template.get("thinking", "off"),
            "stats": {
                "tasks_completed": 0,
                "tasks_failed": 0,
                "success_rate": 0.0,
                "avg_duration_sec": 0,
                "total_duration_sec": 0,
                "last_active": None,
            },
            "task_description": task_description,
        }

        self.agents[agent_id] = agent
        self._save_agent(agent)

        return agent

    def list_agents(self, status: str = None, template: str = None) -> List[Dict]:
        """
        列出 Agent

        Args:
            status: 过滤状态 (active/idle/archived)
            template: 过滤模板类型

        Returns:
            Agent 列表
        """
        agents = list(self.agents.values())

        if status:
            agents = [a for a in agents if a.get("status") == status]

        if template:
            agents = [a for a in agents if a.get("template") == template]

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取 Agent 配置"""
        return self.agents.get(agent_id)

    def update_stats(self, agent_id: str, success: bool, duration_sec: float):
        """
        更新 Agent 统计信息

        Args:
            agent_id: Agent ID
            success: 任务是否成功
            duration_sec: 任务耗时（秒）
        """
        if agent_id not in self.agents:
            return

        agent = self.agents[agent_id]
        stats = agent["stats"]

        if success:
            stats["tasks_completed"] += 1
        else:
            stats["tasks_failed"] += 1

        total_tasks = stats["tasks_completed"] + stats["tasks_failed"]
        stats["success_rate"] = (
            stats["tasks_completed"] / total_tasks if total_tasks > 0 else 0.0
        )

        stats["total_duration_sec"] += duration_sec
        stats["avg_duration_sec"] = (
            stats["total_duration_sec"] / total_tasks if total_tasks > 0 else 0
        )
        stats["last_active"] = datetime.now().isoformat()

        self._update_agent(agent_id, {"stats": stats})

    def archive_agent(self, agent_id: str, reason: str = None):
        """
        归档 Agent

        Args:
            agent_id: Agent ID
            reason: 归档原因
        """
        if agent_id not in self.agents:
            return

        updates = {
            "status": "archived",
            "archived_at": datetime.now().isoformat(),
            "archive_reason": reason,
        }

        self._update_agent(agent_id, updates)

    def find_idle_agents(self, idle_hours: int = 24) -> List[str]:
        """
        查找闲置 Agent

        Args:
            idle_hours: 闲置时长阈值（小时）

        Returns:
            闲置 Agent ID 列表
        """
        threshold = datetime.now() - timedelta(hours=idle_hours)
        idle_agents = []

        for agent_id, agent in self.agents.items():
            if get_agent_status(agent) != "active":
                continue

            last_active = agent["stats"].get("last_active")
            if not last_active:
                # 从未使用过的 Agent
                created_at = datetime.fromisoformat(agent["created_at"])
                if created_at < threshold:
                    idle_agents.append(agent_id)
            else:
                last_active_dt = datetime.fromisoformat(last_active)
                if last_active_dt < threshold:
                    idle_agents.append(agent_id)

        return idle_agents

    def get_agent_summary(self) -> Dict:
        """获取 Agent 系统摘要"""
        active = len([a for a in self.agents.values() if get_agent_status(a) == "active"])
        archived = len([a for a in self.agents.values() if get_agent_status(a) == "archived"])

        by_template = {}
        for agent in self.agents.values():
            if get_agent_status(agent) == "active":
                template = agent["template"]
                by_template[template] = by_template.get(template, 0) + 1

        total_tasks = sum(
            a["stats"].get("tasks_completed", 0) + a["stats"].get("tasks_failed", 0)
            for a in self.agents.values()
        )

        return {
            "total_agents": len(self.agents),
            "active": active,
            "archived": archived,
            "by_template": by_template,
            "total_tasks_processed": total_tasks,
        }


if __name__ == "__main__":
    # 测试
    manager = AgentManager()

    # 创建测试 Agent
    agent = manager.create_agent("coder", "实现一个 Python 爬虫")
    print(f"Created agent: {agent['id']}")

    # 列出所有 Agent
    agents = manager.list_agents()
    print(f"\nTotal agents: {len(agents)}")

    # 获取摘要
    summary = manager.get_agent_summary()
    print(f"\nSummary: {json.dumps(summary, indent=2, ensure_ascii=False)}")

"""
Dynamic Registry - 运行时 Agent 注册与管理

功能：
1. 运行时注册/注销 Agent
2. Agent 数量上限控制（max 15）
3. 自动清理闲置 Agent
4. Agent 能力查询
5. 与 agent_configs.json 同步
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class DynamicRegistry:
    """运行时 Agent 注册表"""

    MAX_AGENTS = 15

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = Path(workspace or Path.home() / ".openclaw" / "workspace")
        self.data_dir = self.workspace / "aios" / "agent_system" / "data"
        self.registry_file = self.data_dir / "dynamic_registry.json"
        self.configs_file = self.data_dir / "agent_configs.json"
        self.templates_file = self.workspace / "aios" / "agent_system" / "agent_templates.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._registry = self._load_registry()

    def _load_registry(self) -> Dict:
        """加载注册表"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"agents": {}, "created_at": datetime.now().isoformat(), "version": "1.0"}

    def _save_registry(self):
        """保存注册表"""
        self._registry["updated_at"] = datetime.now().isoformat()
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, ensure_ascii=False, indent=2)

    def _load_templates(self) -> Dict:
        """加载模板库"""
        if self.templates_file.exists():
            try:
                with open(self.templates_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"templates": {}}

    def active_count(self) -> int:
        """当前活跃 Agent 数量"""
        return sum(
            1 for a in self._registry["agents"].values()
            if a.get("status") == "active"
        )

    def can_register(self) -> bool:
        """是否还能注册新 Agent"""
        return self.active_count() < self.MAX_AGENTS

    def register(self, agent_id: str, config: Dict) -> Dict:
        """
        注册新 Agent
        
        Returns:
            {"ok": True, "agent_id": ...} 或 {"ok": False, "error": ...}
        """
        # 检查上限
        if not self.can_register():
            return {
                "ok": False,
                "error": f"Agent limit reached ({self.MAX_AGENTS}). Clean up idle agents first.",
                "active_count": self.active_count()
            }

        # 检查重复
        if agent_id in self._registry["agents"]:
            existing = self._registry["agents"][agent_id]
            if existing.get("status") == "active":
                return {"ok": False, "error": f"Agent {agent_id} already registered and active"}

        # 注册
        self._registry["agents"][agent_id] = {
            "status": "active",
            "config": config,
            "registered_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "tasks_completed": 0,
            "tasks_failed": 0,
            "created_by": config.get("created_by", "manual"),
            "source": config.get("source", "template")
        }

        self._save_registry()
        self._sync_to_configs(agent_id, config)

        return {"ok": True, "agent_id": agent_id, "active_count": self.active_count()}

    def unregister(self, agent_id: str, reason: str = "manual") -> Dict:
        """注销 Agent"""
        if agent_id not in self._registry["agents"]:
            return {"ok": False, "error": f"Agent {agent_id} not found"}

        self._registry["agents"][agent_id]["status"] = "removed"
        self._registry["agents"][agent_id]["removed_at"] = datetime.now().isoformat()
        self._registry["agents"][agent_id]["remove_reason"] = reason
        self._save_registry()

        # 从 configs 中移除
        self._remove_from_configs(agent_id)

        return {"ok": True, "agent_id": agent_id}

    def update_activity(self, agent_id: str, success: bool = True):
        """更新 Agent 活动状态"""
        if agent_id in self._registry["agents"]:
            agent = self._registry["agents"][agent_id]
            agent["last_active"] = datetime.now().isoformat()
            if success:
                agent["tasks_completed"] = agent.get("tasks_completed", 0) + 1
            else:
                agent["tasks_failed"] = agent.get("tasks_failed", 0) + 1
            self._save_registry()

    def cleanup_idle(self, idle_hours: int = 24) -> List[str]:
        """清理闲置 Agent"""
        cutoff = datetime.now() - timedelta(hours=idle_hours)
        cleaned = []

        for agent_id, agent in list(self._registry["agents"].items()):
            if agent.get("status") != "active":
                continue

            last_active = datetime.fromisoformat(agent.get("last_active", agent["registered_at"]))
            if last_active < cutoff:
                # 保护核心 Agent（不自动清理）
                if agent.get("config", {}).get("protected", False):
                    continue

                self.unregister(agent_id, reason=f"idle>{idle_hours}h")
                cleaned.append(agent_id)

        return cleaned

    def list_agents(self, status: str = "active") -> List[Dict]:
        """列出 Agent"""
        result = []
        for agent_id, agent in self._registry["agents"].items():
            if status == "all" or agent.get("status") == status:
                result.append({"id": agent_id, **agent})
        return result

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取 Agent 信息"""
        if agent_id in self._registry["agents"]:
            return {"id": agent_id, **self._registry["agents"][agent_id]}
        return None

    def find_by_type(self, agent_type: str) -> List[Dict]:
        """按类型查找活跃 Agent"""
        return [
            {"id": aid, **a}
            for aid, a in self._registry["agents"].items()
            if a.get("status") == "active"
            and a.get("config", {}).get("type") == agent_type
        ]

    def find_by_capability(self, capability: str) -> List[Dict]:
        """按能力查找 Agent"""
        results = []
        for aid, a in self._registry["agents"].items():
            if a.get("status") != "active":
                continue
            triggers = a.get("config", {}).get("triggers", [])
            if capability.lower() in [t.lower() for t in triggers]:
                results.append({"id": aid, **a})
        return results

    def get_stats(self) -> Dict:
        """注册表统计"""
        agents = self._registry["agents"]
        active = [a for a in agents.values() if a.get("status") == "active"]
        removed = [a for a in agents.values() if a.get("status") == "removed"]

        return {
            "total_registered": len(agents),
            "active": len(active),
            "removed": len(removed),
            "max_agents": self.MAX_AGENTS,
            "slots_available": self.MAX_AGENTS - len(active),
            "total_tasks": sum(a.get("tasks_completed", 0) + a.get("tasks_failed", 0) for a in active),
            "avg_success_rate": self._calc_avg_success_rate(active)
        }

    def _calc_avg_success_rate(self, agents: List[Dict]) -> float:
        """计算平均成功率"""
        rates = []
        for a in agents:
            total = a.get("tasks_completed", 0) + a.get("tasks_failed", 0)
            if total > 0:
                rates.append(a.get("tasks_completed", 0) / total)
        return round(sum(rates) / len(rates), 3) if rates else 0.0

    def _sync_to_configs(self, agent_id: str, config: Dict):
        """同步到 agent_configs.json"""
        try:
            data = {}
            if self.configs_file.exists():
                with open(self.configs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if "agents" not in data:
                data["agents"] = {}

            data["agents"][agent_id] = {
                "priority": 0.125,
                "env": config.get("env", "prod"),
                "type": config.get("type", "default"),
                "timeout": config.get("timeout", 100),
                "role": config.get("role", ""),
                "goal": config.get("goal", ""),
                "backstory": config.get("backstory", "")
            }

            with open(self.configs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 非关键操作，静默失败

    def _remove_from_configs(self, agent_id: str):
        """从 agent_configs.json 移除"""
        try:
            if not self.configs_file.exists():
                return
            with open(self.configs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if agent_id in data.get("agents", {}):
                del data["agents"][agent_id]
                with open(self.configs_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


if __name__ == "__main__":
    registry = DynamicRegistry()
    stats = registry.get_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))

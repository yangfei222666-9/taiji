"""
AIOS Auto Evolution - 心跳集成模块

安全阀机制：
1. 频率控制（每天一次或每 6 小时一次）
2. 熔断（防反复进化/失败回滚）
3. 输出三种结果：EVOLUTION_OK / EVOLUTION_APPLIED:N / EVOLUTION_ROLLED_BACK:N
"""

import json
import time
from pathlib import Path
from datetime import datetime


class EvolutionHeartbeat:
    """进化系统心跳集成"""

    def __init__(self):
        # 使用脚本所在目录的相对路径，避免硬编码 ~/.openclaw
        _data_dir = Path(__file__).parent / "data" / "evolution"
        _data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = _data_dir / "evolution_state.json"

        self.state = self.load_state()

    def load_state(self):
        """加载状态"""
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "last_run_ts": 0,
            "cooldown_until_ts": 0,
            "applied_history": [],
            "rollback_history": []
        }

    def save_state(self):
        """保存状态"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def should_run(self, interval_hours: int = 24) -> bool:
        """
        检查是否应该运行

        Args:
            interval_hours: 运行间隔（小时），默认 24 小时

        Returns:
            是否应该运行
        """
        now = int(time.time())
        
        # 1.1 频率控制
        if now - self.state["last_run_ts"] < interval_hours * 3600:
            return False
        
        # 1.2 熔断（冷却期）
        if now < self.state["cooldown_until_ts"]:
            return False
        
        return True

    def check_repeated_evolution(self, agent_id: str, lookback_hours: int = 24) -> bool:
        """
        检查是否反复进化同一个 Agent

        Args:
            agent_id: Agent ID
            lookback_hours: 回溯时间（小时）

        Returns:
            是否反复进化
        """
        cutoff_ts = int(time.time()) - (lookback_hours * 3600)
        
        recent_applied = [
            item for item in self.state["applied_history"]
            if item["agent_id"] == agent_id and item["timestamp"] > cutoff_ts
        ]
        
        # 24h 内对同一个 Agent 应用超过 1 次，认为反复进化
        if len(recent_applied) > 1:
            return True
        
        # 检查回滚历史，如果 24h 内回滚过，也禁止再次应用
        recent_rollback = [
            item for item in self.state.get("rollback_history", [])
            if item["agent_id"] == agent_id and item["timestamp"] > cutoff_ts
        ]
        
        if len(recent_rollback) > 0:
            # 触发冷却期
            cooldown_hours = 24
            self.state["cooldown_until_ts"] = int(time.time()) + (cooldown_hours * 3600)
            self.save_state()
            return True
        
        return False

    def run_evolution(self, interval_hours: int = 24) -> dict:
        """
        运行进化（心跳入口）

        Args:
            interval_hours: 运行间隔（小时）

        Returns:
            {
                'status': 'ok' | 'applied' | 'rolled_back' | 'skipped',
                'count': int,
                'message': str
            }
        """
        try:
            from .evolution_events import get_emitter
        except ImportError:
            from evolution_events import get_emitter
        emitter = get_emitter()

        # 检查是否应该运行
        if not self.should_run(interval_hours):
            remaining = self.state["cooldown_until_ts"] - int(time.time())
            if remaining > 0:
                return {
                    "status": "skipped",
                    "count": 0,
                    "message": f"熔断中，剩余 {remaining // 3600}h {(remaining % 3600) // 60}m"
                }
            else:
                return {
                    "status": "skipped",
                    "count": 0,
                    "message": f"距离上次运行不足 {interval_hours}h"
                }

        # 更新运行时间
        self.state["last_run_ts"] = int(time.time())
        self.save_state()

        # 获取所有 active Agents
        try:
            from .core.agent_manager import AgentManager
            from .auto_evolution import AutoEvolution
        except ImportError:
            from core.agent_manager import AgentManager
            from auto_evolution import AutoEvolution
        
        agent_manager = AgentManager()
        auto_evolution = AutoEvolution()
        
        agents = agent_manager.list_agents(status="active")
        
        if not agents:
            return {
                "status": "ok",
                "count": 0,
                "message": "无 active Agent"
            }

        applied_count = 0
        rolled_back_count = 0
        pending_review = []
        
        for agent in agents:
            agent_id = agent["id"]
            
            # 检查是否反复进化
            if self.check_repeated_evolution(agent_id, lookback_hours=24):
                print(f"[WARN] {agent_id} 24h 内已进化过，跳过")
                
                # 发送阻止事件
                emitter.emit_blocked(
                    agent_id=agent_id,
                    reason="24h 内已进化或回滚过，触发冷却期"
                )
                continue
            
            # 尝试自动进化
            result = auto_evolution.auto_evolve(agent_id, agent_manager)
            
            if result["status"] == "applied":
                applied_count += len(result["plans"])
                
                # 记录应用历史
                for plan in result["plans"]:
                    self.state["applied_history"].append({
                        "agent_id": agent_id,
                        "timestamp": int(time.time()),
                        "action": plan["action"],
                        "changes": plan["changes"]
                    })
                
                print(f"[OK] {agent_id} 应用了 {len(result['plans'])} 个进化改进")
            
            elif result["status"] == "pending_review":
                # 记录需要审核的策略
                pending_review.append({
                    "agent_id": agent_id,
                    "strategies": result.get("strategies", [])
                })

        # 保存状态
        self.state["pending_review"] = pending_review
        self.save_state()

        # 返回结果
        if applied_count > 0:
            return {
                "status": "applied",
                "count": applied_count,
                "pending_review": len(pending_review),
                "message": f"应用了 {applied_count} 个低风险改进"
            }
        elif rolled_back_count > 0:
            return {
                "status": "rolled_back",
                "count": rolled_back_count,
                "message": f"回滚了 {rolled_back_count} 个失败的进化"
            }
        elif len(pending_review) > 0:
            return {
                "status": "pending_review",
                "count": len(pending_review),
                "pending_review": pending_review,
                "message": f"{len(pending_review)} 个策略需要人工审核"
            }
        else:
            return {
                "status": "ok",
                "count": 0,
                "message": "无需进化"
            }

    def trigger_cooldown(self, hours: int = 6):
        """
        触发熔断（冷却期）

        Args:
            hours: 冷却时长（小时）
        """
        self.state["cooldown_until_ts"] = int(time.time()) + (hours * 3600)
        self.save_state()


def main():
    """心跳入口"""
    heartbeat = EvolutionHeartbeat()
    
    # 默认每天运行一次
    result = heartbeat.run_evolution(interval_hours=24)
    
    # 输出结果（格式化简报）
    if result["status"] == "applied":
        # 格式：EVOLUTION_APPLIED:N (action1, action2, ...)
        actions = []
        for item in heartbeat.state.get("applied_history", [])[-result["count"]:]:
            actions.append(item.get("action", "unknown"))
        
        actions_str = ", ".join(set(actions))  # 去重
        
        # 如果有需要审核的，也输出
        if result.get("pending_review", 0) > 0:
            print(f"EVOLUTION_APPLIED:{result['count']} ({actions_str})")
            print(f"EVOLUTION_PENDING:{result['pending_review']} (needs_approval)")
        else:
            print(f"EVOLUTION_APPLIED:{result['count']} ({actions_str})")
    
    elif result["status"] == "pending_review":
        # 只有需要审核的
        print(f"EVOLUTION_PENDING:{result['count']} (needs_approval)")
    
    elif result["status"] == "rolled_back":
        print(f"EVOLUTION_ROLLBACK:{result['count']}")
    
    elif result["status"] == "skipped":
        # 不输出，保持静默
        print("EVOLUTION_OK")
    
    else:
        print("EVOLUTION_OK")


if __name__ == "__main__":
    main()

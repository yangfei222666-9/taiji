"""
AIOS Agent Arena - AIOS 和 Agent 对抗系统
让 AIOS 和 Agent 互相挑战，通过对抗来进化

对抗模式：
1. AIOS 提出挑战 → Agent 尝试解决
2. Agent 提出问题 → AIOS 尝试修复
3. 双方互相学习对方的策略
4. 用户作为裁判，决定谁赢
"""
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from enum import Enum


class ChallengeType(Enum):
    """挑战类型"""
    PERFORMANCE = "performance"  # 性能挑战
    RELIABILITY = "reliability"  # 可靠性挑战
    CREATIVITY = "creativity"    # 创造力挑战
    EFFICIENCY = "efficiency"    # 效率挑战
    PROBLEM_SOLVING = "problem_solving"  # 解决问题


class ArenaMode(Enum):
    """对抗模式"""
    AIOS_ATTACK = "aios_attack"      # AIOS 攻击，Agent 防守
    AGENT_ATTACK = "agent_attack"    # Agent 攻击，AIOS 防守
    COLLABORATIVE = "collaborative"   # 协作模式
    COMPETITIVE = "competitive"       # 竞争模式


class AgentArena:
    """Agent 对抗竞技场"""
    
    def __init__(self, workspace: Path = None):
        """
        初始化
        
        Args:
            workspace: 工作目录
        """
        if workspace is None:
            workspace = Path(__file__).parent.parent.parent
        
        self.workspace = Path(workspace)
        self.arena_dir = self.workspace / "aios" / "arena"
        self.arena_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据文件
        self.challenges_file = self.arena_dir / "challenges.jsonl"
        self.battles_file = self.arena_dir / "battles.jsonl"
        self.leaderboard_file = self.arena_dir / "leaderboard.json"
        
        # 初始化排行榜
        self.leaderboard = self._load_leaderboard()
    
    # ========== AIOS 攻击模式 ==========
    
    def aios_challenge_agent(self, challenge_type: ChallengeType) -> Dict:
        """
        AIOS 向 Agent 发起挑战
        
        Args:
            challenge_type: 挑战类型
        
        Returns:
            挑战内容
        """
        challenges = {
            ChallengeType.PERFORMANCE: {
                "title": "性能挑战：在 10 秒内完成 100 个任务",
                "description": "AIOS 挑战 Agent：能否在 10 秒内处理 100 个并发任务？",
                "task": "spawn_100_agents",
                "time_limit": 10,
                "success_criteria": "所有任务成功完成"
            },
            ChallengeType.RELIABILITY: {
                "title": "可靠性挑战：在 502 错误下保持 95% 成功率",
                "description": "AIOS 挑战 Agent：面对持续的 502 错误，能否保持 95% 的成功率？",
                "task": "handle_502_errors",
                "error_rate": 0.5,
                "success_criteria": "成功率 >= 95%"
            },
            ChallengeType.CREATIVITY: {
                "title": "创造力挑战：用 3 种不同方法解决同一个问题",
                "description": "AIOS 挑战 Agent：能否找到 3 种不同的解决方案？",
                "task": "solve_problem_creatively",
                "min_solutions": 3,
                "success_criteria": "至少 3 种不同方法"
            },
            ChallengeType.EFFICIENCY: {
                "title": "效率挑战：用最少的资源完成任务",
                "description": "AIOS 挑战 Agent：能否用最少的 token 和时间完成任务？",
                "task": "optimize_resource_usage",
                "max_tokens": 1000,
                "max_time": 5,
                "success_criteria": "资源使用 < 阈值"
            },
            ChallengeType.PROBLEM_SOLVING: {
                "title": "问题解决挑战：修复 5 个不同类型的错误",
                "description": "AIOS 挑战 Agent：能否在 5 分钟内修复 5 个不同的错误？",
                "task": "fix_multiple_errors",
                "error_count": 5,
                "time_limit": 300,
                "success_criteria": "所有错误修复"
            }
        }
        
        challenge = challenges.get(challenge_type, challenges[ChallengeType.PERFORMANCE])
        challenge["id"] = f"aios-{int(time.time())}"
        challenge["type"] = challenge_type.value
        challenge["mode"] = ArenaMode.AIOS_ATTACK.value
        challenge["created_at"] = datetime.now().isoformat()
        challenge["status"] = "pending"
        
        # 记录挑战
        self._record_challenge(challenge)
        
        return challenge
    
    # ========== Agent 攻击模式 ==========
    
    def agent_challenge_aios(self, challenge_type: ChallengeType) -> Dict:
        """
        Agent 向 AIOS 发起挑战
        
        Args:
            challenge_type: 挑战类型
        
        Returns:
            挑战内容
        """
        challenges = {
            ChallengeType.PERFORMANCE: {
                "title": "性能挑战：AIOS 能否在 1 秒内响应 1000 个事件？",
                "description": "Agent 挑战 AIOS：能否快速处理大量事件？",
                "task": "handle_1000_events",
                "time_limit": 1,
                "success_criteria": "所有事件处理完成"
            },
            ChallengeType.RELIABILITY: {
                "title": "可靠性挑战：AIOS 能否在系统降级时保持运行？",
                "description": "Agent 挑战 AIOS：在 CPU 90%、内存 95% 的情况下能否正常工作？",
                "task": "survive_resource_pressure",
                "cpu_limit": 90,
                "memory_limit": 95,
                "success_criteria": "系统不崩溃"
            },
            ChallengeType.CREATIVITY: {
                "title": "创造力挑战：AIOS 能否设计出新的自动修复规则？",
                "description": "Agent 挑战 AIOS：能否根据历史数据创造新的 playbook？",
                "task": "create_new_playbook",
                "min_rules": 3,
                "success_criteria": "新规则有效"
            },
            ChallengeType.EFFICIENCY: {
                "title": "效率挑战：AIOS 能否优化自己的调度算法？",
                "description": "Agent 挑战 AIOS：能否让调度效率提升 20%？",
                "task": "optimize_scheduler",
                "improvement_target": 0.2,
                "success_criteria": "效率提升 >= 20%"
            },
            ChallengeType.PROBLEM_SOLVING: {
                "title": "问题解决挑战：AIOS 能否解决 Agent 故意制造的 10 个问题？",
                "description": "Agent 挑战 AIOS：我会制造 10 个不同的问题，你能全部解决吗？",
                "task": "solve_agent_problems",
                "problem_count": 10,
                "success_criteria": "所有问题解决"
            }
        }
        
        challenge = challenges.get(challenge_type, challenges[ChallengeType.PERFORMANCE])
        challenge["id"] = f"agent-{int(time.time())}"
        challenge["type"] = challenge_type.value
        challenge["mode"] = ArenaMode.AGENT_ATTACK.value
        challenge["created_at"] = datetime.now().isoformat()
        challenge["status"] = "pending"
        
        # 记录挑战
        self._record_challenge(challenge)
        
        return challenge
    
    # ========== 协作模式 ==========
    
    def collaborative_challenge(self) -> Dict:
        """
        协作挑战：AIOS 和 Agent 一起解决问题
        
        Returns:
            挑战内容
        """
        challenge = {
            "id": f"collab-{int(time.time())}",
            "title": "协作挑战：一起优化系统性能",
            "description": "AIOS 负责调度，Agent 负责执行，一起将系统性能提升 50%",
            "type": ChallengeType.EFFICIENCY.value,
            "mode": ArenaMode.COLLABORATIVE.value,
            "task": "optimize_together",
            "aios_role": "调度优化",
            "agent_role": "执行优化",
            "improvement_target": 0.5,
            "success_criteria": "性能提升 >= 50%",
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        self._record_challenge(challenge)
        
        return challenge
    
    # ========== 竞争模式 ==========
    
    def competitive_challenge(self) -> Dict:
        """
        竞争挑战：AIOS 和 Agent 比赛谁更快
        
        Returns:
            挑战内容
        """
        challenge = {
            "id": f"compete-{int(time.time())}",
            "title": "竞争挑战：谁能更快完成 50 个任务？",
            "description": "AIOS 和 Agent 同时开始，看谁先完成 50 个任务",
            "type": ChallengeType.PERFORMANCE.value,
            "mode": ArenaMode.COMPETITIVE.value,
            "task": "race_50_tasks",
            "task_count": 50,
            "success_criteria": "先完成者获胜",
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        self._record_challenge(challenge)
        
        return challenge
    
    # ========== 战斗记录 ==========
    
    def record_battle(
        self,
        challenge_id: str,
        winner: str,
        aios_score: float,
        agent_score: float,
        details: Dict = None
    ):
        """
        记录战斗结果
        
        Args:
            challenge_id: 挑战 ID
            winner: 获胜者（aios/agent/draw）
            aios_score: AIOS 得分
            agent_score: Agent 得分
            details: 详细信息
        """
        battle = {
            "challenge_id": challenge_id,
            "winner": winner,
            "aios_score": aios_score,
            "agent_score": agent_score,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.battles_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(battle, ensure_ascii=False) + "\n")
        
        # 更新排行榜
        self._update_leaderboard(winner, aios_score, agent_score)
    
    # ========== 排行榜 ==========
    
    def _update_leaderboard(self, winner: str, aios_score: float, agent_score: float):
        """更新排行榜"""
        if "aios" not in self.leaderboard:
            self.leaderboard["aios"] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_score": 0,
                "avg_score": 0
            }
        
        if "agent" not in self.leaderboard:
            self.leaderboard["agent"] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_score": 0,
                "avg_score": 0
            }
        
        # 更新胜负
        if winner == "aios":
            self.leaderboard["aios"]["wins"] += 1
            self.leaderboard["agent"]["losses"] += 1
        elif winner == "agent":
            self.leaderboard["agent"]["wins"] += 1
            self.leaderboard["aios"]["losses"] += 1
        else:
            self.leaderboard["aios"]["draws"] += 1
            self.leaderboard["agent"]["draws"] += 1
        
        # 更新得分
        self.leaderboard["aios"]["total_score"] += aios_score
        self.leaderboard["agent"]["total_score"] += agent_score
        
        # 计算平均分
        aios_total = (
            self.leaderboard["aios"]["wins"] +
            self.leaderboard["aios"]["losses"] +
            self.leaderboard["aios"]["draws"]
        )
        agent_total = (
            self.leaderboard["agent"]["wins"] +
            self.leaderboard["agent"]["losses"] +
            self.leaderboard["agent"]["draws"]
        )
        
        if aios_total > 0:
            self.leaderboard["aios"]["avg_score"] = (
                self.leaderboard["aios"]["total_score"] / aios_total
            )
        
        if agent_total > 0:
            self.leaderboard["agent"]["avg_score"] = (
                self.leaderboard["agent"]["total_score"] / agent_total
            )
        
        self._save_leaderboard()
    
    def get_leaderboard(self) -> Dict:
        """获取排行榜"""
        return self.leaderboard
    
    # ========== 辅助方法 ==========
    
    def _record_challenge(self, challenge: Dict):
        """记录挑战"""
        with open(self.challenges_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(challenge, ensure_ascii=False) + "\n")
    
    def _load_leaderboard(self) -> Dict:
        """加载排行榜"""
        if not self.leaderboard_file.exists():
            return {}
        
        with open(self.leaderboard_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_leaderboard(self):
        """保存排行榜"""
        with open(self.leaderboard_file, "w", encoding="utf-8") as f:
            json.dump(self.leaderboard, f, indent=2, ensure_ascii=False)
    
    def generate_arena_report(self) -> str:
        """生成竞技场报告"""
        report = []
        report.append("=" * 60)
        report.append("🥊 AIOS Agent Arena 排行榜")
        report.append("=" * 60)
        
        if not self.leaderboard:
            report.append("\n还没有战斗记录")
            return "\n".join(report)
        
        # AIOS 统计
        if "aios" in self.leaderboard:
            aios = self.leaderboard["aios"]
            report.append(f"\n🤖 AIOS:")
            report.append(f"  胜: {aios['wins']}, 负: {aios['losses']}, 平: {aios['draws']}")
            report.append(f"  平均得分: {aios['avg_score']:.2f}")
        
        # Agent 统计
        if "agent" in self.leaderboard:
            agent = self.leaderboard["agent"]
            report.append(f"\n👤 Agent:")
            report.append(f"  胜: {agent['wins']}, 负: {agent['losses']}, 平: {agent['draws']}")
            report.append(f"  平均得分: {agent['avg_score']:.2f}")
        
        # 判断领先者
        if "aios" in self.leaderboard and "agent" in self.leaderboard:
            aios_total = aios["wins"] - aios["losses"]
            agent_total = agent["wins"] - agent["losses"]
            
            if aios_total > agent_total:
                report.append(f"\n🏆 当前领先: AIOS (+{aios_total - agent_total})")
            elif agent_total > aios_total:
                report.append(f"\n🏆 当前领先: Agent (+{agent_total - aios_total})")
            else:
                report.append(f"\n🤝 当前平局")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


# 全局单例
_global_arena = None


def get_arena():
    """获取全局 Arena 实例"""
    global _global_arena
    if _global_arena is None:
        _global_arena = AgentArena()
    return _global_arena


if __name__ == "__main__":
    # 测试
    arena = get_arena()
    
    print("=" * 60)
    print("🥊 AIOS Agent Arena")
    print("=" * 60)
    
    # AIOS 发起挑战
    print("\n1. AIOS 发起性能挑战:")
    challenge1 = arena.aios_challenge_agent(ChallengeType.PERFORMANCE)
    print(f"   {challenge1['title']}")
    print(f"   {challenge1['description']}")
    
    # Agent 发起挑战
    print("\n2. Agent 发起可靠性挑战:")
    challenge2 = arena.agent_challenge_aios(ChallengeType.RELIABILITY)
    print(f"   {challenge2['title']}")
    print(f"   {challenge2['description']}")
    
    # 协作挑战
    print("\n3. 协作挑战:")
    challenge3 = arena.collaborative_challenge()
    print(f"   {challenge3['title']}")
    print(f"   {challenge3['description']}")
    
    # 竞争挑战
    print("\n4. 竞争挑战:")
    challenge4 = arena.competitive_challenge()
    print(f"   {challenge4['title']}")
    print(f"   {challenge4['description']}")
    
    # 模拟战斗结果
    print("\n5. 模拟战斗结果:")
    arena.record_battle(challenge1["id"], "agent", 85, 95)
    arena.record_battle(challenge2["id"], "aios", 90, 80)
    arena.record_battle(challenge3["id"], "draw", 95, 95)
    
    # 显示排行榜
    print("\n" + arena.generate_arena_report())

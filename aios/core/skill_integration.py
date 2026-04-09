"""
AIOS Skill Integration - 将 skill 集成到 AIOS 工作流
让 AIOS 能够自动调用 skill 来解决问题
"""
import sys
from pathlib import Path

# 添加路径
AIOS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(AIOS_ROOT))

from core.skill_manager import get_skill_manager
from typing import Dict, List, Any


class SkillIntegration:
    """Skill 集成"""
    
    def __init__(self):
        self.skill_manager = get_skill_manager()
        
        # Skill 映射：问题类型 → skill
        self.skill_mapping = {
            # 系统监控
            "resource_high": ["system-resource-monitor", "server-health"],
            "disk_full": ["file-organizer-skill"],
            
            # 安全
            "security_alert": ["hz-error-guard"],
            
            # 开发
            "code_review": ["github"],
            "test_failed": ["github"],
            
            # 自动化
            "automation_task": ["automation-workflows"],
            
            # 信息收集
            "news_update": ["ai-news-collectors", "news-summary"],
            "web_change": ["web-monitor"],
            "search_needed": ["tavily-search", "baidu-search"],
            
            # 任务管理
            "todo_check": ["todoist"],
            
            # 截图
            "screenshot_needed": ["screenshot"],
            
            # 系统管理
            "sysadmin_task": ["sysadmin-toolbox"],
            
            # Windows UI
            "ui_automation": ["windows-ui-automation"],
        }
    
    def suggest_skill(self, problem_type: str) -> List[str]:
        """
        根据问题类型推荐 skill
        
        Args:
            problem_type: 问题类型
        
        Returns:
            推荐的 skill 列表
        """
        return self.skill_mapping.get(problem_type, [])
    
    def auto_solve(self, problem_type: str, context: Dict = None) -> Dict:
        """
        自动解决问题（调用合适的 skill）
        
        Args:
            problem_type: 问题类型
            context: 上下文信息
        
        Returns:
            解决结果
        """
        # 获取推荐的 skill
        skills = self.suggest_skill(problem_type)
        
        if not skills:
            return {
                "success": False,
                "error": f"No skill available for: {problem_type}"
            }
        
        # 尝试每个 skill
        for skill_name in skills:
            print(f"[SkillIntegration] 尝试 skill: {skill_name}")
            
            # 调用 skill
            result = self.skill_manager.call_skill(
                skill_name,
                command=self._get_command(problem_type, context)
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "skill": skill_name,
                    "result": result
                }
        
        return {
            "success": False,
            "error": "All skills failed",
            "tried": skills
        }
    
    def _get_command(self, problem_type: str, context: Dict = None) -> str:
        """
        根据问题类型生成命令
        
        Args:
            problem_type: 问题类型
            context: 上下文
        
        Returns:
            命令
        """
        # 根据问题类型生成合适的命令
        command_mapping = {
            "resource_high": "check",
            "disk_full": "organize",
            "news_update": "fetch",
            "todo_check": "list",
            "screenshot_needed": "capture"
        }
        
        return command_mapping.get(problem_type, "run")
    
    def list_available_skills(self) -> List[Dict]:
        """列出所有可用的 skill"""
        return self.skill_manager.list_skills()
    
    def get_skill_for_event(self, event_type: str) -> List[str]:
        """
        根据事件类型获取 skill
        
        Args:
            event_type: 事件类型（如 "resource.cpu_spike"）
        
        Returns:
            skill 列表
        """
        # 事件类型 → 问题类型映射
        event_to_problem = {
            "resource.cpu_spike": "resource_high",
            "resource.memory_high": "resource_high",
            "resource.disk_full": "disk_full",
            "agent.error": "code_review",
            "sensor.news": "news_update",
            "sensor.web_change": "web_change"
        }
        
        problem_type = event_to_problem.get(event_type)
        
        if problem_type:
            return self.suggest_skill(problem_type)
        
        return []


# 全局单例
_global_integration = None


def get_skill_integration():
    """获取全局 Skill Integration 实例"""
    global _global_integration
    if _global_integration is None:
        _global_integration = SkillIntegration()
    return _global_integration


if __name__ == "__main__":
    # 测试
    integration = get_skill_integration()
    
    print("=" * 60)
    print("AIOS Skill Integration")
    print("=" * 60)
    
    # 测试推荐
    print("\n问题类型 → Skill 映射:")
    for problem_type in ["resource_high", "news_update", "code_review"]:
        skills = integration.suggest_skill(problem_type)
        print(f"  {problem_type}: {', '.join(skills)}")
    
    # 测试事件映射
    print("\n事件类型 → Skill 映射:")
    for event_type in ["resource.cpu_spike", "sensor.news", "agent.error"]:
        skills = integration.get_skill_for_event(event_type)
        print(f"  {event_type}: {', '.join(skills)}")
    
    print("\n" + "=" * 60)

"""
AIOS Skill Manager - 统一管理和调用所有 skill
让 AIOS 能够使用 OpenClaw 的所有 skill
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any


class SkillManager:
    """Skill 管理器"""
    
    def __init__(self, skills_dir: Path = None):
        """
        初始化
        
        Args:
            skills_dir: skill 目录
        """
        if skills_dir is None:
            workspace = Path(__file__).parent.parent.parent
            skills_dir = workspace / "skills"
        
        self.skills_dir = Path(skills_dir)
        self.skills = self._discover_skills()
    
    def _discover_skills(self) -> Dict[str, Dict]:
        """
        发现所有可用的 skill
        
        Returns:
            {skill_name: {path, description, ...}}
        """
        skills = {}
        
        if not self.skills_dir.exists():
            return skills
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            # 读取 SKILL.md 获取描述
            description = self._extract_description(skill_md)
            
            skills[skill_dir.name] = {
                "path": str(skill_dir),
                "description": description,
                "skill_md": str(skill_md)
            }
        
        return skills
    
    def _extract_description(self, skill_md: Path) -> str:
        """从 SKILL.md 提取描述"""
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
                # 提取第一段作为描述
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line[:200]  # 最多 200 字符
        except:
            pass
        
        return "No description"
    
    def list_skills(self) -> List[Dict]:
        """
        列出所有 skill
        
        Returns:
            skill 列表
        """
        return [
            {
                "name": name,
                "description": info["description"]
            }
            for name, info in self.skills.items()
        ]
    
    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """
        获取 skill 信息
        
        Args:
            skill_name: skill 名称
        
        Returns:
            skill 信息
        """
        return self.skills.get(skill_name)
    
    def call_skill(
        self,
        skill_name: str,
        command: str = None,
        args: List[str] = None
    ) -> Dict[str, Any]:
        """
        调用 skill
        
        Args:
            skill_name: skill 名称
            command: 命令（可选）
            args: 参数列表
        
        Returns:
            执行结果
        """
        skill_info = self.get_skill_info(skill_name)
        
        if not skill_info:
            return {
                "success": False,
                "error": f"Skill not found: {skill_name}"
            }
        
        skill_path = Path(skill_info["path"])
        
        # 查找可执行文件
        executable = self._find_executable(skill_path)
        
        if not executable:
            return {
                "success": False,
                "error": f"No executable found for skill: {skill_name}"
            }
        
        # 构建命令
        cmd = [str(executable)]
        if command:
            cmd.append(command)
        if args:
            cmd.extend(args)
        
        # 执行
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(skill_path)
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Skill execution timeout (30s)"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_executable(self, skill_path: Path) -> Optional[Path]:
        """
        查找 skill 的可执行文件
        
        Args:
            skill_path: skill 目录
        
        Returns:
            可执行文件路径
        """
        # 优先级：
        # 1. skill.py
        # 2. main.py
        # 3. index.js
        # 4. skill.sh / skill.bat
        
        candidates = [
            skill_path / "skill.py",
            skill_path / "main.py",
            skill_path / "index.js",
            skill_path / "skill.sh",
            skill_path / "skill.bat"
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate
        
        return None
    
    def search_skills(self, query: str) -> List[Dict]:
        """
        搜索 skill
        
        Args:
            query: 搜索关键词
        
        Returns:
            匹配的 skill 列表
        """
        query_lower = query.lower()
        results = []
        
        for name, info in self.skills.items():
            if query_lower in name.lower() or query_lower in info["description"].lower():
                results.append({
                    "name": name,
                    "description": info["description"]
                })
        
        return results
    
    def get_skill_usage(self, skill_name: str) -> str:
        """
        获取 skill 使用说明
        
        Args:
            skill_name: skill 名称
        
        Returns:
            使用说明
        """
        skill_info = self.get_skill_info(skill_name)
        
        if not skill_info:
            return f"Skill not found: {skill_name}"
        
        skill_md = Path(skill_info["skill_md"])
        
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return "No usage documentation available"


# 全局单例
_global_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取全局 Skill Manager 实例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = SkillManager()
    return _global_manager


# 便捷函数
def list_skills() -> List[Dict]:
    """列出所有 skill"""
    return get_skill_manager().list_skills()


def call_skill(skill_name: str, command: str = None, args: List[str] = None) -> Dict:
    """调用 skill"""
    return get_skill_manager().call_skill(skill_name, command, args)


def search_skills(query: str) -> List[Dict]:
    """搜索 skill"""
    return get_skill_manager().search_skills(query)


if __name__ == "__main__":
    # 测试
    manager = get_skill_manager()
    
    print("=" * 60)
    print("AIOS Skill Manager")
    print("=" * 60)
    
    # 列出所有 skill
    skills = manager.list_skills()
    print(f"\n发现 {len(skills)} 个 skill:")
    for skill in skills[:10]:
        print(f"  - {skill['name']}: {skill['description'][:60]}...")
    
    if len(skills) > 10:
        print(f"  ... 还有 {len(skills) - 10} 个")
    
    # 搜索示例
    print("\n搜索 'monitor':")
    results = manager.search_skills("monitor")
    for result in results:
        print(f"  - {result['name']}")
    
    print("\n" + "=" * 60)

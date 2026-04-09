"""
AIOS Unified Registry v1.0
统一 Agent + Skill 注册中心

核心理念：
- Agent 和 Skill 是同一个东西的两面
- Skill = 能力定义（做什么、怎么做）
- Agent = 运行实例（谁来做、什么时候做）
- 一个 Skill 可以被多个 Agent 使用
- 一个 Agent 可以拥有多个 Skill

数据结构：
unified_registry.json = 唯一的真相来源（Single Source of Truth）
"""

import json
import os
from datetime import datetime
from pathlib import Path

from aios.agent_system.config_center import openclaw_workspace_root, skills_root

WORKSPACE = openclaw_workspace_root()
REGISTRY_PATH = WORKSPACE / "aios" / "agent_system" / "unified_registry.json"
SKILLS_DIR = skills_root()
OLD_AGENTS_JSON = WORKSPACE / "aios" / "agent_system" / "agents.json"
OLD_AGENTS_DATA = WORKSPACE / "aios" / "agent_system" / "agents_data.json"
OLD_DATA_AGENTS = WORKSPACE / "aios" / "agent_system" / "data" / "agents.json"


def scan_skills():
    """扫描所有 Skill 目录，提取元数据"""
    skills = {}
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        
        name = skill_dir.name
        # 解析 SKILL.md frontmatter
        desc = ""
        try:
            content = skill_md.read_text(encoding="utf-8")
            lines = content.split("\n")
            in_frontmatter = False
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter and line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip().strip("'\"")
        except Exception:
            pass
        
        # 检查是否有可执行脚本
        py_files = list(skill_dir.glob("*.py"))
        
        skills[name] = {
            "name": name,
            "path": str(skill_dir),
            "description": desc[:200] if desc else "",
            "has_script": len(py_files) > 0,
            "scripts": [f.name for f in py_files],
            "category": classify_skill(name, desc),
        }
    return skills


def classify_skill(name, desc):
    """自动分类"""
    text = f"{name} {desc}".lower()
    if any(k in text for k in ["monitor", "health", "resource", "server"]):
        return "monitoring"
    if any(k in text for k in ["aios", "agent", "self-improv", "evaluat", "quality", "data-collect"]):
        return "aios-core"
    if any(k in text for k in ["git", "docker", "api", "database", "code", "skill-creator"]):
        return "development"
    if any(k in text for k in ["automat", "workflow", "file-organ", "cron", "vm", "cloud"]):
        return "automation"
    if any(k in text for k in ["ui", "window", "screenshot"]):
        return "ui"
    if any(k in text for k in ["news", "search", "web", "tavily", "ripgrep", "find"]):
        return "information"
    if any(k in text for k in ["document", "todoist", "team", "deploy"]):
        return "productivity"
    return "other"


def load_old_agents():
    """加载所有旧 Agent 数据，去重合并"""
    all_agents = {}
    
    # 1. agents.json（skill-based agents）
    if OLD_AGENTS_JSON.exists():
        try:
            data = json.loads(OLD_AGENTS_JSON.read_text(encoding="utf-8"))
            for a in data.get("agents", []):
                aid = a.get("id") or a.get("name", "unknown")
                all_agents[aid] = a
        except Exception:
            pass
    
    # 2. agents_data.json（主要的 agent 数据）
    if OLD_AGENTS_DATA.exists():
        try:
            data = json.loads(OLD_AGENTS_DATA.read_text(encoding="utf-8"))
            for a in data.get("agents", []):
                aid = a.get("id", "unknown")
                all_agents[aid] = a
        except Exception:
            pass
    
    # 3. data/agents.json（dispatcher agents）
    if OLD_DATA_AGENTS.exists():
        try:
            data = json.loads(OLD_DATA_AGENTS.read_text(encoding="utf-8"))
            for a in data.get("agents", []):
                aid = a.get("id", "unknown")
                all_agents[aid] = a
        except Exception:
            pass
    
    return all_agents


def deduplicate_agents(agents):
    """去重：同功能只保留最新/最活跃的"""
    # 更精确的分组：按实际功能而非简单 type
    # 同名同功能才算重复
    groups = {}
    for aid, agent in agents.items():
        template = agent.get("template", agent.get("type", "unknown")).lower()
        name = agent.get("name", "").lower()
        goal = agent.get("goal", "")[:50].lower()
        skill_path = agent.get("skill_path", "")
        
        # Skill-based agent 用 skill_path 做 key（每个 Skill 独立）
        if skill_path:
            group_key = f"skill:{Path(skill_path).name}"
        # 有明确 task_types 的用 task_types 做 key
        elif agent.get("task_types"):
            group_key = f"role:{'-'.join(sorted(agent['task_types']))}"
        # GitHub learner 系列合并为一个 researcher
        elif "github-learner" in aid:
            group_key = "role:github-researcher"
        # learner 系列合并
        elif aid.startswith("learner-"):
            group_key = "role:learner"
        # intelligence 系列合并
        elif aid.startswith("intelligence-"):
            group_key = "role:intelligence"
        # 同 template + 类似名称
        else:
            group_key = f"type:{template}:{name[:10]}"
        
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append((aid, agent))
    
    kept = {}
    archived = {}
    
    for group_key, members in groups.items():
        if len(members) == 1:
            aid, agent = members[0]
            kept[aid] = agent
            continue
        
        # 多个同功能 Agent，选最佳
        best_id = None
        best_score = -1
        for aid, agent in members:
            stats = agent.get("stats", {})
            score = 0
            score += stats.get("tasks_completed", 0) * 10
            score += stats.get("success_rate", 0) * 5
            if agent.get("status") != "archived":
                score += 3
            if agent.get("task_types"):
                score += 2
            if agent.get("priority"):
                score += 1
            # 更新的 agent 加分
            created = agent.get("created_at", "")
            if "2026-02-26" in created:
                score += 2
            
            if score > best_score:
                best_score = score
                best_id = aid
        
        for aid, agent in members:
            if aid == best_id:
                kept[aid] = agent
            else:
                agent["_archive_reason"] = f"Duplicate of {best_id} (group: {group_key})"
                archived[aid] = agent
    
    return kept, archived


def build_unified_registry(skills, kept_agents, archived_agents):
    """构建统一注册表"""
    
    # 关联 Agent 和 Skill
    for aid, agent in kept_agents.items():
        agent_skills = agent.get("skills", [])
        # 尝试从 skill_path 推断
        skill_path = agent.get("skill_path", "")
        if skill_path:
            skill_name = Path(skill_path).name
            if skill_name not in agent_skills:
                agent_skills.append(skill_name)
        agent["skills"] = agent_skills
    
    registry = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "skills": skills,
        "agents": {
            "active": {},
            "archived": {},
        },
        "stats": {
            "total_skills": len(skills),
            "skills_with_scripts": sum(1 for s in skills.values() if s["has_script"]),
            "skills_doc_only": sum(1 for s in skills.values() if not s["has_script"]),
            "total_agents_active": len(kept_agents),
            "total_agents_archived": len(archived_agents),
            "agents_with_tasks": sum(1 for a in kept_agents.values() if a.get("stats", {}).get("tasks_completed", 0) > 0),
            "agents_zero_tasks": sum(1 for a in kept_agents.values() if a.get("stats", {}).get("tasks_completed", 0) == 0),
        },
        "categories": {},
    }
    
    # 整理 active agents
    for aid, agent in kept_agents.items():
        registry["agents"]["active"][aid] = {
            "id": aid,
            "name": agent.get("name", aid),
            "type": agent.get("template", agent.get("type", "unknown")),
            "role": agent.get("role", ""),
            "goal": agent.get("goal", ""),
            "skills": agent.get("skills", []),
            "model": agent.get("model", "claude-sonnet-4-6"),
            "priority": agent.get("priority", "normal"),
            "task_types": agent.get("task_types", []),
            "status": "active",
            "stats": agent.get("stats", {}),
            "created_at": agent.get("created_at", ""),
        }
    
    # 整理 archived agents
    for aid, agent in archived_agents.items():
        registry["agents"]["archived"][aid] = {
            "id": aid,
            "name": agent.get("name", aid),
            "type": agent.get("template", agent.get("type", "unknown")),
            "archive_reason": agent.get("_archive_reason", "Deduplicated"),
            "stats": agent.get("stats", {}),
        }
    
    # 按分类统计 Skill
    for sname, skill in skills.items():
        cat = skill["category"]
        if cat not in registry["categories"]:
            registry["categories"][cat] = []
        registry["categories"][cat].append(sname)
    
    return registry


def main():
    print("=" * 60)
    print("AIOS Unified Registry Builder v1.0")
    print("=" * 60)
    
    # 1. 扫描 Skills
    print("\n[1/4] Scanning skills...")
    skills = scan_skills()
    print(f"  Found {len(skills)} skills")
    for cat in set(s["category"] for s in skills.values()):
        count = sum(1 for s in skills.values() if s["category"] == cat)
        print(f"    {cat}: {count}")
    
    # 2. 加载旧 Agents
    print("\n[2/4] Loading old agents...")
    all_agents = load_old_agents()
    print(f"  Found {len(all_agents)} agents (across 3 files)")
    
    # 3. 去重
    print("\n[3/4] Deduplicating agents...")
    kept, archived = deduplicate_agents(all_agents)
    print(f"  Kept: {len(kept)}")
    print(f"  Archived: {len(archived)}")
    for aid, agent in archived.items():
        print(f"    [-] {aid}: {agent.get('_archive_reason', 'duplicate')}")
    
    # 4. 构建统一注册表
    print("\n[4/4] Building unified registry...")
    registry = build_unified_registry(skills, kept, archived)
    
    # 保存
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n  Saved to: {REGISTRY_PATH}")
    
    # 输出摘要
    stats = registry["stats"]
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Skills:           {stats['total_skills']}")
    print(f"    With scripts:   {stats['skills_with_scripts']}")
    print(f"    Doc only:       {stats['skills_doc_only']}")
    print(f"  Agents (active):  {stats['total_agents_active']}")
    print(f"  Agents (archived):{stats['total_agents_archived']}")
    print(f"  Agents with tasks:{stats['agents_with_tasks']}")
    print(f"  Agents zero tasks:{stats['agents_zero_tasks']}")
    print(f"\n  Categories:")
    for cat, items in registry["categories"].items():
        print(f"    {cat}: {', '.join(items)}")
    print("\nDone!")


if __name__ == "__main__":
    main()

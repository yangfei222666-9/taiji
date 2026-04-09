"""
Skill Drafter

Generates complete Skill draft packages from detected candidates.

This module writes to draft_registry/ only, never to production skills directory.
"""

from typing import Dict, Optional
from pathlib import Path


def draft_skill(
    candidate: Dict,
    template_path: str,
    output_dir: str,
    author: str = "auto-generated"
) -> Dict:
    """
    根据候选生成 Skill 草案包。
    
    Args:
        candidate: Candidate dict from detector
        template_path: Path to SKILL_TEMPLATE.md
        output_dir: Output directory (should be draft_registry/{skill_id}/)
        author: Author name (default: "auto-generated")
    
    Returns:
        Draft result dict:
        {
            "skill_id": str,              # Generated skill ID
            "skill_name": str,            # Skill name
            "draft_path": str,            # Path to SKILL.md
            "meta_path": str,             # Path to meta.json
            "status": str,                # "draft"
            "created_at": str,            # ISO timestamp
            "source_pattern_id": str      # Source candidate pattern_id
        }
    
    Raises:
        FileNotFoundError: If template doesn't exist
        ValueError: If candidate is malformed
        IOError: If output directory is not writable
    
    TODO:
        - Implement template filling logic
        - Generate trigger conditions from candidate
        - Create meta.json with full metadata
        - Add support for multi-step procedures
    """
    raise NotImplementedError("draft_skill not yet implemented")


def generate_skill_id(
    skill_name: str,
    timestamp: str
) -> str:
    """
    生成唯一的 Skill ID。
    
    Args:
        skill_name: Skill name
        timestamp: ISO timestamp
    
    Returns:
        Unique skill ID (e.g., "heartbeat_alert_deduper_20260309_154300")
    
    TODO:
        - Define ID format
        - Ensure uniqueness
    """
    raise NotImplementedError("generate_skill_id not yet implemented")


def fill_template(
    template_content: str,
    candidate: Dict,
    metadata: Dict
) -> str:
    """
    填充 SKILL.md 模板。
    
    Args:
        template_content: Template file content
        candidate: Candidate dict
        metadata: Additional metadata
    
    Returns:
        Filled SKILL.md content
    
    TODO:
        - Implement placeholder replacement
        - Generate trigger conditions
        - Generate procedure steps
        - Generate verification steps
    """
    raise NotImplementedError("fill_template not yet implemented")


def generate_trigger_conditions(
    candidate: Dict
) -> Dict:
    """
    从候选中生成触发条件。
    
    Args:
        candidate: Candidate dict
    
    Returns:
        Trigger conditions dict:
        {
            "activation_signals": List[str],
            "negative_conditions": List[str],
            "priority_score": int,
            "required_context_keys": List[str]
        }
    
    TODO:
        - Extract activation signals from pattern
        - Define negative conditions
        - Calculate priority score
    """
    raise NotImplementedError("generate_trigger_conditions not yet implemented")

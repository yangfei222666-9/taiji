"""
Skill Draft Registry

Manages the lifecycle state of Skill drafts.

States: draft → validated → promoted / rejected

Rules:
- No auto-promotion to production
- Immutable after validation (create new version instead)
- Rejection preserves history
"""

from typing import Dict, Optional, List


def update_registry(
    registry_index_path: str,
    skill_id: str,
    new_state: str,
    reason: Optional[str] = None
) -> Dict:
    """
    更新 draft registry 中的草案状态。
    
    Args:
        registry_index_path: Path to draft_registry/index.json
        skill_id: Skill ID to update
        new_state: New state ("draft" | "validated" | "promoted" | "rejected")
        reason: Optional reason for state change
    
    Returns:
        Updated registry entry:
        {
            "skill_id": str,
            "skill_name": str,
            "state": str,
            "previous_state": str,
            "updated_at": str,
            "reason": str | None
        }
    
    Raises:
        FileNotFoundError: If registry index doesn't exist
        ValueError: If skill_id not found or invalid state transition
        PermissionError: If trying to modify a validated draft
    
    TODO:
        - Implement state transition validation
        - Enforce immutability after validation
        - Write state change to index.json
        - Log state change to audit trail
    """
    raise NotImplementedError("update_registry not yet implemented")


def get_draft(
    registry_index_path: str,
    skill_id: str
) -> Optional[Dict]:
    """
    获取单个草案的当前状态。
    
    Args:
        registry_index_path: Path to draft_registry/index.json
        skill_id: Skill ID to look up
    
    Returns:
        Registry entry dict, or None if not found
    
    TODO:
        - Read and parse index.json
        - Return matching entry
    """
    raise NotImplementedError("get_draft not yet implemented")


def list_drafts(
    registry_index_path: str,
    state_filter: Optional[str] = None
) -> List[Dict]:
    """
    列出所有草案（可按状态过滤）。
    
    Args:
        registry_index_path: Path to draft_registry/index.json
        state_filter: Optional state to filter by
    
    Returns:
        List of registry entry dicts
    
    TODO:
        - Read and parse index.json
        - Apply state filter if provided
        - Sort by updated_at descending
    """
    raise NotImplementedError("list_drafts not yet implemented")


def register_draft(
    registry_index_path: str,
    draft_result: Dict
) -> Dict:
    """
    将新草案注册到 index.json。
    
    Args:
        registry_index_path: Path to draft_registry/index.json
        draft_result: Draft result dict from skill_drafter
    
    Returns:
        New registry entry dict
    
    Raises:
        ValueError: If skill_id already exists
    
    TODO:
        - Check for duplicate skill_id
        - Append to index.json
        - Return new entry
    """
    raise NotImplementedError("register_draft not yet implemented")


VALID_TRANSITIONS = {
    "draft": ["validated", "rejected"],
    "validated": ["promoted", "rejected"],
    "promoted": [],       # Terminal state
    "rejected": []        # Terminal state
}

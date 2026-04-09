"""
rbac.py - 角色权限校验模块
角色: admin / operator / viewer
"""
import json
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_rbac() -> dict:
    path = _repo_root() / "aios/agent_system/config/rbac.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_role(token: str) -> Optional[str]:
    rbac = _load_rbac()
    entry = rbac.get("tokens", {}).get(token)
    return entry["role"] if entry else None


def has_permission(token: str, permission: str) -> bool:
    rbac = _load_rbac()
    role = get_role(token)
    if not role:
        return False
    perms = rbac.get("roles", {}).get(role, {}).get("permissions", [])
    return permission in perms


def require_permission(token: str, permission: str) -> None:
    if not has_permission(token, permission):
        role = get_role(token) or "unknown"
        raise PermissionError(f"rbac_denied: role={role} permission={permission}")

"""Central path helpers for the agent system.

Environment overrides:
- OPENCLAW_WORKSPACE / TAIJIOS_WORKSPACE: explicit workspace root
- TAIJIOS_HOME: home-like root containing `.openclaw/workspace`
- AIOS_SKILLS_DIR: explicit skills root
"""

from __future__ import annotations

import os
from pathlib import Path


def openclaw_workspace_root() -> Path:
    """Return the canonical OpenClaw/TaijiOS workspace root."""
    explicit = os.environ.get("OPENCLAW_WORKSPACE") or os.environ.get("TAIJIOS_WORKSPACE")
    if explicit:
        return Path(explicit).expanduser()

    home_root = Path(os.environ.get("TAIJOS_HOME") or os.environ.get("TAIJIOS_HOME") or Path.home())
    return home_root.expanduser() / ".openclaw" / "workspace"


def agent_system_root() -> Path:
    """Return the agent_system directory under the canonical workspace."""
    return openclaw_workspace_root() / "aios" / "agent_system"


def agent_system_data_dir() -> Path:
    """Return the agent_system data directory under the canonical workspace."""
    return agent_system_root() / "data"


def skills_root() -> Path:
    """Return the skills directory."""
    explicit = os.environ.get("AIOS_SKILLS_DIR")
    if explicit:
        return Path(explicit).expanduser()
    return openclaw_workspace_root() / "skills"

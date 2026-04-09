"""
OpenClaw Integration for AIOS

Provides integration with OpenClaw's sessions_spawn tool.

Usage:
    from core.openclaw_integration import spawn_agent
    
    result = spawn_agent(
        task="Analyze error logs",
        agent_id="analyst",
        timeout=60
    )
"""
from __future__ import annotations

import json
import time
from typing import Dict, Optional


def spawn_agent(
    task: str,
    agent_id: str = "coder",
    model: str = "claude-sonnet-4-6",
    timeout: int = 60,
    cleanup: str = "keep",
) -> Dict:
    """
    Spawn an agent using OpenClaw's sessions_spawn.
    
    Args:
        task: Task description
        agent_id: Agent ID (coder/analyst/monitor/etc.)
        model: Model to use
        timeout: Timeout in seconds
        cleanup: Cleanup strategy (keep/delete)
    
    Returns:
        Result dict with success/output/error
    """
    # Since we're running inside OpenClaw, we can use the sessions_spawn tool
    # through the assistant's capabilities
    
    # For now, return a placeholder that indicates we need OpenClaw integration
    return {
        "success": False,
        "error": "sessions_spawn integration pending",
        "note": "This requires OpenClaw assistant to call sessions_spawn tool",
        "task": task,
        "agent_id": agent_id,
    }


def is_openclaw_available() -> bool:
    """Check if we're running in OpenClaw environment."""
    # Check for OpenClaw environment variables or session markers
    import os
    return os.getenv("OPENCLAW_SESSION_KEY") is not None


# For testing/development
if __name__ == "__main__":
    print("OpenClaw Integration Test")
    print(f"OpenClaw available: {is_openclaw_available()}")
    
    result = spawn_agent(
        task="Test task",
        agent_id="coder",
    )
    print(f"Result: {json.dumps(result, indent=2)}")

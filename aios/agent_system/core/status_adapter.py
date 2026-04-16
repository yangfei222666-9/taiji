"""
Status adapter — canonical way to read an agent's status.
"""


def get_agent_status(agent: dict) -> str:
    """Return the normalised status string for an agent dict."""
    return agent.get("status", "unknown")

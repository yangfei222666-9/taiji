#!/usr/bin/env python3
"""
Agent Lifecycle Engine - Minimal Rebuild
Reads task_executions_v2.jsonl and calculates lifecycle scores for agents
"""
import json
import sys
import threading
import tempfile
from pathlib import Path
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Tuple

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from paths import TASK_EXECUTIONS, AGENTS_STATE

# Config
WINDOW_SIZE = 10
FAILURE_THRESHOLD = 0.7
_agents_state_lock = threading.Lock()

COOLDOWN_PERIODS = {
    "active_to_shadow": timedelta(hours=24),
    "shadow_to_disabled": timedelta(hours=72),
}

TIMEOUT_MAP = {
    "active": 60,
    "shadow": 120,
    "disabled": 0,
}

PRIORITY_MAP = {
    "active": "normal",
    "shadow": "low",
    "disabled": "none",
}


def load_recent_executions(agent_id: str, window_size: int = WINDOW_SIZE) -> deque:
    """Load recent executions from task_executions_v2.jsonl"""
    executions = deque(maxlen=window_size)
    
    if not TASK_EXECUTIONS.exists():
        return executions
    
    with open(TASK_EXECUTIONS, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get('agent_id') == agent_id:
                    executions.append({
                        'success': record.get('status') == 'completed',
                        'timestamp': record.get('completed_at') or record.get('created_at'),
                    })
            except Exception:
                pass
    
    return executions


def calculate_failure_rate(executions: deque) -> float:
    """Calculate failure rate from recent executions"""
    if not executions:
        return 0.0
    
    failed = sum(1 for e in executions if not e['success'])
    return failed / len(executions)


def calculate_failure_streak(executions: deque) -> int:
    """Calculate consecutive failure streak"""
    if not executions:
        return 0
    
    streak = 0
    for e in reversed(executions):
        if not e['success']:
            streak += 1
        else:
            break
    
    return streak


def determine_lifecycle_state(
    current_state: str,
    failure_rate: float,
    failure_streak: int,
    cooldown_until: Optional[str],
) -> Tuple[str, Optional[str]]:
    """Determine lifecycle state based on failure metrics"""
    now = datetime.now()
    in_cooldown = False
    
    if cooldown_until:
        try:
            cooldown_end = datetime.fromisoformat(cooldown_until)
            in_cooldown = now < cooldown_end
        except ValueError:
            pass
    
    if current_state == "active":
        if failure_rate >= FAILURE_THRESHOLD or failure_streak >= 5:
            new_cooldown = (now + COOLDOWN_PERIODS["active_to_shadow"]).isoformat()
            return "shadow", new_cooldown
        return "active", None
    
    elif current_state == "shadow":
        if in_cooldown:
            return "shadow", cooldown_until
        
        if failure_rate >= FAILURE_THRESHOLD:
            new_cooldown = (now + COOLDOWN_PERIODS["shadow_to_disabled"]).isoformat()
            return "disabled", new_cooldown
        elif failure_rate < 0.5:
            return "active", None
        else:
            return "shadow", None
    
    elif current_state == "disabled":
        return "disabled", cooldown_until
    
    return current_state, cooldown_until


def calculate_lifecycle_score(agent_id: str, current_state: str, cooldown_until: Optional[str], enabled: bool = True, mode: str = "active") -> dict:
    """
    Calculate lifecycle score for a single agent
    
    Args:
        agent_id: Agent identifier
        current_state: Current lifecycle state
        cooldown_until: Cooldown end time (ISO format)
        enabled: Whether agent is enabled (availability gate)
        mode: Agent mode (active/shadow/disabled)
    
    Returns:
        dict: Lifecycle score with availability-aware state
    """
    # ── Availability Gate ──────────────────────────────────────────────
    # enabled=false → not routable, force lifecycle_state to match mode
    # mode=shadow/disabled → not routable, force lifecycle_state accordingly
    if not enabled or mode in ("shadow", "disabled"):
        # Agent is not available for routing
        forced_state = "disabled" if mode == "disabled" else "shadow"
        return {
            "lifecycle_state": forced_state,
            "last_failure_rate": 0.0,
            "last_failure_streak": 0,
            "cooldown_until": cooldown_until,
            "timeout": TIMEOUT_MAP[forced_state],
            "priority": PRIORITY_MAP[forced_state],
            "window_size": 0,
            "routable": False,
            "availability_gate": "blocked_by_enabled_or_mode",
        }
    
    # ── Normal Lifecycle Calculation (only for enabled + active agents) ──
    executions = load_recent_executions(agent_id, WINDOW_SIZE)
    
    failure_rate = calculate_failure_rate(executions)
    failure_streak = calculate_failure_streak(executions)
    
    new_state, new_cooldown = determine_lifecycle_state(
        current_state, failure_rate, failure_streak, cooldown_until
    )
    
    timeout = TIMEOUT_MAP[new_state]
    priority = PRIORITY_MAP[new_state]
    
    return {
        "lifecycle_state": new_state,
        "last_failure_rate": failure_rate,
        "last_failure_streak": failure_streak,
        "cooldown_until": new_cooldown,
        "timeout": timeout,
        "priority": priority,
        "window_size": len(executions),
        "routable": new_state == "active",
        "availability_gate": "passed",
    }


def calculate_all_lifecycle_scores() -> dict:
    """Calculate lifecycle scores for all agents"""
    if not AGENTS_STATE.exists():
        return {}
    
    with open(AGENTS_STATE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    agents = data.get('agents', [])
    scores = {}
    
    for agent in agents:
        agent_id = agent.get('id') or agent.get('name')
        if not agent_id:
            continue
        
        current_state = agent.get('lifecycle_state', 'active')
        cooldown_until = agent.get('cooldown_until')
        enabled = agent.get('enabled', True)
        mode = agent.get('mode', 'active')
        
        scores[agent_id] = calculate_lifecycle_score(
            agent_id, current_state, cooldown_until, enabled, mode
        )
    
    return scores


def write_lifecycle_states(scores: dict) -> int:
    """Write lifecycle states back to agents.json"""
    if not AGENTS_STATE.exists():
        return 0
    
    with open(AGENTS_STATE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    agents = data.get('agents', [])
    updated = 0
    
    for agent in agents:
        agent_id = agent.get('id') or agent.get('name')
        if agent_id in scores:
            score = scores[agent_id]
            agent['lifecycle_state'] = score['lifecycle_state']
            agent['cooldown_until'] = score['cooldown_until']
            agent['timeout'] = score['timeout']
            agent['priority'] = score['priority']
            agent['routable'] = score.get('routable', False)
            updated += 1
    
    with _agents_state_lock:
        tmp = Path(str(AGENTS_STATE) + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(AGENTS_STATE)

    return updated


def run_lifecycle_engine() -> dict:
    """Run lifecycle engine and return summary"""
    scores = calculate_all_lifecycle_scores()
    
    state_dist = {"active": 0, "shadow": 0, "disabled": 0}
    for score in scores.values():
        state = score['lifecycle_state']
        state_dist[state] = state_dist.get(state, 0) + 1
    
    updated = write_lifecycle_states(scores)
    
    return {
        "total_agents": len(scores),
        "updated_agents": updated,
        "state_distribution": state_dist,
    }


if __name__ == "__main__":
    print("Agent Lifecycle Engine - Hexagram Three-State System")
    print("=" * 60)
    
    result = run_lifecycle_engine()
    print(f"Total agents: {result['total_agents']}")
    print(f"Updated: {result['updated_agents']}")
    print(f"State distribution: {result['state_distribution']}")

"""
AIOS Unified Path Configuration

Centralizes all file paths to avoid path fragmentation.
All data files should be accessed through this module.

Usage:
    from paths import TASK_QUEUE, EVENTS_LOG, LOCKS_DIR
    
    with open(TASK_QUEUE, 'r') as f:
        tasks = [json.loads(line) for line in f]
"""

from pathlib import Path

# Root directories
AIOS_ROOT = Path(__file__).parent  # aios/agent_system/
DATA_DIR = AIOS_ROOT / "data"
LOCKS_DIR = AIOS_ROOT / "locks"

# ============== Core Data Files ==============

# Task Queue & Execution
TASK_QUEUE = DATA_DIR / "task_queue.jsonl"
TASK_EXECUTIONS = DATA_DIR / "task_executions_v2.jsonl"  # 缁熶竴 Schema v2
ARTIFACT_LEDGER = DATA_DIR / "artifact_ledger.jsonl"

# Spawn System
SPAWN_REQUESTS = DATA_DIR / "spawn_requests.jsonl"
SPAWN_PENDING = DATA_DIR / "spawn_pending.jsonl"
SPAWN_RESULTS = DATA_DIR / "spawn_results.jsonl"
SPAWN_EXECUTIONS = DATA_DIR / "spawn_executions.jsonl"

# Events & Logs
EVENTS_LOG = DATA_DIR / "events.jsonl"
TASK_TRACES = DATA_DIR / "task_traces.jsonl"
DECISION_LOG = DATA_DIR / "decision_log.jsonl"
DECISION_AUDIT = DATA_DIR / "decision_audit.jsonl"
EXECUTION_LOG = DATA_DIR / "execution_log.jsonl"
ROUTE_LOG = DATA_DIR / "route_log.jsonl"
DISPATCH_LOG = DATA_DIR / "dispatch_log.jsonl"

# Alerts & Notifications
ALERTS = DATA_DIR / "alerts.jsonl"
DEAD_LETTERS = DATA_DIR / "dead_letters.jsonl"
DLQ_AUDIT = DATA_DIR / "dlq_audit.jsonl"

# ============== State Files ==============

# Agent State
AGENTS_STATE = DATA_DIR / "agents.json"
AGENT_CONTEXTS = DATA_DIR / "agent_contexts.json"
AGENT_HEALTH_REPORT = DATA_DIR / "agent_health_report.json"

# System State
HEARTBEAT_STATE = DATA_DIR / "heartbeat_state.json"
HEARTBEAT_STATS = DATA_DIR / "heartbeat_stats.json"
EVOLUTION_SCORE = DATA_DIR / "evolution_score.json"
BASELINE_SNAPSHOT = DATA_DIR / "baseline_snapshot.json"

# Monitoring State
MONITORS_STATE = DATA_DIR / "monitors_state.json"
API_MONITOR_STATE = DATA_DIR / "api_monitor_state.json"
SITE_MONITOR_STATE = DATA_DIR / "site_monitor_state.json"
WEB_MONITOR_STATE = DATA_DIR / "web_monitor_state.json"
PROCESS_MONITOR_CONFIG = DATA_DIR / "process_monitor_config.json"

# Spawn Lock State
SPAWN_LOCKS = DATA_DIR / "spawn_locks.json"
SPAWN_LOCK_METRICS = DATA_DIR / "spawn_lock_metrics.json"
SPAWN_LOCK_MONITOR_STATE = DATA_DIR / "spawn_lock_monitor_state.json"

# Circuit Breaker
CIRCUIT_BREAKER_STATE = DATA_DIR / "circuit_breaker_state.json"

# ============== Learning & Experience ==============

# Lessons & Feedback
LESSONS = DATA_DIR / "lessons.json"
EXPERIENCE_LIBRARY = DATA_DIR / "experience_library.jsonl"
EXPERIENCE_DB_V4 = DATA_DIR / "experience_db_v4.jsonl"
FEEDBACK_LOG = DATA_DIR / "feedback_log.jsonl"
FEEDBACK_MONITOR = DATA_DIR / "feedback_monitor.jsonl"

# Recommendations & Patterns
RECOMMENDATION_LOG = DATA_DIR / "recommendation_log.jsonl"
PATTERN_HISTORY = DATA_DIR / "pattern_history.jsonl"
ERROR_PATTERNS = DATA_DIR / "error_patterns.json"

# Phase 3 Observations
PHASE3_OBSERVATIONS = DATA_DIR / "phase3_observations.jsonl"

# ============== Hexagram System ==============

# Hexagram History
BIGUA_HISTORY = DATA_DIR / "bigua_history.jsonl"
DAGUO_HISTORY = DATA_DIR / "daguo_history.jsonl"
KUN_HISTORY = DATA_DIR / "kun_history.jsonl"

# ============== Logs ==============

# Main Logs
HEARTBEAT_LOG = DATA_DIR / "heartbeat.log"
DISPATCHER_LOG = DATA_DIR / "dispatcher.log"
MEMORY_QUEUE_LOG = DATA_DIR / "memory_queue.log"

# ============== Reality Ledger ==============

ACTION_LEDGER = DATA_DIR / "action_ledger.jsonl"   # append-only event stream
ACTIONS_STATE = DATA_DIR / "actions_state.jsonl"   # 褰撳墠鍔ㄤ綔蹇収锛屽彲閲嶅缓

# ============== Action Lock ==============

# Action Lock Files
EXECUTED_ACTIONS = DATA_DIR / "executed_actions.jsonl"

# ============== Token & Cost ==============

# Token Monitoring
TOKEN_USAGE = DATA_DIR / "token_usage.jsonl"
TOKEN_MONITOR_CONFIG = DATA_DIR / "token_monitor_config.json"
COST_CONFIG = DATA_DIR / "cost_config.json"

# ============== Router & Stats ==============

# Router Statistics
ROUTER_STATS = DATA_DIR / "router_stats.json"

# ============== Quality & Validation ==============

# Quality Gates
QUALITY_GATE_VALIDATIONS = DATA_DIR / "quality_gate_validations.jsonl"

# Regression Tests
REGRESSION_TEST_REPORT = DATA_DIR / "regression_test_report.json"

# ============== Workflow & Pipeline ==============

# Workflow Progress
WORKFLOW_PROGRESS = DATA_DIR / "workflow_progress.jsonl"
PIPELINE_TIMINGS = DATA_DIR / "pipeline_timings.jsonl"

# ============== Meta & Observations ==============

# Meta Observations
META_META_OBSERVATIONS = DATA_DIR / "meta_meta_observations.jsonl"
META_META_OBSERVATION_SCHEMA = DATA_DIR / "meta_meta_observation_schema.json"

# ============== Git & Testing ==============

# Git Test State
GIT_TEST_STATE = DATA_DIR / "git_test_state.json"
GIT_TEST_EVENTS = DATA_DIR / "git_test_events.jsonl"

# ============== Ensure Directories Exist ==============

def ensure_directories():
    """Create all required directories if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    LOCKS_DIR.mkdir(exist_ok=True)
    
    # Create subdirectories
    subdirs = [
        "events", "evolution", "health", "learning", "reports",
        "feedback", "decisions", "tasks", "traces", "validation",
        "improvements", "rollback", "safety", "security", "testing"
    ]
    for subdir in subdirs:
        (DATA_DIR / subdir).mkdir(exist_ok=True)

# Auto-create directories on import
ensure_directories()


# ============== Migration Helpers ==============

def get_legacy_path(filename: str) -> Path:
    """
    Get legacy path (root directory) for migration.
    
    Args:
        filename: File name (e.g., "task_queue.jsonl")
    
    Returns:
        Path to legacy file location
    """
    return AIOS_ROOT / filename


def migrate_file(filename: str, target_path: Path, backup: bool = True):
    """
    Migrate a file from root directory to data/ directory.
    
    Args:
        filename: File name in root directory
        target_path: Target path in data/ directory
        backup: Whether to keep a backup of the original file
    """
    legacy_path = get_legacy_path(filename)
    
    if not legacy_path.exists():
        print(f"[MIGRATE] {filename} not found in root, skipping")
        return
    
    if target_path.exists():
        print(f"[MIGRATE] {filename} already exists in data/, skipping")
        return
    
    # Ensure target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy file
    import shutil
    shutil.copy2(legacy_path, target_path)
    print(f"[MIGRATE] {filename} 鈫?{target_path.relative_to(AIOS_ROOT)}")
    
    # Backup or remove original
    if backup:
        backup_path = legacy_path.with_suffix(legacy_path.suffix + ".migrated")
        legacy_path.rename(backup_path)
        print(f"[MIGRATE] Backup: {backup_path.name}")
    else:
        legacy_path.unlink()
        print(f"[MIGRATE] Removed: {filename}")


def migrate_all(backup: bool = True):
    """
    Migrate all core data files from root to data/ directory.
    
    Args:
        backup: Whether to keep backups of original files
    """
    print("=" * 60)
    print("AIOS Path Migration")
    print("=" * 60)
    
    # Core files to migrate
    migrations = [
        ("task_queue.jsonl", TASK_QUEUE),
        ("task_executions_v2.jsonl", TASK_EXECUTIONS),
        ("spawn_requests.jsonl", SPAWN_REQUESTS),
        ("spawn_pending.jsonl", SPAWN_PENDING),
        ("spawn_results.jsonl", SPAWN_RESULTS),
        ("spawn_executions.jsonl", SPAWN_EXECUTIONS),
        ("alerts.jsonl", ALERTS),
        ("agents.json", AGENTS_STATE),
        ("lessons.json", LESSONS),
        ("heartbeat_state.json", HEARTBEAT_STATE),
        ("heartbeat_stats.json", HEARTBEAT_STATS),
        ("evolution_score.json", EVOLUTION_SCORE),
        ("executed_actions.jsonl", EXECUTED_ACTIONS),
        ("decision_log.jsonl", DECISION_LOG),
        ("decision_audit.jsonl", DECISION_AUDIT),
        ("route_log.jsonl", ROUTE_LOG),
        ("dispatch_log.jsonl", DISPATCH_LOG),
    ]
    
    for filename, target_path in migrations:
        migrate_file(filename, target_path, backup=backup)
    
    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Test: print all paths
    print("AIOS Path Configuration")
    print("=" * 60)
    print(f"AIOS_ROOT: {AIOS_ROOT}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"LOCKS_DIR: {LOCKS_DIR}")
    print()
    print("Core Files:")
    print(f"  TASK_QUEUE: {TASK_QUEUE}")
    print(f"  TASK_EXECUTIONS: {TASK_EXECUTIONS}")
    print(f"  SPAWN_REQUESTS: {SPAWN_REQUESTS}")
    print(f"  ALERTS: {ALERTS}")
    print(f"  AGENTS_STATE: {AGENTS_STATE}")
    print(f"  LESSONS: {LESSONS}")
    print(f"  HEARTBEAT_LOG: {HEARTBEAT_LOG}")
    print()
    print("Directories created:")
    print(f"  {DATA_DIR.exists()} - {DATA_DIR}")
    print(f"  {LOCKS_DIR.exists()} - {LOCKS_DIR}")


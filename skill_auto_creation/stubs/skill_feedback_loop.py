"""
Skill Feedback Loop

Records shadow/trial run results for Skill drafts.

This module is append-only. It never modifies drafts, never triggers promotion,
never writes to the production chain.
"""

from typing import Dict, List, Optional


def record_feedback(
    skill_id: str,
    run_event: Dict,
    feedback_path: str
) -> Dict:
    """
    记录 shadow/试运行反馈。
    
    Args:
        skill_id: Skill ID this feedback belongs to
        run_event: Shadow run event dict:
            {
                "run_id": str,
                "trigger": str,          # What triggered this run
                "input": dict,           # Input data
                "actual_output": dict,   # What the skill produced
                "expected_output": dict, # What was expected
                "duration_ms": int,      # Execution time
                "error": str | None      # Error message if failed
            }
        feedback_path: Path to draft_registry/{skill_id}/feedback.jsonl
    
    Returns:
        Feedback record dict:
        {
            "feedback_id": str,          # Unique feedback ID
            "skill_id": str,
            "run_id": str,
            "result": str,               # "match" | "mismatch" | "error"
            "delta": dict,               # Diff between actual and expected
            "timestamp": str             # ISO timestamp
        }
    
    Raises:
        FileNotFoundError: If feedback_path directory doesn't exist
        ValueError: If run_event is malformed
    
    TODO:
        - Compute delta between actual and expected output
        - Determine result (match/mismatch/error)
        - Append to feedback.jsonl
        - Return feedback record
    """
    raise NotImplementedError("record_feedback not yet implemented")


def compute_delta(
    actual: Dict,
    expected: Dict
) -> Dict:
    """
    计算实际输出与预期输出的差异。
    
    Args:
        actual: Actual output dict
        expected: Expected output dict
    
    Returns:
        Delta dict:
        {
            "matched_keys": List[str],
            "mismatched_keys": List[str],
            "missing_keys": List[str],
            "extra_keys": List[str],
            "match_rate": float          # 0.0-1.0
        }
    
    TODO:
        - Deep compare actual vs expected
        - Calculate match rate
        - Identify specific mismatches
    """
    raise NotImplementedError("compute_delta not yet implemented")


def get_feedback_summary(
    skill_id: str,
    feedback_path: str
) -> Dict:
    """
    汇总某个 Skill 的所有反馈记录。
    
    Args:
        skill_id: Skill ID
        feedback_path: Path to feedback.jsonl
    
    Returns:
        Summary dict:
        {
            "skill_id": str,
            "total_runs": int,
            "match_count": int,
            "mismatch_count": int,
            "error_count": int,
            "avg_match_rate": float,
            "last_run_at": str | None
        }
    
    TODO:
        - Read and parse feedback.jsonl
        - Aggregate statistics
        - Return summary
    """
    raise NotImplementedError("get_feedback_summary not yet implemented")

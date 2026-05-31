#!/usr/bin/env python3
"""Verify the local evidence-only preflight artifacts.

This verifier is intentionally local-only. It parses files already present in
the repository and does not read env values or call providers. It accepts both
the original staged-index capture mode and a clean checkout review mode.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "evidence" / "summary.json"
PREFLIGHT_PATH = ROOT / "evidence" / "preflight_checklist.json"
EVENT_FLOW_PATH = ROOT / "evidence" / "event_flow.jsonl"
TRIAGE_PATH = ROOT / "evidence" / "hard_gate_line_triage.json"
OWNER_REVIEW_PATH = ROOT / "evidence" / "repo_pass_blocker_owner_review.json"
DIRTY_SCOPE_PATH = ROOT / "evidence" / "dirty_tree_scope_isolation.json"

EXPECTED_SCOPE = "evidence-only / no provider / no judgment / no trade"
EXPECTED_STAGED_FILES = [
    ".gitignore",
    "Makefile",
    "evidence/dirty_tree_scope_isolation.json",
    "evidence/event_flow.jsonl",
    "evidence/hard_gate_line_triage.json",
    "evidence/preflight_checklist.json",
    "evidence/repo_pass_blocker_owner_review.json",
    "evidence/summary.json",
    "tools/verify_evidence_preflight.py",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def load_json(path: Path) -> dict:
    if not path.is_file():
        fail(f"missing required artifact: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"json root must be object: {path.relative_to(ROOT)}")
    return data


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"missing required artifact: {path.relative_to(ROOT)}")
    events: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"invalid jsonl: {path.relative_to(ROOT)}:{line_no}: {exc}")
        if not isinstance(event, dict):
            fail(f"jsonl event must be object: {path.relative_to(ROOT)}:{line_no}")
        events.append(event)
    if not events:
        fail(f"event flow is empty: {path.relative_to(ROOT)}")
    return events


def require_false(mapping: dict, field: str) -> None:
    if mapping.get(field) is not False:
        fail(f"{field} must be false")


def staged_files() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"could not inspect staged files: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    summary = load_json(SUMMARY_PATH)
    preflight = load_json(PREFLIGHT_PATH)
    triage = load_json(TRIAGE_PATH)
    owner_review = load_json(OWNER_REVIEW_PATH)
    dirty_scope = load_json(DIRTY_SCOPE_PATH)
    events = load_jsonl(EVENT_FLOW_PATH)

    if summary.get("scope") != EXPECTED_SCOPE:
        fail("summary scope mismatch")
    if preflight.get("scope") != EXPECTED_SCOPE:
        fail("preflight scope mismatch")

    if summary.get("verdict") not in {"PARTIAL", "BLOCKED"}:
        fail("summary verdict must stay PARTIAL or BLOCKED for this gated lane")

    git_state = summary.get("git", {})
    if git_state.get("is_worktree") is not True:
        fail("git.is_worktree must be true")
    if git_state.get("staged_count") != len(EXPECTED_STAGED_FILES):
        fail("git.staged_count must match exact evidence stage scope")
    if git_state.get("staged_files") != EXPECTED_STAGED_FILES:
        fail("git.staged_files must match exact evidence stage scope")
    actual_staged = staged_files()
    if actual_staged and actual_staged != EXPECTED_STAGED_FILES:
        fail("staged files must match exact evidence scope when index is staged")
    if git_state.get("commit") is not None:
        fail("commit must not be created in this mode")
    if git_state.get("push") is not None:
        fail("push must not be executed in this mode")
    if git_state.get("pr") is not None:
        fail("pr must not be created in this mode")
    if git_state.get("merge") is not None:
        fail("merge must not be executed in this mode")

    boundaries = summary.get("boundaries", {})
    for field in (
        "runtime_logic_modified",
        "secret_read",
        "provider_called",
        "execution_venue_touched",
        "judgment_declared",
        "paper_buy",
        "trade_or_order",
        "promotion",
        "live_ready_declared",
        "commit_push_pr_merge",
    ):
        require_false(boundaries, field)
    if boundaries.get("stage_exact_scope") is not True:
        fail("exact evidence stage must be recorded")

    required_artifacts = summary.get("required_artifacts", {})
    for artifact in (
        "evidence/summary.json",
        "evidence/event_flow.jsonl",
        "evidence/preflight_checklist.json",
        "evidence/hard_gate_line_triage.json",
        "evidence/repo_pass_blocker_owner_review.json",
        "evidence/dirty_tree_scope_isolation.json",
    ):
        if required_artifacts.get(artifact) is not True:
            fail(f"required artifact not marked present: {artifact}")

    hard_gate = preflight.get("hard_gate_grep", {})
    if hard_gate.get("triage_status") != "full_line_triaged":
        fail("hard gate grep must be full-line triaged")
    if hard_gate.get("raw_match_file_count", 0) <= 0:
        fail("hard gate grep count should record the nonempty raw result")
    if hard_gate.get("raw_grep_nonempty_triaged_for_evidence_scope") is not True:
        fail("raw hard-gate grep must be triaged for the evidence scope")
    if hard_gate.get("active_escalation_found_in_this_scope") is not False:
        fail("this scope must not introduce active escalation")
    if triage.get("triage_status") != "full_line_triaged":
        fail("line triage artifact must be full-line triaged")
    if triage.get("raw_match_file_count") != hard_gate.get("raw_match_file_count"):
        fail("triage file count mismatch")
    if triage.get("raw_match_line_count") != hard_gate.get("raw_match_line_count"):
        fail("triage line count mismatch")
    if triage.get("introduced_by_this_scope_count") != 0:
        fail("this scope must not add hard-gate hits")
    if triage.get("scope_escalation_count") != 0:
        fail("this scope must not introduce escalation")
    if owner_review.get("owner_reviewed_line_count") != triage.get("repo_pass_blocking_line_count"):
        fail("owner review count must cover every initially blocking line")
    if owner_review.get("unreviewed_line_count") != 0:
        fail("owner review must leave no unreviewed lines")
    if owner_review.get("introduced_by_this_scope_count") != 0:
        fail("owner review must confirm no newly introduced hard-gate hits")
    if owner_review.get("scope_escalation_count") != 0:
        fail("owner review must confirm no scope escalation")
    if owner_review.get("inline_secret_value_observed_count") != 0:
        fail("owner review must not observe inline secret values")
    if owner_review.get("release_or_runtime_readiness_claim_allowed_count") != 0:
        fail("owner review must not allow release or runtime readiness claims")
    if hard_gate.get("manual_line_review_required_before_repo_pass") is not False:
        fail("manual line review should be closed by owner review")
    if dirty_scope.get("mode") != "dirty_tree_scope_isolation_only":
        fail("dirty tree scope isolation mode mismatch")
    if dirty_scope.get("staged_count") != len(EXPECTED_STAGED_FILES):
        fail("dirty tree isolation staged_count must match exact evidence scope")
    if dirty_scope.get("repo_pass") is not False:
        fail("dirty tree isolation must not claim repo pass")
    if dirty_scope.get("stage_exact_scope") is not True:
        fail("dirty tree isolation must record exact stage")
    if dirty_scope.get("commit_push_pr_merge") is not False:
        fail("dirty tree isolation must not commit, push, create PR, or merge")
    if dirty_scope.get("evidence_sync_scope", {}).get("status") != "isolated":
        fail("evidence sync scope must be isolated")
    if dirty_scope.get("external_dirty_scope", {}).get("status") != "present_outside_scope":
        fail("external dirty scope must remain visible outside this scope")
    if dirty_scope.get("external_dirty_scope", {}).get("file_count", 0) <= 0:
        fail("external dirty files should remain a repo-pass blocker")

    event_names = {event.get("event") for event in events}
    for required_event in (
        "scope_declared",
        "preflight_repaired",
        "hard_gate_grep_triaged",
        "hard_gate_line_triage_completed",
        "owner_review_completed",
        "dirty_tree_scope_isolated",
        "closeout",
    ):
        if required_event not in event_names:
            fail(f"missing event: {required_event}")

    print("VERDICT: PASS evidence_preflight_artifacts_consistent")
    print(f"declared_scope_verdict={summary.get('verdict')}")
    print(f"staged_count={len(actual_staged)}")
    print("repo_pass=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

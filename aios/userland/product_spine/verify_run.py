#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCOPE = "product_spine_verifier_minimal_local_impl_v0_1"
RUN_ID = "product_spine_verifier_minimal_local_impl_v0_1_20260522"

REQUIRED_SUMMARY_FIELDS = ["scope", "mode", "verdict"]
REQUIRED_EVENT_FIELDS = [
    "ts",
    "event",
    "scope",
    "status",
    "product_spine_component",
    "input_refs",
    "output_refs",
    "boundary_flags",
    "evidence",
    "not_claimed",
]
REQUIRED_EVENT_NAMES = [
    "scope_started",
    "boot_preflight_completed",
    "artifact_memory_written",
    "event_flow_written",
    "verifier_completed",
    "closeout_written",
    "scope_completed",
]
REQUIRED_CLOSEOUT_TERMS = [
    "verdict",
    "scope",
    "mode",
    "artifacts",
    "verification",
    "git",
    "boundaries",
    "not claimed",
    "next",
]
REQUIRED_NOT_CLAIMED_TERMS = ["repo", "provider", "trade", "promotion"]
FORBIDDEN_TRUE_KEYS = [
    "trade_allowed",
    "paper_buy_allowed",
    "judgment_allowed",
    "promote_allowed",
    "provider_ready",
    "broker_ready",
    "handoff_pass_is_merge",
    "scope_pass_is_repo_pass",
    "partial_written_as_pass",
    "blocked_written_as_failed",
    "old_dirty_tree_is_baseline",
    "repo_pass_claimed",
]
FORBIDDEN_TEXT_CLAIMS = [
    "trade_allowed=true",
    "paper_buy_allowed=true",
    "judgment_allowed=true",
    "promote_allowed=true",
    "provider_ready=true",
    "broker_ready=true",
    "handoff_pass_is_merge=true",
    "scope_pass_is_repo_pass=true",
    "partial_written_as_pass=true",
    "blocked_written_as_failed=true",
    "old_dirty_tree_is_baseline=true",
    "repo_pass_claimed=true",
    "scope pass is repo pass",
    "partial written as pass",
    "blocked written as failed",
]
SCOPE_PATHS = {
    "aios/userland/__init__.py",
    "aios/userland/product_spine/__init__.py",
    "aios/userland/product_spine/verify_run.py",
    "docs/PRODUCT_SPINE_VERIFIER_PLAN_v0.1.md",
    "tests/test_product_spine_verify_run.py",
}


def build_payload(
    run_dir: str | Path,
    *,
    repo_root: str | Path = ROOT,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_path = Path(run_dir).resolve()
    repo_root_path = Path(repo_root).resolve()
    summary_path = run_path / "summary.json"
    event_flow_path = run_path / "event_flow.jsonl"
    closeout_path = run_path / "closeout.md"

    summary, summary_error = _load_json(summary_path)
    events, event_error = _load_jsonl(event_flow_path)
    closeout_text = _read_text(closeout_path)
    closeout_missing = not closeout_path.exists()
    git_state = _git_state(repo_root_path, output_dir=output_dir)

    checks = {
        "summary_json_present": summary_path.exists(),
        "summary_json_parses": summary_error is None,
        "event_flow_jsonl_present": event_flow_path.exists(),
        "event_flow_jsonl_parses": event_error is None,
        "closeout_md_present": closeout_path.exists(),
        "closeout_md_nonempty": bool(closeout_text.strip()) and not closeout_missing,
        "required_summary_fields_present": _has_required_keys(summary, REQUIRED_SUMMARY_FIELDS),
        "required_event_fields_present": _events_have_required_keys(events),
        "required_event_sequence_present": _events_include_required_names(events),
        "scope_consistent": _scope_consistent(summary, events, closeout_text),
        "mode_consistent": _mode_consistent(summary, closeout_text),
        "terminal_verdict_consistent": _verdict_consistent(summary, closeout_text),
        "closeout_required_terms_present": _closeout_has_terms(closeout_text),
        "not_claimed_boundaries_present": _not_claimed_boundaries_present(summary, events, closeout_text),
        "staged_count_recorded": _staged_count_recorded(summary),
        "repo_pass_not_claimed": not _repo_pass_claimed(summary, events, closeout_text),
        "forbidden_claims_absent": not _forbidden_claims(summary, events, closeout_text),
    }
    errors = [name for name, ok in checks.items() if not ok]
    parse_errors = [error for error in [summary_error, event_error] if error and not error.startswith("missing:")]
    forbidden_claims = _forbidden_claims(summary, events, closeout_text)
    ok = not errors
    single_scope_pass = (
        ok
        and git_state["git_available"]
        and git_state["staged_count"] == 0
        and git_state["changed_files_outside_scope_count"] == 0
    )
    return {
        "ok": ok,
        "verdict": _verdict(ok, errors, parse_errors, forbidden_claims, git_state, single_scope_pass),
        "scope": SCOPE,
        "verified_run_dir": str(run_path),
        "summary_path": str(summary_path),
        "event_flow_path": str(event_flow_path),
        "closeout_path": str(closeout_path),
        "checks": checks,
        "errors": errors,
        "parse_errors": parse_errors,
        "missing": {
            "summary_fields": _missing_keys(summary, REQUIRED_SUMMARY_FIELDS),
            "event_names": _missing_event_names(events),
            "closeout_terms": _missing_closeout_terms(closeout_text),
            "not_claimed_terms": _missing_not_claimed_terms(summary, events, closeout_text),
        },
        "forbidden_claims": forbidden_claims,
        "summary_scope": _field(summary, "scope"),
        "summary_mode": _field(summary, "mode"),
        "summary_verdict": _field(summary, "verdict"),
        "event_count": len(events),
        "git": git_state,
        "can_claim_single_scope_pass": single_scope_pass,
        "repo_pass": False,
        "safety": _safety(),
        "not_claimed": [
            "repo PASS",
            "provider/API ready",
            "broker ready",
            "trade/order ready",
            "paper-buy ready",
            "judgment ready",
            "promotion ready",
            "T7 imported",
        ],
    }


def verify(
    run_dir: str | Path,
    output_dir: str | Path,
    *,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    payload = build_payload(run_dir, repo_root=repo_root_path, output_dir=output_dir_path)
    implementation_verdict = _implementation_verdict(payload)
    payload["implementation_verdict"] = implementation_verdict
    now = _utc_now()
    event = {
        "ts": now,
        "event": "product_spine_run_verified",
        "scope": SCOPE,
        "status": _event_status(implementation_verdict),
        "product_spine_component": "Closeout",
        "input_refs": [str(Path(run_dir).resolve())],
        "output_refs": [
            str(output_dir_path / "summary.json"),
            str(output_dir_path / "event_flow.jsonl"),
            str(output_dir_path / "closeout.md"),
        ],
        "boundary_flags": {
            "read_t7": False,
            "copy_t7": False,
            "read_secret": False,
            "provider_called": False,
            "trade_or_order": False,
            "stage_commit_push": False,
        },
        "evidence": {
            "verifier_scope_verdict": implementation_verdict,
            "verified_run_verdict": payload["verdict"],
            "errors": payload["errors"],
            "forbidden_claims": payload["forbidden_claims"],
            "staged_count": payload["git"]["staged_count"],
            "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        },
        "not_claimed": payload["not_claimed"],
    }
    summary = {
        "run_id": RUN_ID,
        "generated_at_utc": now,
        "scope": SCOPE,
        "component": "product_spine_run_verifier",
        "verified_run_dir": payload["verified_run_dir"],
        "verdict": implementation_verdict,
        "verified_run_verdict": payload["verdict"],
        "ok": payload["ok"],
        "errors": payload["errors"],
        "forbidden_claims": payload["forbidden_claims"],
        "event_count": payload["event_count"],
        "repo_pass": False,
        "provider_ready": False,
        "broker_ready": False,
        "trade_allowed": False,
        "paper_buy_allowed": False,
        "judgment_allowed": False,
        "promote_allowed": False,
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "dirty_count": payload["git"]["dirty_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "changed_files_outside_scope": payload["git"]["changed_files_outside_scope"],
        "can_claim_single_scope_pass": payload["can_claim_single_scope_pass"],
        "not_claimed": payload["not_claimed"],
        "safety": _safety(),
    }
    manifest = {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "artifacts": [
            "summary.json",
            "event_flow.jsonl",
            "manifest.json",
            "product_spine_run_verification.json",
            "closeout.md",
        ],
    }
    _write_json(output_dir_path / "product_spine_run_verification.json", payload)
    _write_json(output_dir_path / "summary.json", summary)
    _write_jsonl(output_dir_path / "event_flow.jsonl", [event])
    _write_json(output_dir_path / "manifest.json", manifest)
    (output_dir_path / "closeout.md").write_text(_closeout(summary), encoding="utf-8")
    return payload


def _load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing:{path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid_json:{path.name}:{exc.lineno}:{exc.colno}"
    if not isinstance(data, dict):
        return {}, f"invalid_json_type:{path.name}:expected_object"
    return data, None


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], f"missing:{path.name}"
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        return [], f"invalid_encoding:{path.name}:{exc}"
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return events, f"invalid_jsonl:{path.name}:{index}:{exc.colno}"
        if not isinstance(event, dict):
            return events, f"invalid_event_type:{path.name}:{index}:expected_object"
        events.append(event)
    return events, None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _has_required_keys(data: dict[str, Any], keys: list[str]) -> bool:
    return not _missing_keys(data, keys)


def _missing_keys(data: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if key not in data]


def _events_have_required_keys(events: list[dict[str, Any]]) -> bool:
    return bool(events) and all(not _missing_keys(event, REQUIRED_EVENT_FIELDS) for event in events)


def _events_include_required_names(events: list[dict[str, Any]]) -> bool:
    return not _missing_event_names(events)


def _missing_event_names(events: list[dict[str, Any]]) -> list[str]:
    names = {str(event.get("event")) for event in events}
    return [name for name in REQUIRED_EVENT_NAMES if name not in names]


def _scope_consistent(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> bool:
    scope = summary.get("scope")
    if not isinstance(scope, str) or not scope:
        return False
    if any(event.get("scope") != scope for event in events):
        return False
    return scope in closeout_text


def _mode_consistent(summary: dict[str, Any], closeout_text: str) -> bool:
    mode = summary.get("mode")
    return isinstance(mode, str) and mode in closeout_text


def _verdict_consistent(summary: dict[str, Any], closeout_text: str) -> bool:
    verdict = summary.get("verdict")
    return isinstance(verdict, str) and verdict in closeout_text


def _closeout_has_terms(closeout_text: str) -> bool:
    return not _missing_closeout_terms(closeout_text)


def _missing_closeout_terms(closeout_text: str) -> list[str]:
    lowered = closeout_text.lower()
    return [term for term in REQUIRED_CLOSEOUT_TERMS if term not in lowered]


def _not_claimed_boundaries_present(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> bool:
    return not _missing_not_claimed_terms(summary, events, closeout_text)


def _missing_not_claimed_terms(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> list[str]:
    combined = _combined_text(summary, events, closeout_text).lower()
    return [term for term in REQUIRED_NOT_CLAIMED_TERMS if term not in combined]


def _staged_count_recorded(summary: dict[str, Any]) -> bool:
    return isinstance(summary.get("staged_count"), int) or isinstance(_nested_get(summary, ["git_scope", "staged_count"]), int)


def _repo_pass_claimed(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> bool:
    if _truthy_key_values(summary, ["repo_pass_claimed", "repo_pass", "scope_pass_is_repo_pass"]):
        return True
    if any(_truthy_key_values(event, ["repo_pass_claimed", "repo_pass", "scope_pass_is_repo_pass"]) for event in events):
        return True
    return "repo pass claimed=true" in closeout_text.lower()


def _forbidden_claims(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> list[str]:
    claims = []
    claims.extend(_truthy_claims(summary, "summary"))
    for index, event in enumerate(events, start=1):
        claims.extend(_truthy_claims(event, f"event:{index}"))
    lowered_text = _combined_text(summary, events, closeout_text).lower()
    for claim in FORBIDDEN_TEXT_CLAIMS:
        if claim in lowered_text:
            claims.append(f"text:{claim}")
    return sorted(set(claims))


def _truthy_claims(data: Any, prefix: str) -> list[str]:
    claims: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            child_prefix = f"{prefix}.{key}"
            if key in FORBIDDEN_TRUE_KEYS and value is True:
                claims.append(child_prefix)
            claims.extend(_truthy_claims(value, child_prefix))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            claims.extend(_truthy_claims(item, f"{prefix}[{index}]"))
    return claims


def _truthy_key_values(data: Any, keys: list[str]) -> bool:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and value is True:
                return True
            if _truthy_key_values(value, keys):
                return True
    elif isinstance(data, list):
        return any(_truthy_key_values(item, keys) for item in data)
    return False


def _nested_get(data: dict[str, Any], keys: list[str]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _combined_text(summary: dict[str, Any], events: list[dict[str, Any]], closeout_text: str) -> str:
    return "\n".join(
        [
            json.dumps(summary, ensure_ascii=False, sort_keys=True),
            json.dumps(events, ensure_ascii=False, sort_keys=True),
            closeout_text,
        ]
    )


def _field(data: dict[str, Any], key: str) -> Any:
    return data.get(key)


def _git_state(repo_root: Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    base = {
        "git_available": False,
        "git_status_available": False,
        "staged_count": 0,
        "dirty_count": 0,
        "changed_files": [],
        "changed_files_outside_scope": [],
        "changed_files_outside_scope_count": 0,
    }
    try:
        subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return base

    base["git_available"] = True
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    changed_files = [_status_path(line) for line in lines]
    scope_paths = set(SCOPE_PATHS)
    if output_dir is not None:
        output_path = Path(output_dir).resolve()
        try:
            rel_output = output_path.relative_to(repo_root)
            scope_paths.add(str(rel_output))
        except ValueError:
            pass
    staged_count = sum(1 for line in lines if line[:2] != "??" and line[0] != " ")
    outside_scope = [path for path in changed_files if not _within_scope(path, scope_paths)]
    base.update(
        {
            "git_status_available": True,
            "staged_count": staged_count,
            "dirty_count": len(changed_files),
            "changed_files": changed_files,
            "changed_files_outside_scope": outside_scope,
            "changed_files_outside_scope_count": len(outside_scope),
        }
    )
    return base


def _status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    return raw.strip().strip('"')


def _within_scope(path: str, scope_paths: set[str]) -> bool:
    return any(path == scope or path.startswith(scope.rstrip("/") + "/") for scope in scope_paths)


def _verdict(
    ok: bool,
    errors: list[str],
    parse_errors: list[str],
    forbidden_claims: list[str],
    git_state: dict[str, Any],
    single_scope_pass: bool,
) -> str:
    if forbidden_claims:
        return "blocked_product_spine_forbidden_claim"
    if parse_errors:
        return "failed_product_spine_artifact_parse"
    missing_artifact_checks = {
        "summary_json_present",
        "event_flow_jsonl_present",
        "closeout_md_present",
        "closeout_md_nonempty",
    }
    if any(error in missing_artifact_checks for error in errors):
        return "blocked_product_spine_artifact_missing"
    if not ok:
        return "partial_product_spine_contract_incomplete"
    if not git_state["git_available"]:
        return "partial_product_spine_git_unavailable"
    if single_scope_pass:
        return "product_spine_run_verified_scope_only"
    return "partial_product_spine_verified_dirty_tree"


def _event_status(verdict: str) -> str:
    if verdict.startswith("blocked"):
        return "blocked"
    if verdict.startswith("failed"):
        return "failed"
    if verdict.startswith("partial"):
        return "partial"
    return "ok"


def _implementation_verdict(payload: dict[str, Any]) -> str:
    if not payload["ok"]:
        return payload["verdict"]
    git_state = payload["git"]
    if not git_state["git_available"]:
        return "partial_product_spine_verifier_impl_git_unavailable"
    if payload["can_claim_single_scope_pass"]:
        return "ok_product_spine_verifier_impl_prepared"
    return "partial_product_spine_verifier_impl_scope_dirty"


def _safety() -> dict[str, bool]:
    return {
        "t7_file_mutation": False,
        "secure_path_opened": False,
        "secret_value_read": False,
        "external_provider_called": False,
        "broker_connected": False,
        "trade_or_order": False,
        "promotion_or_judgment_or_paper_buy": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
    }


def _closeout(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Product Spine Run Verifier Closeout",
            "",
            f"verdict: `{summary['verdict']}`",
            f"scope: `{SCOPE}`",
            "mode: `edit_tests_only`",
            f"verified_run_dir: `{summary['verified_run_dir']}`",
            "",
            "## Artifacts",
            "",
            "- `summary.json`",
            "- `event_flow.jsonl`",
            "- `manifest.json`",
            "- `product_spine_run_verification.json`",
            "- `closeout.md`",
            "",
            "## Verification",
            "",
            f"- ok: `{summary['ok']}`",
            f"- errors: `{summary['errors']}`",
            f"- forbidden_claims: `{summary['forbidden_claims']}`",
            f"- event_count: `{summary['event_count']}`",
            "",
            "## Git State",
            "",
            f"- staged_count: `{summary['staged_count']}`",
            f"- changed_files_outside_scope_count: `{summary['changed_files_outside_scope_count']}`",
            f"- can_claim_single_scope_pass: `{summary['can_claim_single_scope_pass']}`",
            "- repo_pass: `false`",
            "",
            "## Boundaries Kept",
            "",
            "- T7 mutation: `false`",
            "- secret read: `false`",
            "- provider/broker call: `false`",
            "- trade/order: `false`",
            "- promotion/judgment/paper-buy: `false`",
            "- stage/commit/push: `false`",
            "",
            "## Not Claimed",
            "",
            "- repo PASS",
            "- Product Spine runtime completeness",
            "- provider/API readiness",
            "- broker readiness",
            "- trade/order readiness",
            "- paper-buy readiness",
            "- judgment readiness",
            "- promotion readiness",
            "",
            "## Next Allowed Action",
            "",
            "Use this verifier against future Product Spine run packets. Do not treat a",
            "partial/dirty-tree verifier result as repo PASS.",
            "",
        ]
    )


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Product Spine run packet without provider or secret access.")
    parser.add_argument("run_dir", help="Directory containing summary.json, event_flow.jsonl, and closeout.md.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    if args.output_dir:
        payload = verify(args.run_dir, args.output_dir, repo_root=args.repo_root)
    else:
        payload = build_payload(args.run_dir, repo_root=args.repo_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

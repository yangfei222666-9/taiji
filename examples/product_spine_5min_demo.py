#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCOPE = "product_spine_5min_demo_exact_scope_v0_1"
MODE = "edit_verify_no_stage"
RUN_ID = "product_spine_5min_demo_exact_scope_v0_1_20260523"

PRODUCT_SPINE_COMPONENTS = [
    "Boot Preflight",
    "EventFlow",
    "Scope Isolation",
    "Artifact Memory",
    "Closeout",
    "Product Spine verifier",
]

WILL_NOT = [
    "read secrets",
    "call providers",
    "use brokers",
    "trade/order",
    "paper-buy",
    "judgment",
    "promote",
    "mutate T7/external disks",
    "stage",
    "commit",
    "push",
    "PR",
    "merge",
    "deploy",
    "publish",
]

NOT_CLAIMED = [
    "repo PASS",
    "provider/API ready",
    "broker ready",
    "trade/order ready",
    "paper-buy ready",
    "judgment ready",
    "promotion ready",
    "T7 imported",
    "hardware control ready",
]

BOUNDARY_FLAGS = {
    "read_secret": False,
    "provider_called": False,
    "broker_connected": False,
    "trade_or_order": False,
    "paper_buy": False,
    "judgment": False,
    "promotion": False,
    "stage_commit_push": False,
    "t7_or_external_disk_mutation": False,
    "deploy_or_publish": False,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local-only 5-minute TaijiOS Product Spine demo packet."
    )
    parser.add_argument(
        "--run-dir",
        default=str(ROOT / "runs" / "ops_check" / RUN_ID),
        help="Output run directory for summary.json, event_flow.jsonl, and closeout.md.",
    )
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    payload = build_demo_packet(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_demo_packet(run_dir: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    output_paths = _output_paths(run_dir)
    scope_paths = {
        "examples/product_spine_5min_demo.py",
        _repo_relative(run_dir),
    }
    git_state = _git_state(ROOT, scope_paths)
    verdict = (
        "partial_product_spine_5min_demo_scope_dirty"
        if git_state["changed_files_outside_scope_count"]
        else "pass_product_spine_5min_demo_scope_only"
    )
    status = "partial" if verdict.startswith("partial") else "ok"
    now = _utc_now()
    timeline = [
        {
            "component": "Boot Preflight",
            "demo_step": "Declare scope, mode, will_not, and local-only boundaries before execution.",
            "duration_seconds": 45,
        },
        {
            "component": "EventFlow",
            "demo_step": "Append parseable JSONL transition events with explicit evidence fields.",
            "duration_seconds": 60,
        },
        {
            "component": "Scope Isolation",
            "demo_step": "Record branch, staged_count, scope paths, and outside-scope dirty files.",
            "duration_seconds": 60,
        },
        {
            "component": "Artifact Memory",
            "demo_step": "Write manifest and artifact_memory indexes for the run packet.",
            "duration_seconds": 45,
        },
        {
            "component": "Closeout",
            "demo_step": "Write verdict, verification, boundaries, not-claimed, and next gate.",
            "duration_seconds": 45,
        },
        {
            "component": "Product Spine verifier",
            "demo_step": "Run a verifier preview and keep dirty-tree output as PARTIAL, not repo PASS.",
            "duration_seconds": 45,
        },
    ]
    manifest = _manifest(run_dir, output_paths, now)
    artifact_memory = _artifact_memory(run_dir, output_paths, git_state, now)
    events = _events(run_dir, output_paths, git_state, timeline, now, status)
    summary = _summary(run_dir, output_paths, git_state, timeline, now, verdict, status)

    _write_json(output_paths["manifest"], manifest)
    _write_json(output_paths["artifact_memory"], artifact_memory)
    _write_jsonl(output_paths["event_flow"], events)
    _write_json(output_paths["summary"], summary)
    output_paths["closeout"].write_text(_closeout(summary), encoding="utf-8")

    preview = _product_spine_verifier_preview(run_dir)
    summary["verification"]["product_spine_verifier_preview"] = preview
    events[-3]["evidence"]["product_spine_verifier_preview"] = preview
    artifact_memory["verifier_results"]["product_spine_verifier_preview"] = preview
    _write_json(output_paths["artifact_memory"], artifact_memory)
    _write_jsonl(output_paths["event_flow"], events)
    _write_json(output_paths["summary"], summary)
    output_paths["closeout"].write_text(_closeout(summary), encoding="utf-8")
    _write_json(output_paths["product_spine_verifier_preview"], preview)

    return {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "mode": MODE,
        "run_dir": str(run_dir),
        "summary": str(output_paths["summary"]),
        "event_flow": str(output_paths["event_flow"]),
        "closeout": str(output_paths["closeout"]),
        "verdict": verdict,
        "repo_pass": False,
        "staged_count": git_state["staged_count"],
        "changed_files_outside_scope_count": git_state["changed_files_outside_scope_count"],
        "changed_files_outside_scope": git_state["changed_files_outside_scope"],
        "product_spine_verifier_preview_verdict": preview["verdict"],
        "not_claimed": NOT_CLAIMED,
    }


def _summary(
    run_dir: Path,
    output_paths: dict[str, Path],
    git_state: dict[str, Any],
    timeline: list[dict[str, Any]],
    now: str,
    verdict: str,
    status: str,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "generated_at_utc": now,
        "scope": SCOPE,
        "mode": MODE,
        "repo_root": str(ROOT),
        "entrypoint": "Evidence Kernel",
        "product_spine_components": PRODUCT_SPINE_COMPONENTS,
        "verdict": verdict,
        "status": status,
        "repo_pass": False,
        "provider_ready": False,
        "broker_ready": False,
        "trade_allowed": False,
        "paper_buy_allowed": False,
        "judgment_allowed": False,
        "promote_allowed": False,
        "will_not": WILL_NOT,
        "input_paths": [
            "docs/PRODUCT_SPINE_SCHEMA_v0.1.md",
            "aios/userland/product_spine/verify_run.py",
            "examples/product_spine_5min_demo.py",
        ],
        "output_paths": {name: str(path) for name, path in output_paths.items()},
        "demo_timeline": timeline,
        "boot_preflight": {
            "preflight_status": "PASS",
            "blocked_stage": None,
            "minimum_fix": None,
            "repo_root_exists": ROOT.exists(),
            "required_local_files_present": {
                "docs/PRODUCT_SPINE_SCHEMA_v0.1.md": (ROOT / "docs" / "PRODUCT_SPINE_SCHEMA_v0.1.md").exists(),
                "aios/userland/product_spine/verify_run.py": (
                    ROOT / "aios" / "userland" / "product_spine" / "verify_run.py"
                ).exists(),
            },
        },
        "scope_isolation": {
            "branch": git_state["branch"],
            "head": git_state["head"],
            "scope_files": [
                "examples/product_spine_5min_demo.py",
                _repo_relative(run_dir),
            ],
            "outside_scope_dirty_files": git_state["changed_files_outside_scope"],
            "changed_files_outside_scope": git_state["changed_files_outside_scope_count"],
            "staged_count": git_state["staged_count"],
            "staged_scope_files": git_state["staged_scope_files"],
            "staged_outside_scope_files": git_state["staged_outside_scope_files"],
            "repo_pass_claimed": False,
            "scope_pass_claimed": git_state["changed_files_outside_scope_count"] == 0 and git_state["staged_count"] == 0,
            "main_vs_origin_main": git_state["main_vs_origin_main"],
        },
        "artifact_memory": {
            "artifact_id": RUN_ID,
            "authority_level": "local_artifact",
            "import_allowed": False,
            "retention_policy": "keep",
            "paths": {
                "summary": str(output_paths["summary"]),
                "event_flow": str(output_paths["event_flow"]),
                "closeout": str(output_paths["closeout"]),
                "manifest": str(output_paths["manifest"]),
                "artifact_memory": str(output_paths["artifact_memory"]),
            },
        },
        "verification": {
            "summary_json_written": True,
            "event_flow_jsonl_written": True,
            "closeout_md_written": True,
            "event_sequence": [
                "scope_started",
                "boot_preflight_completed",
                "scope_isolation_evaluated",
                "artifact_memory_written",
                "event_flow_written",
                "verifier_started",
                "verifier_completed",
                "closeout_written",
                "scope_completed",
            ],
            "product_spine_verifier_command": (
                "python3 aios/userland/product_spine/verify_run.py "
                f"{_repo_relative(run_dir)} --repo-root {ROOT} --output-dir /tmp/product_spine_5min_demo_verify"
            ),
        },
        "git_scope": {
            "branch": git_state["branch"],
            "head": git_state["head"],
            "staged_count": git_state["staged_count"],
            "dirty_count": git_state["dirty_count"],
            "repo_pass_claimed": False,
        },
        "staged_count": git_state["staged_count"],
        "dirty_count": git_state["dirty_count"],
        "changed_files_outside_scope_count": git_state["changed_files_outside_scope_count"],
        "changed_files_outside_scope": git_state["changed_files_outside_scope"],
        "boundaries": {
            "secret_boundary": {
                "env_read_allowed": False,
                "keychain_read_allowed": False,
                "secret_value_logged": False,
            },
            "provider_boundary": {
                "provider_calls_allowed": False,
                "sandbox_default": True,
                "provider_ready_claimed": False,
            },
            "trade_boundary": {
                "trade_allowed": False,
                "paper_buy_allowed": False,
                "judgment_allowed": False,
                "promote_allowed": False,
            },
            "git_boundary": {
                "stage_allowed": False,
                "commit_allowed": False,
                "push_allowed": False,
                "pr_allowed": False,
                "merge_allowed": False,
            },
        },
        "safety": {
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
            "deploy_or_publish": False,
        },
        "not_claimed": NOT_CLAIMED,
        "next_allowed_action": (
            "Run Product Spine verifier and keep result PARTIAL until outside-scope dirty files are handled."
        ),
    }


def _events(
    run_dir: Path,
    output_paths: dict[str, Path],
    git_state: dict[str, Any],
    timeline: list[dict[str, Any]],
    now: str,
    status: str,
) -> list[dict[str, Any]]:
    output_refs = [str(output_paths[name]) for name in ["summary", "event_flow", "closeout"]]
    event_specs = [
        ("scope_started", "Boot Preflight", "started", {"will_not": WILL_NOT}),
        (
            "boot_preflight_completed",
            "Boot Preflight",
            "ok",
            {"preflight_status": "PASS", "repo_root": str(ROOT)},
        ),
        (
            "scope_isolation_evaluated",
            "Scope Isolation",
            status,
            {
                "staged_count": git_state["staged_count"],
                "changed_files_outside_scope_count": git_state["changed_files_outside_scope_count"],
                "changed_files_outside_scope": git_state["changed_files_outside_scope"],
            },
        ),
        (
            "artifact_memory_written",
            "Artifact Memory",
            "ok",
            {"artifact_memory": str(output_paths["artifact_memory"])},
        ),
        ("event_flow_written", "EventFlow", "ok", {"event_flow": str(output_paths["event_flow"])}),
        (
            "verifier_started",
            "Product Spine verifier",
            "started",
            {"verifier_input": str(run_dir)},
        ),
        (
            "verifier_completed",
            "Product Spine verifier",
            status,
            {"product_spine_verifier_preview": "pending_until_packet_write"},
        ),
        ("closeout_written", "Closeout", status, {"closeout": str(output_paths["closeout"])}),
        (
            "scope_completed",
            "Closeout",
            status,
            {"demo_timeline": timeline, "repo_pass": False},
        ),
    ]
    events = []
    for index, (name, component, event_status, evidence) in enumerate(event_specs):
        events.append(
            {
                "ts": now,
                "event": name,
                "scope": SCOPE,
                "status": event_status,
                "product_spine_component": component,
                "input_refs": [
                    "docs/PRODUCT_SPINE_SCHEMA_v0.1.md",
                    "aios/userland/product_spine/verify_run.py",
                ],
                "output_refs": output_refs,
                "boundary_flags": BOUNDARY_FLAGS,
                "evidence": {"sequence_index": index, **evidence},
                "not_claimed": NOT_CLAIMED,
            }
        )
    return events


def _manifest(run_dir: Path, output_paths: dict[str, Path], now: str) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "mode": MODE,
        "created_at_utc": now,
        "repo_root": str(ROOT),
        "run_dir": str(run_dir),
        "artifacts": {name: str(path) for name, path in output_paths.items()},
        "not_claimed": NOT_CLAIMED,
    }


def _artifact_memory(
    run_dir: Path,
    output_paths: dict[str, Path],
    git_state: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    return {
        "artifact_id": RUN_ID,
        "scope": SCOPE,
        "created_at": now,
        "paths": {
            "summary": str(output_paths["summary"]),
            "event_flow": str(output_paths["event_flow"]),
            "closeout": str(output_paths["closeout"]),
            "manifest": str(output_paths["manifest"]),
            "run_dir": str(run_dir),
        },
        "source_candidates": [
            "docs/PRODUCT_SPINE_SCHEMA_v0.1.md",
            "aios/userland/product_spine/verify_run.py",
        ],
        "verifier_results": {
            "json_artifacts_written": True,
            "event_flow_jsonl_written": True,
            "staged_count": git_state["staged_count"],
            "changed_files_outside_scope_count": git_state["changed_files_outside_scope_count"],
        },
        "authority_level": "local_artifact",
        "retention_policy": "keep",
        "import_allowed": False,
        "not_claimed": NOT_CLAIMED,
    }


def _closeout(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Product Spine 5-Minute Demo Closeout",
            "",
            f"verdict: `{summary['verdict']}`",
            f"scope: `{summary['scope']}`",
            f"mode: `{summary['mode']}`",
            f"repo_root: `{summary['repo_root']}`",
            "",
            "## Artifacts",
            "",
            f"- summary: `{summary['output_paths']['summary']}`",
            f"- event_flow: `{summary['output_paths']['event_flow']}`",
            f"- closeout: `{summary['output_paths']['closeout']}`",
            f"- artifact_memory: `{summary['output_paths']['artifact_memory']}`",
            f"- manifest: `{summary['output_paths']['manifest']}`",
            "",
            "## Verification",
            "",
            "- boot_preflight: `PASS`",
            "- event_flow_jsonl_written: `true`",
            "- artifact_memory_written: `true`",
            f"- product_spine_verifier_preview: `{summary['verification'].get('product_spine_verifier_preview', {}).get('verdict', 'pending')}`",
            f"- verifier_command: `{summary['verification']['product_spine_verifier_command']}`",
            "",
            "## Git State",
            "",
            f"- branch: `{summary['scope_isolation']['branch']}`",
            f"- head: `{summary['scope_isolation']['head']}`",
            f"- staged_count: `{summary['staged_count']}`",
            f"- changed_files_outside_scope_count: `{summary['changed_files_outside_scope_count']}`",
            f"- changed_files_outside_scope: `{summary['changed_files_outside_scope']}`",
            "- repo_pass: `false`",
            "",
            "## Boundaries Kept",
            "",
            "- secret read: `false`",
            "- provider/broker call: `false`",
            "- trade/order: `false`",
            "- paper-buy/judgment/promotion: `false`",
            "- T7/external disk mutation: `false`",
            "- stage/commit/push/PR/merge/deploy/publish: `false`",
            "",
            "## Not Claimed",
            "",
            "- repo PASS",
            "- provider/API ready",
            "- broker ready",
            "- trade/order ready",
            "- paper-buy ready",
            "- judgment ready",
            "- promotion ready",
            "- T7 imported",
            "- hardware control ready",
            "",
            "## Blocked Stage",
            "",
            "- blocked_stage: `none_for_demo_scope`",
            "- repo_pass remains blocked by outside-scope dirty files.",
            "",
            "## Minimum Fix",
            "",
            "- Keep this demo as scope evidence, or run a separate authorized exact-scope cleanup for outside-scope dirty files.",
            "",
            "## Next Allowed Action",
            "",
            f"- {summary['next_allowed_action']}",
            "",
        ]
    )


def _product_spine_verifier_preview(run_dir: Path) -> dict[str, Any]:
    from aios.userland.product_spine.verify_run import build_payload

    payload = build_payload(run_dir, repo_root=ROOT)
    return {
        "ok": payload["ok"],
        "verdict": payload["verdict"],
        "errors": payload["errors"],
        "forbidden_claims": payload["forbidden_claims"],
        "event_count": payload["event_count"],
        "staged_count": payload["git"]["staged_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "repo_pass": payload["repo_pass"],
        "can_claim_single_scope_pass": payload["can_claim_single_scope_pass"],
    }


def _output_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "summary": run_dir / "summary.json",
        "event_flow": run_dir / "event_flow.jsonl",
        "closeout": run_dir / "closeout.md",
        "manifest": run_dir / "manifest.json",
        "artifact_memory": run_dir / "artifact_memory.json",
        "product_spine_verifier_preview": run_dir / "product_spine_verifier_preview.json",
    }


def _git_state(repo_root: Path, scope_paths: set[str]) -> dict[str, Any]:
    lines = _git_lines(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    changed_files = [_status_path(line) for line in lines]
    staged_files = [_status_path(line) for line in lines if line[:2] != "??" and line[0] != " "]
    outside_scope = [path for path in changed_files if not _within_scope(path, scope_paths)]
    staged_outside_scope = [path for path in staged_files if not _within_scope(path, scope_paths)]
    branch = _git_text(repo_root, ["branch", "--show-current"]) or "unknown"
    head = _git_text(repo_root, ["rev-parse", "HEAD"]) or "unknown"
    main_vs_origin = _git_text(repo_root, ["rev-list", "--left-right", "--count", "main...origin/main"])
    return {
        "branch": branch,
        "head": head,
        "main_vs_origin_main": main_vs_origin or "unknown",
        "staged_count": len(staged_files),
        "dirty_count": len(changed_files),
        "changed_files": changed_files,
        "changed_files_outside_scope": outside_scope,
        "changed_files_outside_scope_count": len(outside_scope),
        "staged_scope_files": [path for path in staged_files if _within_scope(path, scope_paths)],
        "staged_outside_scope_files": staged_outside_scope,
    }


def _git_lines(repo_root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _git_text(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return ""
    return result.stdout.strip()


def _status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    return raw.strip().strip('"')


def _within_scope(path: str, scope_paths: set[str]) -> bool:
    return any(path == scope or path.startswith(scope.rstrip("/") + "/") for scope in scope_paths)


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())

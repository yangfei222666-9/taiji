#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCOPE = "pypi_trusted_publish_pipeline_candidate_v0_1"
RUN_ID = "pypi_trusted_publish_pipeline_candidate_v0_1_20260522"
WORKFLOW = Path(".github/workflows/publish-to-pypi.yml")
AUDIT_DOC = Path("PYPI_PUBLISHING_AUDIT.md")

SCOPE_PATHS = {
    str(WORKFLOW),
    str(AUDIT_DOC),
    "tools/verify_pypi_trusted_publish_pipeline.py",
    "tests/test_verify_pypi_trusted_publish_pipeline.py",
}

REQUIRED_WORKFLOW_TERMS = [
    "name: publish-to-pypi",
    "release:",
    "types: [published]",
    "permissions:",
    "contents: read",
    "deployments: read",
    "if: startsWith(github.event.release.tag_name, 'v')",
    "Verify publish environment gate",
    "gh api \"repos/${GITHUB_REPOSITORY}/environments/pypi\"",
    "required_reviewers_enabled",
    "selected_refs_enabled",
    "pypi environment gate is not configured",
    "needs: build",
    "environment:",
    "name: pypi",
    "url: https://pypi.org/p/taijios",
    "id-token: write",
    "actions/checkout@v4",
    "actions/setup-python@v5",
    'python-version: "3.12"',
    "pip install build twine",
    "python -m build",
    "python -m twine check dist/*",
    "sha256sum dist/* | tee artifacts/sha256.txt",
    "actions/upload-artifact@v4",
    "actions/download-artifact@v4",
    "pypa/gh-action-pypi-publish@release/v1",
    "packages-dir: dist/",
    "attestations: true",
    "print-hash: true",
]

REQUIRED_AUDIT_TERMS = [
    "Status: trusted publishing workflow candidate, not live PyPI release evidence.",
    "workflow_defined != pypi_publish_verified",
    "environment_name_declared != environment_protection_configured",
    "trusted_publisher_fields_documented != trusted_publisher_verified_live",
    "attestation_uploaded != artifact_correctness",
    "id-token: write",
    "job-scoped to `publish`",
    "verifies the GitHub `pypi` environment gate",
    "artifacts/environment-preflight.txt",
    "PyPI project",
    "Workflow | `publish-to-pypi.yml`",
    "Environment | `pypi`",
    "Required reviewers | enabled",
    "selected tags only, `v*`",
    "project-scoped",
    "account-wide PyPI token",
    "skip-existing: true",
    "PyPI live configuration and GitHub Environment protection remain external gates.",
]

FORBIDDEN_WORKFLOW_TERMS = [
    "secrets.PYPI",
    "secrets.PYPI_TOKEN",
    "secrets.PYPI_API_TOKEN",
    "TWINE_PASSWORD",
    "TWINE_USERNAME",
    "username:",
    "password:",
    "api-token",
    "skip-existing: true",
    "workflow_dispatch:",
    "branches:",
]

SECRET_PATTERNS = (
    re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", flags=re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
)


def build_payload(
    repo_root: str | Path = ROOT,
    output_dir: str | Path | None = None,
    *,
    github_repo: str | None = None,
    pypi_project: str | None = None,
    check_external: bool = False,
) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    workflow_path = repo_root_path / WORKFLOW
    audit_doc_path = repo_root_path / AUDIT_DOC
    workflow_text = _read_text(workflow_path)
    audit_text = _read_text(audit_doc_path)
    combined_text = workflow_text + "\n" + audit_text
    external = _external_state(github_repo, pypi_project, check_external)
    git_state = _git_state(repo_root_path, output_dir=output_dir)
    checks = {
        "workflow_exists": workflow_path.exists(),
        "audit_doc_exists": audit_doc_path.exists(),
        "required_workflow_terms_present": not _missing_terms(workflow_text, REQUIRED_WORKFLOW_TERMS),
        "required_audit_terms_present": not _missing_terms(audit_text, REQUIRED_AUDIT_TERMS),
        "forbidden_workflow_terms_absent": not _present_terms(workflow_text, FORBIDDEN_WORKFLOW_TERMS),
        "workflow_code_fences_balanced": workflow_text.count("```") % 2 == 0,
        "audit_doc_code_fences_balanced": audit_text.count("```") % 2 == 0,
        "secret_patterns_absent": not _secret_matches(combined_text),
        "publish_job_has_id_token": _publish_job_has_id_token(workflow_text),
        "build_job_has_no_id_token": not _build_job_has_id_token(workflow_text),
        "build_and_publish_jobs_separated": "build:" in workflow_text and "publish:" in workflow_text and "needs: build" in workflow_text,
    }
    errors = [name for name, ok in checks.items() if not ok]
    ok = not errors
    single_scope_pass = (
        ok
        and git_state["git_available"]
        and git_state["staged_count"] == 0
        and git_state["changed_files_outside_scope_count"] == 0
    )
    return {
        "ok": ok,
        "verdict": _verdict(ok, git_state, single_scope_pass, external),
        "scope": SCOPE,
        "workflow_path": str(workflow_path),
        "audit_doc_path": str(audit_doc_path),
        "checks": checks,
        "errors": errors,
        "missing": {
            "workflow_terms": _missing_terms(workflow_text, REQUIRED_WORKFLOW_TERMS),
            "audit_terms": _missing_terms(audit_text, REQUIRED_AUDIT_TERMS),
        },
        "forbidden_workflow_terms": _present_terms(workflow_text, FORBIDDEN_WORKFLOW_TERMS),
        "secret_matches": _secret_matches(combined_text),
        "release_run_executed": False,
        "pypi_publish_executed": False,
        "trusted_publisher_verified_live": False,
        "attestation_verified": False,
        "build_reproducible_verified": False,
        "external_publication_allowed": False,
        "git": git_state,
        "external": external,
        "can_claim_single_scope_pass": single_scope_pass,
        "safety": _safety(check_external),
    }


def verify(
    repo_root: str | Path,
    output_dir: str | Path,
    *,
    github_repo: str | None = None,
    pypi_project: str | None = None,
    check_external: bool = False,
) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    payload = build_payload(
        repo_root_path,
        output_dir=output_dir_path,
        github_repo=github_repo,
        pypi_project=pypi_project,
        check_external=check_external,
    )
    now = _utc_now()
    event = {
        "ts": now,
        "event": "pypi_trusted_publish_pipeline_candidate_verified",
        "scope": SCOPE,
        "ok": payload["ok"],
        "verdict": payload["verdict"],
        "errors": payload["errors"],
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "release_run_executed": False,
        "pypi_publish_executed": False,
        "trusted_publisher_verified_live": False,
        **_safety(check_external),
    }
    summary = {
        "run_id": RUN_ID,
        "generated_at_utc": now,
        "scope": SCOPE,
        "component": "pypi_trusted_publish_pipeline",
        "verdict": payload["verdict"],
        "ok": payload["ok"],
        "errors": payload["errors"],
        "workflow_defined": payload["checks"]["workflow_exists"],
        "audit_doc_defined": payload["checks"]["audit_doc_exists"],
        "release_run_executed": False,
        "pypi_publish_executed": False,
        "trusted_publisher_verified_live": False,
        "attestation_verified": False,
        "build_reproducible_verified": False,
        "external_publication_allowed": False,
        "github_environment_exists": payload["external"]["github_environment_exists"],
        "repo_secret_count": payload["external"]["repo_secret_count"],
        "pypi_project_exists": payload["external"]["pypi_project_exists"],
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "dirty_count": payload["git"]["dirty_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "changed_files_outside_scope": payload["git"]["changed_files_outside_scope"],
        "can_claim_single_scope_pass": payload["can_claim_single_scope_pass"],
        "safety": _safety(check_external),
    }
    manifest = {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "artifacts": [
            "summary.json",
            "event_flow.jsonl",
            "manifest.json",
            "pypi_trusted_publish_pipeline_verification.json",
            "context_packet.md",
            "closeout.md",
        ],
    }
    _write_json(output_dir_path / "pypi_trusted_publish_pipeline_verification.json", payload)
    _write_json(output_dir_path / "summary.json", summary)
    _write_jsonl(output_dir_path / "event_flow.jsonl", [event])
    _write_json(output_dir_path / "manifest.json", manifest)
    (output_dir_path / "context_packet.md").write_text(_context_packet(payload), encoding="utf-8")
    (output_dir_path / "closeout.md").write_text(_closeout(payload), encoding="utf-8")
    return payload


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _missing_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term not in text]


def _present_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _secret_matches(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            matches.append(match.group(0)[:8] + "...redacted")
    return matches


def _job_block(workflow_text: str, job_name: str) -> str:
    match = re.search(rf"(?ms)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", workflow_text)
    return match.group(1) if match else ""


def _publish_job_has_id_token(workflow_text: str) -> bool:
    return "id-token: write" in _job_block(workflow_text, "publish")


def _build_job_has_id_token(workflow_text: str) -> bool:
    return "id-token:" in _job_block(workflow_text, "build")


def _external_state(github_repo: str | None, pypi_project: str | None, check_external: bool) -> dict[str, Any]:
    state: dict[str, Any] = {
        "check_external": check_external,
        "github_repo": github_repo,
        "pypi_project": pypi_project,
        "github_api_called": False,
        "github_environment_exists": None,
        "github_environment_names": [],
        "repo_secret_count": None,
        "pypi_json_checked": False,
        "pypi_project_exists": None,
        "trusted_publisher_verified_live": False,
        "errors": [],
    }
    if not check_external:
        return state

    if github_repo:
        state["github_api_called"] = True
        env_result = _run(["gh", "api", f"repos/{github_repo}/environments", "--jq", "."])
        if env_result["ok"]:
            try:
                data = json.loads(env_result["stdout"] or "{}")
                names = [item.get("name") for item in data.get("environments", []) if item.get("name")]
                state["github_environment_names"] = names
                state["github_environment_exists"] = "pypi" in names
            except json.JSONDecodeError as exc:
                state["errors"].append(f"github_environments_json_error:{exc}")
        else:
            state["errors"].append("github_environments_query_failed")

        secrets_result = _run(["gh", "secret", "list", "--repo", github_repo])
        if secrets_result["ok"]:
            lines = [line for line in secrets_result["stdout"].splitlines() if line.strip()]
            state["repo_secret_count"] = len(lines)
        else:
            state["errors"].append("github_secret_names_query_failed")

    if pypi_project:
        state["pypi_json_checked"] = True
        url = f"https://pypi.org/pypi/{pypi_project}/json"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                state["pypi_project_exists"] = response.status == 200
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                state["pypi_project_exists"] = False
            else:
                state["errors"].append(f"pypi_json_http_error:{exc.code}")
        except urllib.error.URLError as exc:
            state["errors"].append(f"pypi_json_url_error:{exc.reason}")

    return state


def _run(args: list[str], cwd: str | Path | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)
    except OSError as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": None}
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _git_state(repo_root: Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    base = {
        "git_available": False,
        "git_status_available": False,
        "branch": None,
        "head": None,
        "staged_count": 0,
        "dirty_count": 0,
        "changed_files": [],
        "changed_files_outside_scope": [],
        "changed_files_outside_scope_count": 0,
    }
    top = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root)
    if not top["ok"]:
        return base

    base["git_available"] = True
    branch = _run(["git", "branch", "--show-current"], cwd=repo_root)
    head = _run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo_root)
    status = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo_root)
    if branch["ok"]:
        base["branch"] = branch["stdout"].strip() or None
    if head["ok"]:
        base["head"] = head["stdout"].strip() or None
    if not status["ok"]:
        return base

    lines = [line for line in status["stdout"].splitlines() if line.strip()]
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


def _verdict(ok: bool, git_state: dict[str, Any], single_scope_pass: bool, external: dict[str, Any]) -> str:
    if not ok:
        return "blocked_pypi_trusted_publish_pipeline_contract_failure"
    if external.get("check_external") and (
        external.get("github_environment_exists") is not True or external.get("pypi_project_exists") is not True
    ):
        return "partial_pypi_trusted_publish_pipeline_external_gates_missing"
    if not git_state["git_available"]:
        return "partial_pypi_trusted_publish_pipeline_git_unavailable"
    if single_scope_pass:
        return "pypi_trusted_publish_pipeline_contract_verified"
    return "partial_pypi_trusted_publish_pipeline_verified_dirty_tree"


def _safety(check_external: bool = False) -> dict[str, bool]:
    return {
        "github_api_called": check_external,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "tag_created": False,
        "release_run_triggered": False,
        "pypi_publish_performed": False,
        "secret_value_read": False,
        "external_provider_write_performed": False,
        "trade_or_funds_action": False,
    }


def _context_packet(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# PyPI Trusted Publishing Context Packet",
            "",
            f"scope: `{SCOPE}`",
            "repo_root: `/Users/weiwei/Desktop/taiji`",
            "",
            "## Goal",
            "",
            "- Define a PyPI Trusted Publishing workflow using GitHub OIDC.",
            "- Keep OIDC authority job-scoped to the publish job.",
            "- Preserve GitHub Environment and PyPI Trusted Publisher setup as external gates.",
            "- Emit local evidence without claiming a live publish.",
            "",
            "## Boundary",
            "",
            "- `workflow_defined != pypi_publish_verified`",
            "- `environment_name_declared != environment_protection_configured`",
            "- `trusted_publisher_verified_live=false`",
            "- `attestation_verified=false` until a real publish run is reviewed.",
            "",
            "## Verification",
            "",
            f"verdict: `{payload['verdict']}`",
            f"errors: `{payload['errors']}`",
            f"changed_files_outside_scope_count: `{payload['git']['changed_files_outside_scope_count']}`",
            f"github_environment_exists: `{payload['external']['github_environment_exists']}`",
            f"pypi_project_exists: `{payload['external']['pypi_project_exists']}`",
            f"can_claim_single_scope_pass: `{payload['can_claim_single_scope_pass']}`",
            "",
        ]
    )


def _closeout(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# PyPI Trusted Publishing Closeout",
            "",
            f"verdict: `{payload['verdict']}`",
            f"ok: `{payload['ok']}`",
            f"errors: `{payload['errors']}`",
            "",
            "## Evidence",
            "",
            f"- workflow: `{payload['workflow_path']}`",
            f"- audit_doc: `{payload['audit_doc_path']}`",
            "- release_run_executed: `false`",
            "- pypi_publish_executed: `false`",
            "- trusted_publisher_verified_live: `false`",
            "- external_publication_allowed: `false`",
            "",
            "## Git Boundary",
            "",
            f"- branch: `{payload['git']['branch']}`",
            f"- head: `{payload['git']['head']}`",
            f"- staged_count: `{payload['git']['staged_count']}`",
            f"- changed_files_outside_scope_count: `{payload['git']['changed_files_outside_scope_count']}`",
            f"- can_claim_single_scope_pass: `{payload['can_claim_single_scope_pass']}`",
            "",
        ]
    )


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the TaijiOS PyPI Trusted Publishing candidate.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--github-repo", default=None)
    parser.add_argument("--pypi-project", default=None)
    parser.add_argument("--check-external", action="store_true")
    args = parser.parse_args()
    payload = verify(
        args.repo_root,
        args.output_dir,
        github_repo=args.github_repo,
        pypi_project=args.pypi_project,
        check_external=args.check_external,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

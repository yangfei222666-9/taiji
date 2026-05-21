#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCOPE = "release_evidence_pipeline_candidate_v0_1"
RUN_ID = "release_evidence_pipeline_candidate_v0_1_20260520"
WORKFLOW = Path(".github/workflows/release.yml")
AUDIT_DOC = Path("AUDIT_EVIDENCE.md")
STATIC_PROVENANCE = Path("supplychain/provenance.json")

SCOPE_PATHS = {
    str(WORKFLOW),
    str(AUDIT_DOC),
    "tools/verify_release_evidence_pipeline.py",
    "tests/test_verify_release_evidence_pipeline.py",
}

REQUIRED_WORKFLOW_TERMS = [
    "name: release",
    "workflow_dispatch:",
    'tags:',
    '"v*"',
    "packages: write",
    "id-token: write",
    "security-events: write",
    "pip install build pytest pytest-cov cyclonedx-bom pyyaml",
    "pip install -e .",
    "python -m build",
    "--cov=aios",
    "set -o pipefail",
    "--cov-fail-under=70",
    "cyclonedx-py environment -o cyclonedx.sbom.xml",
    "syft . -o json > sbom.json",
    "docker build -t",
    "docker push",
    "crane digest",
    "DIGEST_SHA256=${DIGEST#sha256:}",
    "sha256sum -c checksums.txt",
    "manifest.yaml",
    "supplychain/provenance.json",
    '"_type": "https://in-toto.io/Statement/v1"',
    '"predicateType": "https://slsa.dev/provenance/v1"',
    "cosign sign",
    "cosign attest",
    "cosign verify",
    "cosign verify-attestation",
    "--certificate-identity",
    "image.lock",
    "actions/upload-artifact@v4",
    "hashFiles('results.sarif') != ''",
]

REQUIRED_AUDIT_TERMS = [
    "Status: release evidence template, not live release evidence.",
    "release_workflow_defined != release_passed",
    "artifact_uploaded != artifact_verified",
    "workflow_dispatch != production_cutover",
    "static repository copy of that file is not release evidence.",
    "pytest tests -q",
    "--cov=aios",
    "--cov-fail-under=70",
    "cyclonedx-py environment -o cyclonedx.sbom.xml",
    "syft . -o json > sbom.json",
    "sha256sum -c checksums.txt",
    "image.lock",
    "manifest.yaml",
    "blocked_release_evidence_incomplete",
]

FORBIDDEN_TERMS = [
    "--cov=taiji",
    "2d8dcb92d10f9cb3d7b57d4cbf0f82f0f7744f1e2d7d3fcb02f9e2b16c07ab10",
    "0a4ec8d11c4d03fbd0dcf9d0a5110e1a8a8c0dd9ef6bcb39f6e2f72c6f4f7a0e",
    "8c8de10e09d43c5d52f4f5f44a09c91f4f7f5dc0a22fbc3d45e6e79eebad92c1",
]

SECRET_PATTERNS = (
    re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", flags=re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
)


def build_payload(repo_root: str | Path = ROOT, output_dir: str | Path | None = None) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    workflow_path = repo_root_path / WORKFLOW
    audit_doc_path = repo_root_path / AUDIT_DOC
    static_provenance_path = repo_root_path / STATIC_PROVENANCE
    workflow_text = _read_text(workflow_path)
    audit_text = _read_text(audit_doc_path)
    combined_text = workflow_text + "\n" + audit_text
    git_state = _git_state(repo_root_path, output_dir=output_dir)
    checks = {
        "workflow_exists": workflow_path.exists(),
        "audit_doc_exists": audit_doc_path.exists(),
        "required_workflow_terms_present": not _missing_terms(workflow_text, REQUIRED_WORKFLOW_TERMS),
        "required_audit_terms_present": not _missing_terms(audit_text, REQUIRED_AUDIT_TERMS),
        "forbidden_terms_absent": not _present_terms(combined_text, FORBIDDEN_TERMS),
        "static_provenance_absent": not static_provenance_path.exists(),
        "workflow_code_fences_balanced": workflow_text.count("```") % 2 == 0,
        "audit_doc_code_fences_balanced": audit_text.count("```") % 2 == 0,
        "secret_patterns_absent": not _secret_matches(combined_text),
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
        "verdict": _verdict(ok, git_state, single_scope_pass),
        "scope": SCOPE,
        "workflow_path": str(workflow_path),
        "audit_doc_path": str(audit_doc_path),
        "static_provenance_path": str(static_provenance_path),
        "checks": checks,
        "errors": errors,
        "missing": {
            "workflow_terms": _missing_terms(workflow_text, REQUIRED_WORKFLOW_TERMS),
            "audit_terms": _missing_terms(audit_text, REQUIRED_AUDIT_TERMS),
        },
        "forbidden_terms": _present_terms(combined_text, FORBIDDEN_TERMS),
        "secret_matches": _secret_matches(combined_text),
        "release_workflow_defined": checks["workflow_exists"],
        "release_run_executed": False,
        "artifact_uploaded": False,
        "artifact_verified": False,
        "cosign_verified": False,
        "attestation_verified": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "git": git_state,
        "can_claim_single_scope_pass": single_scope_pass,
        "safety": _safety(),
    }


def verify(repo_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    payload = build_payload(repo_root_path, output_dir=output_dir_path)
    now = _utc_now()
    event = {
        "ts": now,
        "event": "release_evidence_pipeline_candidate_verified",
        "scope": SCOPE,
        "ok": payload["ok"],
        "verdict": payload["verdict"],
        "errors": payload["errors"],
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "release_run_executed": False,
        "artifact_verified": False,
        **_safety(),
    }
    summary = {
        "run_id": RUN_ID,
        "generated_at_utc": now,
        "scope": SCOPE,
        "component": "release_evidence_pipeline",
        "verdict": payload["verdict"],
        "ok": payload["ok"],
        "errors": payload["errors"],
        "release_workflow_defined": payload["release_workflow_defined"],
        "release_run_executed": False,
        "artifact_uploaded": False,
        "artifact_verified": False,
        "cosign_verified": False,
        "attestation_verified": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "dirty_count": payload["git"]["dirty_count"],
        "changed_files_outside_scope_count": payload["git"]["changed_files_outside_scope_count"],
        "changed_files_outside_scope": payload["git"]["changed_files_outside_scope"],
        "can_claim_single_scope_pass": payload["can_claim_single_scope_pass"],
        "safety": _safety(),
    }
    manifest = {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "artifacts": [
            "summary.json",
            "event_flow.jsonl",
            "manifest.json",
            "release_evidence_pipeline_verification.json",
            "context_packet.md",
            "closeout.md",
        ],
    }
    context_packet = _context_packet(payload)
    closeout = _closeout(payload)
    _write_json(output_dir_path / "release_evidence_pipeline_verification.json", payload)
    _write_json(output_dir_path / "summary.json", summary)
    _write_jsonl(output_dir_path / "event_flow.jsonl", [event])
    _write_json(output_dir_path / "manifest.json", manifest)
    (output_dir_path / "context_packet.md").write_text(context_packet, encoding="utf-8")
    (output_dir_path / "closeout.md").write_text(closeout, encoding="utf-8")
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


def _verdict(ok: bool, git_state: dict[str, Any], single_scope_pass: bool) -> str:
    if not ok:
        return "blocked_release_evidence_pipeline_contract_failure"
    if not git_state["git_available"]:
        return "partial_release_evidence_pipeline_git_unavailable"
    if single_scope_pass:
        return "release_evidence_pipeline_contract_verified"
    return "partial_release_evidence_pipeline_verified_dirty_tree"


def _safety() -> dict[str, bool]:
    return {
        "github_api_called": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "tag_created": False,
        "release_run_triggered": False,
        "deployment_performed": False,
        "secret_value_read": False,
        "external_provider_called": False,
        "trade_or_funds_action": False,
    }


def _context_packet(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Release Evidence Pipeline Context Packet",
            "",
            f"scope: `{SCOPE}`",
            "repo_root: `/Users/weiwei/Desktop/taiji`",
            "",
            "## Problem",
            "",
            "A release evidence workflow was requested, but the raw snippet mixed",
            "candidate release wiring with values that could be mistaken for real",
            "evidence. The corrected pipeline must generate evidence at runtime and",
            "avoid static hardcoded provenance/digest claims.",
            "",
            "## Goal",
            "",
            "- Define a tag/manual release workflow for build, test, SBOM, image push, cosign signing, provenance, and artifact upload.",
            "- Keep `AUDIT_EVIDENCE.md` as a template until a real release run produces downloadable artifacts.",
            "- Preserve no-stage, no-commit, no-push, no-tag, no-release-run boundaries.",
            "",
            "## Boundary",
            "",
            "- `release_workflow_defined != release_passed`",
            "- `artifact_uploaded != artifact_verified`",
            "- `workflow_dispatch != production_cutover`",
            "- `static provenance != release evidence`",
            "",
            "## Verification",
            "",
            f"verdict: `{payload['verdict']}`",
            f"errors: `{payload['errors']}`",
            f"changed_files_outside_scope_count: `{payload['git']['changed_files_outside_scope_count']}`",
            f"can_claim_single_scope_pass: `{payload['can_claim_single_scope_pass']}`",
            "",
        ]
    )


def _closeout(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Release Evidence Pipeline Closeout",
            "",
            f"verdict: `{payload['verdict']}`",
            f"ok: `{payload['ok']}`",
            f"errors: `{payload['errors']}`",
            "",
            "## Evidence",
            "",
            f"- workflow: `{payload['workflow_path']}`",
            f"- audit_doc: `{payload['audit_doc_path']}`",
            "- static_provenance_committed: `false`",
            "- release_run_executed: `false`",
            "- artifact_verified: `false`",
            "- external_publication_allowed: `false`",
            "",
            "## Git Boundary",
            "",
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
    parser = argparse.ArgumentParser(description="Verify the TaijiOS release evidence pipeline candidate.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    payload = verify(args.repo_root, args.output_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

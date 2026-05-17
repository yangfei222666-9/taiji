#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCOPE = "github_actions_audit_checklist_canonical_repo_probe_v0_1"
RUN_ID = "github_actions_audit_checklist_canonical_repo_probe_v0_1_20260517"
CONTRACT = "AUDIT_CHECKLIST.md"

REQUIRED_SECTIONS = [
    (0, "Environment Variables"),
    (1, "CI Gate"),
    (2, "Unit Test Gate"),
    (3, "Lint / Static Analysis Gate"),
    (4, "Build Gate"),
    (5, "SBOM Gate"),
    (6, "Supply Chain Attestation Gate"),
    (7, "Container Signature Gate"),
    (8, "Change Audit Gate"),
    (9, "Request Audit Gate"),
    (10, "Config Snapshot Gate"),
    (11, "Deployment Diff Gate"),
    (12, "Kubernetes Snapshot Gate"),
    (13, "Runtime Metrics Gate"),
    (14, "Rollback Gate"),
    (15, "Database Migration Gate"),
    (16, "Model / Rule Version Gate"),
    (17, "ACL / IAM Change Gate"),
    (18, "GitHub Release Gate"),
    (19, "Provenance Gate"),
    (20, "Full Audit Sweep"),
]

REQUIRED_TERMS = [
    "Status: readiness checklist, not an audit pass",
    "checklist_ready != audit_pass",
    "artifact_downloaded != artifact_verified",
    "verified_handoff != GitHub merge",
    "release_exists != deployment_healthy",
    "github_api_called=false",
    "artifact_downloaded=false",
    "cosign_verified=false",
    "oras_verified=false",
    "release_verified=false",
    "deployment_verified=false",
    "runtime_metrics_verified=false",
    "git_available=",
    "staged_count=",
    "audit_pass=false",
    "test-results/junit.xml",
    "coverage/coverage.xml",
    "lint/eslint.json",
    "ruff-report.json",
    "dist/taiji-${COMMIT}.tar.gz",
    "artifacts/sbom/${COMMIT}.spdx.json",
    "artifacts/attestations/taiji-attestation.intoto.json",
    "logs/change/${COMMIT}.jsonl",
    "logs/audit/$(date +%F).jsonl",
    "config/snapshots/config-${TS}.json",
    "ci/artifacts/deploy-${RUN_ID}/diff.patch",
    "k8s/manifests/snapshot-${TS}.tar.gz",
    "metrics/taiji/${TS}.json",
    "rollbacks/${TS}/${COMMIT}.json",
    "db/migrations/*.sql",
    "models/*/manifest.json",
    "security/acl/changes-${TS}.jsonl",
    "cosign verify-attestation",
    "cosign verify",
    "gh release view",
    "oras discover",
    "make audit",
]

FORBIDDEN_PASS_CLAIMS = [
    "audit_pass=true",
    "github_api_called=true",
    "artifact_downloaded=true",
    "cosign_verified=true",
    "oras_verified=true",
    "release_verified=true",
    "deployment_verified=true",
    "runtime_metrics_verified=true",
]

SECRET_PATTERNS = (
    re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", flags=re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
)


def build_payload(checklist_path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    checklist = Path(checklist_path)
    repo_root_path = Path(repo_root).resolve()
    text = checklist.read_text(encoding="utf-8") if checklist.exists() else ""
    git_state = _git_state(repo_root_path)
    checks = {
        "checklist_exists": checklist.exists(),
        "title_present": "# AUDIT_CHECKLIST.md" in text,
        "all_sections_present_in_order": _sections_in_order(text),
        "required_terms_present": not _missing_terms(text, REQUIRED_TERMS),
        "forbidden_pass_claims_absent": not _present_terms(text, FORBIDDEN_PASS_CLAIMS),
        "secret_patterns_absent": not _secret_matches(text),
        "code_fences_balanced": text.count("```") % 2 == 0,
    }
    errors = [name for name, ok in checks.items() if not ok]
    ok = not errors
    return {
        "ok": ok,
        "verdict": _verdict(ok, git_state),
        "scope": SCOPE,
        "contract": CONTRACT,
        "checklist_path": str(checklist),
        "checks": checks,
        "errors": errors,
        "missing": {
            "sections": _missing_sections(text),
            "terms": _missing_terms(text, REQUIRED_TERMS),
        },
        "forbidden_pass_claims": _present_terms(text, FORBIDDEN_PASS_CLAIMS),
        "secret_matches": _secret_matches(text),
        "gates_defined": len(REQUIRED_SECTIONS) - 1,
        "audit_pass": False,
        "github_api_called": False,
        "artifact_downloaded": False,
        "cosign_verified": False,
        "oras_verified": False,
        "release_verified": False,
        "deployment_verified": False,
        "runtime_metrics_verified": False,
        "can_claim_single_scope_pass": False,
        "repo_pass": False,
        "git": git_state,
        "safety": _safety(),
    }


def verify(repo_root: str | Path, output_dir: str | Path, checklist_path: str | Path | None = None) -> dict[str, Any]:
    repo_root_path = Path(repo_root).resolve()
    checklist = Path(checklist_path).resolve() if checklist_path else repo_root_path / "AUDIT_CHECKLIST.md"
    output_dir_path = Path(output_dir).resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)
    payload = build_payload(checklist, repo_root=repo_root_path)
    now = _utc_now()
    event = {
        "ts": now,
        "event": "github_actions_audit_checklist_canonical_repo_probe_completed",
        "scope": SCOPE,
        "contract": CONTRACT,
        "ok": payload["ok"],
        "verdict": payload["verdict"],
        "errors": payload["errors"],
        "git_available": payload["git"]["git_available"],
        "staged_count": payload["git"]["staged_count"],
        "dirty_count": payload["git"].get("dirty_count"),
        **_safety(),
    }
    summary = {
        "run_id": RUN_ID,
        "generated_at_utc": now,
        "scope": SCOPE,
        "component": "github_actions_audit_checklist_canonical_repo_probe",
        "contract": CONTRACT,
        "verdict": payload["verdict"],
        "ok": payload["ok"],
        "errors": payload["errors"],
        "gates_defined": payload["gates_defined"],
        "checklist_path": str(checklist),
        "audit_pass": False,
        "github_api_called": False,
        "artifact_downloaded": False,
        "cosign_verified": False,
        "oras_verified": False,
        "release_verified": False,
        "deployment_verified": False,
        "runtime_metrics_verified": False,
        "git_available": payload["git"]["git_available"],
        "git_status_available": payload["git"]["git_status_available"],
        "staged_count": payload["git"]["staged_count"],
        "dirty_count": payload["git"].get("dirty_count"),
        "can_claim_single_scope_pass": False,
        "repo_pass": False,
        "safety": _safety(),
    }
    manifest = {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "contract": CONTRACT,
        "artifacts": [
            "summary.json",
            "event_flow.jsonl",
            "manifest.json",
            "snapshot.json",
            "closeout.md",
            "github_actions_audit_checklist_verification.json",
        ],
    }
    snapshot = {
        "run_id": RUN_ID,
        "scope": SCOPE,
        "contract": CONTRACT,
        "verdict": payload["verdict"],
        "checklist_path": str(checklist),
        "checks": payload["checks"],
        "git": payload["git"],
    }
    _write_json(output_dir_path / "github_actions_audit_checklist_verification.json", payload)
    _write_json(output_dir_path / "summary.json", summary)
    _write_jsonl(output_dir_path / "event_flow.jsonl", [event])
    _write_json(output_dir_path / "manifest.json", manifest)
    _write_json(output_dir_path / "snapshot.json", snapshot)
    _write_text(output_dir_path / "closeout.md", _closeout(summary))
    artifact_bundle = _artifact_bundle_check(output_dir_path)
    payload["artifact_bundle"] = artifact_bundle
    summary["artifact_bundle"] = artifact_bundle
    _write_json(output_dir_path / "github_actions_audit_checklist_verification.json", payload)
    _write_json(output_dir_path / "summary.json", summary)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AUDIT_CHECKLIST.md locally without calling GitHub.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--checklist", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    checklist = args.checklist or str(Path(args.repo_root) / "AUDIT_CHECKLIST.md")
    if args.output_dir:
        result = verify(args.repo_root, args.output_dir, checklist)
    else:
        result = build_payload(checklist, repo_root=args.repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


def _sections_in_order(text: str) -> bool:
    positions = []
    for number, title in REQUIRED_SECTIONS:
        marker = f"## {number}. {title}"
        pos = text.find(marker)
        if pos < 0:
            return False
        positions.append(pos)
    return positions == sorted(positions)


def _missing_sections(text: str) -> list[str]:
    return [f"{number}. {title}" for number, title in REQUIRED_SECTIONS if f"## {number}. {title}" not in text]


def _missing_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term not in text]


def _present_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _secret_matches(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in SECRET_PATTERNS:
        matches.extend(match.group(0) for match in pattern.finditer(text))
    return sorted(set(matches))


def _git_state(repo_root: Path) -> dict[str, Any]:
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if inside.returncode != 0:
        return {
            "git_available": False,
            "git_status_available": False,
            "is_git_repo": False,
            "staged_count": None,
            "git_error": inside.stderr.strip() or inside.stdout.strip(),
        }
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if staged.returncode != 0:
        return {
            "git_available": True,
            "git_status_available": False,
            "is_git_repo": True,
            "staged_count": None,
            "git_error": staged.stderr.strip() or staged.stdout.strip(),
        }
    return {
        "git_available": True,
        "git_status_available": True,
        "is_git_repo": True,
        "staged_count": len([line for line in staged.stdout.splitlines() if line.strip()]),
        "dirty_count": _dirty_count(repo_root),
    }


def _verdict(ok: bool, git_state: dict[str, Any]) -> str:
    if not ok:
        return "blocked_github_actions_audit_checklist_contract_failure"
    if not git_state["git_status_available"]:
        return "partial_github_actions_audit_checklist_verified_git_unavailable"
    if git_state["staged_count"] != 0:
        return "partial_github_actions_audit_checklist_verified_staged_changes"
    if git_state.get("dirty_count", 0) != 0:
        return "partial_github_actions_audit_checklist_verified_dirty_tree"
    return "github_actions_audit_checklist_verified"


def _dirty_count(repo_root: Path) -> int:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode != 0:
        return -1
    return len([line for line in status.stdout.splitlines() if line.strip()])


def _artifact_bundle_check(run_dir: Path) -> dict[str, Any]:
    required = ["summary.json", "event_flow.jsonl", "manifest.json", "snapshot.json", "closeout.md"]
    parse_errors: list[str] = []
    missing: list[str] = []
    for name in required:
        path = run_dir / name
        if not path.exists():
            missing.append(name)
            continue
        if path.suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                parse_errors.append(f"{name}:{exc}")
        if path.suffix == ".jsonl":
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    parse_errors.append(f"{name}:{index}:{exc}")
    return {
        "verdict": "local_artifact_bundle_verified" if not missing and not parse_errors else "blocked_local_artifact_bundle_invalid",
        "missing": missing,
        "parse_errors": parse_errors,
        "content_echoed": False,
    }


def _safety() -> dict[str, bool]:
    return {
        "external_api_called": False,
        "secret_accessed": False,
        "github_token_read": False,
        "artifact_downloaded": False,
        "cosign_run": False,
        "oras_run": False,
        "gh_run": False,
        "deployed": False,
        "broker_connected": False,
        "trade_or_order": False,
        "judgment": False,
        "paper_buy": False,
        "promote": False,
        "stage_commit_push": False,
    }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _closeout(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# GitHub Actions Audit Checklist Canonical Repo Probe v0.1 Closeout",
            "",
            "## Verdict",
            "",
            f"`{summary['verdict']}`",
            "",
            "## Result",
            "",
            f"- ok: `{str(summary['ok']).lower()}`",
            f"- gates_defined: `{summary['gates_defined']}`",
            f"- git_available: `{str(summary['git_available']).lower()}`",
            f"- staged_count: `{summary['staged_count']}`",
            "",
            "## Boundary",
            "",
            "This verifier did not call GitHub APIs, read GitHub tokens, download artifacts, run Cosign, run ORAS, run gh, deploy, stage, commit, or push.",
            "",
            "It verifies checklist structure only. It does not prove a GitHub Actions audit pass.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())

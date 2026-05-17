from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.verify_github_actions_audit_checklist import REQUIRED_SECTIONS, ROOT, build_payload


VERIFY = ROOT / "tools" / "verify_github_actions_audit_checklist.py"
CHECKLIST = ROOT / "AUDIT_CHECKLIST.md"


def test_current_checklist_verifies_without_audit_pass_claim():
    payload = build_payload(CHECKLIST, repo_root=ROOT)

    assert payload["ok"] is True
    assert payload["gates_defined"] == 20
    assert payload["audit_pass"] is False
    assert payload["github_api_called"] is False
    assert payload["artifact_downloaded"] is False
    assert payload["secret_matches"] == []
    assert payload["can_claim_single_scope_pass"] is False
    assert payload["repo_pass"] is False
    assert payload["verdict"] != "github_actions_audit_checklist_verified" or payload["git"].get("dirty_count", 0) == 0


def test_missing_section_blocks(tmp_path):
    checklist = tmp_path / "AUDIT_CHECKLIST.md"
    checklist.write_text(CHECKLIST.read_text(encoding="utf-8").replace("## 20. Full Audit Sweep", "## 20. Removed"), encoding="utf-8")

    payload = build_payload(checklist, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "blocked_github_actions_audit_checklist_contract_failure"
    assert "20. Full Audit Sweep" in payload["missing"]["sections"]


def test_forbidden_pass_claim_blocks(tmp_path):
    checklist = tmp_path / "AUDIT_CHECKLIST.md"
    checklist.write_text(CHECKLIST.read_text(encoding="utf-8") + "\naudit_pass=true\n", encoding="utf-8")

    payload = build_payload(checklist, repo_root=tmp_path)

    assert payload["ok"] is False
    assert "forbidden_pass_claims_absent" in payload["errors"]
    assert "audit_pass=true" in payload["forbidden_pass_claims"]


def test_secret_like_token_blocks(tmp_path):
    checklist = tmp_path / "AUDIT_CHECKLIST.md"
    token = "Bearer " + ("a" * 24)
    checklist.write_text(CHECKLIST.read_text(encoding="utf-8") + "\n" + token + "\n", encoding="utf-8")

    payload = build_payload(checklist, repo_root=tmp_path)

    assert payload["ok"] is False
    assert "secret_patterns_absent" in payload["errors"]
    assert payload["secret_matches"]


def test_required_sections_are_consecutive():
    assert [number for number, _ in REQUIRED_SECTIONS] == list(range(21))


def test_verifier_avoids_python_311_datetime_utc_symbol():
    source = VERIFY.read_text(encoding="utf-8")

    assert "from datetime import UTC" not in source
    assert "datetime.UTC" not in source
    assert "now(UTC)" not in source


def test_cli_writes_artifacts(tmp_path):
    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY),
            "--repo-root",
            str(ROOT),
            "--checklist",
            str(CHECKLIST),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "event_flow.jsonl").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "snapshot.json").exists()
    assert (output_dir / "closeout.md").exists()
    assert (output_dir / "github_actions_audit_checklist_verification.json").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["audit_pass"] is False
    assert summary["artifact_bundle"]["verdict"] == "local_artifact_bundle_verified"

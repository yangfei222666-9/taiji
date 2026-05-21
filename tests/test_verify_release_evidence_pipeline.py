from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.verify_release_evidence_pipeline import ROOT, build_payload


VERIFY = ROOT / "tools" / "verify_release_evidence_pipeline.py"


def test_current_release_evidence_pipeline_contract():
    payload = build_payload(ROOT)

    assert payload["ok"] is True
    assert payload["checks"]["workflow_exists"] is True
    assert payload["checks"]["audit_doc_exists"] is True
    assert payload["checks"]["static_provenance_absent"] is True
    assert payload["forbidden_terms"] == []
    assert payload["secret_matches"] == []
    assert payload["release_run_executed"] is False
    assert payload["artifact_verified"] is False
    assert payload["external_publication_allowed"] is False


def test_missing_workflow_blocks(tmp_path):
    (tmp_path / "AUDIT_EVIDENCE.md").write_text("Status: release evidence template, not live release evidence.\n", encoding="utf-8")

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert payload["checks"]["workflow_exists"] is False
    assert payload["verdict"] == "blocked_release_evidence_pipeline_contract_failure"


def test_forbidden_static_digest_blocks(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    audit_text = (ROOT / "AUDIT_EVIDENCE.md").read_text(encoding="utf-8")
    (workflow_dir / "release.yml").write_text(workflow_text, encoding="utf-8")
    (tmp_path / "AUDIT_EVIDENCE.md").write_text(
        audit_text + "\n2d8dcb92d10f9cb3d7b57d4cbf0f82f0f7744f1e2d7d3fcb02f9e2b16c07ab10\n",
        encoding="utf-8",
    )

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert "forbidden_terms_absent" in payload["errors"]


def test_static_provenance_file_blocks(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    supplychain_dir = tmp_path / "supplychain"
    supplychain_dir.mkdir()
    (workflow_dir / "release.yml").write_text(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "AUDIT_EVIDENCE.md").write_text((ROOT / "AUDIT_EVIDENCE.md").read_text(encoding="utf-8"), encoding="utf-8")
    (supplychain_dir / "provenance.json").write_text("{}\n", encoding="utf-8")

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert "static_provenance_absent" in payload["errors"]


def test_cli_writes_release_evidence_artifacts(tmp_path):
    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY),
            "--repo-root",
            str(ROOT),
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
    assert (output_dir / "release_evidence_pipeline_verification.json").exists()
    assert (output_dir / "context_packet.md").exists()
    assert (output_dir / "closeout.md").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["release_run_executed"] is False
    assert summary["artifact_verified"] is False
    assert summary["external_publication_allowed"] is False

from __future__ import annotations

import json
import subprocess
import sys

from tools.verify_pypi_trusted_publish_pipeline import ROOT, build_payload


VERIFY = ROOT / "tools" / "verify_pypi_trusted_publish_pipeline.py"


def test_current_pypi_trusted_publish_contract():
    payload = build_payload(ROOT)

    assert payload["ok"] is True
    assert payload["checks"]["workflow_exists"] is True
    assert payload["checks"]["audit_doc_exists"] is True
    assert payload["checks"]["publish_job_has_id_token"] is True
    assert payload["checks"]["build_job_has_no_id_token"] is True
    assert payload["checks"]["build_and_publish_jobs_separated"] is True
    assert payload["forbidden_workflow_terms"] == []
    assert payload["secret_matches"] == []
    assert payload["pypi_publish_executed"] is False
    assert payload["trusted_publisher_verified_live"] is False
    assert payload["external_publication_allowed"] is False


def test_missing_workflow_blocks(tmp_path):
    (tmp_path / "PYPI_PUBLISHING_AUDIT.md").write_text(
        "Status: trusted publishing workflow candidate, not live PyPI release evidence.\n",
        encoding="utf-8",
    )

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert payload["checks"]["workflow_exists"] is False
    assert payload["verdict"] == "blocked_pypi_trusted_publish_pipeline_contract_failure"


def test_long_lived_token_secret_blocks(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_text = (ROOT / ".github" / "workflows" / "publish-to-pypi.yml").read_text(encoding="utf-8")
    audit_text = (ROOT / "PYPI_PUBLISHING_AUDIT.md").read_text(encoding="utf-8")
    (workflow_dir / "publish-to-pypi.yml").write_text(
        workflow_text + "\n# forbidden fallback\n# password: ${{ secrets.PYPI_TOKEN }}\n",
        encoding="utf-8",
    )
    (tmp_path / "PYPI_PUBLISHING_AUDIT.md").write_text(audit_text, encoding="utf-8")

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert "forbidden_workflow_terms_absent" in payload["errors"]


def test_build_job_oidc_blocks(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_text = (ROOT / ".github" / "workflows" / "publish-to-pypi.yml").read_text(encoding="utf-8")
    audit_text = (ROOT / "PYPI_PUBLISHING_AUDIT.md").read_text(encoding="utf-8")
    (workflow_dir / "publish-to-pypi.yml").write_text(
        workflow_text.replace("    steps:\n      - name: Checkout", "    permissions:\n      id-token: write\n    steps:\n      - name: Checkout", 1),
        encoding="utf-8",
    )
    (tmp_path / "PYPI_PUBLISHING_AUDIT.md").write_text(audit_text, encoding="utf-8")

    payload = build_payload(tmp_path)

    assert payload["ok"] is False
    assert "build_job_has_no_id_token" in payload["errors"]


def test_cli_writes_pypi_publish_artifacts(tmp_path):
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
    assert (output_dir / "pypi_trusted_publish_pipeline_verification.json").exists()
    assert (output_dir / "context_packet.md").exists()
    assert (output_dir / "closeout.md").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["pypi_publish_executed"] is False
    assert summary["trusted_publisher_verified_live"] is False
    assert summary["external_publication_allowed"] is False

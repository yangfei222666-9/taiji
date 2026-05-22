from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aios.userland.product_spine.verify_run import ROOT, build_payload


VERIFY_RUN = ROOT / "aios" / "userland" / "product_spine" / "verify_run.py"
FIXTURE_RUN = ROOT / "runs" / "ops_check" / "product_spine_schema_extract_20260522"


def test_current_product_spine_schema_extract_packet_verifies_without_repo_pass():
    payload = build_payload(FIXTURE_RUN, repo_root=ROOT)

    assert payload["ok"] is True
    assert payload["checks"]["summary_json_parses"] is True
    assert payload["checks"]["event_flow_jsonl_parses"] is True
    assert payload["checks"]["forbidden_claims_absent"] is True
    assert payload["forbidden_claims"] == []
    assert payload["repo_pass"] is False
    assert payload["safety"]["secret_value_read"] is False
    assert payload["safety"]["external_provider_called"] is False
    assert payload["safety"]["trade_or_order"] is False
    assert payload["verdict"] in {
        "product_spine_run_verified_scope_only",
        "partial_product_spine_verified_dirty_tree",
    }


def test_missing_summary_blocks(tmp_path):
    _write_valid_run(tmp_path)
    (tmp_path / "summary.json").unlink()

    payload = build_payload(tmp_path, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "blocked_product_spine_artifact_missing"
    assert "summary_json_present" in payload["errors"]


def test_invalid_event_flow_jsonl_fails(tmp_path):
    _write_valid_run(tmp_path)
    (tmp_path / "event_flow.jsonl").write_text("{not json}\n", encoding="utf-8")

    payload = build_payload(tmp_path, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "failed_product_spine_artifact_parse"
    assert payload["parse_errors"]


def test_forbidden_trade_claim_blocks(tmp_path):
    _write_valid_run(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    summary["trade_allowed"] = True
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    payload = build_payload(tmp_path, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "blocked_product_spine_forbidden_claim"
    assert any("trade_allowed" in claim for claim in payload["forbidden_claims"])


def test_scope_pass_as_repo_pass_blocks(tmp_path):
    _write_valid_run(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    summary["git_scope"]["repo_pass_claimed"] = True
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    payload = build_payload(tmp_path, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "blocked_product_spine_forbidden_claim"
    assert any("repo_pass_claimed" in claim for claim in payload["forbidden_claims"])


def test_missing_required_event_sequence_is_partial(tmp_path):
    _write_valid_run(tmp_path)
    events = _read_events(tmp_path / "event_flow.jsonl")
    events = [event for event in events if event["event"] != "closeout_written"]
    _write_events(tmp_path / "event_flow.jsonl", events)

    payload = build_payload(tmp_path, repo_root=tmp_path)

    assert payload["ok"] is False
    assert payload["verdict"] == "partial_product_spine_contract_incomplete"
    assert "required_event_sequence_present" in payload["errors"]
    assert "closeout_written" in payload["missing"]["event_names"]


def test_cli_writes_product_spine_verifier_artifacts(tmp_path):
    _write_valid_run(tmp_path / "run")
    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_RUN),
            str(tmp_path / "run"),
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
    assert (output_dir / "product_spine_run_verification.json").exists()
    assert (output_dir / "closeout.md").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] in {
        "ok_product_spine_verifier_impl_prepared",
        "partial_product_spine_verifier_impl_scope_dirty",
        "partial_product_spine_verifier_impl_git_unavailable",
    }
    assert "verified_run_verdict" in summary
    assert summary["repo_pass"] is False
    assert summary["provider_ready"] is False
    assert summary["trade_allowed"] is False
    assert summary["promote_allowed"] is False


def _write_valid_run(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    scope = "example_product_spine_run"
    summary = {
        "schema_version": "0.1",
        "scope": scope,
        "mode": "docs_schema_tests_only",
        "verdict": "partial_example_scope_dirty",
        "not_claimed": [
            "repo PASS",
            "provider/API ready",
            "trade/order ready",
            "promotion ready",
        ],
        "git_scope": {
            "branch": "main",
            "staged_count": 0,
            "repo_pass_claimed": False,
        },
    }
    (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    events = [
        _event("scope_started", scope),
        _event("boot_preflight_completed", scope),
        _event("artifact_memory_written", scope),
        _event("event_flow_written", scope),
        _event("verifier_completed", scope),
        _event("closeout_written", scope),
        _event("scope_completed", scope),
    ]
    _write_events(path / "event_flow.jsonl", events)
    (path / "closeout.md").write_text(
        "\n".join(
            [
                "# Closeout",
                "",
                "verdict: `partial_example_scope_dirty`",
                f"scope: `{scope}`",
                "mode: `docs_schema_tests_only`",
                "",
                "## Artifacts",
                "- `summary.json`",
                "- `event_flow.jsonl`",
                "",
                "## Verification",
                "- parse: `pass`",
                "",
                "## Git State",
                "- staged_count: `0`",
                "",
                "## Boundaries Kept",
                "- provider/trade/promotion blocked",
                "",
                "## Not Claimed",
                "- repo PASS",
                "- provider/API ready",
                "- trade/order ready",
                "- promotion ready",
                "",
                "## Next Allowed Action",
                "Review only.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _event(name: str, scope: str) -> dict[str, object]:
    return {
        "ts": "2026-05-22T00:00:00+00:00",
        "event": name,
        "scope": scope,
        "status": "ok",
        "product_spine_component": "Closeout",
        "input_refs": [],
        "output_refs": [],
        "boundary_flags": {
            "read_secret": False,
            "provider_called": False,
            "trade_or_order": False,
            "stage_commit_push": False,
        },
        "evidence": {},
        "not_claimed": [
            "repo PASS",
            "provider/API ready",
            "trade/order ready",
            "promotion ready",
        ],
    }


def _read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

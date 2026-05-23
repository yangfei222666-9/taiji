from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.daily_learning_paper_intake import ROOT, build_payload, verify_run_dir, write_run


SCRIPT = ROOT / "tools" / "daily_learning_paper_intake.py"


def _offline_source(tmp_path: Path) -> Path:
    source = tmp_path / "offline_source.json"
    source.write_text(
        json.dumps(
            {
                "papers": [
                    {
                        "title": "Verified Agent Runtime for Tool Use and Event Traces",
                        "url": "https://arxiv.org/abs/2605.00001",
                        "published": "2026-05-23T00:00:00Z",
                        "updated": "2026-05-23T00:00:00Z",
                        "authors": ["Example Author"],
                        "summary": "An AI agent runtime study with workflow verification, tool use, memory, and event trace evidence.",
                    },
                    {
                        "title": "Embodied Robot Mission Evidence for Space Operations",
                        "url": "https://arxiv.org/abs/2605.00002",
                        "published": "2026-05-23T01:00:00Z",
                        "updated": "2026-05-23T01:00:00Z",
                        "authors": ["Example Roboticist"],
                        "summary": "A robotics and rover mission benchmark for physical AI safety and space mission simulation.",
                    },
                ],
                "user_inputs": [
                    {
                        "source": "offline_user_input",
                        "claim": "User note about Evidence Kernel daily learning.",
                        "evidence": {"kind": "note"},
                        "uncertainty": "user_supplied_unverified_note",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return source


def test_build_payload_from_offline_source_is_learning_only(tmp_path):
    payload = build_payload(
        repo_root=ROOT,
        run_date="2026-05-23",
        offline_source=_offline_source(tmp_path),
        skip_network=True,
    )

    assert payload["verdict"] == "PASS"
    assert payload["scope"] == "daily_learning_paper_intake"
    assert payload["mode"] == "learning_only_observe_only"
    assert payload["paper_count"] == 2
    assert payload["user_input_count"] == 1
    assert payload["risk_flags"]["learning_only"] is True
    assert payload["risk_flags"]["judgment_allowed"] is False
    assert payload["risk_flags"]["promote_allowed"] is False
    assert payload["risk_flags"]["paper_buy_allowed"] is False
    assert payload["risk_flags"]["trade_allowed"] is False
    assert payload["repo_pass"] is False
    assert payload["papers_collected"][0]["provider_output_is_truth"] is False
    assert "Operator Toolchain" in payload["papers_collected"][0]["taijios_relevance"]
    assert "Physical AI Sandbox" in payload["papers_collected"][1]["taijios_relevance"]
    assert "SpaceOps Simulation Kernel" in payload["papers_collected"][1]["taijios_relevance"]


def test_write_run_creates_parseable_artifacts(tmp_path):
    payload = build_payload(
        repo_root=ROOT,
        run_date="2026-05-23",
        offline_source=_offline_source(tmp_path),
        skip_network=True,
    )
    run_dir = tmp_path / "run"
    paths = write_run(payload, run_dir)
    verification = verify_run_dir(run_dir)

    assert paths.summary.exists()
    assert paths.event_flow.exists()
    assert paths.learning_digest.exists()
    assert paths.closeout.exists()
    assert verification["ok"] is True
    summary = json.loads(paths.summary.read_text(encoding="utf-8"))
    assert summary["verdict"] == "PASS"
    assert summary["not_claimed"]
    events = [json.loads(line) for line in paths.event_flow.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event"] == "scope_completed"
    assert all(event["boundary_flags"]["trade_allowed"] is False for event in events)


def test_blocked_without_sources_or_network():
    payload = build_payload(
        repo_root=ROOT,
        run_date="2026-05-23",
        skip_network=True,
    )

    assert payload["verdict"] == "BLOCKED"
    assert payload["blocked_stage"] == "source_collection"
    assert payload["minimum_fix"] == "restore network/source access or provide an offline-source JSON file"


def test_user_input_path_metadata_does_not_read_secretish_content(tmp_path):
    secretish = tmp_path / ".env"
    secretish.write_text("SECRET_VALUE=do-not-read\n", encoding="utf-8")
    payload = build_payload(
        repo_root=ROOT,
        run_date="2026-05-23",
        user_input_paths=[secretish],
        skip_network=True,
    )

    assert payload["verdict"] == "PASS"
    item = payload["user_inputs_received"][0]
    assert item["evidence"]["read_content"] is False
    assert item["evidence"]["secretish_name_blocked"] is True
    assert "SECRET_VALUE" not in json.dumps(payload)
    assert item["secret_read"] is False if "secret_read" in item else payload["risk_flags"]["secret_read"] is False


def test_cli_writes_daily_learning_artifacts(tmp_path):
    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(ROOT),
            "--date",
            "2026-05-23",
            "--offline-source",
            str(_offline_source(tmp_path)),
            "--skip-network",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["verdict"] == "PASS"
    assert payload["verification_ok"] is True
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "event_flow.jsonl").exists()
    assert (output_dir / "learning_digest.md").exists()
    assert (output_dir / "closeout.md").exists()

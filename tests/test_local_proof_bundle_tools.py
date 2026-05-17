from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_local_proof_bundle.py"
VERIFY = ROOT / "tools" / "verify_local_proof_bundle_registry.py"


def write_source_run(base: Path, name: str = "source_run") -> Path:
    run_dir = base / name
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps({"schema_version": "test.v1", "verdict": "ok_test"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "event_flow.jsonl").write_text('{"event":"test_done"}\n', encoding="utf-8")
    return run_dir


def run_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def test_build_local_proof_bundle_creates_archive(tmp_path: Path) -> None:
    write_source_run(tmp_path)
    result = run_cmd(
        [
            sys.executable,
            str(BUILD),
            "--base-dir",
            str(tmp_path),
            "--run-dir",
            "source_run",
            "--out-dir",
            "out",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "ok_local_proof_bundle_created"
    assert Path(summary["archive_path"]).exists()
    assert Path(summary["archive_sha256_path"]).exists()
    assert summary["secret_like_findings_count"] == 0


def test_build_local_proof_bundle_blocks_existing_out_dir(tmp_path: Path) -> None:
    write_source_run(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "existing.txt").write_text("already here\n", encoding="utf-8")

    result = run_cmd(
        [
            sys.executable,
            str(BUILD),
            "--base-dir",
            str(tmp_path),
            "--run-dir",
            "source_run",
            "--out-dir",
            "out",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["verdict"] == "blocked_out_dir_already_exists"


def test_build_local_proof_bundle_blocks_secret_like_content(tmp_path: Path) -> None:
    run_dir = write_source_run(tmp_path)
    (run_dir / "token.txt").write_text(
        "DEEPSEEK_API_KEY=fake-deepseek-key-redacted-fixture\n",
        encoding="utf-8",
    )

    result = run_cmd(
        [
            sys.executable,
            str(BUILD),
            "--base-dir",
            str(tmp_path),
            "--run-dir",
            "source_run",
            "--out-dir",
            "out",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 2
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "blocked"
    assert "secret_like_findings_present" in summary["failure_cause"]


def test_verify_registry_blocks_tampered_archive_sha(tmp_path: Path) -> None:
    write_source_run(tmp_path)
    build_result = run_cmd(
        [
            sys.executable,
            str(BUILD),
            "--base-dir",
            str(tmp_path),
            "--run-dir",
            "source_run",
            "--out-dir",
            "out",
        ],
        cwd=ROOT,
    )
    assert build_result.returncode == 0, build_result.stderr
    build_summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    archive = Path(build_summary["archive_path"])
    registry = {
        "schema_version": "taijios.local_proof_bundle_registry.v1",
        "items": [
            {
                "archive_path": str(archive.relative_to(tmp_path)),
                "archive_sha256": "0" * 64,
            }
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")

    result = run_cmd(
        [
            sys.executable,
            str(VERIFY),
            "--base-dir",
            str(tmp_path),
            "--registry",
            "registry.json",
            "--out-dir",
            "verify",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 2
    summary = json.loads((tmp_path / "verify" / "summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "blocked_local_proof_bundle_registry_verification_failed"
    assert summary["failed_archive_count"] == 1

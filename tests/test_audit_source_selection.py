"""Exercise the real detector with fixture HTTP responses; never contact GitHub."""
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CURL_STUB = r'''
import json, os, sys, zipfile
from pathlib import Path
from urllib.parse import urlsplit
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith("https://"))
with open(os.environ["REQUEST_LOG"], "a") as log:
    log.write(url + "\n")
data = json.loads(Path(os.environ["HTTP_FIXTURE"]).read_text())
path = urlsplit(url).path
if path.endswith("/runs"):
    if data.get("runs_error"):
        sys.exit(22)
    print(json.dumps(data.get("runs_payload", {"workflow_runs": data["runs"]})))
elif path.endswith("/artifacts"):
    run_id = path.split("/")[-2]
    if run_id == data.get("artifacts_error"):
        sys.exit(22)
    artifacts = data.get("artifacts", {}).get(run_id, [])
    print(json.dumps({"total_count": len(artifacts), "artifacts": artifacts}))
elif path.startswith("/archive/"):
    target = args[args.index("-o") + 1]
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("build.txt", data.get("content", "build alpha"))
else:
    sys.exit(22)
'''


def run(run_id, path=".github/workflows/release.yml", name="release"):
    return {"id": run_id, "path": path, "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "completed",
            "conclusion": "success"}


def artifact(name="taiji-evidence-abc", expired=False):
    return {"name": name, "expired": expired, "updated_at": datetime.now(timezone.utc).isoformat(),
            "archive_download_url": "https://fixtures.invalid/archive/build.zip"}


@pytest.fixture
def detector(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    # A quoted interpreter path also supports workspaces with spaces.
    curl.write_text('#!/bin/sh\nexec "' + sys.executable + '" "' +
                    str(bin_dir / "curl_fixture.py") + '" "$@"\n')
    curl.chmod(0o755)
    (bin_dir / "curl_fixture.py").write_text(CURL_STUB)
    counter = 0

    def invoke(data, **overrides):
        nonlocal counter
        counter += 1
        fixture = tmp_path / "http.json"
        fixture.write_text(json.dumps(data))
        request_log = tmp_path / f"requests-{counter}.txt"
        out = tmp_path / f"out-{counter}"
        env = {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
               "GH_TOKEN": "fixture-only", "GITHUB_REPOSITORY": "example/project",
               "GITHUB_RUN_ID": "900", "STATE_DIR": str(tmp_path / "state"),
               "AUDIT_OUT_DIR": str(out), "REKOR_REQUIRED": "0",
               "REKOR_OFFLINE_MODE": "1", "COSIGN_VERIFY_REQUIRED": "0",
               "HTTP_FIXTURE": str(fixture), "REQUEST_LOG": str(request_log),
               **overrides}
        result = subprocess.run(["bash", ".audit/material_detector.sh"], cwd=ROOT,
                                env=env, text=True, capture_output=True, timeout=30)
        summary = json.loads((out / "summary.json").read_text())
        requests = request_log.read_text().splitlines()
        return result, summary, requests, out

    return invoke


def test_selects_release_evidence_and_excludes_audit_runs(detector):
    data = {"runs": [run(900), run(899, ".github/workflows/taijios-audit-pulse.yml@main"),
                     run(898, name="taijios-audit-pulse"), run(101)],
            "artifacts": {"101": [artifact(), artifact("coverage-xml-3.12"),
                                    artifact("taiji-evidence-expired", expired=True)]}}
    result, summary, requests, out = detector(data)
    assert result.returncode == 0, result.stderr
    assert summary["run_id"] == "101" and summary["pulse_emitted"]
    assert "/actions/workflows/release.yml/runs?" in requests[0]
    assert len(requests) == 3  # One run list, one artifact list, one download.
    assert [a["name"] for a in json.loads((out / "manifest.json").read_text())["artifacts"]] == ["taiji-evidence-abc"]


@pytest.mark.parametrize("runs, artifacts", [
    ([], {}),
    ([run(899, ".github/workflows/taijios-audit-pulse.yml@refs/heads/main")], {}),
    ([run(101)], {"101": [artifact("taijios-audit-pulse-101")]}),
    ([run(101)], {"101": [artifact("coverage-xml-3.12")]}),
    ([run(101)], {"101": [artifact(expired=True)]}),
])
def test_no_eligible_source_is_pending_without_pulse(detector, runs, artifacts):
    result, summary, requests, _ = detector({"runs": runs, "artifacts": artifacts})
    assert result.returncode == 0, result.stderr
    assert summary["verdict"] == "PENDING"
    assert not summary["pulse_emitted"] and not summary["material_changed"]
    assert not any("/archive/" in url for url in requests)


def test_skips_expired_newer_run_and_deduplicates_unchanged_content(detector):
    data = {"runs": [run(102), run(101)],
            "artifacts": {"102": [artifact(expired=True)], "101": [artifact()]}}
    first, initial, _, _ = detector(data)
    second, repeated, _, _ = detector(data)
    assert first.returncode == second.returncode == 0
    assert initial["run_id"] == repeated["run_id"] == "101"
    assert initial["pulse_emitted"] and not repeated["pulse_emitted"]
    assert not repeated["material_changed"]
    data["content"] = "build beta"
    third, changed, _, _ = detector(data)
    assert third.returncode == 0 and changed["material_changed"] and changed["pulse_emitted"]


@pytest.mark.parametrize("failure", [
    {"runs_error": True}, {"runs_payload": {}}, {"artifacts_error": "101"},
])
def test_api_failure_is_blocked_not_an_empty_source(detector, failure):
    result, summary, _, _ = detector({"runs": [run(101)], **failure})
    assert result.returncode == 2
    assert summary["verdict"] == "BLOCKED" and summary["blocked_stage"] == "github_fetch"
    assert not summary["pulse_emitted"]

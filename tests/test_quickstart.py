"""Test that the quickstart example runs and produces correct output."""
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def test_quickstart_runs_successfully(tmp_path, monkeypatch):
    """python examples/quickstart_minimal.py must exit 0 and produce evidence."""
    monkeypatch.setenv("TAIJI_QUICKSTART_OUTPUT_DIR", str(tmp_path))
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "examples" / "quickstart_minimal.py")],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Quickstart failed:\n{result.stderr}"
    assert "succeeded" in result.stdout.lower()
    assert "Mode: deterministic_simulation" in result.stdout
    assert "fixed scores 0.35 -> 0.90; no model evaluation" in result.stdout

    # Check evidence file was created
    evidence_path = tmp_path / "quickstart_evidence.json"
    assert evidence_path.exists(), "Evidence file not created"

    evidence = json.loads(evidence_path.read_text())
    assert evidence["mode"] == "deterministic_simulation"
    assert evidence["total_tasks"] == 3
    assert evidence["succeeded"] == 3
    assert evidence["self_healed"] == 3
    assert evidence["event_log_count"] == 18
    for task in evidence["results"]:
        scores = [step["output"]["score"] for step in task["trace"]["steps"] if step["name"].startswith("validate:")]
        assert scores == [0.35, 0.90]

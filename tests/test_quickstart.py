"""Test that the quickstart example runs and produces correct output."""
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def test_quickstart_runs_successfully():
    """python examples/quickstart_minimal.py must exit 0 and produce evidence."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "examples" / "quickstart_minimal.py")],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"Quickstart failed:\n{result.stderr}"
    assert "succeeded" in result.stdout.lower()

    # Check evidence file was created
    evidence_path = PROJECT_ROOT / "examples" / "quickstart_output" / "quickstart_evidence.json"
    assert evidence_path.exists(), "Evidence file not created"

    evidence = json.loads(evidence_path.read_text())
    assert evidence["total_tasks"] == 3
    assert evidence["succeeded"] == 3
    assert evidence["self_healed"] == 3

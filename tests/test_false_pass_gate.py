import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "check_false_pass_gate.py"
FIXTURES = PROJECT_ROOT / "examples" / "false_pass_gate" / "fixtures"


def run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_self_test_fixture_suite_passes():
    result = run_gate("--self-test", str(FIXTURES))

    assert result.returncode == 0, result.stderr
    assert "self_test=PASS" in result.stdout
    assert "cases=3" in result.stdout


def test_unsupported_done_claim_is_blocked():
    result = run_gate("--case", str(FIXTURES / "fail_unsupported_done.json"))

    assert result.returncode == 1
    assert "case_id=fail_unsupported_done" in result.stdout
    assert "actual=BLOCKED" in result.stdout
    assert "missing_passing_evidence" in result.stdout


def test_case_with_passing_evidence_and_boundaries_passes():
    result = run_gate("--case", str(FIXTURES / "pass_with_evidence.json"))

    assert result.returncode == 0, result.stderr
    assert "case_id=pass_with_evidence" in result.stdout
    assert "actual=PASS" in result.stdout


def test_proof_index_records_false_pass_gate_claim_and_limits():
    proof_index = json.loads((PROJECT_ROOT / "docs" / "proof_index.json").read_text())

    matching_claims = [
        claim
        for claim in proof_index["claims"]
        if "False-Pass Gate" in claim["claim"]
    ]
    assert matching_claims
    assert matching_claims[0]["verdict"] == "LOCAL_VALIDATED when self-test and pytest pass"
    assert "remote CI" in matching_claims[0]["limitation"]
    assert "false_pass_gate_without_evidence" in proof_index["blocked_claims"]

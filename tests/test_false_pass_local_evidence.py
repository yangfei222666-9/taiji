import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_false_pass_gate.py'


def check(tmp_path, evidence, *, strict=True):
    case = tmp_path / 'case.json'
    case.write_text(json.dumps({
        'case_id': 'local-evidence', 'agent_claim': 'done', 'evidence': evidence,
        'cannot_claim': ['command_execution', 'production_readiness'],
    }))
    args = [sys.executable, str(SCRIPT), '--case', str(case)]
    if strict:
        args += ['--evidence-root', str(tmp_path / 'evidence')]
    return subprocess.run(args, text=True, capture_output=True, timeout=10)


def item(path='result.txt', data=b'synthetic output\n'):
    return {'type': 'test', 'status': 'PASS', 'file': path,
            'sha256': hashlib.sha256(data).hexdigest()}


def test_local_file_hash_accepts_matching_bytes_and_rejects_tampering(tmp_path):
    root = tmp_path / 'evidence'
    root.mkdir()
    (root / 'result.txt').write_bytes(b'synthetic output\n')
    passed = check(tmp_path, [item()])
    assert passed.returncode == 0, passed.stderr
    assert 'verification_mode=local_file_hashes' in passed.stdout
    (root / 'result.txt').write_bytes(b'changed output\n')
    rejected = check(tmp_path, [item()])
    assert rejected.returncode == 1
    assert 'evidence_sha256_mismatch' in rejected.stdout


def test_schema_mode_is_explicit_and_does_not_verify_pointers(tmp_path):
    result = check(tmp_path, [item('does-not-exist.txt')], strict=False)
    assert result.returncode == 0
    assert 'verification_mode=schema_only' in result.stdout


@pytest.mark.parametrize('evidence, reason', [
    ([item('missing.txt')], 'evidence_file_unreadable'),
    ([item('../outside.txt')], 'invalid_evidence_path'),
    ([item('/outside.txt')], 'invalid_evidence_path'),
    ([item('C:\\outside.txt')], 'invalid_evidence_path'),
    ([{**item(), 'sha256': 'not-a-hash'}], 'invalid_evidence_sha256'),
    ([{'type': 'command', 'status': 'PASS', 'command': 'echo done'}], 'missing_local_evidence_file'),
    ([{**item(), 'artifact': 'other.txt'}], 'ambiguous_evidence_path'),
])
def test_local_evidence_rejects_unverifiable_claims(tmp_path, evidence, reason):
    (tmp_path / 'evidence').mkdir()
    result = check(tmp_path, evidence)
    assert result.returncode == 1
    assert reason in result.stdout


def test_valid_file_does_not_hide_another_invalid_pass_claim(tmp_path):
    (tmp_path / 'evidence').mkdir()
    (tmp_path / 'evidence/result.txt').write_bytes(b'synthetic output\n')
    result = check(tmp_path, [item(), item('missing.txt')])
    assert result.returncode == 1
    assert 'evidence_file_unreadable' in result.stdout


@pytest.mark.parametrize('directory', [False, True])
def test_local_evidence_rejects_symlink_files_and_directories(tmp_path, directory):
    root = tmp_path / 'evidence'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'result.txt').write_bytes(b'synthetic output\n')
    if directory:
        (root / 'link').symlink_to(outside, target_is_directory=True)
        path = 'link/result.txt'
    else:
        (root / 'link').symlink_to(outside / 'result.txt')
        path = 'link'
    result = check(tmp_path, [item(path)])
    assert result.returncode == 1
    assert 'evidence_file_unreadable' in result.stdout


def test_nested_artifact_alias_and_uppercase_hash_are_supported(tmp_path):
    (tmp_path / 'evidence/nested folder').mkdir(parents=True)
    (tmp_path / 'evidence/nested folder/result.txt').write_bytes(b'synthetic output\n')
    evidence = item('nested folder/result.txt')
    evidence['artifact'] = evidence.pop('file')
    evidence['sha256'] = evidence['sha256'].upper()
    assert check(tmp_path, [evidence]).returncode == 0


def test_evidence_root_is_required_to_be_a_real_directory(tmp_path):
    result = check(tmp_path, [item()])
    assert result.returncode == 1
    assert 'invalid_evidence_root' in result.stdout


@pytest.mark.parametrize('kind', ['directory', 'fifo'])
def test_special_files_are_rejected_without_blocking(tmp_path, kind):
    (tmp_path / 'evidence').mkdir()
    target = tmp_path / 'evidence/result.txt'
    if kind == 'directory':
        target.mkdir()
    else:
        os.mkfifo(target)
    result = check(tmp_path, [item()])
    assert result.returncode == 1
    assert 'evidence_not_regular_file' in result.stdout


def test_untrusted_command_is_never_executed(tmp_path):
    (tmp_path / 'evidence').mkdir()
    marker = tmp_path / 'must-not-exist'
    result = check(tmp_path, [{'type': 'command', 'status': 'PASS',
                               'command': f'touch {marker}'}])
    assert result.returncode == 1
    assert not marker.exists()


def test_file_descriptor_is_closed_if_metadata_read_fails(tmp_path):
    spec = importlib.util.spec_from_file_location('local_evidence_gate', SCRIPT)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    (tmp_path / 'result.txt').write_bytes(b'synthetic output\n')
    captured = []

    def fail_stat(fd):
        captured.append(fd)
        raise OSError('synthetic metadata failure')

    with mock.patch.object(gate.os, 'fstat', side_effect=fail_stat):
        reason = gate._verify_local_file(item(), tmp_path)
    assert reason == 'evidence_file_unreadable'
    assert len(captured) == 1
    with pytest.raises(OSError):
        os.fstat(captured[0])


def test_invalid_case_is_rejected_without_traceback(tmp_path):
    case = tmp_path / 'case.json'
    case.write_text('[]')
    result = subprocess.run([sys.executable, str(SCRIPT), '--case', str(case)],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert 'invalid_case_input' in result.stdout
    assert 'Traceback' not in result.stderr

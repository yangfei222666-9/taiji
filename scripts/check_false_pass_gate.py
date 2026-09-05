#!/usr/bin/env python3
"""Block unsupported AI-agent success claims before they become evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any


SUCCESS_TOKENS = {
    "done",
    "ready",
    "complete",
    "completed",
    "success",
    "succeeded",
    "pass",
    "passed",
    "local_validated",
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text_tokens(case: dict[str, Any]) -> set[str]:
    values = _as_list(case.get("success_claims"))
    if case.get("agent_claim"):
        values.append(case["agent_claim"])
    return {str(value).lower().replace("-", "_") for value in values}


def _is_success_claim(case: dict[str, Any]) -> bool:
    tokens = _text_tokens(case)
    return any(token in SUCCESS_TOKENS for token in tokens) or any(
        word in token for token in tokens for word in SUCCESS_TOKENS
    )


def _has_passing_evidence(case: dict[str, Any]) -> bool:
    for item in _as_list(case.get("evidence")):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).upper()
        has_pointer = any(item.get(key) for key in ("command", "file", "artifact", "url", "value"))
        if status == "PASS" and item.get("type") and has_pointer:
            return True
    return False


def _verify_local_file(item: dict[str, Any], root: Path) -> str | None:
    """Check bytes through directory-relative, no-follow file descriptors."""
    file_path, artifact = item.get("file"), item.get("artifact")
    if file_path and artifact and file_path != artifact:
        return "ambiguous_evidence_path"
    raw_path = file_path or artifact
    if raw_path is None:
        return "missing_local_evidence_file"
    if not isinstance(raw_path, str) or not raw_path.strip():
        return "invalid_evidence_path"
    path = PurePosixPath(raw_path)
    if (path.is_absolute() or not path.parts or ".." in path.parts
            or "\\" in raw_path or "\0" in raw_path or re.match(r"^[A-Za-z]:", raw_path)):
        return "invalid_evidence_path"
    expected = item.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        return "invalid_evidence_sha256"
    if not isinstance(item.get("type"), str) or not item["type"].strip():
        return "invalid_evidence_type"

    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in path.parts[:-1]:
            child_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                               dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        # NONBLOCK lets us reject FIFOs before any blocking read occurs.
        file_fd = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            return "evidence_not_regular_file"
        with os.fdopen(file_fd, "rb", closefd=False) as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                return "evidence_changed_during_read"
            if digest.hexdigest() != expected.lower():
                return "evidence_sha256_mismatch"
    except (OSError, ValueError):
        return "evidence_file_unreadable"
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    return None


def _local_evidence_reasons(case: dict[str, Any], evidence_root: Path) -> list[str]:
    if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")) or os.open not in os.supports_dir_fd:
        return ["local_file_verification_unsupported"]
    try:
        # The caller chooses this trusted root; symlinks below it are rejected.
        root = evidence_root.resolve(strict=True)
        if not root.is_dir():
            return ["invalid_evidence_root"]
    except (OSError, ValueError, RuntimeError):
        return ["invalid_evidence_root"]
    reasons = []
    for item in _as_list(case.get("evidence")):
        if isinstance(item, dict) and str(item.get("status", "")).upper() == "PASS":
            reason = _verify_local_file(item, root)
            if reason and reason not in reasons:
                reasons.append(reason)
    return reasons


def evaluate_case(case: dict[str, Any], *, evidence_root: Path | None = None) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if _is_success_claim(case) and not _has_passing_evidence(case):
        reasons.append("missing_passing_evidence")

    if not _as_list(case.get("cannot_claim")):
        reasons.append("missing_cannot_claim")

    if evidence_root is not None:
        reasons.extend(_local_evidence_reasons(case, evidence_root))

    if reasons:
        return "BLOCKED", reasons
    return "PASS", ["evidence_and_boundaries_present"]


def load_case(path: Path) -> dict[str, Any]:
    case = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(case, dict):
        raise ValueError("case must be a JSON object")
    return case


def format_case_result(path: Path, actual: str, expected: str | None, reasons: list[str],
                       *, case: dict[str, Any] | None = None, verification_mode: str = "schema_only") -> str:
    case_id = (case if case is not None else load_case(path)).get("case_id", path.stem)
    fields = [
        f"case_id={case_id}",
        f"actual={actual}",
        f"verification_mode={verification_mode}",
        f"reasons={','.join(reasons)}",
    ]
    if expected:
        fields.append(f"expected={expected}")
    return " ".join(fields)


def run_case(path: Path, *, evidence_root: Path | None = None) -> int:
    case = load_case(path)
    actual, reasons = evaluate_case(case, evidence_root=evidence_root)
    mode = "local_file_hashes" if evidence_root is not None else "schema_only"
    print(format_case_result(path, actual, case.get("expected_verdict"), reasons,
                             case=case, verification_mode=mode))
    return 0 if actual == "PASS" else 1


def run_self_test(fixtures_dir: Path) -> int:
    if not fixtures_dir.is_dir():
        print(
            f"self_test=FAIL cases=0 "
            f"reason=fixtures_dir_not_found path={fixtures_dir}"
        )
        return 1

    paths = sorted(fixtures_dir.glob("*.json"))
    if not paths:
        print(
            f"self_test=FAIL cases=0 "
            f"reason=no_fixtures path={fixtures_dir}"
        )
        return 1

    failures: list[str] = []

    for path in paths:
        case = load_case(path)
        actual, reasons = evaluate_case(case)
        expected = str(case.get("expected_verdict", "")).upper()
        print(format_case_result(path, actual, expected, reasons, case=case))
        if actual != expected:
            failures.append(path.name)

    if failures:
        print(f"self_test=FAIL cases={len(paths)} failures={','.join(failures)}")
        return 1

    print(f"self_test=PASS cases={len(paths)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check false-pass evidence gates.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", type=Path, help="Evaluate one JSON case file.")
    group.add_argument("--self-test", type=Path, help="Evaluate all JSON fixtures in a directory.")
    parser.add_argument("--evidence-root", type=Path,
                        help="With --case, verify every PASS file/artifact and its sha256 under this trusted local directory; never execute commands or fetch URLs.")
    args = parser.parse_args()
    if args.evidence_root is not None and args.case is None:
        parser.error("--evidence-root requires --case; --self-test uses schema-only fixtures")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.case:
            return run_case(args.case, evidence_root=args.evidence_root)
        return run_self_test(args.self_test)
    except (OSError, ValueError) as error:
        print(f"actual=BLOCKED reasons=invalid_case_input error_type={type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

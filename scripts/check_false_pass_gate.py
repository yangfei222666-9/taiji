#!/usr/bin/env python3
"""Block unsupported AI-agent success claims before they become evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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


def evaluate_case(case: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if _is_success_claim(case) and not _has_passing_evidence(case):
        reasons.append("missing_passing_evidence")

    if not _as_list(case.get("cannot_claim")):
        reasons.append("missing_cannot_claim")

    if reasons:
        return "BLOCKED", reasons
    return "PASS", ["evidence_and_boundaries_present"]


def load_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_case_result(path: Path, actual: str, expected: str | None, reasons: list[str]) -> str:
    case_id = load_case(path).get("case_id", path.stem)
    fields = [
        f"case_id={case_id}",
        f"actual={actual}",
        f"reasons={','.join(reasons)}",
    ]
    if expected:
        fields.append(f"expected={expected}")
    return " ".join(fields)


def run_case(path: Path) -> int:
    case = load_case(path)
    actual, reasons = evaluate_case(case)
    print(format_case_result(path, actual, case.get("expected_verdict"), reasons))
    return 0 if actual == "PASS" else 1


def run_self_test(fixtures_dir: Path) -> int:
    paths = sorted(fixtures_dir.glob("*.json"))
    failures: list[str] = []

    for path in paths:
        case = load_case(path)
        actual, reasons = evaluate_case(case)
        expected = str(case.get("expected_verdict", "")).upper()
        print(format_case_result(path, actual, expected, reasons))
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.case:
        return run_case(args.case)
    return run_self_test(args.self_test)


if __name__ == "__main__":
    raise SystemExit(main())

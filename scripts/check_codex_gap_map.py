#!/usr/bin/env python3
"""Validate Codex Reliability Gap Map #01 without judging issue truth."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "codex-reliability-gap-map-01.json"
DEFAULT_MD = ROOT / "docs" / "research" / "codex-reliability-gap-map-01.md"
REQUIRED_FIELDS = {
    "issue_id",
    "issue_url",
    "snapshot_date",
    "issue_status",
    "report_type",
    "labels",
    "user_reported_symptom",
    "maintainer_confirmation",
    "independent_reproduction",
    "failure_mode",
    "mapped_gate",
    "cannot_claim",
}
VALID_REPORT_TYPES = {"bug_report", "feature_request"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> int:
    print(f"gap_map=FAIL reason={message}")
    return 1


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return ["issues must be a list"]
    if payload.get("sample_size") != len(issues):
        errors.append("sample_size does not match issue count")
    if len(issues) != 30:
        errors.append("expected exactly 30 issue records")

    ids: list[int] = []
    modes = set((payload.get("failure_modes") or {}).keys())
    for idx, issue in enumerate(issues):
        missing = sorted(REQUIRED_FIELDS - set(issue))
        if missing:
            errors.append(f"issue[{idx}] missing fields: {', '.join(missing)}")
            continue
        issue_id = issue["issue_id"]
        ids.append(issue_id)
        if not isinstance(issue_id, int):
            errors.append(f"issue[{idx}] issue_id must be int")
        if not re.match(r"^https://github\.com/openai/codex/issues/\d+$", issue["issue_url"]):
            errors.append(f"issue[{idx}] issue_url must be an openai/codex issue URL")
        if issue["snapshot_date"] != payload.get("snapshot_date"):
            errors.append(f"issue[{idx}] snapshot_date mismatch")
        if issue["report_type"] not in VALID_REPORT_TYPES:
            errors.append(f"issue[{idx}] invalid report_type")
        if issue["failure_mode"] not in modes:
            errors.append(f"issue[{idx}] unknown failure_mode")
        if not isinstance(issue["labels"], list):
            errors.append(f"issue[{idx}] labels must be a list")
        if not isinstance(issue["cannot_claim"], list) or not issue["cannot_claim"]:
            errors.append(f"issue[{idx}] cannot_claim must be non-empty list")
        if issue["maintainer_confirmation"] == "confirmed" or issue["independent_reproduction"] == "performed":
            errors.append(f"issue[{idx}] validator cannot certify confirmation or reproduction")

    if len(ids) != len(set(ids)):
        errors.append("issue records contain duplicate issue_id values")

    stats = payload.get("statistics") or {}
    expected_counts: dict[str, int] = {}
    for issue in issues:
        expected_counts[issue["failure_mode"]] = expected_counts.get(issue["failure_mode"], 0) + 1
    if stats.get("failure_mode_counts") != dict(sorted(expected_counts.items())):
        errors.append("failure_mode_counts does not match issue records")
    return errors


def validate_markdown(payload: dict[str, Any], md_text: str) -> list[str]:
    errors: list[str] = []
    if "This is a scoped review of public user reports" not in md_text:
        errors.append("markdown missing scope limitation statement")
    if "An open issue is treated as a reported symptom, not a confirmed defect." not in md_text:
        errors.append("markdown missing reported-symptom limitation")
    for issue in payload["issues"]:
        token = f"[#{issue['issue_id']}]({issue['issue_url']})"
        if token not in md_text:
            errors.append(f"markdown missing issue link #{issue['issue_id']}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Codex Reliability Gap Map #01 files.")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_json(args.json)
    md_text = args.markdown.read_text(encoding="utf-8")
    errors = validate_payload(payload) + validate_markdown(payload, md_text)
    if errors:
        for error in errors:
            print(f"error={error}")
        return fail("validation_errors")
    print(
        "gap_map=PASS "
        f"sample_size={payload['sample_size']} "
        f"snapshot_date={payload['snapshot_date']} "
        f"issues={len(payload['issues'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

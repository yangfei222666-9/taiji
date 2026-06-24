from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_codex_gap_map.py"

spec = importlib.util.spec_from_file_location("check_codex_gap_map", SCRIPT)
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def load_payload() -> dict:
    return checker.load_json(ROOT / "data" / "codex-reliability-gap-map-01.json")


def test_gap_map_payload_passes_validator() -> None:
    payload = load_payload()
    md_text = (ROOT / "docs" / "research" / "codex-reliability-gap-map-01.md").read_text(encoding="utf-8")
    assert checker.validate_payload(payload) == []
    assert checker.validate_markdown(payload, md_text) == []


def test_duplicate_issue_ids_fail() -> None:
    payload = load_payload()
    broken = copy.deepcopy(payload)
    broken["issues"][1]["issue_id"] = broken["issues"][0]["issue_id"]
    errors = checker.validate_payload(broken)
    assert any("duplicate issue_id" in error for error in errors)


def test_missing_cannot_claim_fails() -> None:
    payload = load_payload()
    broken = copy.deepcopy(payload)
    broken["issues"][0]["cannot_claim"] = []
    errors = checker.validate_payload(broken)
    assert any("cannot_claim" in error for error in errors)


def test_markdown_must_include_scope_limitation() -> None:
    payload = load_payload()
    errors = checker.validate_markdown(payload, "# Missing the limitation")
    assert any("scope limitation" in error for error in errors)

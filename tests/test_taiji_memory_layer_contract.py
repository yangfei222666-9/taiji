from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_DOC = ROOT / "docs" / "TAIJIOS_MEMORY_LAYER_CONTRACT_v0.1.md"
DESIGN_DOC = ROOT / "docs" / "TAIJI_MEMORY_TREE_DESIGN_v0.1.md"
CHUNK_EXAMPLE = ROOT / "examples" / "taiji_memory_chunk_example.json"

REQUIRED_TRUE_FLAGS = (
    "clean_room",
    "no_openhuman_code_import",
    "local_first",
    "evidence_registry_is_ssot",
    "memory_is_candidate_context_not_truth",
    "model_output_is_not_truth",
    "no_secret_access",
    "no_env_read",
    "no_broker",
    "no_trade",
    "no_promotion",
    "no_judgment",
    "no_paper_buy",
    "no_pass_to_trade",
    "xuan_shu_renderer_only",
)

REQUIRED_FALSE_FLAGS = (
    "provider_called",
    "runtime_memory_store_implemented",
    "auto_fetch_enabled",
    "stage_commit_push",
)

ALLOWED_INPUT_TYPES = (
    "summary.json",
    "event_flow.jsonl",
    "closeout.md",
    "manifest.json",
    "public docs/*.md",
    "README.md",
)

FORBIDDEN_INPUT_TYPES = (
    ".env",
    "keychain",
    "token",
    "broker config",
    "private customer data",
    "Gmail",
    "Slack",
    "Notion",
    "OAuth",
    "raw provider secrets",
)

REQUIRED_PRESERVED_FIELDS = (
    "verdict",
    "scope",
    "mode",
    "repo_root",
    "branch",
    "staged_count",
    "dirty_tree",
    "commit",
    "push",
    "PR",
    "merge",
    "blocked_stage",
    "failure_cause",
    "minimum_fix",
    "not_claimed",
    "forbidden_claims",
    "what_is_verified",
    "what_is_not_claimed",
    "can_claim_single_scope_pass",
    "source_refs",
    "source_hashes",
)

COMPRESSION_MUST_NOT = (
    "convert PARTIAL to PASS",
    "convert BLOCKED to FAILED",
    "remove BLOCKED reasons",
    "remove forbidden_claims",
    "hide dirty tree",
    "hide staged_count",
    "claim repo PASS from scope PASS",
    "claim judgment from learning_only",
    "claim trade from observe_only",
)


def load_chunk() -> dict[str, object]:
    return json.loads(CHUNK_EXAMPLE.read_text(encoding="utf-8"))


def test_contract_doc_locks_clean_room_and_authority_boundaries():
    doc = CONTRACT_DOC.read_text(encoding="utf-8")

    assert "verdict=ok_taijios_memory_layer_contract_verified" in doc
    assert "evidence_registry_is_ssot=true" in doc
    assert "memory_is_candidate_context_not_truth=true" in doc
    assert "model_output_is_not_truth=true" in doc
    assert "XuanShu must remain `renderer_only`" in doc

    for flag in REQUIRED_TRUE_FLAGS:
        assert f"{flag}=true" in doc

    for forbidden in FORBIDDEN_INPUT_TYPES:
        assert forbidden in doc

    assert "clone_openhuman=false" in doc
    assert "import_openhuman_code=false" in doc
    assert "copy_gpl_source=false" in doc
    assert "connect_openhuman_backend=false" in doc


def test_design_doc_defines_memory_tree_below_evidence_registry():
    doc = DESIGN_DOC.read_text(encoding="utf-8")

    assert "Memory Tree" in doc
    assert "Evidence Tree" in doc
    assert "Decision Tree" in doc
    assert "Blocker Tree" in doc
    assert "Neither outranks the Evidence Registry" in doc
    assert "auto_fetch=false" in doc
    assert "oauth_integrations=false" in doc
    assert "runtime_memory_db=false" in doc

    for field in REQUIRED_PRESERVED_FIELDS:
        assert field in doc

    for input_type in ALLOWED_INPUT_TYPES:
        assert input_type in doc


def test_memory_chunk_example_is_parseable_and_allowlisted():
    chunk = load_chunk()
    input_types = {source["input_type"] for source in chunk["source_refs"]}

    assert chunk["schema_version"] == "0.1"
    assert chunk["scope"] == "taijios_memory_layer_contract_v0_1"
    assert chunk["mode"] == "contract_only_docs_schema_tests"
    assert chunk["verdict"] == "PARTIAL"
    assert set(ALLOWED_INPUT_TYPES) <= input_types | {"manifest.json"}
    assert set(chunk["forbidden_input_types"]) == set(FORBIDDEN_INPUT_TYPES)
    assert all(source["allowed"] is True for source in chunk["source_refs"])
    assert all(source["secret_read"] is False for source in chunk["source_refs"])


def test_chunk_preserves_required_fields_and_git_scope_boundaries():
    chunk = load_chunk()
    preserved = set(chunk["preserved_fields"])
    git_scope = chunk["git_scope"]

    assert set(REQUIRED_PRESERVED_FIELDS) <= preserved
    assert git_scope["repo_root"] == "/Users/weiwei/Desktop/taiji"
    assert git_scope["staged_count"] == 0
    assert git_scope["repo_pass_claimed"] is False
    assert git_scope["can_claim_single_scope_pass"] is False
    assert "repo PASS" in chunk["what_is_not_claimed"]


def test_chunk_locks_authority_and_safety_flags():
    chunk = load_chunk()
    authority = chunk["authority"]
    flags = chunk["boundary_flags"]

    assert authority["evidence_registry_is_ssot"] is True
    assert authority["memory_is_candidate_context_not_truth"] is True
    assert authority["model_output_is_not_truth"] is True
    assert authority["memory_chunk_is_truth"] is False
    assert authority["provider_output_is_truth"] is False

    for flag in REQUIRED_TRUE_FLAGS:
        assert flags[flag] is True

    for flag in REQUIRED_FALSE_FLAGS:
        assert flags[flag] is False


def test_compression_rules_cannot_upgrade_status_or_remove_blockers():
    chunk = load_chunk()
    rules = chunk["compression_rules"]

    assert set(REQUIRED_PRESERVED_FIELDS[:3]) <= set(rules["must_preserve"])
    assert "staged_count" in rules["must_preserve"]
    assert "blocked_stage" in rules["must_preserve"]

    for forbidden in COMPRESSION_MUST_NOT:
        assert forbidden in rules["must_not"]
        assert forbidden in CONTRACT_DOC.read_text(encoding="utf-8")
        assert forbidden in DESIGN_DOC.read_text(encoding="utf-8")


def test_xuan_shu_is_renderer_only_not_execution_authority():
    chunk = load_chunk()
    xuan_shu = chunk["xuan_shu"]

    assert xuan_shu["renderer_only"] is True
    assert "BLOCKED" in xuan_shu["allowed_status"]
    assert "no_trade" in xuan_shu["allowed_status"]
    assert "provider_ready" in xuan_shu["forbidden_claims"]
    assert "ready_for_trade" in xuan_shu["forbidden_claims"]

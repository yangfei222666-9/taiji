from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_DOC = ROOT / "docs" / "TAIJIOS_SCENARIO_SANDBOX_CONTRACT_v0.1.md"
DESIGN_DOC = ROOT / "docs" / "WORLDLINE_SIMULATOR_DESIGN_v0.1.md"
SEED_EXAMPLE = ROOT / "examples" / "scenario_sandbox_seed_example.json"

REQUIRED_TRUE_FLAGS = (
    "clean_room",
    "no_mirofish_code_import",
    "simulation_only",
    "learning_only",
    "candidate_only",
    "prediction_is_candidate_not_truth",
    "model_output_is_not_truth",
    "evidence_kernel_remains_authority",
    "no_secret_access",
    "no_env_read",
    "no_provider_call_by_default",
    "no_broker",
    "no_trade",
    "no_order",
    "no_promotion",
    "no_judgment",
    "no_paper_buy",
    "no_pass_to_trade",
    "no_real_hardware_control",
    "no_satellite_command",
    "no_radio_tx",
    "preflight_required",
    "event_flow_required",
    "closeout_required",
    "every_scenario_simulation_requires_preflight_event_flow_closeout",
    "scenario_output_cannot_claim_PASS_without_verifier",
    "xuan_shu_renderer_only",
)

REQUIRED_FALSE_FLAGS = (
    "mirofish_connected",
    "mirofish_code_imported",
    "provider_called",
    "env_read",
    "secret_read",
    "broker_connected",
    "trade_or_order",
    "judgment_allowed",
    "paper_buy_allowed",
    "promote_allowed",
    "pass_to_trade_allowed",
    "real_hardware_control",
    "satellite_command",
    "radio_tx",
)

REQUIRED_SEED_FIELDS = (
    "scenario_id",
    "seed_material",
    "entities",
    "relationships",
    "simulation_mode",
    "forbidden_actions",
    "expected_artifacts",
    "expected_verdict",
)

EXPECTED_ARTIFACTS = (
    "scenario_graph.json",
    "candidate_paths.json",
    "event_flow.jsonl",
    "simulation_closeout.md",
)

ALLOWED_VERDICTS = (
    "scenario_candidate_generated",
    "scenario_partial_insufficient_evidence",
    "scenario_blocked_forbidden_claim",
)

FORBIDDEN_VERDICTS = (
    "future_predicted",
    "truth_validated",
    "mission_approved",
    "trade_signal",
    "provider_ready",
    "ready_for_trade",
    "pass_to_trade",
    "judgment_approved",
    "promotion_ready",
)

FORBIDDEN_UPGRADES = (
    "candidate path -> verified truth",
    "simulated event -> observed event",
    "model output -> evidence authority",
    "learning_only -> judgment",
    "observe_only -> trade",
    "scenario_candidate_generated -> mission approved",
    "scope pass -> repo pass",
    "renderer output -> command authority",
)


def load_seed() -> dict[str, object]:
    return json.loads(SEED_EXAMPLE.read_text(encoding="utf-8"))


def test_contract_doc_locks_clean_room_and_safety_boundaries():
    doc = CONTRACT_DOC.read_text(encoding="utf-8")

    assert "verdict=ok_taijios_scenario_sandbox_contract_verified" in doc
    assert "clean_room=true" in doc
    assert "no_mirofish_code_import=true" in doc
    assert "copy_agpl_source=false" in doc
    assert "connect_mirofish_service=false" in doc
    assert "claim_mirofish_integration_ready=false" in doc
    assert "TaijiOS Evidence Kernel remains the authority" in doc

    for flag in REQUIRED_TRUE_FLAGS:
        assert f"{flag}=true" in doc

    for flag in ("mirofish_connected", "provider_called", "env_read", "stage_commit_push"):
        assert f"{flag}=false" in doc


def test_design_doc_defines_worldline_simulator_below_evidence_kernel():
    doc = DESIGN_DOC.read_text(encoding="utf-8")

    assert "Worldline Simulator v0.1" in doc
    assert "docs/TAIJIOS_SCENARIO_SANDBOX_CONTRACT_v0.1.md" in doc
    assert "scenario_graph.json" in doc
    assert "candidate_paths.json" in doc
    assert "event_flow.jsonl" in doc
    assert "simulation_closeout.md" in doc
    assert "No artifact may claim `PASS` unless a verifier has checked" in doc

    for flag in REQUIRED_TRUE_FLAGS:
        assert f"{flag}=true" in doc

    for upgrade in FORBIDDEN_UPGRADES:
        assert upgrade in doc


def test_seed_example_is_parseable_and_has_required_fields():
    seed = load_seed()

    assert seed["schema_version"] == "0.1"
    assert seed["scope"] == "taijios_scenario_sandbox_contract_v0_1"
    assert seed["mode"] == "contract_only_docs_schema_tests"
    assert seed["scenario_id"] == "mars_rover_demo_001"
    assert set(REQUIRED_SEED_FIELDS) <= set(seed)
    assert seed["simulation_mode"] == "simulation_only"
    assert seed["seed_material"]["is_truth_source"] is False
    assert {entity["id"] for entity in seed["entities"]} >= {
        "rover",
        "battery",
        "terrain",
        "dust_storm",
        "ground_control",
    }
    assert any(
        relationship["from"] == "dust_storm"
        and relationship["to"] == "solar_charging"
        and relationship["type"] == "reduces"
        for relationship in seed["relationships"]
    )


def test_seed_locks_required_true_and_false_flags():
    seed = load_seed()
    boundary_flags = seed["boundary_flags"]
    runtime_state = seed["runtime_state"]

    for flag in REQUIRED_TRUE_FLAGS:
        assert boundary_flags[flag] is True

    for flag in REQUIRED_FALSE_FLAGS:
        assert runtime_state[flag] is False


def test_forbidden_actions_and_verdicts_are_explicit():
    seed = load_seed()
    forbidden_actions = seed["forbidden_actions"]

    for action in (
        "clone_mirofish",
        "import_mirofish_code",
        "copy_agpl_source",
        "read_env",
        "read_secret",
        "provider_call",
        "broker_connect",
        "trade",
        "order",
        "paper_buy",
        "judgment",
        "promotion",
        "pass_to_trade",
        "real_hardware_control",
        "satellite_command",
        "radio_tx",
    ):
        assert forbidden_actions[action] is True

    assert seed["expected_artifacts"] == list(EXPECTED_ARTIFACTS)
    assert seed["allowed_verdicts"] == list(ALLOWED_VERDICTS)
    assert seed["expected_verdict"] in ALLOWED_VERDICTS
    assert seed["forbidden_verdicts"] == list(FORBIDDEN_VERDICTS)


def test_docs_forbid_prediction_truth_trade_and_pass_to_trade_claims():
    contract = CONTRACT_DOC.read_text(encoding="utf-8")
    design = DESIGN_DOC.read_text(encoding="utf-8")
    seed = load_seed()

    for forbidden in FORBIDDEN_VERDICTS:
        assert forbidden in contract
        assert forbidden in seed["forbidden_verdicts"]

    for non_claim in (
        "future predicted",
        "truth validated",
        "mission approved",
        "trade signal",
        "judgment ready",
        "promotion ready",
        "repo PASS",
    ):
        assert non_claim in seed["not_claimed"]

    assert "prediction_is_candidate_not_truth=true" in contract
    assert "model_output_is_not_truth=true" in contract
    assert "observe_only -> trade" in design
    assert "scenario_output_cannot_claim_PASS_without_verifier=true" in design


def test_xuanshu_is_renderer_only_not_authority():
    contract = CONTRACT_DOC.read_text(encoding="utf-8")
    design = DESIGN_DOC.read_text(encoding="utf-8")
    seed = load_seed()

    assert "xuan_shu_renderer_only=true" in contract
    assert "XuanShu must remain `renderer_only`" in design
    assert seed["boundary_flags"]["xuan_shu_renderer_only"] is True
    assert "renderer output -> command authority" in design

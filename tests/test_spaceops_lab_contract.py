from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPACEOPS_DOC = ROOT / "docs" / "TAIJIOS_SPACEOPS_LAB_v0.1.md"
MARS_DOC = ROOT / "docs" / "MARS_ROVER_SIM_CONTRACT_v0.1.md"
MISSION_REQUEST = ROOT / "examples" / "mars_rover_mission_request.json"

REQUIRED_TRUE_FLAGS = (
    "simulation_only",
    "learning_only",
    "no_real_vehicle_control",
    "no_satellite_command",
    "no_radio_tx",
    "no_external_api_by_default",
    "no_secret_access",
    "no_broker",
    "no_trade",
    "no_paper_buy",
    "no_promotion",
    "no_judgment",
    "boot_preflight_required",
    "event_flow_required",
    "closeout_required",
    "partial_blocked_cannot_be_success",
    "xuan_shu_is_renderer_only",
)

MISSION_FIELDS = (
    "mission_id",
    "target",
    "energy_budget",
    "terrain_risk",
    "comm_delay",
    "sensor_status",
    "allowed_actions",
    "forbidden_actions",
    "expected_closeout",
)

FORBIDDEN_ACTIONS = {
    "real_vehicle_control",
    "satellite_command",
    "radio_tx",
    "external_api_call",
    "secret_read",
    "broker_connect",
    "trade",
    "paper_buy",
    "promote",
    "judge",
}


def load_request() -> dict:
    return json.loads(MISSION_REQUEST.read_text(encoding="utf-8"))


def test_spaceops_lab_doc_locks_simulation_only_boundary():
    doc = SPACEOPS_DOC.read_text(encoding="utf-8")

    assert "contract_only_simulation_evidence_kernel" in doc
    assert "simulation-only Evidence Kernel for remote autonomy missions" in doc
    assert "docs/MARS_ROVER_SIM_CONTRACT_v0.1.md" in doc
    assert "examples/mars_rover_mission_request.json" in doc
    assert "tests/test_spaceops_lab_contract.py" in doc
    assert "XuanShu must remain `renderer_only`" in doc

    for key in REQUIRED_TRUE_FLAGS:
        assert f'"{key}": true' in doc


def test_mars_rover_contract_doc_requires_schema_and_status_rules():
    doc = MARS_DOC.read_text(encoding="utf-8")

    assert "contract_only_mars_rover_sim" in doc
    assert "docs/TAIJIOS_SPACEOPS_LAB_v0.1.md" in doc
    for field in MISSION_FIELDS:
        assert f"`{field}`" in doc or f'"{field}"' in doc
    for key in REQUIRED_TRUE_FLAGS:
        assert f"`{key}=true`" in doc
    assert "`partial` and `blocked` cannot be written as `success`" in doc
    assert "The event flow example above is a schema example only" in doc


def test_mission_request_json_is_parseable_and_has_required_fields():
    request = load_request()

    assert set(MISSION_FIELDS) <= set(request)
    assert request["mission_id"] == "MARS-SIM-EXAMPLE-001"
    assert request["target"]["site"]
    assert request["energy_budget"]["available"] > request["energy_budget"]["reserve_minimum"]
    assert request["comm_delay"]["one_way"] >= 0
    assert request["terrain_risk"]["level"] in {"low", "medium", "high"}
    assert set(request["sensor_status"]) == {"navcam", "hazcam", "imu", "wheel_odometry"}


def test_mission_request_locks_forbidden_actions_and_boundaries():
    request = load_request()

    assert FORBIDDEN_ACTIONS <= set(request["forbidden_actions"])
    assert "real_vehicle_control" not in request["allowed_actions"]
    assert "satellite_command" not in request["allowed_actions"]
    assert "radio_tx" not in request["allowed_actions"]
    assert "external_api_call" not in request["allowed_actions"]

    boundary = request["boundary"]
    for key in REQUIRED_TRUE_FLAGS:
        if key in {"boot_preflight_required", "event_flow_required", "closeout_required", "partial_blocked_cannot_be_success"}:
            continue
        assert boundary[key] is True


def test_expected_closeout_requires_preflight_event_flow_and_no_fake_success():
    request = load_request()
    closeout = request["expected_closeout"]

    assert closeout["boot_preflight_required"] is True
    assert closeout["event_flow_required"] is True
    assert closeout["event_flow_path"].endswith("/event_flow.jsonl")
    assert closeout["closeout_required"] is True
    assert closeout["closeout_path"].endswith("/closeout.md")
    assert closeout["allowed_verdicts"] == ["success", "partial", "blocked"]
    assert closeout["partial_blocked_cannot_be_success"] is True

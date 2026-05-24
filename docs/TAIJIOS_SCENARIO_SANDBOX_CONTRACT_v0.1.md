# TaijiOS Scenario Sandbox Contract v0.1

## Verdict

```text
verdict=ok_taijios_scenario_sandbox_contract_verified
scope=taijios_scenario_sandbox_contract_v0_1
mode=contract_only_docs_schema_tests
repo_root=/Users/weiwei/Desktop/taiji
clean_room=true
no_mirofish_code_import=true
simulation_only=true
learning_only=true
candidate_only=true
prediction_is_candidate_not_truth=true
model_output_is_not_truth=true
evidence_kernel_remains_authority=true
no_secret_access=true
no_env_read=true
no_provider_call_by_default=true
no_broker=true
no_trade=true
no_order=true
no_promotion=true
no_judgment=true
no_paper_buy=true
no_pass_to_trade=true
no_real_hardware_control=true
no_satellite_command=true
no_radio_tx=true
preflight_required=true
event_flow_required=true
closeout_required=true
every_scenario_simulation_requires_preflight_event_flow_closeout=true
scenario_output_cannot_claim_PASS_without_verifier=true
xuan_shu_renderer_only=true
mirofish_connected=false
provider_called=false
env_read=false
stage_commit_push=false
```

This contract defines a clean-room TaijiOS Scenario Sandbox inspired by the
operator-provided MiroFish pattern: relationship graphs, multi-agent simulation,
and candidate event-path exploration. It does not clone MiroFish, import
MiroFish code, connect to MiroFish, reuse AGPL implementation details, read
`.env`, call providers, connect brokers, trade, paper-buy, judge, promote, or
control real hardware.

Scenario Sandbox v0.1 is a contract and schema layer only. It can describe how
to turn seed material into an entity graph and candidate paths, but any output
is candidate evidence only. The TaijiOS Evidence Kernel remains the authority.

## Authority Model

Scenario Sandbox proposes possible worldlines. It does not decide truth.

| Layer | Role | Authority boundary |
| --- | --- | --- |
| Evidence Kernel | Verifies artifacts, event flow, closeout, and allowed verdicts | Remains authority for PASS / PARTIAL / BLOCKED |
| Scenario Sandbox | Builds scenario graph and candidate paths | Candidate-only, simulation-only, learning-only |
| Multi-agent simulation | Produces hypothetical interactions | Model output is not truth |
| XuanShu | Renders approved state | Renderer-only, no verdict generation |

Hard rules:

```text
evidence_kernel_remains_authority=true
scenario_output_is_candidate_not_truth=true
prediction_is_candidate_not_truth=true
model_output_is_not_truth=true
candidate_path_without_verifier_is_unverified=true
scenario_output_cannot_claim_PASS_without_verifier=true
xuan_shu_renderer_only=true
```

## Clean-Room Boundary

Allowed:

```text
operator_supplied_reference_summary=true
architecture_reference=true
clean_room_reimplementation=true
local_contract_tests=true
scenario_schema_design=true
```

Blocked:

```text
clone_mirofish=false
import_mirofish_code=false
copy_agpl_source=false
connect_mirofish_service=false
reuse_mirofish_runtime=false
claim_mirofish_integration_ready=false
```

## Scenario Lifecycle

Every Scenario Sandbox run must preserve this sequence:

```text
scope_declared
scenario_preflight_completed
scenario_graph_written
candidate_paths_written
event_flow_written
verifier_completed_or_missing_recorded
closeout_written
scope_completed_or_blocked
```

Required artifacts:

```text
scenario_graph.json
candidate_paths.json
event_flow.jsonl
simulation_closeout.md
```

The event flow must be parseable JSONL. The closeout must report what was
verified and what was not claimed.

## Input Schema

Every scenario seed must include:

- `scenario_id`
- `seed_material`
- `entities`
- `relationships`
- `simulation_mode`
- `boundary_flags`
- `forbidden_actions`
- `expected_artifacts`
- `expected_verdict`

The v0.1 seed schema is documented in:

```text
examples/scenario_sandbox_seed_example.json
```

The v0.1 design companion is:

```text
docs/WORLDLINE_SIMULATOR_DESIGN_v0.1.md
```

The executable contract tests are:

```text
tests/test_scenario_sandbox_contract.py
```

## Required Boundary Flags

Scenario Sandbox v0.1 must lock:

```text
clean_room=true
no_mirofish_code_import=true
simulation_only=true
learning_only=true
candidate_only=true
prediction_is_candidate_not_truth=true
model_output_is_not_truth=true
evidence_kernel_remains_authority=true
no_secret_access=true
no_env_read=true
no_provider_call_by_default=true
no_broker=true
no_trade=true
no_order=true
no_promotion=true
no_judgment=true
no_paper_buy=true
no_pass_to_trade=true
no_real_hardware_control=true
no_satellite_command=true
no_radio_tx=true
preflight_required=true
event_flow_required=true
closeout_required=true
every_scenario_simulation_requires_preflight_event_flow_closeout=true
scenario_output_cannot_claim_PASS_without_verifier=true
xuan_shu_renderer_only=true
```

## Allowed Verdicts

Scenario Sandbox may emit only these v0.1 verdict strings:

```text
scenario_candidate_generated
scenario_partial_insufficient_evidence
scenario_blocked_forbidden_claim
```

Forbidden verdict strings:

```text
future_predicted
truth_validated
mission_approved
trade_signal
provider_ready
ready_for_trade
pass_to_trade
judgment_approved
promotion_ready
```

## Forbidden Runtime Actions

Scenario Sandbox v0.1 forbids:

- Cloning MiroFish.
- Importing MiroFish or other AGPL implementation code.
- Connecting Zep, DashScope, OpenAI, DeepSeek, Claude, or any other provider by
  default.
- Reading `.env` or secret values.
- Broker, exchange, order, trade, paper-buy, judgment, promotion, or
  pass-to-trade behavior.
- Real hardware, robot, vehicle, satellite, radio, actuator, or ground station
  control.
- Treating a simulated worldline as a verified fact.
- Treating XuanShu renderer output as command authority.

## Domain Mappings

Scenario Sandbox may be used as a candidate-only layer for:

| Domain | Candidate value | Hard boundary |
| --- | --- | --- |
| XuanShu narrative | Character graph, conflict graph, event paths | Renderer-only, no execution authority |
| SpaceOps | Mission agents and risk events | No hardware, satellite, or radio command |
| OrderFlow learning | Market participant hypotheses | Observe-only, no trade, no signal |
| Enterprise security | Candidate reviewer questions | Not verified customer evidence |

## Phase 1 Validation

Run:

```bash
pytest tests/test_scenario_sandbox_contract.py -q
python3 -m json.tool examples/scenario_sandbox_seed_example.json
git diff --check
git status --short
```

## Non-Claims

Scenario Sandbox v0.1 does not prove:

- Direct MiroFish integration.
- Provider availability.
- Secret availability.
- Runtime multi-agent simulation.
- Prediction truth.
- Judgment, paper-buy, trade, order, promotion, or pass-to-trade authority.
- Real mission, robot, satellite, radio, or hardware readiness.
- Repo pass, branch pass, commit pass, push pass, PR pass, or merge pass.

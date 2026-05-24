# Worldline Simulator Design v0.1

## Verdict

```text
verdict=ok_worldline_simulator_design_contract_verified
scope=taijios_scenario_sandbox_contract_v0_1
mode=design_only_candidate_paths
repo_root=/Users/weiwei/Desktop/taiji
clean_room=true
simulation_only=true
learning_only=true
candidate_only=true
evidence_kernel_remains_authority=true
runtime_simulator_implemented=false
provider_connected=false
stage_commit_push=false
```

Worldline Simulator v0.1 is the design companion for:

```text
docs/TAIJIOS_SCENARIO_SANDBOX_CONTRACT_v0.1.md
```

It describes the clean-room Scenario Sandbox shape: seed material becomes an
entity relationship graph, graph nodes become bounded agent personas, scenario
rules become a simulation environment, and the output becomes candidate paths
that must pass TaijiOS verification before any stronger claim.

## Core Pipeline

```text
seed_material
entity_graph
agent_personas
simulation_environment
candidate_paths
event_flow
simulation_closeout
taijios_verifier
```

The pipeline is intentionally below the Evidence Kernel. It can create
candidate paths, but cannot approve missions, validate truth, promote rules, or
generate trade signals.

## Artifact Model

Required output artifacts for any future implementation:

| Artifact | Purpose | Authority |
| --- | --- | --- |
| `scenario_graph.json` | Entity, relationship, persona, and constraint graph | Candidate graph only |
| `candidate_paths.json` | Hypothetical event path list | Candidate paths only |
| `event_flow.jsonl` | Parseable execution and boundary log | Evidence input |
| `simulation_closeout.md` | Verdict, blockers, non-claims, and next action | Closeout only |

No artifact may claim `PASS` unless a verifier has checked the required
artifacts, forbidden claims, and boundary flags.

## Scenario Graph Shape

Minimum `scenario_graph.json` shape:

```json
{
  "schema_version": "0.1",
  "scenario_id": "mars_rover_demo_001",
  "nodes": [
    {
      "id": "rover",
      "type": "agent",
      "persona": {
        "role": "mobile science platform",
        "goal": "reach target and preserve safety margin",
        "memory_policy": "scenario_local_only"
      }
    }
  ],
  "edges": [
    {
      "from": "dust_storm",
      "to": "solar_charging",
      "type": "reduces",
      "confidence": "operator_supplied"
    }
  ],
  "boundary_flags": {
    "simulation_only": true,
    "learning_only": true,
    "candidate_only": true,
    "evidence_kernel_remains_authority": true
  }
}
```

## Candidate Path Shape

Minimum `candidate_paths.json` shape:

```json
{
  "schema_version": "0.1",
  "scenario_id": "mars_rover_demo_001",
  "verdict": "scenario_candidate_generated",
  "paths": [
    {
      "path_id": "candidate_path_001",
      "status": "candidate",
      "events": [
        {
          "event_id": "event_001",
          "actor": "dust_storm",
          "action": "reduces_solar_charging",
          "effect": "battery_margin_decreases"
        }
      ],
      "not_claimed": [
        "future predicted",
        "truth validated",
        "mission approved",
        "trade signal"
      ]
    }
  ]
}
```

## Event Flow Minimum

Any future runner must emit parseable JSONL with at least these events:

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

Each event must include:

```text
ts
event
scope
scenario_id
mode
status
artifact_refs
boundary_flags
forbidden_claims
not_claimed
```

Boundary flags must preserve:

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

## Verifier Rules

A future verifier may report `scenario_candidate_generated` only when:

```text
seed_json_parses=true
scenario_graph_json_parses=true
candidate_paths_json_parses=true
event_flow_jsonl_parses=true
closeout_present=true
required_boundary_flags_present=true
forbidden_claims_absent=true
repo_pass_claimed=false
provider_called=false
env_read=false
secret_read=false
trade_or_order=false
judgment_allowed=false
paper_buy_allowed=false
promote_allowed=false
pass_to_trade_allowed=false
real_hardware_control=false
satellite_command=false
radio_tx=false
```

It must report `scenario_partial_insufficient_evidence` when the schema exists
but verifier output, event flow, or closeout evidence is incomplete.

It must report `scenario_blocked_forbidden_claim` when any forbidden claim or
forbidden action appears.

## Forbidden Upgrades

The design must never upgrade:

```text
candidate path -> verified truth
simulated event -> observed event
model output -> evidence authority
learning_only -> judgment
observe_only -> trade
scenario_candidate_generated -> mission approved
scope pass -> repo pass
renderer output -> command authority
```

## XuanShu Boundary

XuanShu may render Scenario Sandbox states only after a scenario closeout or
verifier supplies the state.

XuanShu must remain `renderer_only`. It may display `simulation_only`,
`learning_only`, `candidate_only`, `PARTIAL`, `BLOCKED`, and artifact paths.
It must not generate verdicts, approve worldlines, command hardware, call
providers, read secrets, trade, paper-buy, judge, promote, or claim
pass-to-trade.

# TaijiOS Rearchitecture Plan v0.1

## Verdict

```text
verdict=partial_win11_t7_inventory_scope_dirty
source_inventory=docs/WIN11_T7_PROJECT_INVENTORY_v0.1.md
mode=docs_plan_only
runtime_changed=false
provider_connected=false
secret_read=false
git_stage=false
```

This plan turns the T7/Win11 project inventory into a conservative TaijiOS rearchitecture path. It does not import old code and does not claim canonical repo pass.

## North Star

TaijiOS should be rebuilt around Evidence Kernel first.

```text
claim / workflow / agent output
        -> Boot Preflight
        -> EventFlow
        -> Scope Isolation
        -> Artifact Memory
        -> Closeout
        -> XuanShu Shell display
```

Everything else becomes a use case or adapter.

## Long-Term Direction

The long-term direction is to make TaijiOS the evidence and safety runtime for
AI agents, robots, Physical AI, SpaceOps simulation, and future autonomous
missions.

```text
TaijiOS
  -> AI Agent Evidence Kernel
  -> AI Workflow Safety Runtime
  -> Physical AI / Robotics Safety Runtime
  -> SpaceOps Simulation Kernel
  -> Autonomous Mission Evidence OS
```

This is a strategic direction, not a current runtime capability claim. Every
future layer must inherit the Product Spine gates:

```text
preflight before action
parseable event_flow before completion claim
scope isolation before pass claim
verifier and closeout before promotion
rollback / recovery / replay path before higher-risk execution
```

Current boundary:

```text
long_term_direction_recorded=true
runtime_capability_claimed=false
real_robot_or_vehicle_control=false
satellite_or_radio_command=false
external_api_by_default=false
secret_access=false
broker_trade_judgment_promote=false
```

## Target Architecture

| Layer | Role | Candidate source classes | Boundary |
| --- | --- | --- | --- |
| Evidence Kernel | Verdict engine for verified/partial/blocked/pending states | A, C | Must be deterministic and artifact-backed |
| Product Spine | Boot Preflight, EventFlow, Scope Isolation, Artifact Memory, Closeout | C | Highest import priority, but still review-gated |
| XuanShu / UI | Human-facing renderer, HUD, demo, TaijiPet surface | D | Renderer-only unless future action gates exist |
| TaijiMind / Provider Sandbox | LLM Gateway, RAG, local model candidates, API router | E | Sandbox by default; no provider truth without live scoped probe |
| Lab | Experimental candidates and self-improvement skeletons | B | No production/runtime authority |
| Archive | Historical releases, backups, tmp packages | F | Index only |
| Quarantine | Secrets, binaries, old builds, trade/order/broker risk | G | Do not migrate |

## Import Policy

No path from T7 can enter canonical repo by existence alone.

Minimum future import packet:

```text
source_path
migration_class
file_allowlist
reason
hash_or_manifest
summary.json
event_flow.jsonl
tests_or_verifier
not_claimed
rollback/removal plan
```

Default:

```text
import_allowed=false
copy_allowed=false
stage_allowed=false
commit_allowed=false
push_allowed=false
```

## Phase Plan

### Phase 0: Preserve Boundaries

Keep T7 read-only. Keep `/Volumes/T7/secure`, `.env*`, binaries, old builds, caches, and trade/order/broker material out of scope.

Output:

```text
WIN11_T7_PROJECT_INVENTORY_v0.1.md
summary.json
event_flow.jsonl
closeout.md
```

### Phase 1: Product Spine Extraction

Review only C-class candidates:

```text
/Volumes/T7/taijios_full_workspace/runs/ops_check
/Volumes/T7/taijios_full_workspace/runs/event_flow
/Volumes/T7/TAIJI_MAC_REVIEW_FINAL_DROP_20260512_185347
/Volumes/T7/TaijiOS_Exchange
```

Goal:

```text
standardize summary schema
standardize event_flow event vocabulary
standardize closeout verdict fields
standardize handoff admission gates
```

No runtime code import in this phase.

### Phase 2: Canonical Core Review

Review A-class candidates only after Product Spine schema is stable:

```text
/Volumes/T7/taijios_full_workspace/aios/core
/Volumes/T7/taijios_full_workspace/aios/agent_system
```

Allowed output:

```text
design notes
small patch candidates
test cases
context packets
```

Blocked output:

```text
bulk copy
dirty-tree migration
unverified rewrite
provider/live runtime enablement
```

### Phase 3: XuanShu / UI Demo

Review D-class candidates:

```text
/Volumes/T7/TaijiOS_Evidence_Studio
/Volumes/T7/taijios_full_workspace/frontend
/Volumes/T7/taijios-landing
```

Goal:

```text
render Evidence Kernel states
show verified/partial/blocked/pending
produce demo scripts without overclaiming runtime capability
```

### Phase 4: TaijiMind Sandbox

Review E-class candidates:

```text
/Volumes/T7/taijios_full_workspace/aios/gateway
/Volumes/T7/taijios_full_workspace/aios/learning
```

Rules:

```text
provider_live_verified=false until scoped probe
local_model_output=candidate evidence only
RAG output != truth source
API router existence != provider readiness
```

### Phase 5: Lab and Archive

Move B-class ideas into future `lab/` only after a separate proposal. Keep F-class historical roots indexed. Keep G-class quarantined.

## A-G Decision Rules

Use these rules for every future T7 path:

```text
If it improves Product Spine evidence mechanics -> C
If it renders evidence states -> D
If it routes LLM/API/local model calls -> E
If it is reusable core code with tests -> A
If it is promising but unstable -> B
If it is old history -> F
If it may contain secrets, binaries, builds, caches, trade/order, or unknown state -> G
```

Ambiguous entries downgrade:

```text
A -> B
B -> F
C -> F
D -> F
E -> G when provider/secret risk is present
```

## Acceptance Criteria For Future Migration

A future migration can be considered only when:

```text
changed_files_outside_scope=0
staged_count=0 unless explicitly authorized
source packet parseable
summary.json parseable
event_flow.jsonl parseable
file_allowlist exact
tests/verifier pass
not_claimed explicit
rollback path documented
```

If any condition fails:

```text
verdict=partial or blocked
```

Never upgrade to repo PASS from a local artifact pass.

## Next Safe Action

The next safe action is to extract a Product Spine schema draft from C-class candidates only:

```text
Boot Preflight fields
EventFlow event vocabulary
Scope Isolation state fields
Artifact Memory path/index fields
Closeout required fields
```

That future scope must remain docs/schema/tests only until separately authorized.

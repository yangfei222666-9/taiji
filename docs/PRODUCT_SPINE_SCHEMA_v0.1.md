# Product Spine Schema v0.1

## Verdict

```text
verdict=partial_product_spine_schema_extract_scope_dirty
scope=product_spine_schema_extract_from_win11_t7_C_class_candidates_v0_1
mode=docs_schema_tests_only
repo_root=/Users/weiwei/Desktop/taiji
source_inventory=docs/WIN11_T7_PROJECT_INVENTORY_v0.1.md
runtime_changed=false
provider_connected=false
secret_read=false
stage_commit_push=false
```

This document is a draft contract for the TaijiOS Product Spine. It extracts
schema requirements from C-class Win11/T7 candidates only. It does not import
runtime code and does not make any provider, broker, trade, promotion,
judgment, paper-buy, or pass-to-trade claim.

## Source Candidates

| Source | Product Spine contribution | Boundary |
| --- | --- | --- |
| `/Volumes/T7/taijios_full_workspace/runs/ops_check` | `summary.json`, `event_flow.jsonl`, `closeout.md` package convention | Artifact currentness still requires receiver-side verification |
| `/Volumes/T7/taijios_full_workspace/runs/event_flow` | Event vocabulary and dry-run promotion evidence | Promotion remains blocked; dry-run is not authority |
| `/Volumes/T7/TAIJI_MAC_REVIEW_FINAL_DROP_20260512_185347` | Cross-machine handoff and receiver verification model | Handoff is not merge, admission, or repo pass |
| `/Volumes/T7/TaijiOS_Exchange` | Proposal/admission split and artifact manifest ideas | Proposal is not admission |
| `/Volumes/T7/taijios_full_workspace/docs` | Prior policies and gate language | Stale docs must not become runtime truth |

## Product Spine

The first product entrypoint is the Evidence Kernel. Product Spine is the
minimum evidence pipeline around it:

```text
claim_or_workflow
  -> Boot Preflight
  -> EventFlow
  -> Scope Isolation
  -> Artifact Memory
  -> Closeout
  -> XuanShu Shell rendering
```

Quant, Telegram, Enterprise Pack, OrderFlow, SpaceOps, Physical AI, TaijiMind,
provider routing, and UI demos are use cases or future lines. They are not the
first product entrypoint.

## Shared Status Vocabulary

Only these terminal verdict classes are allowed at the Product Spine boundary:

| Status | Meaning | Allowed next state |
| --- | --- | --- |
| `PASS` | Exact scope has complete evidence and verification | Review, package, or user-authorized stage |
| `PARTIAL` | Artifact exists but repo/scope/verifier boundary is incomplete | Fix missing evidence or split scope |
| `BLOCKED` | Safety gate stopped progression | Minimum fix only; not a failure claim |
| `PENDING` | Planned or queued, not executed | Execute a safe verifier or mark stale |
| `FAILED` | Execution attempted and failed with a concrete error | Fix the failing stage, rerun verifier |
| `UNVERIFIED` | Claimed output lacks parseable evidence | Add evidence or downgrade claim |

Hard rule:

```text
PARTIAL must not be written as PASS
BLOCKED must not be written as FAILED
scope PASS must not be written as repo PASS
provider output must not be written as truth source
local model output is candidate evidence only
```

## Boot Preflight Record

Boot Preflight records whether a workflow is allowed to start. It is not a
success verdict.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Product Spine schema version, for example `0.1` |
| `scope` | string | yes | Exact task scope |
| `mode` | string | yes | `read_only`, `docs_only`, `verify`, `package`, `edit`, or narrower local mode |
| `repo_root` | string | yes | Canonical repo path used for Git checks |
| `entrypoint` | string | yes | Must be `Evidence Kernel` for first product entrypoint claims |
| `product_spine_components` | array | yes | Declared components touched by the task |
| `will_not` | array | yes | Explicit forbidden actions for the run |
| `input_paths` | array | yes | Paths read by the run; secret paths must be excluded or existence-only |
| `output_paths` | array | yes | Paths expected to be written |
| `secret_boundary` | object | yes | Secret/keychain/env policy |
| `provider_boundary` | object | yes | Provider/API/broker policy |
| `trade_boundary` | object | yes | Trade/order/paper-buy/pass-to-trade policy |
| `git_boundary` | object | yes | Branch, staged policy, commit/push/PR/merge policy |
| `preflight_status` | string | yes | `PASS`, `PARTIAL`, `BLOCKED`, or `PENDING` |
| `blocked_stage` | string or null | yes | Blocking stage when status is `BLOCKED` |
| `minimum_fix` | string or null | yes | Minimum repair action when blocked/partial |

Minimum example:

```json
{
  "schema_version": "0.1",
  "scope": "example_scope",
  "mode": "docs_only",
  "repo_root": "/Users/weiwei/Desktop/taiji",
  "entrypoint": "Evidence Kernel",
  "product_spine_components": [
    "Boot Preflight",
    "EventFlow",
    "Scope Isolation",
    "Artifact Memory",
    "Closeout"
  ],
  "will_not": [
    "read secrets",
    "call providers",
    "trade/order",
    "stage/commit/push"
  ],
  "input_paths": [
    "docs/WIN11_T7_PROJECT_INVENTORY_v0.1.md"
  ],
  "output_paths": [
    "docs/PRODUCT_SPINE_SCHEMA_v0.1.md"
  ],
  "secret_boundary": {
    "env_read_allowed": false,
    "keychain_read_allowed": false,
    "secret_value_logged": false
  },
  "provider_boundary": {
    "provider_calls_allowed": false,
    "sandbox_default": true,
    "provider_ready_claimed": false
  },
  "trade_boundary": {
    "trade_allowed": false,
    "paper_buy_allowed": false,
    "judgment_allowed": false,
    "promote_allowed": false
  },
  "git_boundary": {
    "stage_allowed": false,
    "commit_allowed": false,
    "push_allowed": false,
    "pr_allowed": false,
    "merge_allowed": false
  },
  "preflight_status": "PASS",
  "blocked_stage": null,
  "minimum_fix": null
}
```

## EventFlow Record

EventFlow records what happened. Every significant transition must be append-only
JSONL and parseable by line.

Required fields per JSONL event:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `ts` | string | yes | ISO-8601 timestamp |
| `event` | string | yes | Stable event name |
| `scope` | string | yes | Same scope as preflight |
| `status` | string | yes | `started`, `ok`, `partial`, `blocked`, `failed`, or `skipped` |
| `product_spine_component` | string | yes | One Product Spine component |
| `input_refs` | array | yes | Paths or artifact ids read |
| `output_refs` | array | yes | Paths or artifact ids written |
| `boundary_flags` | object | yes | Secret/provider/trade/git boundary booleans |
| `evidence` | object | yes | Verifier output, counts, hashes, or reason |
| `not_claimed` | array | yes | Claims explicitly not made |

Allowed event names:

```text
scope_started
boot_preflight_completed
candidate_inventory_loaded
scope_isolation_evaluated
artifact_memory_written
event_flow_written
verifier_started
verifier_completed
closeout_written
schema_drafted
verifier_plan_drafted
blocked
partial
failed
scope_completed
```

Forbidden event upgrades:

```text
blocked -> failed unless execution failed after gate release
partial -> pass without missing evidence fixed
dry_run -> promotion
learning_only -> judgment
observe_only -> trade
provider_sandbox -> provider_ready
```

## Scope Isolation Record

Scope Isolation protects the repo from mixed truths.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `branch` | string | yes | Current branch and upstream summary |
| `scope_files` | array | yes | Files intentionally touched by this scope |
| `outside_scope_dirty_files` | array | yes | Dirty files not owned by this scope |
| `changed_files_outside_scope` | integer | yes | Count of outside-scope files changed by this run |
| `staged_count` | integer | yes | Current staged file count |
| `staged_scope_files` | array | yes | Staged files in scope; normally empty without user approval |
| `staged_outside_scope_files` | array | yes | Must be empty unless explicitly authorized |
| `repo_pass_claimed` | boolean | yes | Must be false when unrelated dirty files exist |
| `scope_pass_claimed` | boolean | yes | True only when exact-scope criteria pass |

Single-scope PASS requires:

```text
changed_files_outside_scope=0
staged_count=0 unless explicit stage authorization exists
summary.json parseable
event_flow.jsonl parseable
scope verifier passes
not_claimed explicit
```

## Artifact Memory Record

Artifact Memory is the local evidence index for a Product Spine run.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `artifact_id` | string | yes | Stable id for the run artifact |
| `scope` | string | yes | Scope that produced the artifact |
| `created_at` | string | yes | ISO-8601 timestamp |
| `paths` | object | yes | `summary`, `event_flow`, `closeout`, and docs paths |
| `source_candidates` | array | yes | C-class source candidates used as evidence |
| `verifier_results` | object | yes | Parse/lint/git/status checks |
| `authority_level` | string | yes | `docs_only`, `local_artifact`, `scope_verified`, or `repo_verified` |
| `retention_policy` | string | yes | `keep`, `archive_index`, or `quarantine` |
| `import_allowed` | boolean | yes | False by default for old T7 candidates |

Authority levels:

```text
docs_only < local_artifact < scope_verified < repo_verified
```

A docs-only schema draft cannot claim runtime capability.

## Closeout Record

Closeout is the terminal statement for one scope. It must be stricter than the
chat summary.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `verdict` | string | yes | Exact terminal verdict |
| `scope` | string | yes | Exact task scope |
| `mode` | string | yes | Actual execution mode |
| `artifacts` | array | yes | Files written |
| `verification` | object | yes | Commands and pass/partial/blocked result |
| `git_state` | object | yes | Branch, dirty tree, staged count |
| `boundaries_kept` | array | yes | Secret/provider/trade/git boundaries preserved |
| `not_claimed` | array | yes | Explicit non-claims |
| `blocked_stage` | string or null | yes | Blocking stage when applicable |
| `minimum_fix` | string or null | yes | Minimum fix for partial/blocked |
| `next_allowed_action` | string | yes | Safe next step |

Closeout must include these non-claims when true:

```text
repo PASS not claimed
provider readiness not claimed
trade/order readiness not claimed
promotion readiness not claimed
old dirty tree not migrated
new Mac migration not performed
```

## Handoff Admission Record

Handoff Admission is needed for old machine, Win11, iCloud, external agent, or
new Mac packages.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `handoff_id` | string | yes | Stable handoff id |
| `source_machine` | string | yes | Machine or disk source |
| `receiver_repo` | string | yes | Canonical receiver path |
| `manifest_path` | string | yes | Manifest path |
| `summary_path` | string | yes | Summary path |
| `event_flow_path` | string | yes | Event flow path |
| `hashes_verified` | boolean | yes | Receiver-side hash verification result |
| `receiver_tests_passed` | boolean | yes | Receiver-side verifier result |
| `admission_status` | string | yes | `PENDING`, `PARTIAL`, `BLOCKED`, or `PASS` |
| `merge_authorized` | boolean | yes | False unless user explicitly authorized Git merge path |

Handoff rule:

```text
handoff PASS != canonical branch PASS
receiver verification PASS != GitHub merge
manifest present != import allowed
```

## Product Line Boundaries

| Line | Product Spine role | Authority |
| --- | --- | --- |
| Quant | Use case | `learning_only` / `observe_only` by default |
| Telegram | Status and command surface | Does not prove artifact truth |
| Enterprise Pack | Packaging and customer workflow | Must consume Evidence Kernel outputs |
| OrderFlow | Future line | No order/trade authority by default |
| SpaceOps | Simulation/lab use case | Lab evidence only unless separately promoted |
| Physical AI | Future line | Requires safety gates and hardware boundary |
| TaijiMind / Provider | Candidate evidence side brain | Not truth source |
| XuanShu Shell | Renderer | Renderer-only unless future action gate exists |

## Not Claimed

```text
runtime Product Spine implemented
provider/API ready
broker ready
trade ready
paper-buy ready
judgment ready
promotion ready
repo PASS
new Mac migrated
old dirty tree accepted
T7 imported
```

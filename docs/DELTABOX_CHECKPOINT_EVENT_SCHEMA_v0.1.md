# DeltaBox Checkpoint Event Schema v0.1

## Verdict

```text
verdict=pass_deltabox_checkpoint_event_schema_draft_scope_only
repo_verdict=partial_dirty_tree
scope=deltabox_checkpoint_event_schema_draft
mode=docs_only_learning_only
repo_root=/Users/weiwei/Desktop/taiji
source_artifact=runs/ops_check/daily_learning_paper_intake_20260523/summary.json
runtime_checkpointing_implemented=false
provider_connected=false
secret_read=false
stage_commit_push=false
```

This document turns the DeltaBox daily-learning candidate into a TaijiOS
checkpoint/rollback event schema draft. It is a docs-only learning artifact. It
does not implement DeltaFS, DeltaCR, process checkpointing, file snapshotting,
sandbox orchestration, provider calls, broker access, judgment, promotion,
paper-buy, trade, or pass-to-trade.

The source is the 2026-05-23 daily learning intake artifact for:

```text
DeltaBox: Scaling Stateful AI Agents with Millisecond-Level Sandbox Checkpoint/Rollback
```

The paper remains candidate evidence only:

```text
paper_metadata_and_abstract_only_not_reproduced=true
paper_is_truth_source=false
learning_candidate_is_system_authority=false
```

## Product Spine Mapping

Checkpoint and rollback belong under Product Spine only when they are evidence
events, not hidden runtime side effects.

| Product Spine component | Checkpoint/rollback role | Boundary |
| --- | --- | --- |
| Boot Preflight | Declare sandbox, run, scope, checkpoint policy, and rollback limits before state capture | Preflight success is not runtime success |
| EventFlow | Append every checkpoint and rollback transition as parseable JSONL | No silent rollback |
| Scope Isolation | Bind checkpoint lineage to run id, workspace id, dirty scope, and parent checkpoint | No cross-scope replay claim |
| Artifact Memory | Store checkpoint ids, lineage, evidence paths, and verifier output | Artifact pointer is not capability proof |
| Closeout | Report PASS / PARTIAL / BLOCKED for the checkpoint scope | Scope pass is not repo pass |

## Event Names

Allowed checkpoint event names:

```text
checkpoint_preflight_completed
checkpoint_requested
checkpoint_created
checkpoint_lineage_recorded
rollback_requested
rollback_started
rollback_completed
rollback_failed
checkpoint_verifier_completed
checkpoint_closeout_written
```

Forbidden event upgrades:

```text
checkpoint_created -> runtime_reliable
rollback_completed -> system_safe
paper_candidate -> implemented_runtime
learning_only -> judgment
docs_only -> promote
scope_pass -> repo_pass
```

## Event Schema

Every checkpoint/rollback event must be JSONL and parseable by line.

Required fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `ts` | string | yes | ISO-8601 timestamp |
| `event` | string | yes | One allowed checkpoint event name |
| `scope` | string | yes | Exact run or schema scope |
| `mode` | string | yes | `learning_only`, `docs_only`, `dry_run`, `verify`, or narrower mode |
| `status` | string | yes | `started`, `ok`, `partial`, `blocked`, `failed`, or `skipped` |
| `run_id` | string | yes | Product Spine run id |
| `sandbox_id` | string | yes | Logical sandbox id; may be `unimplemented` in docs-only drafts |
| `workspace_id` | string | yes | Workspace or repo identifier |
| `checkpoint_id` | string or null | yes | Stable checkpoint id when created |
| `parent_checkpoint_id` | string or null | yes | Parent checkpoint id for lineage |
| `rollback_target_checkpoint_id` | string or null | yes | Target checkpoint for rollback events |
| `checkpoint_policy` | object | yes | Policy declared before checkpointing |
| `scope_isolation` | object | yes | Git/workspace/scope state at event time |
| `artifact_refs` | object | yes | Summary, event flow, closeout, lineage, and verifier paths |
| `boundary_flags` | object | yes | Secret/provider/trade/git/runtime authority flags |
| `evidence` | object | yes | Counts, hashes, verifier output, or failure reason |
| `not_claimed` | array | yes | Explicit non-claims |

Minimum event:

```json
{
  "ts": "2026-05-23T00:00:00Z",
  "event": "checkpoint_preflight_completed",
  "scope": "example_checkpoint_scope",
  "mode": "learning_only",
  "status": "ok",
  "run_id": "example_run",
  "sandbox_id": "unimplemented",
  "workspace_id": "/Users/weiwei/Desktop/taiji",
  "checkpoint_id": null,
  "parent_checkpoint_id": null,
  "rollback_target_checkpoint_id": null,
  "checkpoint_policy": {
    "runtime_checkpointing_allowed": false,
    "docs_only": true,
    "rollback_allowed": false,
    "external_disk_mutation_allowed": false
  },
  "scope_isolation": {
    "repo_root": "/Users/weiwei/Desktop/taiji",
    "branch": "main",
    "staged_count": 0,
    "scope_pass_is_repo_pass": false
  },
  "artifact_refs": {
    "summary": "runs/ops_check/example/summary.json",
    "event_flow": "runs/ops_check/example/event_flow.jsonl",
    "closeout": "runs/ops_check/example/closeout.md",
    "lineage": null,
    "verifier": null
  },
  "boundary_flags": {
    "learning_only": true,
    "paper_is_truth_source": false,
    "runtime_checkpointing_implemented": false,
    "provider_output_is_truth": false,
    "judgment_allowed": false,
    "promote_allowed": false,
    "paper_buy_allowed": false,
    "trade_allowed": false,
    "secret_read": false
  },
  "evidence": {
    "source": "daily_learning_paper_intake_20260523",
    "reason": "schema draft only"
  },
  "not_claimed": [
    "repo PASS",
    "runtime checkpointing implemented",
    "rollback safety proven",
    "provider/API ready",
    "judgment ready",
    "promotion ready",
    "trade/order ready"
  ]
}
```

## Checkpoint Policy

A future checkpoint policy must declare:

```text
checkpoint_allowed
rollback_allowed
runtime_checkpointing_implemented
docs_only
run_id
sandbox_id
workspace_id
scope
max_checkpoint_count
retention_policy
rollback_authority
secret_boundary
external_disk_boundary
provider_boundary
trade_boundary
git_boundary
```

Default for this draft:

```text
checkpoint_allowed=false
rollback_allowed=false
runtime_checkpointing_implemented=false
docs_only=true
rollback_authority=none
```

## Closeout Rules

Checkpoint/rollback closeout may report `PASS` only when all of these are true:

```text
event_flow_jsonl_parse=true
checkpoint_preflight_completed=true
checkpoint_or_rollback_terminal_event_present=true
scope_isolation_recorded=true
staged_count_recorded=true
boundary_flags_safe=true
not_claimed_present=true
repo_pass_claimed=false
```

Closeout must report `PARTIAL` when:

```text
schema exists but verifier is not implemented
runtime code is absent
dirty tree remains outside exact scope
checkpoint lineage is incomplete
artifact refs are present but not independently verified
```

Closeout must report `BLOCKED` when:

```text
secret path is requested
provider/broker/trade/paper-buy/judgment/promote boundary is requested
event_flow is missing
rollback claims success without checkpoint lineage
runtime checkpointing is claimed from docs-only evidence
paper candidate is treated as truth source
```

Closeout must not report:

```text
repo PASS
runtime checkpointing implemented
DeltaFS implemented
DeltaCR implemented
rollback safety proven
provider/API ready
broker ready
trade/order ready
paper-buy ready
judgment ready
promotion ready
pass-to-trade ready
```

## Future Implementation Gate

Before any runtime checkpointing work, create a separate exact-scope packet with:

```text
runtime target
sandbox model
file/process state boundary
secret exclusion plan
rollback failure mode table
lineage artifact schema
verifier fixture set
rollback disabled-by-default policy
operator confirmation for code changes
```

Until that packet exists, DeltaBox remains a learning-only context source for
TaijiOS design.

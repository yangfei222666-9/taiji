# Product Spine Verifier Plan v0.1

## Verdict

```text
verdict=partial_product_spine_schema_extract_scope_dirty
scope=product_spine_schema_extract_from_win11_t7_C_class_candidates_v0_1
mode=docs_schema_tests_only
repo_root=/Users/weiwei/Desktop/taiji
runtime_changed=false
provider_connected=false
secret_read=false
stage_commit_push=false
```

This plan defines how a future Product Spine verifier should check Boot
Preflight, EventFlow, Scope Isolation, Artifact Memory, and Closeout. It is a
docs-only plan, not an implemented verifier.

## Verifier Goals

1. Confirm every run has parseable `summary.json`, `event_flow.jsonl`, and
   `closeout.md`.
2. Confirm `PASS`, `PARTIAL`, `BLOCKED`, `PENDING`, `FAILED`, and `UNVERIFIED`
   are not rewritten into a stronger state.
3. Confirm `scope PASS` is not called `repo PASS`.
4. Confirm provider/API, local model, broker, trade/order, paper-buy, judgment,
   and promotion claims remain blocked unless explicitly verified in a separate
   authorized scope.
5. Confirm old Win11/T7 artifacts remain candidate evidence until receiver-side
   verification and user-approved import.

## Inputs

Future verifier input should be a run directory:

```text
runs/ops_check/<scope_or_run_id>/
  summary.json
  event_flow.jsonl
  closeout.md
```

Optional docs inputs:

```text
docs/PRODUCT_SPINE_SCHEMA_v0.1.md
docs/WIN11_T7_PROJECT_INVENTORY_v0.1.md
docs/TAIJIOS_REARCHITECTURE_PLAN_v0.1.md
```

The verifier must not read `.env`, keychain, provider secrets, `/Volumes/T7/secure`,
broker credentials, or trade/order material.

## Checks

| Check | Required result | Failure verdict |
| --- | --- | --- |
| `summary.json` parses | `PASS` | `BLOCKED` if missing, `FAILED` if invalid JSON |
| `event_flow.jsonl` parses per line | `PASS` | `BLOCKED` if missing, `FAILED` if invalid JSONL |
| `closeout.md` exists and is non-empty | `PASS` | `BLOCKED` |
| `scope` matches across artifacts | `PASS` | `PARTIAL` |
| `mode` matches declared boundary | `PASS` | `PARTIAL` or `BLOCKED` |
| terminal verdict is consistent | `PASS` | `PARTIAL` |
| forbidden claims absent | `PASS` | `BLOCKED` |
| `staged_count` recorded | `PASS` | `PARTIAL` |
| outside-scope dirty files recorded | `PASS` | `PARTIAL` |
| provider/trade/promote flags false by default | `PASS` | `BLOCKED` |

## Forbidden Claim Rules

The verifier should hard-block any artifact that claims:

```text
trade_allowed=true
paper_buy_allowed=true
judgment_allowed=true
promote_allowed=true
provider_ready=true without scoped live probe
broker_ready=true
handoff_pass_is_merge=true
scope_pass_is_repo_pass=true
partial_written_as_pass=true
blocked_written_as_failed=true
old_dirty_tree_is_baseline=true
```

## Minimal Pseudocode

```text
load summary.json
parse event_flow.jsonl line by line
read closeout.md

verify required keys
verify scope/mode consistency
verify terminal verdict consistency
verify event_flow has started and closeout events
verify not_claimed includes repo/provider/trade/promotion boundaries
verify git staged_count exists
verify outside-scope dirty state is explicit

if forbidden claim found:
    verdict=blocked
elif parse failure found:
    verdict=failed
elif missing scope/git/evidence fields:
    verdict=partial
else:
    verdict=pass_for_scope_only
```

## EventFlow Minimum Sequence

A valid Product Spine run should have at least:

```text
scope_started
boot_preflight_completed
artifact_memory_written
event_flow_written
verifier_completed
closeout_written
scope_completed
```

For docs-only runs, `boot_preflight_completed` may be represented by the initial
scope declaration and boundary event. It must still be explicit in
`summary.json` or `event_flow.jsonl`.

## Closeout Minimum Fields

Closeout should contain:

```text
verdict
scope
mode
artifacts
verification
git_state
boundaries_kept
not_claimed
blocked_stage
minimum_fix
next_allowed_action
```

If the repo has unrelated dirty files, closeout must use `PARTIAL` or a scoped
verdict. It must not claim repo PASS.

## Future Implementation Target

The future verifier can be implemented as:

```text
python -m aios.userland.product_spine.verify_run runs/ops_check/<run_id>
```

That implementation was out of scope for the original document-only schema
extract run. A later minimal local verifier now exists at:

```text
aios/userland/product_spine/verify_run.py
tests/test_product_spine_verify_run.py
```

This implementation verifies local Product Spine run packets only. It does not
call providers, read secrets, import T7 code, connect brokers, trade/order,
promote, judge, paper-buy, stage, commit, push, or prove runtime Product Spine
readiness.

## Acceptance Criteria For Future Code Work

Before implementation:

```text
schema doc approved
test fixtures defined
forbidden claims listed
sample pass/partial/blocked/failed runs available
runtime import boundary explicit
```

After implementation:

```text
unit tests for PASS/PARTIAL/BLOCKED/FAILED/UNVERIFIED
JSON/JSONL parse tests
forbidden claim tests
git scope isolation tests
no secret read tests
event_flow terminal-state tests
```

## Not Claimed

```text
full/runtime Product Spine verifier implemented
Product Spine live
provider/API ready
broker ready
trade/order ready
paper-buy ready
judgment ready
promotion ready
repo PASS
```

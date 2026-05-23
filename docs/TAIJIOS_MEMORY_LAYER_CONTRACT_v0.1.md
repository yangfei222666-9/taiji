# TaijiOS Memory Layer Contract v0.1

## Verdict

```text
verdict=ok_taijios_memory_layer_contract_verified
scope=taijios_memory_layer_contract_v0_1
mode=contract_only_docs_schema_tests
repo_root=/Users/weiwei/Desktop/taiji
clean_room=true
no_openhuman_code_import=true
local_first=true
evidence_registry_is_ssot=true
memory_is_candidate_context_not_truth=true
model_output_is_not_truth=true
no_secret_access=true
no_env_read=true
no_broker=true
no_trade=true
no_promotion=true
no_judgment=true
no_paper_buy=true
no_pass_to_trade=true
xuan_shu_renderer_only=true
runtime_memory_store_implemented=false
provider_connected=false
stage_commit_push=false
```

This contract defines a clean-room TaijiOS Memory Layer inspired by public
memory-tree and local-vault product patterns described by the operator. It does
not import OpenHuman code, clone OpenHuman, connect to an OpenHuman backend,
reuse GPL implementation details, call providers, read secrets, read env files,
or promote memory into judgment authority.

The Memory Layer is not the Evidence Kernel. It is a candidate context layer
that folds TaijiOS evidence artifacts into readable, searchable, and
compressible chunks. The Evidence Registry remains the source of truth.

## Authority Model

Memory can make context easier to retrieve. It cannot make facts true.

| Layer | Authority | Boundary |
| --- | --- | --- |
| Evidence Registry | Source of truth for artifacts, hashes, verifier output, and closeout state | Must stay above model output and memory summaries |
| Memory Layer | Candidate context derived from allowed artifacts | Must not claim repo pass, judgment, trade, or promotion |
| Model Output | Draft explanation, summary, or extraction | Must be verified against evidence before use |
| XuanShu | Renderer-only status shell | Must render only approved status and artifact pointers |

Hard rules:

```text
evidence_registry_is_ssot=true
memory_is_candidate_context_not_truth=true
model_output_is_not_truth=true
memory_chunk_must_reference_source_artifact=true
memory_chunk_without_parseable_source_is_unverified=true
compression_output_is_not_new_authority=true
```

## Clean-Room Boundary

This repository may study architecture ideas, product boundaries, and operator
notes. It must not import OpenHuman code or create a source-level dependency on
OpenHuman.

Allowed:

```text
architecture_reference=true
clean_room_reimplementation=true
operator_supplied_product_notes=true
local_contract_tests=true
```

Blocked:

```text
clone_openhuman=false
import_openhuman_code=false
copy_gpl_source=false
connect_openhuman_backend=false
reuse_openhuman_oauth_flow=false
claim_openhuman_integration_ready=false
```

## Input Allowlist

Memory Layer v0.1 may ingest only TaijiOS local evidence and public repo docs:

```text
summary.json
event_flow.jsonl
closeout.md
manifest.json
public docs/*.md
README.md
```

Each input must be recorded with path, input type, parse status, source hash
when available, and whether the source was allowed by this contract.

## Forbidden Inputs

The v0.1 Memory Layer must not read or ingest:

```text
.env
keychain
token
broker config
private customer data
Gmail
Slack
Notion
OAuth
raw provider secrets
browser history
chat exports containing secrets
```

Secret handling is existence-only when a path must be classified by name. Secret
values must not be read, copied, summarized, hashed from plaintext, written into
memory, written into event flow, or displayed.

## Required Chunk Fields

Every memory chunk must preserve the fields that keep TaijiOS audit semantics
from collapsing into fake success:

```text
verdict
scope
mode
repo_root
branch
staged_count
dirty_tree
commit
push
PR
merge
blocked_stage
failure_cause
minimum_fix
not_claimed
forbidden_claims
what_is_verified
what_is_not_claimed
can_claim_single_scope_pass
source_refs
source_hashes
```

Missing `verdict`, `scope`, `mode`, `staged_count`, or `blocked_stage` must make
the chunk `BLOCKED` or `UNVERIFIED`, not `PASS`.

## Compression Rules

Compression is allowed only when it keeps the safety semantics intact.

Must preserve:

```text
verdict
scope
mode
staged_count
branch
commit
push
PR
merge
blocked_stage
failure_cause
minimum_fix
forbidden_claims
source_hashes
```

Must not:

```text
convert PARTIAL to PASS
convert BLOCKED to FAILED
remove BLOCKED reasons
remove forbidden_claims
hide dirty tree
hide staged_count
claim repo PASS from scope PASS
claim judgment from learning_only
claim trade from observe_only
claim paper-buy from observe_only
claim trade from paper_action_sheet
```

May compress:

```text
repeated paths
long log excerpts after preserving errors
duplicated event payloads
redundant markdown prose
provider payload bodies after preserving provider status and failure reason
```

## Chunk Verdict Rules

Allowed terminal verdict classes:

| Verdict | Meaning | Allowed next action |
| --- | --- | --- |
| `PASS` | Exact chunk source is parseable, within allowlist, and verifier-compatible | Use as candidate context |
| `PARTIAL` | Source is parseable but scope, freshness, or verifier evidence is incomplete | Fix evidence or keep candidate-only |
| `BLOCKED` | A safety boundary stopped ingestion or compression | Minimum fix only |
| `PENDING` | Chunk is planned but not generated | Run local verifier or mark stale |
| `UNVERIFIED` | Memory text has no parseable source artifact | Rebuild from evidence |

Forbidden upgrades:

```text
scope PASS -> repo PASS
candidate context -> truth
model output -> verified evidence
local docs -> runtime capability
learning_only -> judgment
observe_only -> trade
renderer status -> execution authority
```

## Event Flow Requirements

A future Memory Layer implementation must append parseable event flow for each
ingestion, compression, indexing, and closeout transition.

Required event fields:

| Field | Type | Required |
| --- | --- | --- |
| `ts` | string | yes |
| `event` | string | yes |
| `scope` | string | yes |
| `mode` | string | yes |
| `status` | string | yes |
| `source_refs` | array | yes |
| `output_refs` | array | yes |
| `boundary_flags` | object | yes |
| `preserved_fields` | array | yes |
| `not_claimed` | array | yes |

Allowed event names:

```text
memory_ingest_preflight_completed
memory_source_loaded
memory_chunk_created
memory_chunk_compressed
memory_chunk_indexed
memory_verifier_completed
memory_closeout_written
memory_ingest_blocked
memory_ingest_completed
```

## XuanShu Boundary

XuanShu must remain `renderer_only`.

Allowed render states:

```text
PASS
PARTIAL
BLOCKED
PENDING
learning_only
observe_only
no_trade
local_only
artifact_available
```

Forbidden XuanShu claims:

```text
ready_for_live
ready_for_trade
paper_buy_allowed
judgment_allowed
promote_allowed
provider_ready
repo_pass
external_integration_verified
```

## Completion Criteria

Memory Layer v0.1 is complete only when:

```text
contract_doc_exists=true
design_doc_exists=true
example_chunk_json_parseable=true
contract_tests_pass=true
allowed_inputs_locked=true
forbidden_inputs_locked=true
compression_safety_locked=true
xuan_shu_renderer_only_locked=true
no_secret_access=true
no_provider_call=true
no_git_stage_commit_push=true
```

This contract does not claim a working runtime memory database, auto-fetcher,
OAuth integration, provider route, broker route, judgment workflow, paper-buy
workflow, promotion workflow, or repo-wide pass.

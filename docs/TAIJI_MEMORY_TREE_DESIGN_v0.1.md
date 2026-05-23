# Taiji Memory Tree Design v0.1

## Verdict

```text
verdict=ok_taiji_memory_tree_design_scope_only
scope=taijios_memory_layer_contract_v0_1
mode=design_only_contract_only
repo_root=/Users/weiwei/Desktop/taiji
runtime_memory_store_implemented=false
auto_fetch_enabled=false
provider_connected=false
secret_read=false
trade_allowed=false
judgment_allowed=false
promote_allowed=false
```

This design maps TaijiOS evidence artifacts into a local-first Memory Tree. It
is a design contract, not a runtime implementation. The source of truth remains
the Evidence Registry and the original artifacts.

## Design Goal

TaijiOS should not lose operational context between agents, machines, or review
sessions. The Memory Tree turns durable evidence into structured candidate
context while preserving the fields that prevent fake success:

```text
verdict
scope
mode
repo_root
staged_count
dirty_tree
branch
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

The design is clean-room. It uses operator-supplied product observations as
inspiration only and does not copy OpenHuman code, schemas, OAuth flows,
storage code, UI code, or backend behavior.

## Storage Layout

Proposed local layout:

```text
memory/
  sqlite/
    taiji_memory.db
  vault/
    projects/
      taijios/
    closeouts/
    prs/
    contracts/
    blockers/
    decisions/
  chunks/
    event_flow_chunks/
    closeout_chunks/
    pr_chunks/
    docs_chunks/
  indexes/
    by_scope.json
    by_verdict.json
    by_blocker.json
    by_commit.json
    by_date.json
```

The SQLite store is for indexing, lineage, and deterministic lookup. The vault
is for human-readable Markdown. Both are derived surfaces. Neither outranks the Evidence Registry.

## Trees

| Tree | Purpose | Source |
| --- | --- | --- |
| Memory Tree | Long-lived candidate context by project and scope | Allowed artifacts and docs |
| Evidence Tree | Pointers to source artifacts, hashes, verifier outputs, and closeouts | Evidence Registry |
| Decision Tree | Human or verifier-approved decisions and their supporting evidence | Closeouts and contracts |
| Blocker Tree | Current and historical blockers with minimum fixes | Summary and event flow |

## Chunk Lifecycle

```text
source_allowlist_preflight
  -> parse_source
  -> extract_preserved_fields
  -> create_chunk
  -> compress_without_status_upgrade
  -> index_by_scope_verdict_blocker_commit_date
  -> write_event_flow
  -> write_closeout
```

If source parsing fails, the lifecycle stops at `memory_ingest_blocked`. If
compression would remove a blocker or change `PARTIAL` to `PASS`, the lifecycle
stops at `memory_ingest_blocked`.

## Source Types

Allowed v0.1 source types:

```text
summary.json
event_flow.jsonl
closeout.md
manifest.json
public docs/*.md
README.md
```

Not allowed in v0.1:

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
```

## Index Rules

Each chunk should be indexed by:

```text
scope
verdict
blocked_stage
failure_cause
minimum_fix
date
branch
commit
PR
merge
source_hash
```

An index hit is retrieval evidence only. It does not prove freshness, runtime
success, provider access, GitHub status, trade readiness, or promotion
authority.

## Compression Profile

TaijiOS compression is audit-safe compression, not generic summarization.

Preserve exactly:

```text
PASS / PARTIAL / BLOCKED / PENDING / UNVERIFIED
scope
mode
staged_count
dirty_tree
branch
commit
push
PR
merge
blocked_stage
failure_cause
minimum_fix
forbidden_claims
not_claimed
what_is_verified
what_is_not_claimed
```

Compress carefully:

```text
long logs
duplicated paths
repeated event payloads
markdown narrative
large provider payload excerpts after retaining status and failure reason
```

Reject compression when:

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
```

## Agent Bridge

Future agent bridge files may include:

```text
bridge/operator_context.yaml
bridge/current_scope.json
bridge/retrieval_packet.json
```

They may provide context to Codex, Cursor, Claude Code, Warp, local models,
TaijiMind, or XuanShu. They must remain below Evidence Registry authority and
must not include secrets, bearer tokens, OAuth refresh tokens, broker config, or
private customer data.

## XuanShu Rendering

XuanShu reads status packets and artifact pointers only.

```text
renderer_only=true
allowed_status=PASS,PARTIAL,BLOCKED,PENDING,learning_only,observe_only,no_trade,local_only,artifact_available
execution_authority=false
provider_authority=false
trade_authority=false
promotion_authority=false
```

XuanShu must not render memory retrieval as live readiness.

## v0.1 Non-Goals

```text
auto_fetch=false
oauth_integrations=false
gmail_slack_notion=false
secret_ingestion=false
broker_ingestion=false
provider_runtime=false
runtime_memory_db=false
repo_pass_claim=false
judgment=false
paper_buy=false
trade=false
promotion=false
```

The first implementation should eat only TaijiOS artifacts and public docs. It
should not start with Gmail, Slack, Notion, browser history, broker data, or
provider-side private state.

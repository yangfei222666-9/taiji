# Proof API Runtime Contract v1

## Contract Status

```text
contract_id=proof_api_runtime_contract_v1
scope=proof_api_runtime_contract_v1_definition_only
mode=docs_only_contract
document_status=DRAFT_DOCS_ONLY
contract_status=PENDING_CONTRACT_ONLY
contract_definition_verdict=PENDING
runtime_acceptance_verdict=BLOCKED
blocked_reason=missing_executable_proof_api_path_and_fresh_runtime_evidence
surface_decision_status=ACCEPTED_FOR_CONTRACT_FREEZE_ONLY
document_acceptance_status=PENDING
base_ref=main
base_commit=62907fce7f081dedba2125ebd3ea442bc5d3be04
base_tree=5bc874815529acaa12bf1651ecf923dd6f64d8ee
canonical_surface=next_supabase_evidence_lane
llm_gateway_is_proof_authority=false
implementation_status=NOT_STARTED
implementation_present=false
proof_endpoint_present=false
health_endpoint_present=false
runtime_verification=UNVERIFIED
runtime_changed=false
runtime_readiness=PENDING
runtime_smoke_run=false
negative_runtime_gate_run=false
ci_runtime_coverage=false
ci_health_smoke_covered=false
ci_proof_smoke_covered=false
ci_negative_runtime_covered=false
provider_called=false
secret_read=false
repo_pass_claimed=false
production_ready=false
canonical_truth=false
```

This document freezes the candidate contract for a future Proof API. It does
not implement an endpoint, change a database, execute a runtime, or validate a
deployment. The maximum claim supported by this file is:

```text
PENDING_CONTRACT_ONLY
```

## 1. Purpose

The Proof API must answer one narrow question:

> Does the evidence attached to this exact run satisfy the declared Proof API
> contract at the expected source revision?

The answer must be derived from inspectable identifiers, stored artifacts,
digests, an immutable receipt, and explicit failure reasons. A successful run
label, provider response, signed URL, demo replay, or CI job name is not proof
by itself.

## 2. Authority Boundary

### 2.1 Canonical candidate surface

The future Proof API belongs to the Next.js and Supabase evidence lane:

```text
Next.js request boundary
  -> Supabase run identity and state
  -> event identity
  -> stored artifact bytes and digest
  -> immutable receipt
  -> Proof API response
```

### 2.2 Explicit non-authorities

The following are not Proof truth authorities:

- `aios/gateway/*` and its LLM provider health or completion responses.
- A provider or model response.
- `runs.status = succeeded` without complete evidence.
- A storage path, signed URL, byte count, or database row without verified
  artifact bytes and digest.
- `make verify`, public demo replay, or a CI job name without HTTP runtime
  evidence for the exact revision.
- This contract document, a future implementation diff, a local commit, a
  pushed ref, or a Draft PR.

The LLM Gateway remains a provider gateway. The Proof API must not call it,
Ollama, or any external model provider.

### 2.3 Current CI coverage truth

At the frozen base tree, the job named `Proof API contract` runs `make verify`
and three deterministic public demo replays. It does not start the Next.js
server, call either contracted endpoint, execute negative HTTP cases, or bind a
runtime receipt to the job SHA.

Its current maximum claim is evidence-contract and synthetic-demo coverage for
its exact CI run. The job name, successful steps, or demo output must not be
described as Proof API HTTP runtime coverage.

## 3. Contracted Endpoints

Version 1 freezes two routes:

```text
GET  /api/health
POST /api/proof
```

No other existing route is promoted to Proof authority by this contract.

## 4. GET /api/health

### 4.1 Semantics

`GET /api/health` is a side-effect-free liveness and revision endpoint. It must
not:

- call Supabase, storage, GitHub, Cloud Run, the LLM Gateway, Ollama, or any
  provider;
- read secret values;
- create or modify files;
- create database rows;
- claim that evidence or runtime behavior has passed.

An HTTP `200` from this route means only that the Next.js handler responded.
It is not Proof API acceptance and is not runtime readiness.

### 4.2 Response schema

```json
{
  "schema_version": "taiji.proof.health.v1",
  "service": "taiji-proof-api",
  "status": "ok",
  "revision_binding": "configured",
  "api_exact_sha": "0123456789abcdef0123456789abcdef01234567",
  "reason_codes": [],
  "cannot_claim": [
    "proof_accepted",
    "runtime_readiness",
    "supabase_reachable"
  ]
}
```

Rules:

- `schema_version`, `service`, `status`, `revision_binding`, `api_exact_sha`,
  `reason_codes`, and `cannot_claim` are required. Additional properties are
  rejected.
- `status` is `ok` when the handler responds normally.
- `revision_binding` is `configured` only when a valid 40-character lowercase
  hexadecimal revision was injected from server-side immutable build metadata;
  a request value, run payload, or mutable runtime override is not a valid
  source. Otherwise it is `unconfigured` and `reason_codes` contains
  `missing_api_exact_sha`.
- `api_exact_sha` is the valid Next.js revision string when configured and
  `null` when unconfigured.
- `cannot_claim` is always non-empty.
- Health must not infer dependency readiness from secret presence.
- A smoke gate must compare `api_exact_sha` to its expected SHA. A mismatch blocks
  the smoke even when HTTP status is `200`.

## 5. POST /api/proof

### 5.1 Semantics

`POST /api/proof` is a read-only verification request over a previously
finalized run. It must not create or repair evidence, mutate run state, mint a
replacement receipt, dispatch a workflow, or call a provider.

The receipt and artifact digests must already exist before a run can enter
`succeeded`. The Proof API verifies them; it does not manufacture missing proof
at query time.

### 5.2 Request schema

```json
{
  "schema_version": "taiji.proof.request.v1",
  "expected_evidence_profile": "taiji.proof.evidence.mock.v1",
  "proof_query_id": "16906589-bcfd-4338-af90-766e5d8f4b6d",
  "run_request_id": "62c15237-bd79-434a-9a79-b9fbe1280af5",
  "run_id": "1ac16c0f-7b83-45c8-a3ee-80a72650bfa4",
  "expected_root_event_id": "d478d62b-64ca-45bc-af29-c719e4286824",
  "expected_api_exact_sha": "0123456789abcdef0123456789abcdef01234567",
  "expected_producer_exact_sha": "0123456789abcdef0123456789abcdef01234567",
  "expected_producer_image_digest": null
}
```

All nine fields are required. `expected_producer_image_digest` is `null` for
`mock` and a lowercase `sha256:` image digest for `github`.

| Field | Contract |
| --- | --- |
| `schema_version` | Exact value `taiji.proof.request.v1` |
| `expected_evidence_profile` | Exactly `taiji.proof.evidence.mock.v1` or `taiji.proof.evidence.github.v1` |
| `proof_query_id` | Caller-supplied correlation UUID for this read-only Proof query; not receipt-bound, authoritative, or an idempotency key |
| `run_request_id` | Valid UUID created when the run was accepted; receipt-bound |
| `run_id` | Valid UUID identifying one `runs.id` |
| `expected_root_event_id` | Valid UUID previously returned for this run |
| `expected_api_exact_sha` | Exactly 40 lowercase hexadecimal characters |
| `expected_producer_exact_sha` | Exactly 40 lowercase hexadecimal characters |
| `expected_producer_image_digest` | `null` for `mock`; `sha256:` plus 64 lowercase hexadecimal characters for `github` |

Additional properties are rejected. The request body must be JSON, must not
contain invite tokens or secrets, and must not exceed 16 KiB before decoding.
`Content-Type` must be `application/json`.

Version 1 always requires run-access authentication, even when demo invite
checks are disabled elsewhere. The future implementation may reuse token
extraction and hashing helpers, but it must not reuse the current
`assertRunAccess` behavior unchanged.

The Proof route must accept authentication only from either
`x-taiji-invite-token` or `Authorization: Bearer`, validate that the invite
exists and is not expired, and verify that the run belongs to that invite.
Exactly one credential carrier is allowed. Neither carrier maps to
`missing_invite_token`; both carriers or a malformed carrier map to
`invalid_request`; an unrecognized token maps to `invalid_invite_token`. It must
not consume quota or increment `used_runs`. Expired and cross-invite access
normalize to the closed reason codes in Section 9. Authentication material must
never be echoed into the response, logs, artifacts, or receipt.

### 5.3 Response schema

```json
{
  "contract_id": "proof_api_runtime_contract_v1",
  "schema_version": "taiji.proof.response.v1",
  "proof_scope": "stored_run_evidence_integrity_v1",
  "evidence_profile": "taiji.proof.evidence.mock.v1",
  "proof_query_id": "16906589-bcfd-4338-af90-766e5d8f4b6d",
  "verdict": "PASS",
  "proof_accepted": true,
  "reason_codes": [],
  "receipt": {
    "contract_id": "proof_api_runtime_contract_v1",
    "schema_version": "taiji.proof.receipt.v1",
    "proof_scope": "stored_run_evidence_integrity_v1",
    "evidence_profile": "taiji.proof.evidence.mock.v1",
    "receipt_id": "48df17fc-cd74-47a6-a39d-fbff4286a02a",
    "created_at": "2026-08-11T00:00:00Z",
    "finalized_at": "2026-08-11T00:00:01Z",
    "run_request_id": "62c15237-bd79-434a-9a79-b9fbe1280af5",
    "run_id": "1ac16c0f-7b83-45c8-a3ee-80a72650bfa4",
    "root_event_id": "d478d62b-64ca-45bc-af29-c719e4286824",
    "api_exact_sha": "0123456789abcdef0123456789abcdef01234567",
    "producer_exact_sha": "0123456789abcdef0123456789abcdef01234567",
    "producer_image_digest": null,
    "terminal_run_status": "succeeded",
    "trigger_mode": "mock",
    "event_manifest": [
      {
        "event_id": "d478d62b-64ca-45bc-af29-c719e4286824",
        "parent_event_id": null,
        "event_type": "run.created",
        "occurred_at": "2026-08-11T00:00:00Z",
        "payload_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
      },
      {
        "event_id": "e269409e-d64a-4fd8-b369-58997952bb3b",
        "parent_event_id": "d478d62b-64ca-45bc-af29-c719e4286824",
        "event_type": "artifact.stored",
        "occurred_at": "2026-08-11T00:00:01Z",
        "payload_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
      }
    ],
    "artifact_manifest": [
      {
        "artifact_id": "b5682f1c-2266-48fc-9362-6c35b17638c5",
        "producer_event_id": "e269409e-d64a-4fd8-b369-58997952bb3b",
        "bucket": "taiji-artifacts",
        "path": "runs/1ac16c0f-7b83-45c8-a3ee-80a72650bfa4/result.json",
        "label": "result.json",
        "content_type": "application/json",
        "bytes": 128,
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    ],
    "verifier_name": "taiji-proof-verifier",
    "verifier_version": "1.0.0",
    "verdict": "PASS",
    "reason_codes": [],
    "cannot_claim": [
      "deployment_provenance",
      "github_execution",
      "producer_execution_identity",
      "production_readiness",
      "provider_readiness",
      "repo_wide_pass",
      "task_correctness"
    ],
    "receipt_sha256": "ae8a2200d9b70b6088ee5da61dd1c60c0609feeb1c413975436de44f74bf8dc0"
  },
  "checked_at": "2026-08-11T00:00:02Z",
  "cannot_claim": [
    "deployment_provenance",
    "github_execution",
    "producer_execution_identity",
    "production_readiness",
    "provider_readiness",
    "repo_wide_pass",
    "task_correctness"
  ]
}
```

Rules:

- The complete canonical receipt is returned for `PASS`; a receipt summary or
  pointer alone is insufficient.
- Top-level `contract_id`, `proof_scope`, and `evidence_profile` must equal the
  corresponding receipt fields. The first two are the exact constants shown in
  the example.
- `proof_query_id` must echo the query value and is not persisted in the run
  receipt. Reusing it does not authorize access, deduplicate a query, or change
  the verification result.
- Receipt `evidence_profile`, `run_request_id`, `run_id`, `root_event_id`,
  `api_exact_sha`, `producer_exact_sha`, and `producer_image_digest` must match
  the request.
- `trigger_mode=mock` requires `taiji.proof.evidence.mock.v1`;
  `trigger_mode=github` requires `taiji.proof.evidence.github.v1`.
- `event_manifest` and `artifact_manifest` must exactly satisfy the selected
  evidence profile in Section 6. A non-empty arbitrary subset is insufficient.
- Artifact and receipt identifiers are UUIDs. Unprefixed payload, artifact, and
  receipt SHA-256 fields are exactly 64 lowercase hexadecimal characters;
  `producer_image_digest` separately uses `^sha256:[0-9a-f]{64}$`. Artifact
  `bytes` is non-negative.
- Each artifact path must be normalized below `runs/{run_id}/` and must not
  contain traversal segments.
- Signed URLs are delivery conveniences and are excluded from proof identity.
  The Proof route must not create one; delivery verification is a separate
  smoke scope.
- Top-level `verdict`, `reason_codes`, and `cannot_claim` must equal the
  corresponding verified receipt fields exactly.
- Every response `reason_codes` and `cannot_claim` array contains unique values
  sorted lexicographically.
- `proof_accepted=true` is derived only after the complete receipt digest,
  event manifest, artifact manifest, revisions, and request bindings verify.
- `cannot_claim` is a non-empty array even for `PASS`.
- Receipt and top-level `cannot_claim` include the complete selected-profile
  baseline from Section 6; omitting a required non-claim fails with
  `receipt_manifest_mismatch`.
- `verdict` is exactly one of `PASS`, `PENDING`, `BLOCKED`, `FAILED`, or
  `UNVERIFIED`.
- Raw database, storage, provider, or exception messages must not be returned.
- A `mock` result can support only its explicitly authorized mock smoke scope;
  it cannot prove GitHub, Cloud Run, provider, or production behavior.

### 5.4 Non-PASS response envelope

When full proof fields cannot be returned safely, the response uses this
minimum envelope:

```json
{
  "contract_id": "proof_api_runtime_contract_v1",
  "schema_version": "taiji.proof.response.v1",
  "proof_scope": "stored_run_evidence_integrity_v1",
  "evidence_profile": null,
  "proof_query_id": null,
  "run_request_id": null,
  "run_id": null,
  "verdict": "BLOCKED",
  "proof_accepted": false,
  "reason_codes": ["invalid_request"],
  "receipt": null,
  "checked_at": "2026-08-11T00:00:00Z",
  "cannot_claim": [
    "proof_accepted",
    "repo_wide_pass",
    "runtime_readiness"
  ]
}
```

`evidence_profile`, `proof_query_id`, `run_request_id`, and `run_id` are
populated only after their values have passed format validation. `checked_at`
is RFC 3339 UTC. Additional properties are rejected in both PASS and non-PASS
response schemas.

### 5.5 Required upstream contract changes

This document does not implement them, but a conforming future implementation
must also:

- return `run_request_id`, `run_id`, `root_event_id`, `api_exact_sha`,
  `evidence_profile`, and `trigger_mode` when a run is accepted;
- persist the root event before the run leaves `queued`;
- persist event lineage, artifact digests, and one immutable receipt;
- persist a closed `failure_code` atomically with any `failed` transition;
- finalize `succeeded` only after the receipt has been verified.

For `github` mode, the producer revision and immutable image digest are not
claimed at run acceptance. The final receipt records them as receipt-declared
producer identifiers subject to this contract's checks; because the receipt is
unsigned, they are not provenance or producer-execution-identity proof.

## 6. Identity and Evidence Graph

The persisted run evidence graph is:

```text
run_request_id
  -> run_id
  -> contract_id + proof_scope + evidence_profile
  -> root_event_id
  -> event_manifest with parent lineage
  -> profile-required artifact_id values
  -> artifact bytes + sha256
  -> receipt_id + receipt sha256
  -> api_exact_sha
  -> producer_exact_sha + producer_image_digest when applicable
```

### 6.1 Frozen evidence profiles

Both version 1 profiles prove only stored-run evidence integrity. They do not
prove task correctness, provider behavior, production readiness, or deployment
provenance.

| Evidence profile | Trigger | Required event inventory | Required artifact inventory |
| --- | --- | --- | --- |
| `taiji.proof.evidence.mock.v1` | `mock` | Exactly one root `run.created` and exactly one descendant `artifact.stored` | Exactly one `result.json`; path `runs/{run_id}/result.json`; content type `application/json`; producer is the required `artifact.stored` event |
| `taiji.proof.evidence.github.v1` | `github` | Exactly one root `run.created` and exactly one descendant `artifact.stored` | Exactly one `result.json`; path `runs/{run_id}/result.json`; content type `application/json`; producer is the required `artifact.stored` event |

An event or artifact outside the selected inventory is a
`receipt_manifest_mismatch`; an absent required event or artifact is
`event_missing` or `artifact_missing`. The artifact bytes remain opaque to this
profile: their integrity is verified, but their task semantics are not judged.

Every accepted receipt must contain at least this lexicographically sorted
`cannot_claim` baseline:

```text
deployment_provenance
github_execution
producer_execution_identity
production_readiness
provider_readiness
repo_wide_pass
task_correctness
```

The `github` profile name records the declared trigger mode only; without a
separate workflow/run/job/execution attestation, it does not prove GitHub or
Cloud Run execution. Additional honest non-claims are allowed, remain sorted,
and are included in the receipt digest.

`proof_query_id` identifies only the read-only verification call. It is echoed
in the response and smoke receipt but is not part of the persisted run receipt
or its evidence lineage.

### 6.2 Identity invariants

Invariants:

1. `proof_query_id`, `run_request_id`, `run_id`, and event identifiers are
   distinct namespaces and are never substituted for each other.
2. `run_id` identifies exactly one run.
3. `run_request_id` is created when the run is accepted, is persisted on the
   run, and is bound into the receipt.
4. Every run has exactly one `root_event_id` before it leaves `queued`.
5. Every event manifest entry contains `event_id`, nullable
   `parent_event_id`, `event_type`, RFC 3339 UTC `occurred_at`, and
   `payload_sha256` over the RFC 8785 canonical payload.
6. The root event has `parent_event_id=null`. Every other event reaches that
   root exactly once, with no cycle, duplicate ID, orphan, or foreign root.
7. Every event belongs to the same `run_id` and `root_event_id` lineage.
8. Every artifact has one `artifact_id`, one `run_id`, and one
   `producer_event_id` that exists in the same lineage.
9. Artifact SHA-256 is computed from the stored raw bytes, not from a URL,
   path, database row, or serialized metadata.
10. The stored byte count must equal the downloaded byte count used for digest
   verification.
11. `serving_api_sha`, request `expected_api_exact_sha`, health
   `api_exact_sha`, and receipt `api_exact_sha` are equal and originate from the
   same server-side immutable build metadata. Request or run data cannot set the
   serving value.
12. In mock mode, receipt `producer_exact_sha` equals receipt `api_exact_sha`
   and `producer_image_digest` is null. In GitHub mode, producer identifiers
   come from server-side execution metadata and `producer_image_digest` matches
   `^sha256:[0-9a-f]{64}$`.
13. The receipt binds `contract_id`, `proof_scope`, `evidence_profile`, both
   execution-plane revisions, the run, root event, complete event manifest,
   ordered artifact manifest, terminal state, verifier version, verdict, and
   `cannot_claim` list.
14. The Proof response is accepted only when every requested, serving, and
   persisted identifier matches.
15. A missing link is `BLOCKED`; a contradictory link is `FAILED`.

## 7. Receipt Contract

The future runtime must persist one immutable receipt before it can mark a run
`succeeded`.

Required receipt fields:

```text
contract_id
schema_version
proof_scope
evidence_profile
receipt_id
created_at
finalized_at
run_request_id
run_id
root_event_id
api_exact_sha
producer_exact_sha
producer_image_digest
terminal_run_status
trigger_mode
event_manifest
artifact_manifest
verifier_name
verifier_version
verdict
reason_codes
cannot_claim
receipt_sha256
```

The event manifest is ordered lexicographically by `event_id`. The artifact
manifest is ordered lexicographically by `artifact_id` and contains
`artifact_id`, `producer_event_id`, `bucket`, `path`, `label`, `content_type`,
`bytes`, and `sha256` for every required artifact. `reason_codes` and
`cannot_claim` are unique arrays sorted lexicographically. These ordering rules
apply before receipt hashing.

Version 1 receipts are success-only. In a conforming state, a receipt exists if
and only if the run is `succeeded`; its `terminal_run_status` is `succeeded`,
its `verdict` is `PASS`, and `reason_codes` is empty. `queued`, `running`,
`failed`, and `cancelled` runs have no receipt, and every non-PASS Proof
response returns `receipt=null`. A `succeeded` row with no valid unique receipt
is non-conforming and cannot receive Proof PASS.

`contract_id` is exactly `proof_api_runtime_contract_v1`; `proof_scope` is
exactly `stored_run_evidence_integrity_v1`; `evidence_profile` is one of the two
Section 6 profiles and must match `trigger_mode`.

`producer_image_digest` is `null` in `mock` mode and required in `github` mode.
The receipt never contains `proof_query_id`. The Proof response returns the
complete receipt so a caller can independently recompute its digest.

`receipt_sha256` is calculated over the receipt with the `receipt_sha256`
field omitted, using UTF-8 JSON Canonicalization Scheme semantics. An
implementation must freeze the exact canonicalization library or equivalent
test vectors before claiming digest compatibility. The complete PASS example
in Section 5.3 recomputes to its shown `receipt_sha256` under these rules; it is
a contract test vector, not runtime evidence.

Version 1 uses RFC 8785 JSON Canonicalization Scheme semantics. The receipt is
unsigned and is not an in-toto attestation, signature, or provenance claim.

Receipt and response timestamps use RFC 3339 UTC. They must satisfy
`run.created_at <= receipt.created_at <= receipt.finalized_at <= checked_at`.
Receipt `finalized_at` must equal run `finished_at`. The Proof API must not use
an unbound `latest` file as freshness evidence.

A second receipt for the same run is forbidden unless a future version defines
an explicit supersession lineage. Version 1 returns `FAILED` with reason code
`duplicate_receipt`.

## 8. State and Finalization Rules

Allowed run transitions remain:

```text
queued -> running
       -> failed
       -> cancelled
running -> succeeded
        -> failed
        -> cancelled
terminal -> no further transition
```

State invariants:

- `queued`: `progress=0`, with no `started_at` or `finished_at`.
- `running`: `progress` is 1 through 99, `started_at` is set, and
  `finished_at` is null.
- Every terminal state has `progress=100` and `finished_at` set.
- A terminal state is immutable in version 1.
- A v1 `failed` transition persists one closed `failure_code` in the same
  transaction. Known causes use their Section 9 reason code; `run_failed` is
  the fallback only when no more specific durable cause exists.
- `failure_code` is null for `queued`, `running`, `succeeded`, and `cancelled`.

`succeeded` is allowed only through this finalization protocol:

1. The producer stores required artifact bytes at deterministic run-scoped
   paths while the run remains `running`.
2. The verifier reads the stored bytes, calculates byte counts and SHA-256
   values, and verifies the complete event lineage and selected evidence
   profile.
3. The runtime prepares the canonical artifact manifest and receipt candidate,
   computes `receipt_sha256`, then independently canonicalizes and recomputes
   that digest before any terminal transaction begins. A mismatch stops here.
4. One Supabase database transaction or RPC uses compare-and-set semantics on
   `status=running` and commits pending required event rows, artifact rows, the
   immutable receipt, mutual run/receipt references, `status=succeeded`,
   `progress=100`, and one shared `finalized_at` value atomically.
5. Any failure inside that transaction rolls back every database effect. A
   receipt row and `succeeded` state must never be observable separately.
6. An optional post-commit read-back is an integrity observation only, not a
   delayed precondition for committing success. A read-back mismatch makes
   subsequent Proof responses `FAILED/receipt_digest_mismatch`; it cannot
   manufacture, replace, or repair the committed receipt.

Finalization is idempotent for the same `run_id` and identical receipt digest:
an already committed identical result returns the existing receipt. A retry
with different bytes, manifest, receipt digest, or terminal state returns
`FAILED/finalization_conflict` and must not overwrite the committed receipt.

If storage succeeds but database finalization fails, the run must not become
`succeeded`. The runtime attempts a bounded `failed` transition with the exact
closed `failure_code`. If that transition also fails, the durable run remains
`running`, so the Proof response remains `PENDING/run_not_terminal`; an
out-of-band operational error is not Proof state. Any unbound storage object is
not evidence, does not authorize a receipt, and is outside automatic cleanup in
this contract.

No artifact upload failure, artifact-row insert failure, missing event lineage,
receipt persistence failure, invalid state transition, or digest mismatch known
before the atomic transaction may commit `succeeded`. Any later corruption or
contradiction forces Proof non-PASS; the status label alone never overrides it.

Terminal-state repair, receipt replacement, truth promotion, and historical
backfill are outside version 1 and require separate contracts and authorization.

## 9. Verdict and HTTP Mapping

`proof_accepted=true` if and only if HTTP is `200`, top-level verdict is `PASS`,
the returned receipt verdict is `PASS`, and the complete receipt has passed all
binding and digest checks.

Version 1 uses a closed reason-code mapping. A non-PASS response contains
exactly one primary reason code, which fixes its HTTP status and verdict:

| Primary reason code | HTTP | Verdict |
| --- | ---: | --- |
| none; fully verified receipt | 200 | `PASS` |
| `run_not_terminal` | 202 | `PENDING` |
| `invalid_request` | 400 | `BLOCKED` |
| `request_too_large` | 413 | `BLOCKED` |
| `unsupported_media_type` | 415 | `BLOCKED` |
| `unsupported_contract` | 422 | `BLOCKED` |
| `missing_invite_token` | 401 | `BLOCKED` |
| `invalid_invite_token` | 401 | `BLOCKED` |
| `invite_expired` | 403 | `BLOCKED` |
| `run_access_denied` | 403 | `BLOCKED` |
| `run_not_found` | 404 | `BLOCKED` |
| `missing_api_exact_sha` | 503 | `UNVERIFIED` |
| `producer_revision_missing` | 409 | `BLOCKED` |
| `producer_image_digest_missing` | 409 | `BLOCKED` |
| `run_failed` | 409 | `FAILED` |
| `run_cancelled` | 409 | `FAILED` |
| `run_id_mismatch` | 409 | `FAILED` |
| `run_request_id_mismatch` | 409 | `FAILED` |
| `root_event_mismatch` | 409 | `FAILED` |
| `event_missing` | 409 | `BLOCKED` |
| `event_lineage_mismatch` | 409 | `FAILED` |
| `event_payload_digest_mismatch` | 409 | `FAILED` |
| `api_sha_mismatch` | 409 | `FAILED` |
| `producer_sha_mismatch` | 409 | `FAILED` |
| `producer_image_digest_mismatch` | 409 | `FAILED` |
| `artifact_missing` | 409 | `BLOCKED` |
| `artifact_object_missing` | 409 | `BLOCKED` |
| `stored_bytes_unverified` | 409 | `BLOCKED` |
| `artifact_path_invalid` | 409 | `FAILED` |
| `artifact_bytes_mismatch` | 409 | `FAILED` |
| `artifact_digest_mismatch` | 409 | `FAILED` |
| `artifact_upload_failed` | 409 | `FAILED` |
| `artifact_record_failed` | 409 | `FAILED` |
| `event_persist_failed` | 409 | `FAILED` |
| `receipt_missing` | 409 | `BLOCKED` |
| `receipt_malformed` | 409 | `FAILED` |
| `duplicate_receipt` | 409 | `FAILED` |
| `receipt_persist_failed` | 409 | `FAILED` |
| `receipt_digest_mismatch` | 409 | `FAILED` |
| `receipt_manifest_mismatch` | 409 | `FAILED` |
| `invalid_state_transition` | 409 | `FAILED` |
| `finalization_conflict` | 409 | `FAILED` |
| `dependency_unavailable` | 503 | `UNVERIFIED` |
| `provider_call_forbidden` | 500 | `FAILED` |
| `secret_exposure_detected` | 500 | `FAILED` |
| `internal_verification_error` | 500 | `UNVERIFIED` |

Malformed JSON and missing required fields map to `invalid_request`. Unknown
fields, invalid UUID/SHA/digest formats, and unsupported schema values map to
`unsupported_contract`. An unknown reason code fails response-schema
validation.

The following potentially overlapping cases are resolved explicitly:

- `missing_api_exact_sha` means the serving process has no valid configured API
  revision. A receipt that omits its required `api_exact_sha` is
  `receipt_malformed`.
- A receipt or persisted evidence graph bound to a different run is
  `run_id_mismatch`; a different accepted-request identity is
  `run_request_id_mismatch`.
- A missing artifact `producer_event_id` field is `receipt_malformed`; an
  unknown referenced event is `event_missing`; a reference into another run is
  `event_lineage_mismatch`.
- A terminal success with no required artifact is `artifact_missing`. Treating
  a path or signed URL as verified bytes is `stored_bytes_unverified`.
- A receipt observable without its matching atomic terminal update is
  `invalid_state_transition`; a retry with different finalization content is
  `finalization_conflict`.
- A required receipt control field that is absent is `receipt_malformed`.
  A valid request, run, and receipt whose `contract_id`, `proof_scope`,
  `evidence_profile`, or `trigger_mode` disagree is
  `receipt_manifest_mismatch`. A top-level response control field that differs
  from the already verified receipt is `internal_verification_error`.
- Storage upload, artifact-row, event-row, receipt-row, and terminal-state
  persistence failures use `artifact_upload_failed`, `artifact_record_failed`,
  `event_persist_failed`, `receipt_persist_failed`, and
  `invalid_state_transition`, respectively.
- For a terminal `failed` run, a valid durable `failure_code` is the primary
  response reason even if its table row appears later; `run_failed` is used only
  when the cause is absent or cannot be normalized safely.

Evaluation is deterministic and short-circuits in this order:

1. raw body size and media type;
2. JSON decoding, required fields, additional fields, and field formats;
3. authentication and run authorization;
4. run lookup and terminal state;
5. request-to-run identity and revision bindings;
6. receipt existence, shape, uniqueness, digest, and atomic finalization;
7. event lineage and payload digests;
8. artifact identity, path, stored bytes, byte count, and digest;
9. response serialization and final safety assertions.

Within one stage, the first applicable reason in the Section 9 table wins,
subject to the durable `failure_code` rule above.
`secret_exposure_detected` and `provider_call_forbidden` are final safety
assertions and override every lower-severity result. Dependency or internal
errors map to their named `UNVERIFIED` reasons only when no more specific
contract failure has already been established.

For every non-`PASS` response:

- `proof_accepted` is `false`;
- `reason_codes` contains exactly the one mapped primary reason;
- `cannot_claim` is non-empty;
- no success language appears outside quoted input evidence.

Version 1 does not return `PARTIAL`: incomplete evidence is `BLOCKED`.
`PENDING`, `BLOCKED`, `FAILED`, and `UNVERIFIED` must not be converted to `PASS`
by a client, UI, closeout, or CI summary.

## 10. Required Fail-Closed Cases

The RED package must cover at least:

1. Malformed JSON.
2. Request body exceeds 16 KiB or has a non-JSON content type.
3. Missing required field.
4. Unknown additional field.
5. Unsupported schema version.
6. Invalid UUID or SHA format.
7. Missing, invalid, expired, unauthorized, or ambiguously transported invite
   access.
8. Run not found.
9. Run still queued or running.
10. Run failed or cancelled.
11. `run_request_id`, root event, or run binding mismatch.
12. Event missing, duplicated, orphaned, cyclic, attached to a foreign root, or
    carrying a mismatched payload digest.
13. API SHA, producer SHA, or required producer image digest is missing or
    mismatched.
14. `succeeded` run with zero artifacts.
15. Artifact row exists but stored object is missing.
16. Stored bytes do not match recorded byte count.
17. Artifact digest mismatch.
18. Artifact path escapes or does not match `runs/{run_id}/`.
19. Artifact `producer_event_id` is missing or belongs to another run.
20. Receipt missing, malformed, duplicated, digest-mismatched, or manifest-
    mismatched.
21. Receipt transaction commits without the matching terminal run update, or a
    retry attempts different finalization content.
22. Signed URL presence is accepted instead of reading and hashing stored
    bytes. Signed URL delivery failure alone must not change Proof verdict.
23. Provider, LLM Gateway, Ollama, workflow dispatch, or external model call is
    attempted by either contracted endpoint.
24. Secret or invite material appears in response, stdout, logs, artifacts, or
    receipt.
25. Artifact, event, receipt, or terminal-state persistence fails before atomic
    finalization.
26. Health performs any dependency, network, database, storage, provider,
    filesystem, or secret access.
27. Proof changes `used_runs`, inserts, updates, or deletes a database row,
    writes or deletes a storage object, creates a signed URL, dispatches work,
    or otherwise changes state.
28. Receipt `contract_id`, `proof_scope`, selected evidence profile, required
    inventory, or required `cannot_claim` baseline is missing or mismatched.
29. Serving API build metadata, request `expected_api_exact_sha`, and receipt
    `api_exact_sha` are not identical; or a mode-specific producer invariant is
    violated.

For response-producing cases, a negative self-test passes only when each case
is rejected with the expected Section 9 HTTP status, verdict, and reason code.
Items 26 and 27 are side-effect assertions: the harness fails with
`health_side_effect_detected` or `proof_mutation_detected` even if the endpoint
returns a superficially successful response; these two harness codes are not
Proof API response reasons. A validator crash, skipped case, empty output, or
unexpected error is not a passing negative test.

## 11. Future Smoke Command Shape

These commands are contract candidates only. They must not be run until a
separate runtime authorization binds the implementation and exact SHA.

```bash
curl -sS -i http://127.0.0.1:3000/api/health

curl -sS -i -X POST http://127.0.0.1:3000/api/proof \
  -H 'content-type: application/json' \
  -H 'x-taiji-invite-token: REDACTED_FOR_CONTRACT_EXAMPLE' \
  --data '{"schema_version":"taiji.proof.request.v1","expected_evidence_profile":"taiji.proof.evidence.mock.v1","proof_query_id":"16906589-bcfd-4338-af90-766e5d8f4b6d","run_request_id":"62c15237-bd79-434a-9a79-b9fbe1280af5","run_id":"1ac16c0f-7b83-45c8-a3ee-80a72650bfa4","expected_root_event_id":"d478d62b-64ca-45bc-af29-c719e4286824","expected_api_exact_sha":"0123456789abcdef0123456789abcdef01234567","expected_producer_exact_sha":"0123456789abcdef0123456789abcdef01234567","expected_producer_image_digest":null}'
```

`REDACTED_FOR_CONTRACT_EXAMPLE` is a deliberately invalid literal, not an
unresolved secret or executable credential. The shown POST is therefore an
authentication-negative candidate only. A future accepted-case command must
receive authorized authentication material through a protected runtime
mechanism, must not print it, and must record only redacted transport metadata.

The future smoke must include one accepted case and the required negative
cases. It must fail when the response SHA differs from the authorized SHA, even
if the endpoint returns HTTP `200`.

## 12. Required Smoke Receipt

```text
audit_event_id
scope
contract_id
proof_scope
evidence_profile
expected_evidence_profile
trigger_mode
audit_exact_sha
exact_tree
environment
base_url
commands_run
started_at
finished_at
raw_exit_codes
http_methods
http_statuses
proof_query_id
run_request_id
run_id
expected_root_event_id
root_event_id
event_ids
event_manifest_sha256
state_transitions
artifact_ids
artifact_manifest_sha256
artifact_sha256_values
receipt_id
receipt_sha256
expected_api_exact_sha
serving_api_sha
receipt_api_exact_sha
expected_producer_exact_sha
producer_exact_sha
expected_producer_image_digest
producer_image_digest
expected_verdicts
actual_verdicts
reason_codes
stdout_sha256
stderr_sha256
allowed_network_destinations
observed_network_destinations
provider_calls
operator_secret_read
auth_material_transport
secret_value_exposed
health_dependency_call_count
health_secret_access_count
health_filesystem_mutation_count
proof_db_mutation_count
proof_storage_mutation_count
used_runs_before
used_runs_after
signed_url_created
repository_write
changed_files
verdict
blocker
cannot_claim
next_gate
```

Secret values, invite tokens, authorization headers, signed URLs, and raw
credentials must be redacted before receipt persistence.

`allowed_network_destinations` and `observed_network_destinations` use logical
classes such as `loopback`, `supabase_db`, and `supabase_storage`; they never
record credentials or signed query strings. Observed destinations must be a
subset of the authorized list. `provider_calls` must be empty,
`operator_secret_read=false`, and `secret_value_exposed=false`.

`audit_event_id` identifies the smoke audit and is never substituted for a run
event. `event_manifest_sha256` and `artifact_manifest_sha256` are SHA-256 over
the RFC 8785 canonical `event_manifest` and `artifact_manifest` returned in the
receipt.

`audit_exact_sha` identifies the checked-out API source authorized for the
smoke. In both modes it equals `expected_api_exact_sha`, `serving_api_sha`, and
`receipt_api_exact_sha`. In mock mode it also equals `producer_exact_sha`, with
`producer_image_digest=null`. In GitHub mode the receipt separately binds the
producer revision and immutable producer image digest.

`expected_evidence_profile` equals both the request and receipt profile, and
the receipt `trigger_mode` must select that profile. `expected_root_event_id`,
`expected_producer_exact_sha`, and `expected_producer_image_digest` equal the
corresponding request and receipt fields exactly.

The accepted health case requires `health_dependency_call_count=0` and
`health_secret_access_count=0` and `health_filesystem_mutation_count=0`. Every
Proof case requires
`proof_db_mutation_count=0`, `proof_storage_mutation_count=0`,
`used_runs_before=used_runs_after`, and `signed_url_created=false`.

## 13. Gate Sequence

The contract freezes this order:

```text
1. read-only contract review and human acceptance
2. exact-scope RED schema/fixture/test package
3. minimum implementation
4. positive and negative local verification
5. independent read-only review
6. separately authorized provider-free runtime smoke
7. separately authorized stage
8. separately authorized local commit
9. separately authorized non-force push
10. exact-SHA CI audit
11. separate Ready and merge decisions
```

No later gate is implied by acceptance of an earlier gate.

## 14. Contract Acceptance Evidence

Acceptance of this document requires only documentation evidence:

- the file exists at the authorized path;
- its base commit and tree match the authorized contract-freeze base;
- it names the Next.js and Supabase evidence lane as the candidate Proof
  surface and excludes the LLM Gateway from Proof authority;
- it defines both endpoint schemas, identity bindings, receipt invariants,
  fail-closed cases, smoke receipt, and explicit non-claims;
- it contains no unresolved placeholder markers, implementation-active status,
  runtime-success claim, or production-readiness claim;
- the Git worktree change scope is exactly this one Markdown file.

Document acceptance does not accept an implementation or runtime.

## 15. Cannot Claim

This contract cannot prove or claim:

```text
proof_api_implemented=true
proof_contract_accepted=true
schema_internal_consistency_verified=true
health_endpoint_exists=true
proof_endpoint_exists=true
schema_enforced=true
database_migrated=true
fail_open_fixed=true
negative_tests_exist=true
red_package_ready=true
tests_pass=true
runtime_smoke_pass=true
provider_ready=true
external_runtime_ready=true
production_ready=true
security_complete=true
availability_or_durability_proven=true
performance_slo_met=true
signed_attestation_exists=true
deployment_provenance_verified=true
producer_execution_identity_proven=true
task_correctness_proven=true
remote_ref_synced=true
ci_covers_http_runtime=true
repo_wide_pass=true
canonical_truth=true
all_blockers_removed=true
```

## 16. Stop Conditions and Next Gate

Stop and keep the contract `PENDING_CONTRACT_ONLY` if:

- the canonical surface decision changes;
- the base SHA or tree cannot be bound;
- required identifiers or digest rules remain ambiguous;
- acceptance would require source, schema, fixture, runtime, provider, or Git
  changes outside this file;
- an implementation or runtime claim is inferred from this document.

The immediate next gate for this unaccepted draft is:

```text
PROOF_API_RUNTIME_CONTRACT_V1_READONLY_ACCEPTANCE
```

If that gate accepts the document, the only subsequent gate is:

```text
PROOF_API_RUNTIME_CONTRACT_V1_EXACT_RED_PACKAGE_AUTH
```

That gate must separately freeze its exact file set, commands, expected RED
results, exclusions, and receipt before any implementation begins.

# Provider Boundary Gate

## Verdict

```text
verdict=provider_boundary_gate_draft
scope=external_provider_execution_boundary_v0_1
mode=docs_only_provider_boundary
external_provider_execution=BLOCKED
provider_smoke_test=not_run
api_keys_configured=false
env_read=false
secret_read=false
runtime_changed=false
stage_commit_push=false
repo_pass_claimed=false
```

## Purpose

This document defines the gate that must be passed before TaijiOS can execute
external provider calls in a reviewed scope.

External provider execution is BLOCKED until explicit gate approval.

## Hard Rules

```text
no API keys in repo
no .env reading during onboarding
no provider smoke test during onboarding
no secret values printed, copied, summarized, or logged
no provider output becomes PASS directly
no external API execution without explicit scope approval
```

Provider readiness is a separate claim. It cannot be inferred from model
availability, local configuration, README examples, or user intent.

## Required Provider Call Evidence

Every approved provider call must capture:

| Evidence | Required | Notes |
| --- | --- | --- |
| request metadata | yes | Request id, caller, mode, timestamp, and scope |
| model/provider | yes | Exact provider and model route |
| cost/token estimate | yes | Estimate or actual usage when available |
| output artifact | yes | Saved response or redacted result pointer |
| failure mode | yes | Timeout, auth, rate limit, provider error, policy block |
| fallback path | yes | What happens if provider fails |
| audit event | yes | EventFlow or gateway audit entry |

If any required evidence is missing, the call may still be useful, but it must
remain PARTIAL or BLOCKED.

## Provider Output Boundary

Provider output is not truth.

Provider output may become candidate evidence only after:

```text
scope is declared
request metadata is recorded
output artifact is saved
forbidden claims are checked
verifier or human review evaluates the result
closeout records what is and is not claimed
```

## Approved Future Gate Shape

A future provider smoke test should be a separate, explicit scope with:

```text
preflight
existence-only secret checks
no secret value printing
single minimal provider call
cost limit
timeout limit
audit event
output artifact
closeout
git state capture
```

## Blocked Actions

Blocked by default:

```text
reading .env values
copying API keys
printing secret values
calling external providers during onboarding
using provider output as PASS
using provider failure as repo failure
configuring paid providers without approval
promoting direct SDK calls around Gateway policy
```

## Non-Claims

This document does not claim:

```text
provider ready
API configured
gateway live
external API access available
budget ready
auth ready
production route ready
runtime readiness
```

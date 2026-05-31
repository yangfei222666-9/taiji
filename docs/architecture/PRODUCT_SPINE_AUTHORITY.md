# Product Spine Authority

## Verdict

```text
verdict=product_spine_authority_boundary_draft
scope=product_spine_authority_docs_v0_1
mode=docs_only_authority_boundary
runtime_changed=false
provider_called=false
secret_read=false
stage_commit_push=false
repo_pass_claimed=false
runtime_readiness=PENDING
```

## Purpose

Product Spine is the core authority path for TaijiOS. It is the minimum
evidence pipeline that turns a claim, workflow, demo, module, or model output
into an auditable state.

The Product Spine path is:

```text
Boot Preflight
-> EventFlow
-> Scope Isolation
-> Artifact Memory
-> Closeout
```

No feature, provider, UI surface, symbolic renderer, automation, SpaceOps
simulation, or future module may outrank this path.

## Authority Rule

The Evidence Kernel is the authority for verdicts.

Allowed verdicts must be based on evidence:

```text
PASS
PARTIAL
PENDING
BLOCKED
FAILED
UNVERIFIED
```

Model output is candidate evidence only. Provider output is not truth. Local
notes, drafts, screenshots, demos, and generated summaries are not canonical
truth until the relevant evidence gate verifies them.

## Required Components

Every Product Spine claim should preserve these components.

| Component | Role | Boundary |
| --- | --- | --- |
| Boot Preflight | Decide whether the run is allowed to start | Not a success verdict |
| EventFlow | Record parseable transitions | Append-only evidence, not narrative memory |
| Scope Isolation | Separate exact-scope truth from repo truth | Scope pass is not repo pass |
| Artifact Memory | Preserve evidence and source references | Memory is candidate context, not authority |
| Closeout | State final verdict, boundaries, and next action | Must not hide blockers or missing gates |

## Candidate Layers

The following layers may feed Product Spine, but they do not create verdict
authority by themselves:

```text
models
UI
XuanShu
automation
SpaceOps
scenario simulation
agent runtime modules
future product modules
external research
T7 archive material
```

These layers can propose, render, summarize, simulate, or assist. They cannot
promote a claim into PASS without Evidence Kernel review.

## Forbidden Upgrades

```text
provider output -> truth
model agreement -> canonical truth
local draft -> repo PASS
scope PASS -> repo PASS
demo success -> runtime readiness
renderer output -> command authority
learning_only -> judgment
observe_only -> trade
blocked -> failed
partial -> pass
```

## Non-Claims

This document does not claim:

```text
repo-level PASS
runtime readiness
provider readiness
external API readiness
production readiness
SpaceX readiness
trade/order readiness
paper-buy readiness
judgment readiness
```

## Acceptance Criteria

This boundary can be treated as reviewed only after:

```text
all Product Spine components are represented in docs or verifier code
required evidence fields are preserved in closeout artifacts
provider/model/UI layers are kept below Evidence Kernel authority
tests or verifier output support any stronger claim
git status, branch, commit, and staged state are captured for repo claims
```

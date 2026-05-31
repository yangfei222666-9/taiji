# HSDL Canonical Spec v0.1

## Verdict

```text
verdict=hsdl_spec_draft
scope=hidden_systems_design_language_v0_1
mode=docs_only_visual_audit_language
production_ui_readiness=PENDING
runtime_changed=false
code_changed=false
secret_read=false
stage_commit_push=false
repo_pass_claimed=false
t7_imported=false
```

## Purpose

HSDL means Hidden Systems Design Language.

Motto:

```text
Hidden systems, visible evidence.
```

HSDL is the visual audit language for TaijiOS, Hidden Systems OS, Evidence Kernel surfaces, XuanShu renderer states, and future Xiaojiu Tongtianlu presentation layers.

It is not production UI readiness. It is not repo-level `PASS`. It is not proof that any runtime, deployment, provider, external API, robot, SpaceOps, trading, or high-risk workflow is ready.

## Visual Direction

HSDL combines three layers:

```text
Dark Mission Control -> Enterprise Trust -> Mythic Energy
```

Meaning:

| Layer | Role | Boundary |
| --- | --- | --- |
| Dark Mission Control | operational focus, telemetry, state awareness | must stay readable and evidence-first |
| Enterprise Trust | auditability, restraint, reliability, review readiness | must avoid hype and unverifiable claims |
| Mythic Energy | symbolic depth, cultivation route, XuanShu resonance | renderer-only; never overrides evidence |

## Verdict Color System

| State | Color | Meaning |
| --- | --- | --- |
| `PASS` | `#00E676` | scoped evidence supports the claim |
| `PARTIAL` | `#FFB300` | some evidence exists, but validation is incomplete |
| `PENDING` | `#29B6F6` | planned, unverified, or waiting for evidence |
| `BLOCKED` | `#FF3D00` | hard boundary, missing gate, or unsafe next step |
| `CANONICAL` | `#D4AF37` | accepted source-of-truth after explicit verification |
| `LOCAL_ONLY` | `#9575CD` | local artifact, not repo truth |
| `DRAFT_PR` | `#AB47BC` | proposed review packet, not merged truth |
| `MERGED` | `#4DB6AC` | merged into repo, still not automatically repo-level `PASS` |

## State Semantics

`MERGED` is not repo-level `PASS`.

`CANONICAL` requires explicit evidence. At minimum, it needs merge plus a clean clone or an equivalent verification packet that captures branch, commit, remotes, status, and relevant validation commands.

`LOCAL_ONLY` means useful context or artifact, but not canonical truth.

`DRAFT_PR` means review is possible, not accepted.

`BLOCKED` does not mean failure. It means the next action must not proceed until the blocking condition is resolved.

## Required Rendering Rules

Every HSDL surface that displays a claim should preserve:

```text
verdict
scope
mode
source artifact
last verified time
what cannot be claimed
next allowed action
```

When space is limited, the surface may compress the fields, but it must not hide the distinction between:

```text
local artifact
draft PR
merged file
canonical truth
repo-level validation
production readiness
```

## Non-Claims

HSDL does not claim:

```text
production UI readiness
repo-level PASS
runtime readiness
provider readiness
external API readiness
SpaceX readiness
trading readiness
medical/legal/safety authority
```

## Acceptance Criteria

This spec can move from draft to reviewed only after:

```text
status colors are used consistently
state labels preserve audit meaning
UI examples separate vision from verified state
manual review confirms no overclaiming
frontend implementation, if any, passes build/lint/responsive/accessibility checks
```

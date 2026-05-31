# Multi-Model Architecture Gate

## Verdict

```text
verdict=multi_model_architecture_gate_draft
scope=multi_model_collaboration_boundary_v0_1
mode=docs_only_ai_tool_routing_boundary
external_provider_execution=BLOCKED
secret_read=false
runtime_changed=false
stage_commit_push=false
repo_pass_claimed=false
```

## Purpose

TaijiOS can use multiple AI systems, but no model is an authority source. Every
model output is candidate evidence until Product Spine, TaijiOS Audit, tests,
or human review validates the exact claim.

## Role Split

| Actor | Primary role | Allowed output | Boundary |
| --- | --- | --- | --- |
| Codex | Planning, architecture, repo-aware validation commands | Scope packets, docs, implementation plans, validation commands | Cannot claim repo PASS without evidence |
| CC + DeepSeek | Scoped implementation | Small diffs, tests, local repair candidates | Implementation is candidate until tested and reviewed |
| Gemini | Visual and UI direction | Visual direction, layout ideas, taste candidates | Visual approval is not production readiness |
| Human owner | Final product judgment | Taste, product direction, explicit go/no-go | Human approval does not bypass safety gates |
| TaijiOS Audit | Evidence gate | PASS, PARTIAL, PENDING, BLOCKED classifications | Evidence only; no provider output as truth |

## Operating Rule

```text
multi_model_output = candidate_evidence
candidate_evidence != canonical_truth
canonical_truth requires Product Spine evidence
```

Models can disagree. Disagreement is useful signal and must be logged, not
hidden.

## Cross-Model Disagreement Rule

When models disagree on architecture, implementation, visual direction, or
readiness:

```text
record the disagreement
name the affected scope
preserve each model's claim as candidate evidence
identify required validation
do not average the outputs into a fake consensus
do not hide the disagreement in closeout
```

The final verdict must come from evidence, tests, artifact review, or explicit
human judgment when the decision is subjective.

## Default Flow

```text
Codex scopes the work and validation evidence
CC + DeepSeek may implement exact-scope changes
Gemini may propose visual direction
Human owner decides taste and product direction
TaijiOS Audit classifies evidence
Product Spine closeout records final state
```

## Forbidden Upgrades

```text
model confidence -> truth
model agreement -> repo PASS
visual approval -> production readiness
provider output -> validated evidence
implementation diff -> runtime readiness
human excitement -> gate approval
missing tests -> pass
```

## Required Evidence

Before a multi-model result can be promoted:

```text
scope must be named
files changed must be listed
validation command or review gate must be named
model disagreement must be recorded when present
secret/provider/trade boundaries must be preserved
closeout must state what is not claimed
```

## Non-Claims

This document does not claim:

```text
any provider is configured
any model is authoritative
multi-model routing is production-ready
runtime execution is ready
repo-level PASS
SpaceX readiness
```

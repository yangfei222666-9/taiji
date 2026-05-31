# Runtime Maturity Matrix

## Verdict

```text
verdict=runtime_maturity_matrix_draft
scope=runtime_maturity_classification_v0_1
mode=docs_only_runtime_review_boundary
runtime_changed=false
provider_called=false
secret_read=false
stage_commit_push=false
repo_pass_claimed=false
production_ready=false
runtime_readiness=PENDING
```

## Purpose

This matrix separates Product Spine assets, partially reviewed runtime modules,
experimental modules, platform-blocked modules, and legacy paths. It prevents
prototype code from being promoted into production claims without tests and
closeout.

No module can be called production-ready without tests and closeout.

## Classification Vocabulary

| Class | Meaning |
| --- | --- |
| STABLE | Exact scope has tests, evidence, and closeout supporting stable local use |
| PARTIAL | Useful and partly evidenced, but missing broader validation or gate review |
| EXPERIMENTAL | Research, prototype, or skeleton; not runtime authority |
| BLOCKED_PLATFORM | Blocked or pending because platform assumptions are not verified |
| LEGACY_PENDING | Existing path needs review, deprecation, or boundary assignment |

Some files may also carry operational aliases such as `PROVIDER_BLOCKED`,
`PLATFORM_PENDING`, or `DIRECT_PROVIDER_PENDING`; these aliases do not upgrade
the maturity class.

## Current Matrix

| Module or path | Current class | Known status | Notes |
| --- | --- | --- | --- |
| Product Spine verifier | PARTIAL | CORE_ASSET / needs tests reviewed | Strong evidence asset, but current repo-level readiness is not claimed |
| `aios/userland/product_spine/verify_run.py` | PARTIAL | CORE_ASSET | Verifies local run packets; does not prove runtime Product Spine readiness |
| LLM Gateway | PARTIAL | PROVIDER_BLOCKED | Auth, policy, route, audit exist; external provider execution remains blocked |
| `aios/gateway/*` | PARTIAL | PROVIDER_BLOCKED | Provider calls require explicit Provider Boundary Gate |
| `aios/agent_system/task_queue.py` | PARTIAL | DURABLE_QUEUE_CANDIDATE | Durable queue mechanics look valuable; needs exact-scope validation |
| `aios/core/event_bus.py` | PARTIAL | EVENT_BUS_CANDIDATE | Useful core pattern; persistence and runtime scope need review |
| `aios/core/engine.py` | PARTIAL | EVENT_SCHEMA_CANDIDATE | Local JSONL event schema; writes runtime data |
| `examples/quickstart_minimal.py` | PARTIAL | RUNNABLE_DEMO | Demonstrates self-healing evidence loop; demo is not runtime readiness |
| `examples/demo_app.py` | PARTIAL | LEARNING_ONLY_DEMO | External APIs disabled by default; judgment path blocked |
| `self_improving_loop/` | EXPERIMENTAL | PENDING | Skeleton for threshold and rollback; not stable self-evolution |
| `aios/core/reactor.py` | BLOCKED_PLATFORM | PLATFORM_PENDING | Contains platform-specific assumptions; not Mac-ready by default |
| `aios/core/safe_click.py` | BLOCKED_PLATFORM | PLATFORM_PENDING | Windows-oriented UI automation assumptions; requires platform review |
| `rpa_vision/` | BLOCKED_PLATFORM | PLATFORM_PENDING | Safe Click validation lane needs platform-specific evidence |
| `aios/agent_system/llm_caller.py` | LEGACY_PENDING | DIRECT_PROVIDER_PENDING | Direct provider path must route through Gateway or be fenced as legacy fallback |
| `aios/core/model_router.py` | LEGACY_PENDING | PLACEHOLDER_PROVIDER_PATH | Contains placeholder Claude response behavior; needs review before claims |
| `taiji-sandbox/` and root Next app | PARTIAL | PRODUCT_SHELL_CANDIDATE | Sandbox/product shell exists; deployment readiness requires separate gates |
| `xuan_shu/` | PARTIAL | RENDERER_ONLY_RESEARCH | Learning/observe-only symbolic layer; no command authority |

## Known Risk Examples

```text
self_improving_loop: EXPERIMENTAL / PENDING
reactor.py: PLATFORM_PENDING
safe_click.py: PLATFORM_PENDING
llm_caller.py: DIRECT_PROVIDER_PENDING
Gateway: PARTIAL / PROVIDER_BLOCKED
Product Spine verifier: CORE_ASSET / needs tests reviewed
```

## Production-Ready Rule

A module may not be called production-ready unless it has:

```text
declared scope
tests or verifier output
runtime platform identified
failure modes recorded
security and secret boundary checked
provider boundary checked when relevant
event flow or equivalent audit record
closeout
git status, branch, commit, and staged state captured for repo claims
```

## Forbidden Claims

```text
prototype -> stable
experimental -> production-ready
platform-pending -> Mac-ready
provider-blocked -> API-ready
demo-runnable -> runtime-ready
direct caller exists -> provider-ready
tests exist -> repo PASS
scope PASS -> repo PASS
```

## Next Review Targets

Suggested exact-scope review order:

```text
1. Product Spine verifier test review
2. Gateway provider boundary review
3. Direct LLM caller boundary decision
4. Runtime platform matrix for Reactor and Safe Click
5. Product shell canonical path decision
```

## Non-Claims

This matrix does not claim:

```text
production readiness
runtime readiness
provider readiness
external API readiness
repo-level PASS
deployment readiness
SpaceX readiness
trade/order readiness
judgment readiness
```

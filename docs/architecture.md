# TaijiOS Architecture 系统架构

## Overview 概览

TaijiOS is a layered AI operating system. Each layer has a clear responsibility and communicates through the EventBus.

太极OS 是分层的 AI 操作系统。每层职责清晰，通过事件总线通信。

## Layer Diagram 分层图

```
Layer 5: GitHub Learning        外部学习层
         discover → analyze → digest → gate → solidify
              │                                  │
              │         learns from               │ writes to
              ▼                                  ▼
Layer 4: Self-Improving Loop    自进化层
         feedback_loop ←→ evolution ←→ policy_learner
              │                │              │
              │ scores         │ evolves      │ rollback
              ▼                ▼              ▼
Layer 3: Agent System           智能体层
         task_queue → task_executor → lifecycle_engine
              │              │              │
              │ enqueue      │ execute      │ experience
              ▼              ▼              ▼
Layer 2: LLM Gateway            网关层
         auth → policy → router → providers → audit
              │                        │
              │ authenticate           │ failover
              ▼                        ▼
Layer 1: Core Engine              核心层
         EventBus ←→ Scheduler ←→ Reactor
              │           │           │
              │ events    │ schedule  │ react
              ▼           ▼           ▼
         Memory    Registry    CircuitBreaker
```

## Core Engine (Layer 1) 核心层

The foundation. Everything is an event.

| Component | File | Role |
| --------- | ---- | ---- |
| EventBus | `aios/core/event_bus.py` | Central nervous system. All components publish/subscribe events |
| Scheduler | `aios/core/scheduler.py` | Decides what runs when. Priority-based with resource awareness |
| Reactor | `aios/core/reactor.py` | Auto-responds to events using playbooks |
| Memory | `aios/core/memory.py` | Layered memory: working, episodic, semantic |
| Registry | `aios/core/registry.py` | Plugin/component discovery and registration |
| CircuitBreaker | `aios/core/circuit_breaker.py` | Prevents cascade failures. States: closed → open → half-open |
| Budget | `aios/core/budget.py` | Token and resource budget control |
| ModelRouter | `aios/core/model_router.py` | Routes LLM calls to optimal provider based on task complexity |

## LLM Gateway (Layer 2) 网关层

Unified control plane for all LLM calls. Every request goes through auth → policy → routing → provider → audit.

| Component | File | Role |
| --------- | ---- | ---- |
| Auth | `aios/gateway/auth.py` | API key validation, RBAC (viewer/operator/admin) |
| Policy | `aios/gateway/policy.py` | Rate limiting, budget enforcement |
| Router | `aios/gateway/router.py` | Provider selection with health-aware routing |
| Providers | `aios/gateway/providers.py` | Ollama, OpenAI-compatible, with failover loop |
| Audit | `aios/gateway/audit.py` | Every request logged: caller, model, tokens, latency, status |
| Errors | `aios/gateway/errors.py` | Structured error hierarchy with reason codes (403/429/504) |
| Streaming | `aios/gateway/streaming.py` | SSE streaming support |

Key design: provider failover. If provider A times out, the gateway automatically tries provider B, marks A as degraded, and logs the failover in audit.

## Agent System (Layer 3) 智能体层

Task execution with durable state and experience harvesting.

| Component | File | Role |
| --------- | ---- | ---- |
| TaskQueue | `aios/agent_system/task_queue.py` | Durable queue with atomic transitions: queued → running → succeeded/failed |
| TaskExecutor | `aios/agent_system/task_executor.py` | Executes tasks with retry and error handling |
| Lifecycle | `aios/agent_system/agent_lifecycle_engine.py` | Agent state machine: init → running → paused → stopped |
| Experience | `aios/agent_system/experience_learner_v4.py` | Harvests execution results into reusable experience with idempotent keys and grayscale rollout |

Key design: every task execution produces a run trace. Failed tasks generate experience records that improve future runs.

## Self-Improving Loop (Layer 4) 自进化层

Safe self-modification with evidence and rollback.

| Component | File | Role |
| --------- | ---- | ---- |
| FeedbackLoop | `aios/core/feedback_loop.py` | Collects execution outcomes, computes improvement signals |
| Evolution | `aios/core/evolution.py` | Scores system health, tracks improvement over time |
| PolicyLearner | `aios/core/policy_learner.py` | Learns scheduling/routing policies from experience |
| Rollback | `self_improving_loop/` | Safe rollback if a self-modification degrades performance |

Key design: every self-modification is gated by a threshold. If the evolution score drops, the system rolls back automatically.

## GitHub Learning (Layer 5) 外部学习层

Absorbs knowledge from the open-source ecosystem.

| Step | File | Role |
| ---- | ---- | ---- |
| Discover | `github_learning/discoverer.py` | GitHub Search API with rotating daily topics |
| Analyze | `github_learning/analyzer.py` | LLM answers 4 questions: root problem, pitfalls, mechanisms, gate plan |
| Digest | `github_learning/digester.py` | Extracts concrete mechanisms with idempotent keys |
| Gate | `github_learning/gate.py` | Human review CLI: list, review, approve, reject |
| Solidify | `github_learning/solidifier.py` | Approved mechanisms become EchoCore experiences or skill scaffolds |

Key design: the gate is always manual. Auto-discovery feeds candidates, humans decide what enters TaijiOS. This prevents the system from "becoming someone else" — it absorbs external knowledge but maintains its own identity.

## Data Flow 数据流

```
External GitHub repos
       │
       ▼ discover
  discovered_repos.jsonl
       │
       ▼ analyze (LLM)
  analyses.jsonl
       │
       ▼ digest
  pending_review/*.json ──→ Human approves/rejects
       │                         │
       ▼ solidify                ▼
  EchoCore experience      gate_decisions.jsonl
       │
       ▼ retrieve (next job)
  Injected into planner system prompt
       │
       ▼ execute
  run_trace.json + webhook delivery
       │
       ▼ feedback
  Evolution score update
```

## Key Patterns 关键模式

1. **Idempotent keys** — All experience records use content-hash keys to prevent duplicates
2. **Grayscale rollout** — New experiences start at 10% injection rate, increase with success
3. **Structured reason codes** — Every failure has a machine-parseable reason code (e.g., `gateway.provider.timeout`)
4. **Evidence-first** — Every decision produces a JSON evidence file that can be audited
5. **Graceful degradation** — Gateway unavailable? Fall back to direct LLM call. EchoCore down? Skip experience, don't block the job

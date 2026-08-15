# TaijiOS Architecture 系统架构

## Overview 概览

TaijiOS is a layered AI operating system. Each layer has a clear responsibility and communicates through the event engine (`aios/core/engine.py`, JSONL).

太极OS 是分层的 AI 操作系统。每层职责清晰，通过事件引擎(`aios/core/engine.py`,JSONL)通信。

## Layer Diagram 分层图

```
Layer 5: External Learning      外部学习候选层
         collect → analyze → digest → gate → apply
              │                                  │
              │         learns from               │ writes to
              ▼                                  ▼
Layer 4: Reliability Learning   学习/回滚层
         (feedback_loop/evolution/policy_learner 已于 2026-08 P0 死代码清理移除;
          保留 self_improving_loop/ 回滚骨架与人工 gate 原则)
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
         engine.py (五层事件 + JSONL) ← executor.py (幂等执行)
         (event_bus/scheduler/reactor/registry/circuit_breaker 已于 2026-08 P0 清理移除)
```

## Core Engine (Layer 1) 核心层

The foundation. Everything is an event.

| Component | File | Role |
| --------- | ---- | ---- |
| Engine | `aios/core/engine.py` | Five-layer event engine, emits JSONL events |
| Executor | `aios/core/executor.py` | Idempotent execution guard |
| Memory | `aios/core/memory.py` | Layered memory: working, episodic, semantic |
| ModelRouter | `aios/core/model_router.py` | Routes LLM calls to optimal provider based on task complexity |
| Removed 2026-08 | `event_bus.py` / `scheduler*.py` / `reactor*.py` / `registry.py` / `circuit_breaker.py` / `budget.py` / `model_router_v2.py` | P0 死代码清理:全仓库零 import 引用,见 git 历史 |

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
| MemoryRetrieval | `aios/agent_system/memory_retrieval.py` | Episodic memory hints: Jaccard keyword-overlap retrieval + feedback log; deterministic baseline, NOT vector search |
| Removed 2026-08 | `experience_learner_v4.py` / `meta_agent.py` / `evolution*.py` / `AgentSystem` facade / `core/agent_manager.py` | P0 死代码清理 + A2 门面移除(unified_router_v1.py 从未存在于 git 历史) |

Key design: every task execution produces a run trace. Failed tasks generate experience records that improve future runs.

## Reliability Learning (Layer 4) 学习/回滚层

Learning and rollback proposals with evidence and threshold gates.

| Component | File | Role |
| --------- | ---- | ---- |
| Removed 2026-08 | `feedback_loop.py` / `evolution.py` / `policy_learner.py` | P0 死代码清理:全仓库零 import 引用,见 git 历史 |
| Rollback | `self_improving_loop/` | Safe rollback if a self-modification degrades performance |

Key design: learning output is evidence first. A proposal must pass explicit thresholds and tests before it can affect runtime behavior; otherwise it remains a review candidate.

## External Learning (Layer 5) 外部学习候选层

Converts local event history and external research into review candidates. The `aios/learning/` analytics package was removed in the 2026-08 P0 dead-code cleanup (zero import references); local events are emitted as JSONL by `aios/core/engine.py`. The repo does not ship a top-level external GitHub mining package.

| Step | File | Role |
| ---- | ---- | ---- |
| Removed 2026-08 | `aios/learning/` (analyze / report / baseline / extract) | P0 死代码清理:全仓库零 import 引用,见 git 历史 |
| Gate | planned | External GitHub mining must feed human-review candidates before any runtime change |

Key design: the gate is always manual. External discovery may feed candidates, but humans decide what enters TaijiOS. This prevents the system from treating third-party patterns as verified local behavior.

## Data Flow 数据流

```
Local event logs / external research
       │
       ▼ analyze
  metrics + top issues + suggestions
       │
       ▼ report / baseline
  daily_report.md + metrics_history.jsonl ──→ Human approves/rejects candidates
       │                         │
       ▼ apply after gate         ▼
  runtime config / tests    gate_decisions.jsonl
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

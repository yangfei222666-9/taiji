# Changelog

All notable changes to TaijiOS will be documented in this file.

## [0.1.0] - 2026-04-09

Initial open-source release.

### Core
- Event-driven architecture: EventBus + Scheduler + Reactor
- Memory system with structured evidence chain
- Circuit Breaker for fault isolation

### LLM Gateway
- Unified multi-provider gateway with auth, rate limiting, failover
- Streaming support and audit logging
- 12/12 extreme scenario stress tests passed

### Agent System
- Task queue with atomic state transitions
- Agent lifecycle management and experience harvesting
- MetaAgent: auto-detect gaps, design agents, sandbox test, register
- Self-evolution agent with safe rollback

### Safe Click
- Four-gate controlled click executor
- Window binding + risk zone prohibition + target whitelist + OCR confidence
- Audit log for every click decision

### Self-Improving Loop
- Feedback loop + evolution scoring + policy learning
- Safe rollback with threshold gates

### GitHub Learning Pipeline
- Discover + Analyze + Digest + Human Gate + Solidify
- Learn from open-source projects with human approval

### Match Analysis
- Multi-source odds cross-validation framework

### Skill Auto-Creation
- Pattern detection from runtime logs
- Skill drafting with 3-layer validation

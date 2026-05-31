# Direct LLM Caller Boundary

## Verdict

```text
verdict=direct_llm_caller_boundary_draft
scope=direct_llm_caller_review_boundary_v0_1
mode=docs_only_direct_provider_boundary
direct_provider_calls=BLOCKED
llm_caller_py_status=PENDING_REVIEW
gateway_bypass_allowed=false
secret_read=false
runtime_changed=false
stage_commit_push=false
repo_pass_claimed=false
```

## Purpose

The direct LLM caller path is pending review. In the current repository, direct
provider call code exists outside the LLM Gateway boundary. That path must not
be treated as approved runtime authority.

Primary file under review:

```text
aios/agent_system/llm_caller.py
```

## Required Decision

The direct caller path must either:

```text
1. be routed through Gateway
```

or:

```text
2. be marked legacy/direct fallback with strict boundaries
```

Until one of those decisions is reviewed and evidenced, direct provider calls
remain BLOCKED.

## Gateway Boundary

Direct calls cannot bypass:

```text
auth
policy
budget
audit
provider boundary
Evidence Registry
Product Spine closeout
```

If the Gateway exists to centralize provider access, direct SDK usage must be
exceptional, explicitly scoped, and fully audited.

## Legacy Fallback Requirements

If direct calling remains as a legacy/direct fallback, it must preserve:

```text
explicit opt-in
provider boundary gate
cost/token accounting
timeout limits
failure mode recording
fallback reason code
audit event
output artifact
no secret values in logs
closeout with not_claimed fields
```

## Blocked By Default

Blocked by default:

```text
calling DeepSeek, Anthropic, OpenAI-compatible, relay, or Doubao providers
reading .env values for provider setup
using direct output as PASS
using direct output as policy decision
using direct output as judgment, promotion, paper-buy, trade, or public claim
silently falling back from Gateway to direct SDK
```

## Review Questions

Before enabling any direct caller path:

```text
Which scopes may use it?
Which environment variables are existence-checked only?
Where is the audit event written?
Where is the output artifact saved?
What is the cost ceiling?
What is the timeout?
What happens if Gateway and direct caller disagree?
What cannot be claimed from a direct response?
```

## Non-Claims

This document does not claim:

```text
direct caller ready
provider configured
Gateway bypass approved
API smoke test passed
runtime readiness
production readiness
repo-level PASS
```

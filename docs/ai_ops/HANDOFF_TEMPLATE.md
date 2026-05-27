# AI Handoff Templates

## Codex Planning Prompt

```text
scope=<exact task scope>
mode=planning_only / verify_only / edit_docs_only / implementation_preflight
repo_root=<absolute path>
will_not=<forbidden actions: secrets, external APIs, email, broker/live trade, automation, stage/commit/push/PR/merge, runtime promotion>

task:
Create the plan, architecture, boundaries, files to inspect, files to change, validation commands, expected verdict, and stop conditions.

required_output:
- scope
- assumptions
- files/artifacts
- validation commands
- expected PASS/PARTIAL/PENDING/BLOCKED conditions
- what cannot be claimed
```

## CC + DeepSeek Implementation Prompt

```text
scope=<narrow implementation scope>
mode=scoped_implementation
repo_root=<absolute path>
will_not=<forbidden actions and out-of-scope files>

task:
Implement only the requested scope. Return changed files, diff summary, tests run, failures, and remaining gaps.

requirements:
- no secret values
- no external API calls unless explicitly authorized
- no broker/live trade
- no email sending
- no git stage/commit/push/PR/merge
- no repo-level PASS claim

expected_output:
- changed files
- tests run
- validation output
- known risks
- handoff notes for TaijiOS Audit
```

## Gemini Frontend Design Prompt

```text
scope=<frontend visual direction scope>
mode=visual_direction_only / frontend_code_candidate
repo_root=<absolute path if code is involved>
will_not=<no production readiness claim, no secret handling, no deployment, no external API calls>

task:
Explore visual direction, layout, interaction feel, typography, spacing, and UI alternatives.

requirements:
- mark visual_direction as DEFAULT_ACCEPT only after human approval
- mark frontend_code as VERIFY_REQUIRED
- do not claim production readiness
- do not treat screenshots as build/lint/runtime proof

expected_output:
- visual direction notes
- UI risks
- review checklist
- required build/lint/responsive/accessibility/manual review gates
```

## Audit Closeout Prompt

```text
scope=<audited scope>
mode=audit_closeout
repo_root=<absolute path>
will_not=<no secret values, no external effects, no repo writes unless explicitly authorized>

evidence:
- files created or changed
- command output
- git status, branch, commit if repo-level claims are requested
- test/verifier output
- event_flow or equivalent audit record

expected_verdict:
- PASS only with evidence
- PARTIAL for scoped implementation without full validation
- PENDING for unverified work
- BLOCKED for missing gates, secrets, external APIs, broker/live trade, email sending, non-git repo, or missing validation

required_closeout:
- verdict
- blocked_stage if applicable
- failure_cause if applicable
- evidence_path
- minimum_fix
- next_allowed_action
```

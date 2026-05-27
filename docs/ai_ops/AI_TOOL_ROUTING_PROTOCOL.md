# AI Tool Routing Protocol

## Purpose

Define how TaijiOS routes planning, implementation, frontend direction, human judgment, and audit authority across AI tools without treating any model output as truth.

## Operating Rule

AI output is candidate work. Evidence decides status. TaijiOS Audit assigns `PASS`, `PARTIAL`, `PENDING`, or `BLOCKED` only from verifiable artifacts, tests, diffs, command output, and declared boundaries.

## Routing Matrix

| Actor | Primary role | Allowed outputs | Not allowed |
| --- | --- | --- | --- |
| Codex | Global planning, architecture, task decomposition, validation commands | Scope packets, implementation plans, repo-aware validation commands, audit-ready handoff prompts | Repo-level PASS without evidence; secret handling; production claims from plans |
| CC + DeepSeek | Scoped implementation, tests, local fixes, repetitive coding work | Small diffs, tests, local repair candidates, mechanical coding tasks | Untested trust claims; bypassing diff review; runtime authority promotion |
| Gemini | Frontend aesthetics, visual direction, UI exploration | Visual direction, style references, layout alternatives, taste candidates | Production readiness claims; unreviewed frontend code approval |
| Human owner | Final product judgment and taste approval | Final taste decision, product judgment, go/no-go authority where human judgment is required | Secret exposure through chats or docs; implicit approval for forbidden actions |
| TaijiOS Audit | Evidence gate and `PASS` / `PARTIAL` / `BLOCKED` classification | Verdicts based on files, tests, git state, event flow, verifier output, and explicit boundary checks | Treating provider output, screenshots, or visual approval as truth by itself |

## Default Routing Flow

1. Codex defines scope, boundaries, expected artifacts, and validation commands.
2. CC + DeepSeek may implement only the scoped task and must return diff, tests, and known gaps.
3. Gemini may explore frontend visual direction, but visual preference does not validate code.
4. Human owner approves final taste, product judgment, and any subjective product call.
5. TaijiOS Audit reviews evidence and assigns `PASS`, `PARTIAL`, `PENDING`, or `BLOCKED`.

## Stop Conditions

- Secret values appear in prompts, docs, logs, or model output.
- A tool tries to call external APIs outside the approved scope.
- A tool tries to send email, broker/live trade, stage, commit, push, PR, merge, release, publish, or create automation without explicit approval.
- A model output is being treated as truth without tests, verifier output, event flow, or human review where required.
- Frontend visual approval is being treated as production readiness.

## Non-Claims

This protocol does not grant runtime authority, repo-level readiness, production readiness, trade authority, email authority, provider access, or secret access.

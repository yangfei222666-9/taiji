# Codex Reliability Gap Map #01

A Scoped Review of Public Coding-Agent Failure Reports

## Research Question

What recurring reliability risks can be observed in a dated, deterministic sample of public `openai/codex` issue reports, and how can those reported symptoms be mapped to evidence-gate design patterns without overstating them as confirmed product defects?

## Scope and Sampling Method

- `snapshot_date`: `2026-06-24`
- `sample_size`: `30` public GitHub issues
- `sample_type`: `deterministic_non_random_snapshot`
- `source_repo`: `openai/codex`
- `sampling_rule`: Take the first 30 open, non-PR GitHub issues with created_at <= 2026-06-24T23:59:59Z after sorting by created_at descending.
- `report_type_counts`: bug_report=27, feature_request=3

The sample was not randomly drawn and should not be used to infer product-wide prevalence. GitHub labels are not mutually exclusive; one issue can count toward multiple label buckets, so label totals are descriptive metadata rather than incidence rates.

## Sources

- https://openai.com/index/introducing-codex/
- https://github.com/openai/codex/issues
- https://arxiv.org/abs/2603.20847
- https://arxiv.org/abs/2605.18583
- https://arxiv.org/abs/2606.22721

## What This Study Cannot Establish

This is a scoped review of public user reports, not a prevalence study, security audit, or assessment of current Codex product quality. An open issue is treated as a reported symptom, not a confirmed defect.

- prevalence across all Codex users
- maintainer-confirmed product defects
- root causes
- whether reports remain valid after later releases
- security impact
- current Codex product quality

## Five Failure Modes

| Failure mode | Records | Evidence gate | Why it matters |
|---|---:|---|---|
| Completion evidence integrity | 10 | Closeout Evidence Gate | Completion claims need inspectable evidence rather than partial, stale, or UI-only success signals. |
| Session and state continuity | 6 | State Resume Receipt | Long-running tasks need receipts that preserve resumable state, connection assumptions, and stale-context boundaries. |
| Authorization and scope control | 4 | Exact-Scope Authorization Gate | Agent actions need scoped permission records before touching files, config, tools, credentials, or persistent settings. |
| Tool and sandbox execution integrity | 6 | Tool-Call Execution Receipt | Command, tool-call, sandbox, ACL, and cross-platform execution results need explicit receipts. |
| Cost and runaway-loop visibility | 4 | Run Budget / Stop-Condition Gate | Users need visible budgets, loop stop conditions, and cost or performance degradation signals. |

## Thirty-Issue Evidence Table

| Issue | Type | Labels | Reported symptom | Failure mode | Evidence gate |
|---|---|---|---|---|---|
| [#29882](https://github.com/openai/codex/issues/29882) | bug_report | bug, windows-os, app, performance | Windows Codex Desktop may trigger full system freeze after Modern Standby resume; prior LiveKernelEvent 193 dxgkrnl watchdog | session_state_continuity | State Resume Receipt |
| [#29881](https://github.com/openai/codex/issues/29881) | bug_report | bug, windows-os, sandbox, CLI, app | [Windows] Switching App Agent Environment WSL → Native initializes the sandbox and fixes both App and CLI | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |
| [#29880](https://github.com/openai/codex/issues/29880) | bug_report | bug, app | Codex app image thumbnails fail to render after feedback upload | completion_evidence_integrity | Closeout Evidence Gate |
| [#29879](https://github.com/openai/codex/issues/29879) | bug_report | bug, model-behavior, app | Model not respecting agents instructions | authorization_scope_control | Exact-Scope Authorization Gate |
| [#29878](https://github.com/openai/codex/issues/29878) | feature_request | enhancement, CLI, safety-check, skills | open source codex-security plugin | authorization_scope_control | Exact-Scope Authorization Gate |
| [#29876](https://github.com/openai/codex/issues/29876) | bug_report | bug, extension, app, performance | Excessive disk writes / SSD wear concern on macOS Codex app and JetBrains ACP | cost_runaway_loop_visibility | Run Budget / Stop-Condition Gate |
| [#29873](https://github.com/openai/codex/issues/29873) | bug_report | bug, app | Office files open from output links but show unsupported preview from workspace file picker | completion_evidence_integrity | Closeout Evidence Gate |
| [#29872](https://github.com/openai/codex/issues/29872) | bug_report | bug, CLI, app-server | "app-server/src/lib.rs" has unused mutable "loader_overrides" | completion_evidence_integrity | Closeout Evidence Gate |
| [#29871](https://github.com/openai/codex/issues/29871) | bug_report | bug, windows-os, app, safety-check, skills | [Codex Security] Workspace fails on Japanese Windows when Git commit subject contains non-ASCII characters | authorization_scope_control | Exact-Scope Authorization Gate |
| [#29868](https://github.com/openai/codex/issues/29868) | bug_report | bug, app, session, app-server | Codex Desktop exposes stale ghost conversations that cannot be resumed or archived | session_state_continuity | State Resume Receipt |
| [#29867](https://github.com/openai/codex/issues/29867) | bug_report | bug, windows-os, sandbox, app | Windows sandbox can leave workspace owned by CodexSandboxOnline, then setup refresh fails with SetNamedSecurityInfoW 5 | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |
| [#29866](https://github.com/openai/codex/issues/29866) | bug_report | bug, windows-os, extension, sandbox, connectivity, session, remote | Codex IDE chat loses SSH/network access after idle/resume in same conversation | session_state_continuity | State Resume Receipt |
| [#29864](https://github.com/openai/codex/issues/29864) | bug_report | bug, app, session | Codex Desktop resume can fail when shell snapshot tmp file disappears during validation | session_state_continuity | State Resume Receipt |
| [#29860](https://github.com/openai/codex/issues/29860) | bug_report | bug, code-review, app | Review comments are not cleared after being addressed | completion_evidence_integrity | Closeout Evidence Gate |
| [#29859](https://github.com/openai/codex/issues/29859) | feature_request | enhancement, exec, CLI, skills, session | TypeScript SDK: Expand feature coverage — fork, session management, messages, metadata | session_state_continuity | State Resume Receipt |
| [#29858](https://github.com/openai/codex/issues/29858) | bug_report | bug, windows-os, app, performance | Windows: Opening Codex tab in non-Git workspace causes continuous git.exe spawning and high Defender CPU | cost_runaway_loop_visibility | Run Budget / Stop-Condition Gate |
| [#29857](https://github.com/openai/codex/issues/29857) | bug_report | bug, mcp, exec, CLI, config | codex exec silently auto-cancels MCP tool calls regardless of default_tools_approval_mode | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |
| [#29855](https://github.com/openai/codex/issues/29855) | bug_report | bug, windows-os, app | Spell checker incorrectly flags common English words in Codex Desktop 26.616.81150 (Windows 11) | completion_evidence_integrity | Closeout Evidence Gate |
| [#29854](https://github.com/openai/codex/issues/29854) | bug_report | bug, windows-os, app, connectivity, app-server, performance | Codex Windows app-server saturates upload bandwidth and causes packet loss | session_state_continuity | State Resume Receipt |
| [#29849](https://github.com/openai/codex/issues/29849) | bug_report | bug, app | PR status panel shows GitHub CLI unavailable in non-GitHub workspace | completion_evidence_integrity | Closeout Evidence Gate |
| [#29848](https://github.com/openai/codex/issues/29848) | bug_report | bug, windows-os, app | BUG Codex Windows  404 Not Found Model not found gpt-5.5 | completion_evidence_integrity | Closeout Evidence Gate |
| [#29847](https://github.com/openai/codex/issues/29847) | bug_report | bug, windows-os, app | codex pc app bug | completion_evidence_integrity | Closeout Evidence Gate |
| [#29846](https://github.com/openai/codex/issues/29846) | bug_report | bug, CLI, skills, subagent, config | skills.config enabled=false cannot be overridden by project or custom subagent config | authorization_scope_control | Exact-Scope Authorization Gate |
| [#29843](https://github.com/openai/codex/issues/29843) | bug_report | bug, model-behavior, TUI, CLI | Codex CLI scroll view jump on type and queued messages steering too hard | completion_evidence_integrity | Closeout Evidence Gate |
| [#29840](https://github.com/openai/codex/issues/29840) | bug_report | bug, tool-calls, app | Gmail connector _create_draft fails for threaded replies with reply_message_id: Subject does not match | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |
| [#29838](https://github.com/openai/codex/issues/29838) | feature_request | enhancement, rate-limits, CLI | Add /usage command to codex cli | cost_runaway_loop_visibility | Run Budget / Stop-Condition Gate |
| [#29836](https://github.com/openai/codex/issues/29836) | bug_report | bug, windows-os, sandbox, exec, CLI | Can't run WinGet executables in the sandbox when Windows Developer mode is enabled | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |
| [#29834](https://github.com/openai/codex/issues/29834) | bug_report | bug, app | codex crash bug when I enter information in a running task | completion_evidence_integrity | Closeout Evidence Gate |
| [#29832](https://github.com/openai/codex/issues/29832) | bug_report | bug, windows-os, app, performance | Windows Codex app updated to 26.616.10790.0, but continuous disk writes persist and appear worse. | cost_runaway_loop_visibility | Run Budget / Stop-Condition Gate |
| [#29830](https://github.com/openai/codex/issues/29830) | bug_report | bug, windows-os, sandbox, tool-calls, app | The Codex App always requires my approval, and I've granted it all permissions. | tool_sandbox_execution_integrity | Tool-Call Execution Receipt |

## Failure Mode To Evidence Gate Map

### Completion Evidence Integrity -> Closeout Evidence Gate

A completion claim should cite inspectable evidence: commands run, exit status, test output, changed files, unresolved blockers, and `cannot_claim`. UI-level success, stale status, or partial evidence should not be enough to mark work complete.

### Session And State Continuity -> State Resume Receipt

Long-running tasks need a resume packet that records current branch, HEAD, dirty state, pending user choices, active tool sessions, remote connections, and stale assumptions. A resumed session should explicitly prove continuity before acting.

### Authorization And Scope Control -> Exact-Scope Authorization Gate

Benign requests can still trigger out-of-scope work. The gate should bind each write, command, network call, file upload, provider call, branch operation, and submit action to a narrow user-approved scope.

### Tool And Sandbox Execution Integrity -> Tool-Call Execution Receipt

Tool and sandbox failures should leave typed evidence: command, cwd, exit code, stdout/stderr summary, sandbox permission state, platform, and retry outcome. Silent auto-cancel or UI-only reporting is insufficient.

### Cost And Runaway-Loop Visibility -> Run Budget / Stop-Condition Gate

Long-running agent work needs visible usage, loop counters, stop conditions, retry limits, and degradation state. A task should not keep spending tokens or repeatedly editing without an explicit budget and closeout.

## Existing False-Pass Gate Demonstration

The existing False-Pass Gate proof is aligned with the first failure mode: it blocks unsupported success language when passing evidence pointers or explicit `cannot_claim` boundaries are missing. This Gap Map extends that idea from one proof into a broader failure-mode taxonomy.

## Cross-Layer Risk: Review Habituation

Even when evidence is present, repeated AI-generated reviews may reduce active human scrutiny. Reviewer-facing gates should therefore surface evidence deltas, negative tests, scope changes, and `cannot_claim` boundaries rather than burying them in long summaries.

## Open Questions

- Which reported symptoms can be independently reproduced in a clean environment?
- Which reports remain current after later Codex releases?
- Which gates should be implemented as local validators, UI affordances, or reviewer checklist items?
- Which risks are best handled by product changes versus user workflow conventions?

## Reproduction Instructions

1. Query `https://api.github.com/repos/openai/codex/issues?state=open&per_page=100&sort=created&direction=desc`.
2. Exclude pull requests.
3. Keep issues with `created_at <= 2026-06-24T23:59:59Z`.
4. Take the first 30 records in descending creation order.
5. Store issue id, URL, status, labels, title, snapshot date, report type, mapped failure mode, mapped evidence gate, and `cannot_claim`.
6. Run `python3 scripts/check_codex_gap_map.py` to verify the JSON and Markdown stay aligned.

## Cannot Claim

- Cannot claim Codex is missing all mapped capabilities.
- Cannot claim the open issues are maintainer-confirmed defects.
- Cannot claim these reports are statistically representative.
- Cannot claim the failure modes remain present in later versions.
- Cannot claim the existing gates solve the reported issues in production.

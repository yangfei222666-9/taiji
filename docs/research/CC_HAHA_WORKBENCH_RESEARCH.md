# CC Haha Workbench Research

Date: 2026-05-27

Scope: research-only reference for TaijiOS AI agent desktop workbench design.

Repo root: `/Users/weiwei/Desktop/taiji`

## Verdicts

| Area | Verdict |
| --- | --- |
| Research note | PASS |
| Installation | BLOCKED |
| Secret access | BLOCKED |
| Runtime execution | BLOCKED |
| TaijiOS implementation | PENDING |
| Production readiness | PENDING |

## Hard Boundaries

- Do not install cc-haha.
- Do not download unsigned binaries.
- Do not run leaked-source code.
- Do not paste, read, copy, or summarize secret values.
- Do not configure API keys or auth tokens.
- Do not open the real TaijiOS repo inside cc-haha.
- Do not call external execution APIs.
- Do not enable Computer Use.
- Do not enable H5 remote access.
- Do not enable IM integration.
- Do not stage, commit, push, create PRs, or merge.
- Do not claim production readiness from this research note.

## Sources Reviewed

- NanmiCoder/cc-haha README: https://github.com/NanmiCoder/cc-haha/blob/main/README.en.md
- Raw README mirror used for text review: https://raw.githubusercontent.com/NanmiCoder/cc-haha/main/README.en.md
- Environment variable docs: https://github.com/NanmiCoder/cc-haha/blob/main/docs/en/guide/env-vars.md
- Computer Use docs: https://github.com/NanmiCoder/cc-haha/blob/main/docs/en/features/computer-use.md
- H5 remote access docs: https://github.com/NanmiCoder/cc-haha/blob/main/docs/desktop/06-h5-access.md
- IM integration docs: https://github.com/NanmiCoder/cc-haha/blob/main/docs/im/index.md

## Source Risk Notes

- The README describes cc-haha as based on fixes to leaked source. TaijiOS must treat it as a product-pattern reference only, not as an implementation dependency.
- The reviewed docs include API key, auth token, remote access token, IM adapter, and desktop-control surfaces. Those are design inputs for TaijiOS gate modeling, not permissions to configure or execute them.
- Provider output, UI screenshots, and model-generated responses are not truth. TaijiOS truth must remain evidence-first: event flow, artifacts, diffs, verifier output, and human owner judgment where required.

## Product Patterns Extracted

| cc-haha pattern | Observed product shape | Primary risk |
| --- | --- | --- |
| Multi-session workbench | Multiple concurrent Claude Code sessions/tabs across work contexts. | Session drift, mixed scope, unclear authority per session. |
| Project selector | User can select and switch project roots. | Wrong repository opened, non-git mirror treated as repo truth. |
| Branch/worktree isolation | Work can be organized around branches or separate task contexts. | Cross-scope dirty tree contamination, false repo-level PASS. |
| Right-side diff panel | UI exposes file changes next to the agent session. | Diff review mistaken for test/build/audit evidence. |
| Permission approval flow | Tool calls and sensitive actions require user approval paths. | Overbroad approval, unclear audit trail, approval reused outside scope. |
| Provider configuration | Environment variables and provider settings route models and API endpoints. | Secret exposure, tainted provider path, unverified model output. |
| Token usage view | UI shows cost or usage visibility. | Cost view mistaken for quality, correctness, or trust. |
| H5 remote access | Browser/mobile remote console can control or review sessions through pairing. | Remote token leakage, unauthorized repo exposure, network attack surface. |
| IM approval flow | Messaging integrations can approve or route remote tasks. | Chat approval replay, identity ambiguity, accidental external side effects. |
| Scheduled tasks | Repeated or timed agent work can be configured. | Silent automation, stale baseline, recurring unsafe action. |
| Computer Use boundary | Desktop control can inspect screen and perform actions. | Local UI control, credential exposure, irreversible desktop operations. |

## TaijiOS Concept Mapping

| Pattern | TaijiOS mapping | Required TaijiOS gate |
| --- | --- | --- |
| Multi-session workbench | EventFlow + Closeout per session. | Every session needs `scope`, `mode`, `repo_root`, `will_not`, event log, and closeout verdict. |
| Project selector | Scope Isolation. | Require `git rev-parse --show-toplevel` before repo truth; mirrors stay filesystem-only. |
| Branch/worktree isolation | Scope Isolation + Evidence Registry. | Record branch, commit, status, and dirty paths before claiming repo-level state. |
| Right-side diff panel | Artifact Diff. | Diff is evidence input only; PASS still requires validators and audit commands. |
| Permission approval flow | Provider Gate + Closeout. | Approval must be scoped, time-bound, action-specific, and recorded in event flow. |
| Provider configuration | Provider Gate. | Existence-only checks for secrets; provider identity and model route must be logged without secret values. |
| Token usage view | Evidence Registry. | Track usage as cost telemetry only; never as correctness or trust evidence. |
| H5 remote access | Remote Review Console. | Disabled by default; allow only local/sandbox review with explicit token lifecycle and no secret surfaces. |
| IM approval flow | Remote Review Console + EventFlow. | Disabled by default; require verified human identity, command scope, and non-replayable approval records. |
| Scheduled tasks | EventFlow + Closeout. | No recurring automation without explicit schedule, stop condition, owner, and artifact output contract. |
| Computer Use boundary | Provider Gate + Scope Isolation. | BLOCKED by default; require sandbox, screenshot redaction, no secret windows, and explicit manual approval. |

## Design Implications For TaijiOS

### Workbench Shell

- A TaijiOS desktop workbench should start from a project selector, but the selected path must be classified as `git_worktree`, `non_git_directory`, `artifact_pool`, or `unknown`.
- Every session should have a visible scope header: `scope`, `mode`, `repo_root`, `branch`, `commit`, `dirty_state`, `allowed_actions`, and `blocked_actions`.
- Session tabs should not share authority. A token, permission, or approval granted in one tab must not automatically authorize another tab.

### Evidence-First Diff Review

- A diff panel should be treated as `Artifact Diff`, not final proof.
- The UI should show three separate states: `changed`, `validated`, and `approved`.
- Runtime code changes, docs changes, generated artifacts, staged files, and untracked files should be grouped separately.

### Provider And Secret Gate

- Provider configuration belongs behind a `Provider Gate`, not inside the normal chat surface.
- Secret handling must be existence-only in docs and audit output: `exists=true/false`, source name/path, and migration method.
- Model output must be labeled candidate-only until confirmed by tests, verifiers, or human owner judgment.

### Remote Review Console

- H5 and IM features are useful as reference patterns for remote review, but TaijiOS should not enable them by default.
- A TaijiOS Remote Review Console should be read-only first: inspect event flow, diffs, summaries, and closeout reports.
- Any remote approval path must create an immutable approval record with user identity, scope, command, timestamp, and expiry.

### Automation Boundary

- Scheduled tasks must not exist as silent background workers.
- A recurring task needs a written contract: schedule, owner, allowed commands, blocked commands, output path, event flow path, failure policy, and stop condition.
- Missing event flow, missing summary, missing validation, non-git repo, secret boundary, broker/live trade path, email sending, and external side effects must produce `BLOCKED`.

### Computer Use Boundary

- Computer Use should be modeled as a high-risk actuator, not as a normal provider tool.
- Default verdict: `BLOCKED`.
- Minimum future sandbox requirements: no real secrets on screen, no production repo mutation, no browser session with sensitive accounts, visible manual approval, event flow, screenshot redaction policy, and immediate stop condition.

## Proposed TaijiOS Protocol Objects

### EventFlow

Records session start, selected project, branch/worktree facts, commands proposed, commands run, provider route, validation outputs, failures, and closeout verdict.

### Scope Isolation

Prevents a docs-only or research-only task from inheriting authority over runtime code, provider configuration, broker actions, email, external APIs, or recurring automation.

### Artifact Diff

Captures file-level changes and classifies them as docs, code, config, generated evidence, or unknown. Diff presence never equals PASS by itself.

### Provider Gate

Separates model/provider configuration from implementation. It records provider identity, route class, allowed use, blocked use, and secret existence without exposing secret values.

### Evidence Registry

Indexes artifacts such as `summary.json`, `event_flow.jsonl`, verifier output, git status, branch, commit, remotes, test logs, and closeout reports.

### Closeout

Reports `PASS`, `PARTIAL`, `PENDING`, or `BLOCKED` by scope. It must explicitly list what cannot be claimed.

### Remote Review Console

Optional future read-only console for reviewing EventFlow, Artifact Diff, and Closeout from another device or chat surface. Write actions remain blocked until separately authorized.

## Minimum Future Acceptance Criteria

- Real git worktree is verified with branch, commit, status, and remotes before repo-level claims.
- Each agent session has a scope contract and event flow.
- Right-side diff is backed by validation commands before PASS.
- Provider configuration never prints or stores secret values.
- Remote access and IM approval are disabled unless a separate security design exists.
- Computer Use remains blocked unless sandboxed and explicitly approved.
- Scheduled tasks remain blocked unless they include owner, stop condition, event flow, and closeout output.
- Human owner retains final product judgment and taste approval.

## What Cannot Be Claimed

- This note does not approve installing, running, or integrating cc-haha.
- This note does not certify cc-haha source, binaries, dependencies, or security posture.
- This note does not enable H5 remote access, IM integration, Computer Use, scheduled tasks, provider routing, or API usage.
- This note does not prove TaijiOS repo-level readiness.
- This note does not prove production readiness.
- This note does not make any model output truth.

## Next Allowed Action

Run exact-scope validation for this research note:

```bash
git status --short
test -f docs/research/CC_HAHA_WORKBENCH_RESEARCH.md
sed -n '1,260p' docs/research/CC_HAHA_WORKBENCH_RESEARCH.md
git diff -- docs/research
git diff --check -- docs/research
```

Do not stage this file unless the human owner explicitly authorizes exact-scope staging.

# New Computer Runbook - 2026-05-31

## Purpose: SpaceX Engineer Workstation

Prepare a clean engineering workstation for TaijiOS development, audit work, and SpaceX career-evidence planning without claiming SpaceX readiness, repo-level readiness, credential readiness, or model-truth authority.

This runbook is documentation-only. It does not authorize runtime changes, secret migration, external API execution, broker/live trade actions, email sending, automation creation, git writes, public release, or production cutover.

## Current Verdicts

| Gate | Verdict |
| --- | --- |
| Hardware arrival | PENDING |
| Hardware verification | PENDING |
| Machine security baseline | PENDING |
| Dev environment | PENDING |
| Repo migration | PENDING |
| Git truth | PENDING |
| Secret migration | BLOCKED_MANUAL_ONLY |
| External API execution | BLOCKED |
| Broker/live trade execution | BLOCKED |
| Email sending | BLOCKED |
| SpaceX readiness | PENDING |
| Repo-level PASS | FORBIDDEN until git status, branch, commit, and remotes are verified |

## Pre-Arrival Checklist

1. Keep hardware arrival as `PENDING` until the machine is physically received.
2. Confirm the intended source-of-truth repo path after clone.
3. Prepare a non-secret list of required developer tools.
4. Prepare a password-manager-only secret migration plan.
5. Keep external disks, backups, and old-machine artifacts in read-only inventory mode until hashes and paths are verified.
6. Keep SpaceX career materials as evidence planning only, not readiness claims.
7. Record expected first-week acceptance criteria before changing production or public-facing systems.

## Unboxing And Hardware Verification Checklist

1. Confirm box, serial number, accessories, and order match expected hardware.
2. Inspect for visible damage.
3. Confirm power adapter, cable, display, keyboard, trackpad, ports, Wi-Fi, Bluetooth, camera, microphone, and speakers work.
4. Record hardware verification status as `PENDING` until all checks are complete.
5. Do not migrate secrets or repo write authority before hardware is verified.

## First Boot Security Checklist

1. Complete macOS setup.
2. Apply all system updates.
3. Enable FileVault.
4. Set a strong local login password.
5. Enable password manager access without exposing secret values.
6. Configure screen lock and recovery options.
7. Review privacy permissions before installing development tools.
8. Do not paste credentials into docs, AI chats, terminals, tickets, or email.

## Development Environment Setup

1. Install Xcode Command Line Tools.
2. Install Homebrew.
3. Install Git and GitHub CLI.
4. Install supported Python and Node versions for the repo.
5. Install Docker only after the security baseline is complete.
6. Install editor tooling and extensions from a reviewed list.
7. Install project dependencies only after repo truth validation passes.
8. Keep external API probes blocked until a separate provider boundary check is approved.

## Directory Layout

Recommended new-machine layout:

```text
~/code/taiji/                  # source-of-truth repo clone candidate
~/code/taiji-worktrees/        # optional isolated worktrees
~/artifacts/taijios/           # non-secret generated artifacts
~/inbox/taijios/               # pending handoff packages before verification
~/career/spacex/               # SpaceX career-evidence planning workspace
```

Rules:

- Do not store secret values in repo, artifacts, inbox, docs, or AI chats.
- Keep external disk material read-only until inventory and hashes are verified.
- Do not treat iCloud, backup folders, or review mirrors as source-of-truth repo state without git validation.

## Git / GitHub Setup

1. Install Git.
2. Install `gh`.
3. Configure user name and email manually.
4. Create or import SSH authentication through an approved secure method.
5. Prefer generating a new SSH key on the new machine if old key hygiene is uncertain.
6. Re-authenticate GitHub manually; do not copy token values.
7. Do not stage, commit, push, create PRs, merge, release, tag, or publish until repo truth is verified and the exact gate is approved.

## Repo Truth Validation

Run only read-only validation after cloning or locating the repo:

```text
pwd
git status --short
git branch --show-current
git log -1 --oneline
git remote -v
git rev-parse --show-toplevel
```

Repo-level `PASS` is forbidden until all of the following are captured and reviewed:

1. Real git worktree path.
2. Branch.
3. Latest commit.
4. Remote URLs.
5. `git status --short`.
6. Dirty, staged, unstaged, and untracked state.
7. Scope-specific validation commands.

## Secret Migration Boundaries

Secret migration is `BLOCKED_MANUAL_ONLY`.

Rules:

- Never paste secret values into docs or AI chats.
- Do not read, print, copy, summarize, export, or transmit secret values during AI-assisted setup.
- Do not create or rotate credentials from this runbook.
- Use a password manager, provider console, OS keychain, or approved secret manager.
- Only migrate secrets after hardware verification, security baseline, repo truth validation, dependency setup, and local tests are complete.
- Existence checks may report only `exists=true/false` and source name/path, not values.

## AI Tool Routing Protocol Summary

| Actor | Role |
| --- | --- |
| Codex | Planning, architecture, task decomposition, validation commands |
| CC + DeepSeek | Scoped implementation and repetitive coding work |
| Gemini | Frontend aesthetics and visual direction |
| Human owner | Final product judgment and taste approval |
| TaijiOS Audit | `PASS` / `PARTIAL` / `BLOCKED` evidence gate |

Boundary:

- Provider output is not truth.
- Model output is candidate work until evidence validates it.
- Gemini visual direction can support taste decisions, but frontend code still requires build, lint, responsive review, accessibility smoke check, and manual review.
- No AI tool can assign repo-level `PASS`, bypass tests, expose secrets, send email, or call broker/live trade actions.

## SpaceX Career Workspace Setup

Create a conservative planning workspace:

```text
~/career/spacex/
```

Suggested non-secret files:

```text
target_roles.md
evidence_map.md
skill_gap_map.md
project_translation.md
weekly_closeout.md
```

Rules:

- Keep SpaceX career work as evidence planning, not employment readiness.
- Do not infer eligibility, visa status, clearance, degree status, or hiring readiness.
- Do not send outreach, email, applications, or messages automatically.
- Do not turn TaijiOS docs or screenshots into readiness claims without independent evidence.

## First Week Acceptance Criteria

The new machine first week is acceptable only if:

1. Hardware arrival and hardware verification are complete.
2. FileVault and baseline security are enabled.
3. Git repo is cloned or located in a real worktree.
4. Branch, commit, remotes, and `git status --short` are captured.
5. Dependencies install without unexplained errors.
6. Local tests or verifiers run and results are recorded.
7. Secret migration remains manual-only and value-free.
8. External API, email, broker/live trade, automation, release, PR, merge, and production gates remain blocked unless separately approved.
9. SpaceX career workspace exists as planning-only and does not claim readiness.

## Stop Conditions

Stop if any of the following occurs:

- Hardware cannot be verified.
- FileVault or baseline security cannot be enabled.
- The repo path is not a git worktree.
- `git status --short` has unexplained changes.
- Branch, commit, or remotes cannot be verified.
- A workflow requires secret values in docs, AI chats, terminal output, email, or logs.
- A setup path requires external API execution without approval.
- A broker/live trade, paper-buy, email send, production cutover, public release, or recurring automation action is requested.
- A model output is being treated as truth without evidence.
- SpaceX readiness is being claimed from plans, docs, screenshots, or AI output.

## What Cannot Be Claimed

- Hardware arrival is not complete until the machine is physically received.
- Hardware verification is not complete until device checks pass.
- Machine security baseline is not complete until FileVault and security settings are verified.
- Dev environment readiness is not proven by installing tools alone.
- Repo migration is not complete until the real worktree is validated.
- Git truth is not proven without status, branch, commit, and remotes.
- Secret migration is not authorized by this runbook.
- External API execution remains blocked.
- Broker/live trade execution remains blocked.
- Email sending remains blocked.
- SpaceX readiness remains `PENDING`.
- Repo-level `PASS` is forbidden until git status, branch, commit, remotes, and scope validation are verified.
- No model output is truth without evidence.

# Implementation Audit Protocol

## Purpose

Define TaijiOS audit verdict rules for AI-assisted implementation, documentation, frontend work, and repo validation.

## Verdict Rules

### PASS

Use `PASS` only with evidence.

Minimum evidence depends on scope:

- Filesystem scope: target files exist and required sections are readable.
- Code scope: diff is scoped, tests pass, and validation commands pass.
- Repo scope: `git status --short`, branch, commit, and validation commands are explicitly verified.
- Frontend code scope: build, lint, responsive review, accessibility smoke check, and manual UI review pass.

### PARTIAL

Use `PARTIAL` for scoped implementation without full validation.

Examples:

- Files exist but repo-level git truth is missing.
- Code changed and local tests pass, but broader validation is not run.
- Frontend visual direction is approved, but build/lint/manual review is not complete.
- A scoped verifier passes while unrelated dirty tree items remain.

### PENDING

Use `PENDING` for unverified work.

Examples:

- Planned but not executed work.
- Files expected but not inspected.
- Tests specified but not run.
- Human approval required but not provided.

### BLOCKED

Use `BLOCKED` for hard boundary or missing-gate conditions:

- Secrets requested, exposed, copied, printed, summarized, or needed for the next step.
- External API execution is required but not authorized.
- Broker/live trade action is requested or required.
- Email sending is requested or required.
- Current path is not a git repository for repo-level claims.
- Validation commands are missing or fail.
- Event flow or equivalent audit record is missing for a claim that requires it.
- A model tries to turn provider output into truth.
- Frontend visual approval is being treated as production readiness.

## Repo-Level PASS Requirements

No repo-level `PASS` without all of the following:

1. `git status --short` captured and explained.
2. Branch captured.
3. Latest commit captured.
4. Relevant validation commands captured.
5. Dirty/staged/untracked state explicitly reported.
6. Runtime/code/docs scope separated from unrelated dirty tree items.
7. Push, PR, merge, release, tag, and publish gates reported separately.

## Audit Closeout Fields

Every closeout should include:

- `verdict`
- `scope`
- `mode`
- `repo_root`
- `evidence_path`
- `validation_commands`
- `blocked_stage` when blocked
- `failure_cause` when blocked or failed
- `minimum_fix`
- `next_allowed_action`
- `what_cannot_be_claimed`

## Non-Claims

Audit does not authorize secrets, external APIs, email sending, broker/live trade, runtime promotion, repo writes, production readiness, or public claims unless those gates are separately approved and evidenced.

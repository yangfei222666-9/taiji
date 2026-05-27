# Model Trust Boundaries

## Hard Rules

- Provider output is not truth.
- No model can assign repo-level `PASS`.
- No model can bypass tests.
- No model can access or expose secrets.
- No model can send emails automatically.
- No model can call broker/live trade actions.
- No model can promote `learning_only` work into judgment, paper-buy, trade, runtime default, or public claim authority.

## Tool-Specific Boundaries

### Codex

- Codex plans require execution evidence.
- Codex may propose validation commands, but command output and artifacts decide status.
- Codex must keep git gates separate: status, staged state, branch, commit, push, PR, merge, release, and publish.
- Codex must not claim repo-level `PASS` unless git status, branch, commit, and validation commands are explicitly verified.

### CC + DeepSeek

- DeepSeek implementation requires tests and diff review.
- CC + DeepSeek output is a candidate implementation until local validation passes.
- Repetitive coding work still needs scoped diff review and test evidence.
- Provider/model confidence is not a substitute for tests.

### Gemini

- Gemini visual direction may be accepted by taste after human approval.
- Gemini frontend code requires build, lint, responsive review, accessibility smoke check, and manual review.
- Visual approval does not imply production readiness.
- Screenshot-level approval does not replace runtime, routing, data, auth, or deployment checks.

### Human Owner

- Human owner may approve taste and product judgment.
- Human approval does not authorize secret exposure, live broker actions, email sending, production cutover, or repo writes unless explicitly scoped.

### TaijiOS Audit

- TaijiOS Audit classifies outcomes from evidence only.
- Audit verdicts must separate filesystem scope from repo scope and local validation from external readiness.
- Audit must mark missing validation, missing event flow, non-git repo context, secret boundary, external API boundary, broker/live trade boundary, and email boundary as `BLOCKED` when applicable.

## Required Evidence

| Claim | Minimum evidence |
| --- | --- |
| Files exist | `find`, `ls`, or equivalent file command output |
| Code builds | Build command output |
| Tests pass | Test command output |
| Repo-level state | `git status --short`, branch, commit, and relevant validation commands |
| Frontend implementation ready for review | Build, lint, responsive review, accessibility smoke check, manual UI review |
| Production readiness | Separate deployment, runtime, auth, data, monitoring, rollback, and human approval evidence |

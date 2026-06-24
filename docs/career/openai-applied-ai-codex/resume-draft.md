# Yang Fei (Xiaojiu) - OpenAI Codex Applied AI Resume Draft

Johor Bahru, Malaysia | Email: [private email] | Phone: [private phone] | LinkedIn: [add LinkedIn] | GitHub: https://github.com/yangfei222666-9
AI Agent Reliability / Evals / Developer Tools Engineer

## Target Role

Applied AI Engineer, Codex Core Agent
Official role page: https://openai.com/careers/applied-ai-engineer-codex-core-agent-san-francisco/

This draft is local prep material. It should be converted into a private final application copy before submission.

## Summary

AI agent reliability engineer focused on evals, failure analysis, and evidence-gated workflows. I build reproducible checks that prevent unsupported "done" claims, preserve explicit uncertainty boundaries, and separate local validation, remote CI, provider output, and canonical truth.

My current public proof is narrow and inspectable: a False-Pass Gate, a zero-case validation fix, a provider-locked candidate-review bridge, and a recruiter-readable proof page merged to GitHub main with CI evidence. I am interested in Codex work that turns agent capability into dependable completion of real software-engineering tasks.

## Selected Engineering Work

### Agent Reliability False-Pass Gate | Python, Pytest, GitHub Actions | 2026

- Built a schema-level evidence gate that rejects AI-agent success claims when required passing-evidence pointers or explicit `cannot_claim` boundaries are missing.
- Identified and fixed a zero-case validation flaw where missing or empty fixtures could incorrectly produce `self_test=PASS cases=0`; added fail-closed regression coverage.
- Designed a provider-locked candidate-review bridge with sanitized stdin-only inputs, credential isolation, no repository reads, and explicitly non-canonical model output.
- Published the implementation, reviewer guide, limitations, and reproducible validation path to GitHub main with remote CI passing.

### Product Spine / Reliability Tooling | Python, TypeScript, CI/CD | 2026

- Built and maintained evidence-first workflow artifacts that distinguish local evidence, remote CI, provider output, and canonical truth before making completion claims.
- Added proof-index and reviewer-facing documentation so claims can be inspected by status, evidence command, limitation, and `cannot_claim` boundary.
- Used GitHub PR, CI, local regression tests, and closeout records as separate gates instead of treating a local pass as final truth.
- Practiced fail-closed review behavior: blocked or partial states are preserved instead of being rewritten into unsupported success language.

## Technical Skills

- Languages and tools: Python, TypeScript, Bash, Git, GitHub CLI, JSON, Markdown.
- Testing and validation: Pytest, CLI self-tests, regression fixtures, CI/CD, GitHub Actions, proof-index validation.
- AI-agent reliability: false-pass prevention, evidence gates, agent closeout review, provider-output boundaries, `cannot_claim` handling.
- Developer tooling: command-line validators, reviewer docs, reproducible local setup, Git evidence hygiene.

## Experience

### Independent AI Systems Engineer | March 2026 - Present

- Built public proof around AI-agent reliability, false-pass prevention, and evidence-gated task closeouts.
- Converted agent workflow failures into testable validation rules, proof documents, and reviewer-readable engineering artifacts.
- Maintained strict boundaries around credentials, provider output, local validation, remote CI, and human approval.

### Prior Experience

[Add verified prior company, role, dates, and measurable bullets before final submission. Do not invent experience.]

## Education

[Add verified school, degree, field, and dates before final submission.]

## Selected Links

- Agent Reliability proof: https://github.com/yangfei222666-9/taiji/blob/main/docs/portfolio/agent-reliability-proof.md
- Main repository: https://github.com/yangfei222666-9/taiji
- One-line technical case: Agent said done. Where is the evidence?

## Interview Stories

### 1. Zero-case false-pass bug

A validator designed to block false-pass behavior could itself pass with zero cases when fixtures were missing or empty. I changed the behavior to fail closed, added regression coverage, and documented the limitation so reviewers could inspect the evidence.

### 2. Local pass is not remote truth

The project keeps local validation, remote CI, provider output, and canonical truth as separate states. This prevents a common AI-agent failure mode where a local check becomes an unsupported completion claim.

### 3. Provider output remains advisory

The candidate-review bridge uses sanitized input and explicit provider/model boundaries, but model output is not treated as canonical. The final gate remains evidence, CI, and human approval.

## Final Submission Gaps

- Add private contact details in the final application copy only.
- Add verified education.
- Add verified prior work experience, if applicable.
- Confirm work authorization and relocation/sponsorship language for the specific application form.
- Convert to a clean PDF only after private details and final links are confirmed.

## Boundaries

This material should not claim deployed-system readiness, external customer adoption, third-party endorsement, fleet-scale sandboxing, production eval infrastructure, or self-updating agent authority.

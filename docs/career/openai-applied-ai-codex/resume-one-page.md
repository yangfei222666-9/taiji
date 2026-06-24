# Yang Fei (Xiaojiu)

Johor Bahru, Malaysia | Email: [private email] | LinkedIn: [add LinkedIn] | GitHub: https://github.com/yangfei222666-9
AI Agent Reliability / Evals / Developer Tools Engineer

## Summary

AI agent reliability engineer focused on evals, failure analysis, and evidence-gated workflows. I build reproducible checks that prevent unsupported "done" claims, preserve explicit uncertainty boundaries, and separate local validation, remote CI, provider output, and canonical truth. Recent public work includes a merged False-Pass Gate with fail-closed regression coverage and reviewer-readable proof.

## Selected Engineering Work

### Agent Reliability False-Pass Gate | Python, Pytest, GitHub Actions | 2026

- Built a schema-level evidence gate that rejects AI-agent success claims when required passing-evidence pointers or explicit `cannot_claim` boundaries are missing.
- Identified and fixed a zero-case validation flaw where missing or empty fixtures could incorrectly produce `self_test=PASS cases=0`; added fail-closed regression coverage.
- Designed a provider-locked candidate-review bridge with sanitized stdin-only inputs, credential isolation, no repository reads, and explicitly non-canonical model output.
- Published the implementation, reviewer guide, limitations, and reproducible validation path to GitHub main with remote CI passing.

### Product Spine / Reliability Tooling | Python, TypeScript, CI/CD | 2026

- Built and maintained evidence-first workflow artifacts that distinguish local evidence, remote CI, provider output, and canonical truth before making completion claims.
- Added proof-index and reviewer-facing documentation so project claims can be inspected by status, command, limitation, and `cannot_claim` boundary.
- Used GitHub PR, CI, local regression tests, and closeout records as separate gates instead of treating a local pass as final truth.

## Technical Skills

Python, Pytest, CLI validation tools, TypeScript, GitHub Actions, CI/CD, Git, JSON evidence manifests, LLM/API boundary design, agent workflow auditing, eval-style regression checks, developer documentation.

## Experience

### Independent AI Systems Engineer | March 2026 - Present

- Built public proof around AI-agent reliability, false-pass prevention, and evidence-gated task closeouts.
- Converted agent workflow failures into testable validation rules, proof documents, and reviewer-readable engineering artifacts.
- Maintained strict boundaries around credentials, provider output, local validation, remote CI, and human approval.

### Prior Experience

[Add verified prior company, role, dates, and 2-3 measurable bullets before final submission. Do not invent experience.]

## Education

[Add verified school, degree, field, and dates before final submission.]

## Selected Links

- Portfolio proof: https://github.com/yangfei222666-9/taiji/blob/main/docs/portfolio/agent-reliability-proof.md
- Main repository: https://github.com/yangfei222666-9/taiji
- Target technical case: Agent said done. Where is the evidence?

## Boundaries

Current public proof supports local and GitHub-level evidence for false-pass prevention. It does not claim deployed-system readiness, external customer adoption, third-party endorsement, fleet-scale sandboxing, or production eval infrastructure.

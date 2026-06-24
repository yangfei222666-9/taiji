# OpenAI Applied AI Engineer, Codex Core Agent - Cover Note Draft

Target role: Applied AI Engineer, Codex Core Agent
Candidate positioning: AI Agent Reliability / Evals / Developer Tools Engineer
Contact: [insert private contact details only in final application copy]

## Short Cover Note

Dear OpenAI Codex team,

I am applying for the Applied AI Engineer, Codex Core Agent role because my strongest recent work is about agent reliability: preventing AI-agent workflows from claiming "done" without evidence.

My current public proof is an Agent Reliability False-Pass Gate. It blocks unsupported success claims when passing-evidence pointers or explicit `cannot_claim` boundaries are missing. While building it, I found and fixed a real false-pass issue: an empty or missing fixture directory could make a self-test appear successful with `self_test=PASS cases=0`. I hardened the gate, added negative tests, and published the evidence path through merged PRs and a reviewer-readable proof page.

This experience is relevant to Codex work on evals, failure modes, edge cases, and dependable completion of software-engineering tasks. My work is local and narrow, not a claim of production-scale eval infrastructure, but it shows how I think about turning model behavior into dependable systems.

Best,
Yang Fei (Xiaojiu)

## Longer Version

Dear OpenAI Codex team,

I am interested in the Applied AI Engineer, Codex Core Agent role because I have been working on a concrete reliability problem: how to make AI-agent closeouts inspectable enough that a reviewer can trust the evidence instead of the claim.

My recent public work is an Agent Reliability False-Pass Gate. The premise is simple: an agent saying "done" is not evidence. The gate checks whether a success claim has passing-evidence pointers and explicit `cannot_claim` boundaries. If those are missing, it blocks the closeout instead of allowing unsupported success language.

The most useful part of the project was catching a false-pass inside the gate itself. A missing or empty fixture directory could produce a fake pass with zero cases. I changed the behavior to fail closed, added regression coverage, and kept the proof narrow: local validation, merged PR evidence, remote CI status, provider output, and production claims are not collapsed into one generic success state.

I also built a candidate-review bridge for sanitized agent summaries and locked its provider/model boundary. The goal was not to add another model for its own sake. The goal was to preserve model review as advisory while keeping local verification, GitHub evidence, and human approval as separate gates.

I believe this experience is relevant to Codex agent work because reliability is not only about model capability. It is also about eval design, failure modes, edge cases, closeout discipline, and the systems that make the difference between an impressive demo and a dependable tool.

Best,
Yang Fei (Xiaojiu)

## Role Match Notes

- OpenAI role theme: improve Codex agents from impressive demos into dependable tools.
- Candidate proof theme: false-pass prevention for AI-agent closeouts.
- OpenAI role theme: evals, failure modes, edge cases, robustness, real-world coding tasks.
- Candidate proof theme: fail-closed validation, negative tests, zero-case fixture fix, explicit `cannot_claim` state.
- OpenAI role theme: define what good completion looks like for agents handling complex tasks.
- Candidate proof theme: a task is not complete until evidence, validation, and limitations are visible.

## Final Submission Gaps

- Insert private contact details only in the final application copy.
- Confirm the exact application destination before transmitting any personal details.
- Keep the proof language narrow: local and GitHub-level evidence, not production readiness or customer validation.

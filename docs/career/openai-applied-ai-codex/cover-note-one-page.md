# OpenAI Applied AI Engineer, Codex Core Agent - Cover Note

Dear OpenAI Codex team,

I am applying for the Applied AI Engineer, Codex Core Agent role because my strongest recent work is about agent reliability: preventing AI-agent workflows from claiming "done" without evidence.

My current public proof is an Agent Reliability False-Pass Gate. It blocks unsupported success claims when passing-evidence pointers or explicit `cannot_claim` boundaries are missing. While building it, I found and fixed a real false-pass issue: an empty or missing fixture directory could make a self-test appear successful with `self_test=PASS cases=0`. I hardened the gate, added negative tests, and published the evidence path through merged PRs and a reviewer-readable proof page.

This experience is relevant to Codex work on evals, failure modes, edge cases, and dependable completion of software-engineering tasks. My work is local and narrow, not a claim of production-scale eval infrastructure, but it shows how I think about turning model behavior into dependable systems.

Best,
Yang Fei (Xiaojiu)

# Start Here for Reviewers

Review TaijiOS first as **Agent Reliability Evidence**: a public, evidence-first proof path for AI-agent reliability work. The narrow claim is: agent "done" language should require inspectable evidence and explicit `cannot_claim` boundaries.

## Five-Minute Path

1. Read the Agent Reliability proof: [docs/portfolio/agent-reliability-proof.md](docs/portfolio/agent-reliability-proof.md)
2. Check the machine-readable index: [docs/proof_index.json](docs/proof_index.json)
3. Inspect the Gap Map: [docs/research/codex-reliability-gap-map-01.md](docs/research/codex-reliability-gap-map-01.md)
4. Run the local checks:

```bash
pip install -e .
bash scripts/replay_public_demo.sh
python3 scripts/check_false_pass_gate.py --self-test examples/false_pass_gate/fixtures
python3 scripts/check_codex_gap_map.py
```

## Current Verdicts

- False-Pass Gate: `REMOTE_CI_VALIDATED` for a schema-level gate that blocks unsupported success claims when passing evidence pointers or `cannot_claim` boundaries are missing.
- Gap Map #01: `REMOTE_CI_VALIDATED` for a scoped 30-issue public-report review mapped to evidence-gate patterns.
- Broader TaijiOS runtime: `PARTIAL`; useful context, not production readiness.
- External adoption, recruiter review, interview status, and hiring validation: `UNVERIFIED` unless separately evidenced.

## Do Not Overclaim

This repository does not prove OpenAI/Codex endorsement, production deployment, current Codex product quality, prevalence of public issues, third-party adoption, provider/API readiness, hardware control, trading control, or recruiting validation.

Treat provider/model output, local demo success, draft PRs, and local files as candidate evidence until a named gate records canonical status.

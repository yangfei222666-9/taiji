# Start Here for Reviewers

TaijiOS should be reviewed first as an evidence-first reliability runtime for AI agents.
The core claim is narrow: agent progress should require parseable evidence before it is accepted.

## Current Verdict

| Claim surface | Verdict | Boundary |
|---|---|---|
| Public evidence-first runtime sample | `PASS / PARTIAL` | Runnable local demo and proof docs exist, but this is not a repo-wide production claim. |
| Agent Reliability implementation and research proof | `REMOTE_CI_VALIDATED` | False-Pass Gate and Codex Reliability Gap Map #01 are merged to remote main; they do not prove production readiness or Codex product quality. |
| xAI / SpaceX-style proof packet | `PARTIAL` | Useful for human review; no endorsement or hiring-bar claim. |
| External validation or community traction | `PENDING` | Public artifact exists; independent reproduction and traction are not established here. |
| Production readiness | `BLOCKED` | No production, hardware, provider/API, trading, or release evidence authority is claimed. |

## Three-Bullet Proof

1. **Hard problem solved:** AI agents can report success while silently failing. TaijiOS requires evidence artifacts before success language is accepted.
2. **Implementation proof:** the False-Pass Gate blocks unsupported success language when passing evidence pointers or explicit `cannot_claim` boundaries are missing.
3. **Research proof:** Codex Reliability Gap Map #01 maps a deterministic 30-issue public-report snapshot to evidence-gate patterns without treating reports as confirmed defects.

## Five-Minute Review Path

```bash
pip install -e .
bash scripts/replay_public_demo.sh
python scripts/check_false_pass_gate.py --self-test examples/false_pass_gate/fixtures
python3 scripts/check_codex_gap_map.py
```

The replay script writes to a temporary output directory by default so review
runs do not dirty the git worktree. To keep inspectable artifacts, set an
explicit output root:

```bash
TAIJI_REPLAY_OUTPUT_ROOT=.audit/public_demo bash scripts/replay_public_demo.sh
```

Then inspect:

- `.audit/public_demo/run-1/quickstart_evidence.json`
- `.audit/public_demo/run-1/quickstart_trace.json`
- `.audit/public_demo/run-1/quickstart_events.json`
- `docs/proof_index.json`
- `docs/SPACE_X_AI_PROOF_PACKET.md`
- `AUDIT_EVIDENCE.md`
- `docs/research/codex-reliability-gap-map-01.md`
- `data/codex-reliability-gap-map-01.json`

## Agent Reliability: False-Pass Gate

The False-Pass Gate is a schema-level check for AI-agent success claims. It
requires passing evidence pointers and explicit `cannot_claim` boundaries before
success language is accepted. It is intentionally local and synthetic:

```bash
python scripts/check_false_pass_gate.py --self-test examples/false_pass_gate/fixtures
```

Expected local result:

```text
self_test=PASS cases=3
```

This gate can support `LOCAL_VALIDATED` after the self-test and pytest pass. It
does not execute evidence commands, prove that the success claim is true, prove
remote CI, public adoption, production readiness, provider/API readiness, or
recruiting validation.

## Agent Reliability: Codex Reliability Gap Map #01

The Gap Map is a scoped public-report review for coding-agent reliability risks.
It maps 30 dated `openai/codex` issue reports to evidence-gate patterns:

```bash
python3 scripts/check_codex_gap_map.py
```

Remote evidence:

- PR #43: `https://github.com/yangfei222666-9/taiji/pull/43`
- Merge commit: `44dee657fb112f8ea3bfa207c104684079bd94de`
- Main CI run: `https://github.com/yangfei222666-9/taiji/actions/runs/28116696880`

This proof supports failure-mode taxonomy work. It does not prove prevalence,
current Codex product quality, maintainer-confirmed defects, root causes, or
production mitigation.

## Verdict Semantics

- `PASS`: a named local check passed with parseable evidence.
- `PARTIAL`: a packet is useful for review, but a larger claim is still not proven.
- `BLOCKED`: a safety gate stopped the claim; this is not rewritten as failure or success.
- `PENDING`: the evidence has not been produced or independently verified yet.

## I Ching Boundary

Hexagram and I Ching labels are used as role-boundary and system-state abstractions.
They are not mystical claims, scientific proof, production authority, or external endorsement.

## Stop Rules

Do not claim:

- xAI, SpaceX, Elon, or external organization endorsement.
- Production readiness.
- Real spacecraft, vehicle, robot, radio, satellite, hardware, broker, exchange, order, or trading control.
- Provider/API readiness unless a scoped live probe verifies it.
- Release evidence `PASS` while `AUDIT_EVIDENCE.md` remains template-only.
- Local demo `PASS` as repo-wide `PASS`.
- Agent "done", "ready", or "complete" claims without passing evidence and explicit `cannot_claim` boundaries.
- Codex Reliability Gap Map as a prevalence study, security audit, or current Codex product-quality conclusion.

# Start Here for Reviewers

TaijiOS should be reviewed first as an evidence-first reliability runtime for AI agents.
The core claim is narrow: agent progress should require parseable evidence before it is accepted.

## Current Verdict

| Claim surface | Verdict | Boundary |
|---|---|---|
| Public evidence-first runtime sample | `PASS / PARTIAL` | Runnable local demo and proof docs exist, but this is not a repo-wide production claim. |
| xAI / SpaceX-style proof packet | `PARTIAL` | Useful for human review; no endorsement or hiring-bar claim. |
| External validation or community traction | `PENDING` | Public artifact exists; independent reproduction and traction are not established here. |
| Production readiness | `BLOCKED` | No production, hardware, provider/API, trading, or release evidence authority is claimed. |

## Three-Bullet Proof

1. **Hard problem solved:** AI agents can report success while silently failing. TaijiOS requires evidence artifacts before success language is accepted.
2. **Concrete evidence artifact:** the no-API-key quickstart writes local evidence and should show 3 tasks, 3/3 succeeded, 3/3 self-healed, and 18 logged events.
3. **Exact limitation:** the current public packet is `PARTIAL`; it is not production-ready, not externally endorsed, and not live release evidence `PASS`.

## Five-Minute Review Path

```bash
pip install -e .
bash scripts/replay_public_demo.sh
```

Then inspect:

- `examples/quickstart_output/quickstart_evidence.json`
- `examples/quickstart_output/quickstart_trace.json`
- `examples/quickstart_output/quickstart_events.json`
- `docs/proof_index.json`
- `docs/SPACE_X_AI_PROOF_PACKET.md`
- `AUDIT_EVIDENCE.md`

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

# XuanShu Research Protocol

## Verdict

Route: `AI + XuanShu Research Path`

Research subjects:

- `Journey to the West`
- `I Ching`
- Third book slot: `PENDING`

Status:

| Gate | Verdict |
| --- | --- |
| Journey to the West research path | PASS |
| I Ching research path | PASS |
| Direct mapping to current TaijiOS / AI / SpaceX path | PASS |
| Third book | PENDING |
| AI + XuanShu as long-term research direction | PASS |
| XuanShu as scientific fact | PENDING |
| XuanShu direct authority over major decisions | BLOCKED |
| Investment, trading, health, legal, or high-impact use | BLOCKED unless learning_only / observe_only |

This protocol defines a research lane. It does not create runtime authority, judgment authority, paper-buy authority, trade authority, health advice, legal advice, hiring readiness, or public proof.

## Core Rule

Science verifies. XuanShu observes patterns. AI expands analysis. TaijiOS prevents fake pass.

Short form:

```text
Use AI to learn science.
Use XuanShu to observe change.
Use TaijiOS to record evidence.
Use engineering results to prove capability.
```

Compressed route:

```text
AI trains speed.
Engineering trains capability.
Journey to the West trains heart and discipline.
I Ching trains timing and system-change awareness.
TaijiOS trains truth.
```

Current route:

```text
Journey to the West trains heart.
I Ching observes timing.
AI accelerates learning.
Engineering proves capability.
TaijiOS audits truth.
```

## Authority Split

| Layer | Role | Authority |
| --- | --- | --- |
| Science | Experiment, math, engineering, code, tests | Highest truth authority |
| AI | Search, inference, summary, modeling, learning support | Tool authority only |
| XuanShu | Symbol, cycle, timing, relationship, attention, system mood | Observation and hypothesis authority only |
| TaijiOS | Evidence, verdict, event flow, closeout, anti-self-deception | Audit authority |
| Human owner | Goal, taste, judgment, long-term direction | Sovereign authority |

AI output is `PENDING until reviewed`.

XuanShu output is `observe_only until validated`.

Evidence outranks both.

## Hard Boundaries

XuanShu must not:

- Override tests, verifier output, event flow, hashes, git truth, or runtime evidence.
- Turn a feeling into a fact.
- Turn a vague match into `PASS`.
- Turn post-hoc explanation into prediction success.
- Promote `learning_only` into `judgment`.
- Promote `observe_only` into paper-buy, trade, or live action.
- Provide medical, legal, financial, or safety-critical authority.
- Claim SpaceX readiness, engineering readiness, or employment readiness.
- Replace science, engineering validation, or human review.

AI must not:

- Fabricate XuanShu narratives as truth.
- Hide misses and preserve only hits.
- Convert symbolic interpretation into command authority.
- Create public claims without evidence.

TaijiOS must:

- Require timestamped records.
- Preserve misses, ambiguous results, and invalidated hypotheses.
- Keep `PASS`, `PARTIAL`, `PENDING`, and `BLOCKED` explicit.
- Keep science, XuanShu, AI, and human-owner authority separate.

## Research Scope

P0: Journey to the West

- Focus: practice, discipline, power, hierarchy, restraint, ordeal, and long-term route.
- Study as:
  - cultivation route map
  - mindset model
  - power-system model
  - master-apprentice model
  - growth metaphor
  - risk and ordeal model
- First themes:
  - Bodhi Patriarch and Sun Wukong
  - seventy-two transformations
  - Somersault Cloud
  - Great Havoc in Heaven
  - Five Elements Mountain
  - journey to obtain scriptures
- Boundary: metaphor and study model only; not historical, scientific, or destiny authority.

P1: I Ching

- Focus: change, timing, state transition, risk, context, evolution.
- TaijiOS mapping:
  - hexagram -> system state
  - changing line -> state transition
  - auspicious / inauspicious -> risk verdict
  - timing / position -> context
  - changed hexagram -> scenario evolution
  - not suitable to act -> BLOCKED
  - suitable to proceed -> PASS with boundary

P2: Yin-Yang and Wuxing

- Focus: feedback, balance, overload, suppression, amplification, resource flow.
- Modern mapping:
  - generation / control -> feedback loop
  - excess / deficiency -> imbalance
  - restraint -> constraint
  - transformation -> state change

P3: Fengshui as workstation and environment study

- Treat as spatial psychology and workflow design first.
- Study: lighting, noise, line of sight, support behind the seat, desk order, device placement, distraction boundaries.
- Allowed output: workstation notes and environment hypotheses.
- Forbidden output: supernatural certainty or high-impact decision authority.

P4: Bazi / Ziwei / life-pattern systems

- Treat as cultural, narrative, personality, and cycle-model research only.
- Forbidden output: life sentence, wealth guarantee, marriage conclusion, medical conclusion, investment trigger, or employment-readiness claim.

P5: Qimen / Liuren / Taiyi

- Deferred. These are high-complexity systems and stay future research until the P0-P2 evidence discipline is stable.

## Case Log Contract

Every XuanShu observation must be recorded before verification.

Required fields:

```json
{
  "id": "xuan_shu_case_YYYYMMDD_NNN",
  "created_at": "ISO-8601 timestamp",
  "question": "plain question",
  "scope": "personal | project | environment | learning | other",
  "method": "yijing | wuxing | fengshui | bazi | ziwei | other",
  "input_context": "non-secret summary",
  "observation": "symbolic or pattern observation",
  "claim_type": "hypothesis | rhythm_note | risk_signal | environment_note",
  "allowed_authority": "observe_only",
  "forbidden_authority": [
    "scientific_fact",
    "judgment",
    "paper_buy",
    "trade",
    "health_advice",
    "legal_advice",
    "public_claim",
    "SpaceX_readiness"
  ],
  "verification_window": "when this can be reviewed",
  "expected_evidence": "what would count as evidence",
  "closeout": {
    "status": "PENDING",
    "result": null,
    "misses_preserved": true
  }
}
```

Allowed closeout statuses:

- `PENDING`
- `HIT_WITH_EVIDENCE`
- `MISS_WITH_EVIDENCE`
- `AMBIGUOUS`
- `NOT_VERIFIABLE`
- `INVALIDATED`

`HIT_WITH_EVIDENCE` is still not scientific proof unless the evidence meets the relevant scientific or engineering standard.

## Engineering Interface

XuanShu may influence:

- Research questions.
- Reflection prompts.
- Risk hypotheses.
- Timing notes.
- Workspace layout experiments.
- Personal discipline and review rhythm.

XuanShu may not influence directly:

- Git stage, commit, push, PR, merge, release, or publish.
- Provider calls.
- Trading or paper-buy actions.
- Health, legal, financial, or safety decisions.
- Runtime default settings.
- Promotion of rules into production.
- Public claims.

## SpaceX Boundary

This lane does not claim SpaceX readiness.

SpaceX-facing progress still requires:

- Code.
- Systems work.
- Reliability evidence.
- Tests and reproducible artifacts.
- Engineering writing.
- Long-term training.

XuanShu may support rhythm, self-observation, and long-term steadiness. It cannot replace engineering evidence.

## First Actions

1. Keep this protocol as the authority boundary for AI + XuanShu research.
2. Use `JOURNEY_TO_THE_WEST_STUDY.md` for cultivation and power-system analysis.
3. Use `YIJING_SYSTEM_MAPPING.md` for system-state and timing analysis.
4. Use `CURRENT_PATH_MAPPING.md` to keep the research tied to the current AI / engineering / TaijiOS / SpaceX route.
5. Use `SYMBOL_TO_SYSTEM_MAP.md` to translate symbolic language into engineering language.
6. Use `CASE_LOG.md` and `PREDICTION_CLOSEOUT.md` to prevent fake hits.
7. Keep all early cases `learning_only` and `observe_only`.
8. Review misses and ambiguous cases before making any pattern claim.
9. Do not promote this protocol into runtime behavior without a separate explicit promotion gate.

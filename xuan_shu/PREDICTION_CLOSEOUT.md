# Prediction Closeout

## Purpose

Prevent fake hits, hindsight bias, and narrative inflation in XuanShu research.

Authority: audit only.

## Anti-Fake-Hit Rules

1. Record predictions before outcomes.
2. Record misses as well as hits.
3. Mark vague results as `PARTIAL`, `AMBIGUOUS`, or `UNVERIFIABLE`.
4. Do not upgrade intuition to `PASS`.
5. Do not use XuanShu for trading, medical, legal, or safety-critical decisions.
6. Do not rewrite the original claim after the outcome.
7. Do not count broad symbolic language as precise prediction.
8. Do not let AI generate a flattering interpretation after the fact.

## Required Closeout Fields

```text
Case ID:
Original timestamp:
Original claim:
Verification window:
Expected evidence:
Actual outcome:
Evidence path:
Result:
Miss preserved:
Ambiguity noted:
What cannot be claimed:
Next action:
```

## Result Labels

Use exactly one primary result:

- `HIT_WITH_EVIDENCE`
- `MISS_WITH_EVIDENCE`
- `PARTIAL`
- `AMBIGUOUS`
- `UNVERIFIABLE`
- `INVALIDATED`
- `BLOCKED_NO_EVIDENCE`

## Promotion Rule

No single hit can promote a pattern into truth.

A pattern requires:

- timestamped cases
- preserved misses
- clear evidence
- repeated review
- explicit scope
- no high-stakes authority

Even a repeated pattern remains below science unless it passes the relevant scientific or engineering standard.

## Blocked Uses

Always blocked:

- trading
- paper-buy
- medical advice
- legal advice
- safety-critical decisions
- credential handling
- secret handling
- public claims
- SpaceX readiness claims
- repo-level PASS claims

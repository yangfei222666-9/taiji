# Quantitative Evidence Plan

Current verdict: `PENDING`.

This plan defines how TaijiOS can turn the public quickstart from a single runnable demo into quantified evidence. The default mode is local-only: no external API, no provider key, no GPU, no production service, no trading, and no release claim.

## Target Runs

| Batch | Purpose | Current state |
|---|---|---|
| 100 local replays | First stability signal for reviewer confidence | `PENDING` |
| 1,000 local replays | Larger deterministic regression sample | `PENDING` |

## Command

```bash
bash scripts/replay_public_demo.sh --runs 100
```

The script reruns `examples/quickstart_minimal.py` and verifies the generated JSON evidence after each run.

## Metrics

| Metric | Expected value | Verdict rule |
|---|---:|---|
| `total_tasks` | `3` per run | Any mismatch blocks the batch. |
| `succeeded` | `3` per run | Any failed task blocks the batch. |
| `self_healed` | `3` per run | Any non-healed task blocks the self-healing claim. |
| `event_log_count` | `18` per run | Any drift blocks event-count consistency. |
| JSON parseability | all evidence files parse | Any parse error blocks the batch. |
| External API use | none | Any required provider/API blocks local-only claim. |

## Summary Table Template

| Runs | Passed | Failed | Retry-to-pass count | Event-count mismatches | Verdict |
|---:|---:|---:|---:|---:|---|
| 100 | `PENDING` | `PENDING` | `PENDING` | `PENDING` | `PENDING` |
| 1,000 | `PENDING` | `PENDING` | `PENDING` | `PENDING` | `PENDING` |

## Confidence Limits

Use a binomial confidence interval for batch pass rate. Until the batches are actually run, confidence is not claimed.

Reference lower bounds if every run passes:

| Batch | Observed pass rate | Approximate 95% lower bound |
|---:|---:|---:|
| 100/100 | 100% | 96.3% |
| 1,000/1,000 | 100% | 99.6% |

These are planning numbers, not current evidence.

## Blocked Claims

Passing this plan would still not prove production readiness, external endorsement, provider/API readiness, hardware control, trading authority, or release evidence `PASS`.

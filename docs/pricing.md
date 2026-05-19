# Pricing Guardrails

This starter kit is designed for a small invitation demo.

## Default Limits

- `DEMO_MAX_ACTIVE_RUNS=3`
- `DEMO_RUN_TIMEOUT_SECONDS=30`
- `ARTIFACT_TTL_HOURS=24`
- `max_runs=20` per invite

## Cost Levers

- Lower `DEMO_MAX_ACTIVE_RUNS` before inviting a larger group.
- Keep Cloud Run `--max-retries=0` until the agent is stable.
- Keep artifacts private and short-lived.
- Run cleanup daily.
- Split CPU and GPU jobs if GPU is added later.

## What This Does Not Cover

- Billing integration.
- Per-user payment enforcement.
- Provider quota arbitration.
- Production abuse detection beyond invite tokens and active-run caps.

# Live Preflight

`preflight:live` is an existence-only readiness check before any Supabase, Vercel, GitHub, or Cloud Run action.

## No Secret Values

The preflight must never print, copy, transmit, or store secret values. It only reports:

- variable name
- exists true or false
- source name/path
- whether the variable is classified as secret

It does not call Supabase, GitHub, GCP, Vercel, or any provider API.

## Commands

```bash
npm run preflight:live
```

This writes:

```text
runs/preflight/live_<timestamp>/summary.json
runs/preflight/live_<timestamp>/event_flow.jsonl
```

Use strict mode when a deployment script should stop on blockers:

```bash
npm run preflight:live:strict
```

## Verdicts

- `ready_for_manual_external_gate`: local names, commands, and static deploy contracts look ready. Human approval is still required before live external actions.
- `blocked_missing_env`: one or more required env names are missing.
- `blocked_preflight`: a non-env readiness blocker exists.

GitHub-only secrets such as `GCP_CREDENTIALS` are reported as manual gates, not local `.env.local` blockers. A ready local preflight still does not authorize deploy or tester invites until the GitHub Actions secret gate is manually completed and release readiness allows it.

## Required Env Names

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE`
- `DEMO_REQUIRE_INVITE`
- `DEMO_TRIGGER_MODE`
- `DEMO_MAX_ACTIVE_RUNS`
- `DEMO_RUN_TIMEOUT_SECONDS`
- `ARTIFACT_BUCKET`
- `GH_REPO`
- `GH_TOKEN`
- `GH_REF`
- `GH_WORKFLOW`

## Manual Gate Env

- `GCP_CREDENTIALS` belongs in GitHub Actions Secrets.

The script also checks for forbidden public secret names such as `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE`.

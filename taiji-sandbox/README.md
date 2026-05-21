# Taiji Sandbox

Forkable starter kit for an invitation-only AI runtime demo.

Stack:

- Frontend: Next.js App Router
- API: `app/api/*`
- DB: Supabase Postgres
- Artifact store: Supabase Storage
- Ephemeral execution: Cloud Run Jobs
- Queue trigger: GitHub Actions `workflow_dispatch`

## Local Start

1. Create a Supabase project.
2. Apply `db/schema.sql`, then `db/seed.sql`.
3. Copy `.env.example` to `.env.local` and fill `SUPABASE_URL` plus `SUPABASE_SERVICE_ROLE`.
4. Keep `DEMO_TRIGGER_MODE=mock` for local smoke tests.
5. Run:

```bash
npm ci --ignore-scripts
npm run verify:local
npm run dev
```

Open `http://localhost:3000` and use the seed invite token:

```text
dev-invite-token
```

## Production Path

1. Deploy the Next.js app on Vercel.
2. Set `DEMO_TRIGGER_MODE=github`.
3. Set `GH_REPO`, `GH_TOKEN`, `GH_REF`, and `GH_WORKFLOW`.
4. Build and deploy the Cloud Run Job image from `agent/`.
5. Store `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE` as Cloud Run Job env/secrets.
6. Add GitHub secret `GCP_CREDENTIALS`.
7. Invite testers by inserting hashed tokens into `invites`.

The API never exposes the Supabase service role to the browser. Browser clients only call the internal Next.js API routes.

Use `docs/fork-deploy-runbook.md` as the gate checklist. Local verification does not count as deployed runtime proof.

## Safety Defaults

- Invite tokens are hashed before storage.
- Each invite has `max_runs`, `used_runs`, and `expires_at`.
- Active run count is capped before queue dispatch.
- Cloud Run timeout is fixed at 30 seconds by default.
- Artifacts are private and returned through short-lived signed URLs.
- Artifact TTL cleanup is implemented in `agent/main.py` with `CLEANUP_MODE=artifacts`.

## Core Routes

- `POST /api/start_run`: validates invite, creates a run, dispatches queue.
- `GET /api/run_status?id=<run_id>`: returns progress for a run.
- `GET /api/artifacts?run_id=<run_id>`: returns signed artifact URLs.

## Boundaries

This kit does not perform live trading, provider arbitration, billing, or system-rule promotion. It is a runnable invitation sandbox scaffold.

## Verification

Local repository proof:

```bash
npm run verify:local
npm run e2e:evidence
npm run typecheck
npm audit --omit=dev
npm run build
python3 -m py_compile agent/main.py
```

Full local verifier:

```bash
npm run verify:full
```

Before touching live Supabase, Vercel, GitHub Actions, or Cloud Run:

```bash
npm run env:wiring
npm run preflight:live
npm run deploy:plan
```

This reports env-name and local-tool readiness without printing secret values or calling external APIs. Use `npm run preflight:live:strict` in deployment scripts.

Generate invite SQL offline:

```bash
npm run invite:create -- --email tester@example.com --max-runs 20 --expires-days 14
```

Use `--print-token` only when you are ready to display the tester token once. Raw invite tokens are bearer credentials; do not write them into repo files or logs.

Render a tester handoff packet without writing the raw token:

```bash
npm run tester:packet -- --email tester@example.com --app-url https://your-demo.vercel.app
```

The packet keeps `{{INVITE_TOKEN}}` as a placeholder. Replace it only in the private message you send to the tester, not in repo artifacts.

Before forking, staging, or handing off the repo, render a local source readiness manifest:

```bash
npm run fork:readiness
```

This checks required source files, ignored generated folders, local env files, and raw invite token patterns without calling external APIs.

Aggregate all local gates into one release readiness report:

```bash
npm run readiness:report
```

If the report says `local_release_packet_ready_cloud_runtime_blocked`, the package is locally reviewable but still not ready for deploy or tester invites.

Render the current operator next-action packet:

```bash
npm run next:actions
```

This summarizes allowed repair actions and prohibited release actions from the latest local artifacts.

Render a manual wiring handoff packet for the blocked env/CLI gate:

```bash
npm run wiring:packet
```

This creates a Supabase/Vercel/GitHub Actions/Cloud Run checklist from local artifacts without reading secret values, calling external APIs, deploying, or creating `.env` files.

# Fork Deploy Runbook

This runbook is the minimum path from fork to invite tester. It separates local proof, deploy proof, and live workflow proof.

## Fork Gate

Run locally after cloning:

```bash
npm ci --ignore-scripts
npm run verify:local
npm run fork:readiness
npm run env:wiring
npm run typecheck
npm audit --omit=dev
npm run build
python3 -m py_compile agent/main.py
npm run readiness:report
npm run next:actions
npm run deploy:gate
npm run wiring:packet
```

Pass means the repository shape, TypeScript build, dependency audit, and Python agent syntax are locally valid. It does not prove Supabase, GitHub Actions, Cloud Run, or Vercel are configured.

## Supabase Gate

Before applying anything live, run:

```bash
npm run preflight:live
```

If the verdict is not `ready_for_manual_external_gate`, stop and fix the local readiness blocker first.

When the blocker is missing env or local CLI setup, render a manual handoff packet:

```bash
npm run wiring:packet
```

This is handoff evidence only. It does not read secret values, create `.env` files, call external APIs, deploy, dispatch workflows, or invite testers.

Apply:

```bash
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f db/schema.sql -f db/seed.sql
```

Then confirm:

- `invites`, `runs`, and `run_artifacts` exist.
- RLS is enabled on all three tables.
- bucket `taiji-artifacts` is private.
- seed invite token `dev-invite-token` exists only as a hash.

## Deploy Gate

Before any external deploy, render the local deploy gate:

```bash
npm run deploy:gate
```

This writes an auditable gate artifact. It does not deploy and does not verify remote GitHub Secrets unless a human separately confirms the GitHub UI state.

Deploy the Next.js app to Vercel with:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE`
- `DEMO_REQUIRE_INVITE=true`
- `DEMO_TRIGGER_MODE=github`
- `DEMO_MAX_ACTIVE_RUNS=3`
- `DEMO_RUN_TIMEOUT_SECONDS=30`
- `ARTIFACT_BUCKET=taiji-artifacts`
- `GH_REPO`
- `GH_TOKEN`
- `GH_REF`
- `GH_WORKFLOW=ephemeral-run.yml`
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `CLOUD_RUN_JOB`
- `AGENT_IMAGE_NAME`

Do not expose the service-role key as a `NEXT_PUBLIC_*` variable.

## Cloud Run Gate

Render the manual deploy plan:

```bash
npm run deploy:plan
```

Then review `docs/deploy-agent-workflow.md`.

The GitHub workflow `.github/workflows/deploy-agent.yml` can build and push the image, then create or update the Cloud Run Job. It is manual only and must be dispatched by a human.

If creating the job directly, keep the hard timeout:

```bash
gcloud run jobs create taiji-agent \
  --image=us-central1-docker.pkg.dev/PROJECT/taiji/taiji-agent:latest \
  --region=us-central1 \
  --task-timeout=30s \
  --max-retries=0 \
  --set-env-vars=ARTIFACT_BUCKET=taiji-artifacts,DEMO_RUN_TIMEOUT_SECONDS=30,ARTIFACT_TTL_HOURS=24 \
  --set-secrets=SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE=supabase-service-role:latest
```

## Invite Gate

Create one token per tester and store only the SHA-256 hash in `invites.token_hash`.

Recommended defaults:

- `max_runs=20`
- expiry: 7 to 14 days
- active run cap: 3

## Live Verification Gate

Before inviting testers, execute exactly one end-to-end run:

1. Open the deployed URL.
2. Enter a single tester token.
3. Start one run.
4. Confirm `runs.status` moves `queued -> running -> succeeded`.
5. Confirm `run_artifacts` has one artifact row.
6. Confirm artifact signed URL opens.
7. Confirm `used_runs` increments once.
8. Confirm GitHub Actions and Cloud Run logs reference the same `run_id`.

If any step fails, keep the demo at `blocked_external_runtime` and do not invite testers yet.

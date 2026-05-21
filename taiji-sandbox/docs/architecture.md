# Architecture

Taiji Sandbox is an invitation runtime, not only a UI demo.

## Request Flow

1. Tester enters an invite token in the Next.js UI.
2. `POST /api/start_run` hashes the token and checks `invites`.
3. API rejects expired or exhausted invites.
4. API counts active `queued` and `running` runs and returns `429` when the cap is reached.
5. API inserts a `runs` row with `status=queued`.
6. In production mode, API calls GitHub `workflow_dispatch`.
7. GitHub Actions executes a Cloud Run Job with `RUN_ID`.
8. The agent updates `runs`, uploads artifacts to Supabase Storage, and inserts `run_artifacts`.
9. UI polls `GET /api/run_status` and fetches private artifact signed URLs through `GET /api/artifacts`.

## Runtime Boundary

Vercel hosts UI and API routes. Cloud Run Jobs execute short-lived agent work. GitHub Actions is the queue shim. Supabase is the state and artifact source of truth.

## Cost Guardrails

- `DEMO_MAX_ACTIVE_RUNS` caps active work.
- `DEMO_RUN_TIMEOUT_SECONDS=30` is mirrored in Cloud Run Job creation with `--task-timeout=30s`.
- `ARTIFACT_TTL_HOURS=24` cleanup is available through `CLEANUP_MODE=artifacts`.
- Invite rows enforce `max_runs`, `used_runs`, and `expires_at`.

## Cloud Run Job Setup

Build and push the agent image, then create the job:

```bash
gcloud run jobs create taiji-agent \
  --image=us-central1-docker.pkg.dev/PROJECT/taiji/taiji-agent:latest \
  --region=us-central1 \
  --task-timeout=30s \
  --max-retries=0 \
  --set-env-vars=ARTIFACT_BUCKET=taiji-artifacts,DEMO_RUN_TIMEOUT_SECONDS=30,ARTIFACT_TTL_HOURS=24 \
  --set-secrets=SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE=supabase-service-role:latest
```

For cleanup, create a second scheduled execution with:

```bash
gcloud run jobs execute taiji-agent \
  --region=us-central1 \
  --update-env-vars=CLEANUP_MODE=artifacts
```

Wire that command through Cloud Scheduler or a second GitHub scheduled workflow.

## Supabase Security Notes

The public browser never receives the service-role key. Tables have RLS enabled and no anon/authenticated table grants by default. API routes use service-role access server-side and return only the minimum run/artifact fields.

Supabase currently warns that SQL-created tables may not be automatically exposed to the Data API. This kit avoids browser Data API dependence, so the table exposure setting is not part of tester access.

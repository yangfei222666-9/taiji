# Invite Checklist

## Supabase

- Apply `db/schema.sql`.
- Apply `db/seed.sql`.
- Confirm bucket `taiji-artifacts` exists and is private.
- Create one invite token per tester with the offline helper.
- Store only `sha256(token)` in `invites.token_hash`; never store raw invite tokens.

Generate redacted SQL first:

```bash
npm run invite:create -- --email tester@example.com --max-runs 20 --expires-days 14
```

When ready to hand the token to the tester, display it once in a private terminal:

```bash
npm run invite:create -- --email tester@example.com --max-runs 20 --expires-days 14 --print-token
```

The SQL output is safe to paste into Supabase SQL editor because it only contains the token hash. The `--print-token` output contains a bearer credential and must not be committed, redirected into repo files, or copied into logs.

## Vercel

- Set `SUPABASE_URL`.
- Set `SUPABASE_SERVICE_ROLE`.
- Set `DEMO_REQUIRE_INVITE=true`.
- Set `DEMO_TRIGGER_MODE=github`.
- Set `DEMO_MAX_ACTIVE_RUNS=3`.
- Set `DEMO_RUN_TIMEOUT_SECONDS=30`.
- Set `ARTIFACT_BUCKET=taiji-artifacts`.
- Set `GH_REPO`, `GH_TOKEN`, `GH_REF`, and `GH_WORKFLOW`.

## GitHub

- Add secret `GCP_CREDENTIALS`.
- Add repository variables `GCP_REGION` and `CLOUD_RUN_JOB`.
- Confirm Actions can run `ephemeral-run.yml`.
- Do not dispatch the workflow manually with a fake `RUN_ID` except for an explicit test.

## Cloud Run

- Job uses the image built from `agent/`.
- Job has `--task-timeout=30s`.
- Job has `--max-retries=0` for demo cost control.
- Job receives Supabase env/secrets.
- Job does not receive tester invite tokens.

## Tester Invite

- Render a tester packet:

```bash
npm run tester:packet -- --email tester@example.com --app-url https://your-demo.vercel.app
```

- Replace `{{INVITE_TOKEN}}` only in the private message to the tester.
- Send tester URL.
- Send one token.
- State max run count and expiry.
- Monitor `/dashboard` and Supabase `runs`.
- Revoke by setting `expires_at=now()` or `max_runs=used_runs`.
- Do not reuse tokens between testers.
- Treat raw invite tokens as bearer secrets.

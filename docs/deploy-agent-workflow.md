# Deploy Agent Workflow

`deploy-agent.yml` is the manual path for building the Cloud Run agent image and creating or updating the Cloud Run Job.

## Manual Only

The workflow uses `workflow_dispatch` only. It must not run on `push` or `pull_request`.

Dispatching this workflow is an external action. It can create remote logs, push a container image, and create or update a Cloud Run Job. Do not run it without human approval.

## Required GitHub Secret

- `GCP_CREDENTIALS`

Never paste this secret into chat, docs, logs, or artifacts.

## Required GitHub Variables

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `CLOUD_RUN_JOB`
- `AGENT_IMAGE_NAME`

## Cost Guardrails

The Cloud Run Job path keeps:

- `--task-timeout=30s`
- `--max-retries=0`
- `DEMO_RUN_TIMEOUT_SECONDS=30`
- `ARTIFACT_TTL_HOURS=24`

## Non-Claims

Adding this workflow is not a deployment proof. Deployment is only proven after a manual dispatch completes, the Cloud Run Job exists, and an end-to-end run writes matching Supabase `runs` and `run_artifacts` rows.

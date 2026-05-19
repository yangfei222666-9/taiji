#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = process.cwd();
const generatedAt = new Date().toISOString();
const runId = generatedAt.replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const outDir = join(ROOT, 'runs', 'deploy_plan', runId);

function read(path) {
  return readFileSync(join(ROOT, path), 'utf8');
}

function fileExists(path) {
  return existsSync(join(ROOT, path));
}

const requiredFiles = [
  '.github/workflows/deploy-agent.yml',
  '.github/workflows/ephemeral-run.yml',
  'docs/fork-deploy-runbook.md',
  'docs/live-preflight.md',
  'agent/Dockerfile',
  'agent/main.py',
  'db/schema.sql'
];

const missingFiles = requiredFiles.filter((path) => !fileExists(path));
const deployWorkflow = fileExists('.github/workflows/deploy-agent.yml') ? read('.github/workflows/deploy-agent.yml') : '';
const ephemeralWorkflow = fileExists('.github/workflows/ephemeral-run.yml') ? read('.github/workflows/ephemeral-run.yml') : '';

const checks = [
  {
    name: 'required_files',
    status: missingFiles.length === 0 ? 'ok' : 'blocked',
    missing: missingFiles
  },
  {
    name: 'deploy_agent_manual_only',
    status: deployWorkflow.includes('workflow_dispatch') && !deployWorkflow.includes('push:') && !deployWorkflow.includes('pull_request:') ? 'ok' : 'blocked'
  },
  {
    name: 'deploy_agent_timeout',
    status: deployWorkflow.includes('--task-timeout=30s') && deployWorkflow.includes('--max-retries=0') ? 'ok' : 'blocked'
  },
  {
    name: 'ephemeral_run_manual_only',
    status: ephemeralWorkflow.includes('workflow_dispatch') && !ephemeralWorkflow.includes('push:') && !ephemeralWorkflow.includes('pull_request:') ? 'ok' : 'blocked'
  }
];

const blocked = checks.filter((check) => check.status === 'blocked');
const plan = {
  schema_version: 'taiji_sandbox.deploy_plan.v0',
  generated_at: generatedAt,
  verdict: blocked.length === 0 ? 'ready_for_manual_review_not_deployed' : 'blocked_local_deploy_plan',
  external_api_calls_performed: false,
  secret_values_read_or_printed: false,
  blocked_count: blocked.length,
  checks,
  manual_gates: [
    'Run npm run preflight:live and require ready_for_manual_external_gate before external actions.',
    'Create GitHub secret GCP_CREDENTIALS and repo variables GCP_PROJECT_ID, GCP_REGION, GCP_ARTIFACT_REPOSITORY, CLOUD_RUN_JOB, AGENT_IMAGE_NAME.',
    'Manually dispatch deploy-agent.yml with create_or_update_job=true after reviewing cost and timeout settings.',
    'Apply Supabase schema and seed only after a human confirms the target project.',
    'Deploy Vercel only after env names are present and service-role key is not public.',
    'Manually dispatch ephemeral-run.yml only with a real run_id created by the API.'
  ],
  non_claims: [
    'This plan is not a deployment proof.',
    'This plan does not verify Supabase credentials.',
    'This plan does not verify GCP credentials.',
    'This plan does not verify Vercel access.',
    'This plan does not authorize any live workflow.'
  ]
};

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(plan, null, 2)}\n`);
writeFileSync(
  join(outDir, 'event_flow.jsonl'),
  [
    {
      ts: generatedAt,
      event: 'deploy_plan_rendered',
      status: plan.verdict === 'ready_for_manual_review_not_deployed' ? 'ok' : 'blocked',
      external_api_calls_performed: false,
      secret_values_read_or_printed: false
    }
  ].map((event) => JSON.stringify(event)).join('\n') + '\n'
);

console.log(JSON.stringify({
  verdict: plan.verdict,
  summary: `runs/deploy_plan/${runId}/summary.json`,
  event_flow: `runs/deploy_plan/${runId}/event_flow.jsonl`
}, null, 2));

if (blocked.length > 0) process.exit(1);

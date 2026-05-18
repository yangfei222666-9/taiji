#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const ROOT = process.cwd();
const STRICT = process.argv.includes('--strict');
const WRITE = !process.argv.includes('--no-write');
const generatedAt = new Date().toISOString();
const runId = generatedAt.replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const outDir = join(ROOT, 'runs', 'preflight', `live_${runId}`);
const events = [];
const checks = [];
const CLI_PROBE_TIMEOUT_MS = Number(process.env.TAIJI_CLI_PROBE_TIMEOUT_MS ?? 15000);

const SECRET_NAMES = new Set([
  'SUPABASE_SERVICE_ROLE',
  'GH_TOKEN',
  'GCP_CREDENTIALS',
  'SUPABASE_DB_URL'
]);

const REQUIRED_ENV = [
  'SUPABASE_URL',
  'SUPABASE_SERVICE_ROLE',
  'DEMO_REQUIRE_INVITE',
  'DEMO_TRIGGER_MODE',
  'DEMO_MAX_ACTIVE_RUNS',
  'DEMO_RUN_TIMEOUT_SECONDS',
  'ARTIFACT_BUCKET',
  'GH_REPO',
  'GH_TOKEN',
  'GH_REF',
  'GH_WORKFLOW',
  'GCP_PROJECT_ID',
  'GCP_REGION',
  'GCP_ARTIFACT_REPOSITORY',
  'CLOUD_RUN_JOB',
  'AGENT_IMAGE_NAME'
];

const MANUAL_GATE_ENV = [
  'GCP_CREDENTIALS'
];

const OPTIONAL_ENV = [
  'ARTIFACT_TTL_HOURS',
  'SUPABASE_DB_URL'
];

const ENV_FILES = ['.env.local', '.env.production.local', '.env.production', '.env'];

function event(stage, status, extra = {}) {
  events.push({
    ts: new Date().toISOString(),
    stage,
    status,
    ...extra
  });
}

function check(name, status, extra = {}) {
  checks.push({
    name,
    status,
    ...extra
  });
}

function parseEnvNames(path) {
  if (!existsSync(path)) return new Set();

  const names = new Set();
  const body = readFileSync(path, 'utf8');
  for (const line of body.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (match) names.add(match[1]);
  }
  return names;
}

function collectEnvSources() {
  const sourcesByName = new Map();

  for (const [name, value] of Object.entries(process.env)) {
    if (value !== undefined && value !== '') {
      sourcesByName.set(name, ['process.env']);
    }
  }

  for (const file of ENV_FILES) {
    const path = join(ROOT, file);
    for (const name of parseEnvNames(path)) {
      const sources = sourcesByName.get(name) ?? [];
      sources.push(file);
      sourcesByName.set(name, sources);
    }
  }

  return sourcesByName;
}

function commandVersion(command, args = ['--version']) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    encoding: 'utf8',
    timeout: Number.isFinite(CLI_PROBE_TIMEOUT_MS) && CLI_PROBE_TIMEOUT_MS > 0 ? CLI_PROBE_TIMEOUT_MS : 15000
  });

  if (result.error) {
    check(`cli:${command}`, 'blocked', { reason: result.error.code || result.error.message });
    return;
  }

  if (result.status !== 0) {
    check(`cli:${command}`, 'blocked', { reason: `exit_${result.status}` });
    return;
  }

  const firstLine = `${result.stdout || result.stderr}`.split(/\r?\n/).find(Boolean) ?? 'version_detected';
  check(`cli:${command}`, 'ok', { version: firstLine.slice(0, 80) });
}

function read(path) {
  return readFileSync(join(ROOT, path), 'utf8');
}

function includes(path, text) {
  return read(path).includes(text);
}

event('preflight_started', 'ok', {
  strict: STRICT,
  write_artifacts: WRITE,
  external_api_calls: false,
  secret_values_read_or_printed: false
});

const envSources = collectEnvSources();

for (const name of REQUIRED_ENV) {
  const sources = envSources.get(name) ?? [];
  check(`env:${name}`, sources.length > 0 ? 'ok' : 'blocked', {
    exists: sources.length > 0,
    sources,
    secret: SECRET_NAMES.has(name)
  });
}

for (const name of MANUAL_GATE_ENV) {
  const sources = envSources.get(name) ?? [];
  check(`env_manual:${name}`, sources.length > 0 ? 'ok' : 'manual_required', {
    exists: sources.length > 0,
    sources,
    secret: SECRET_NAMES.has(name),
    note: 'GitHub Actions secret; not required in local .env for preflight'
  });
}

for (const name of OPTIONAL_ENV) {
  const sources = envSources.get(name) ?? [];
  check(`env_optional:${name}`, sources.length > 0 ? 'ok' : 'missing_nonblocking', {
    exists: sources.length > 0,
    sources,
    secret: SECRET_NAMES.has(name)
  });
}

const publicSecretNames = [...SECRET_NAMES].map((name) => `NEXT_PUBLIC_${name}`);
const foundPublicSecrets = publicSecretNames.filter((name) => envSources.has(name));
check('forbidden_public_secret_names', foundPublicSecrets.length === 0 ? 'ok' : 'blocked', {
  found: foundPublicSecrets.map((name) => ({
    name,
    sources: envSources.get(name) ?? []
  }))
});

if (process.env.DEMO_RUN_TIMEOUT_SECONDS) {
  const timeout = Number(process.env.DEMO_RUN_TIMEOUT_SECONDS);
  const ok = Number.isFinite(timeout) && timeout > 0 && timeout <= 30;
  check('env:DEMO_RUN_TIMEOUT_SECONDS_value', ok ? 'ok' : 'blocked', {
    value_kind: 'non_secret_number',
    max_allowed_seconds: 30
  });
} else {
  check('env:DEMO_RUN_TIMEOUT_SECONDS_value', 'missing_nonblocking', {
    reason: 'value only checked from process.env to avoid reading env file values'
  });
}

for (const [command, args] of [
  ['node', ['--version']],
  ['npm', ['--version']],
  ['python3', ['--version']],
  ['git', ['--version']],
  ['docker', ['--version']],
  ['gcloud', ['--version']],
  ['vercel', ['--version']]
]) {
  commandVersion(command, args);
}

check('workflow:ephemeral_dispatch', includes('.github/workflows/ephemeral-run.yml', 'workflow_dispatch') && includes('.github/workflows/ephemeral-run.yml', 'run_id') ? 'ok' : 'blocked');
check('workflow:cloud_run_wait', includes('.github/workflows/ephemeral-run.yml', 'gcloud run jobs execute') && includes('.github/workflows/ephemeral-run.yml', '--wait') ? 'ok' : 'blocked');
check('workflow:deploy_agent_manual_only', includes('.github/workflows/deploy-agent.yml', 'workflow_dispatch') && !includes('.github/workflows/deploy-agent.yml', 'push:') ? 'ok' : 'blocked');
check('workflow:deploy_agent_timeout', includes('.github/workflows/deploy-agent.yml', '--task-timeout=30s') && includes('.github/workflows/deploy-agent.yml', '--max-retries=0') ? 'ok' : 'blocked');
check('runbook:cloud_run_timeout', includes('docs/fork-deploy-runbook.md', '--task-timeout=30s') ? 'ok' : 'blocked');
check('runbook:no_public_service_role_warning', includes('docs/fork-deploy-runbook.md', 'NEXT_PUBLIC_*') ? 'ok' : 'blocked');
check('schema:rls_enabled', includes('db/schema.sql', 'alter table public.invites enable row level security') && includes('db/schema.sql', 'alter table public.runs enable row level security') && includes('db/schema.sql', 'alter table public.run_artifacts enable row level security') ? 'ok' : 'blocked');
check('schema:private_bucket', includes('db/schema.sql', "'taiji-artifacts'") && includes('db/schema.sql', 'false,') ? 'ok' : 'blocked');
check('api:no_public_service_role_source', !includes('lib/supabase.ts', 'NEXT_PUBLIC_SUPABASE_SERVICE_ROLE') ? 'ok' : 'blocked');

const blockers = checks.filter((item) => item.status === 'blocked');
const missingEnv = checks.filter((item) => item.name.startsWith('env:') && item.status === 'blocked');
const missingManualEnv = checks.filter((item) => item.name.startsWith('env_manual:') && item.status === 'manual_required');
const verdict = blockers.length === 0
  ? 'ready_for_manual_external_gate'
  : missingEnv.length > 0
    ? 'blocked_missing_env'
    : 'blocked_preflight';

event('preflight_completed', verdict.startsWith('ready') ? 'ok' : 'blocked', {
  verdict,
  blocked_count: blockers.length,
  missing_required_env_count: missingEnv.length,
  missing_manual_env_count: missingManualEnv.length
});

const summary = {
  schema_version: 'taiji_sandbox.live_preflight.v0',
  generated_at: generatedAt,
  verdict,
  strict: STRICT,
  external_api_calls_performed: false,
  secret_values_read_or_printed: false,
  env_files_scanned_for_names_only: ENV_FILES.filter((file) => existsSync(join(ROOT, file))),
  checked_count: checks.length,
  blocked_count: blockers.length,
  missing_required_env_count: missingEnv.length,
  missing_manual_env_count: missingManualEnv.length,
  checks,
  next_allowed_action: verdict === 'ready_for_manual_external_gate'
    ? 'request_human_approval_before_supabase_vercel_github_gcp_live_actions'
    : 'fill_missing_env_or_install_missing_local_cli_then_rerun_preflight'
};

if (WRITE) {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
  writeFileSync(join(outDir, 'event_flow.jsonl'), `${events.map((item) => JSON.stringify(item)).join('\n')}\n`);
  summary.artifacts = {
    summary: `runs/preflight/live_${runId}/summary.json`,
    event_flow: `runs/preflight/live_${runId}/event_flow.jsonl`
  };
  writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
}

console.log(JSON.stringify(summary, null, 2));
if (STRICT && blockers.length > 0) process.exit(1);

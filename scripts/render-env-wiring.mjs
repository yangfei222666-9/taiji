#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import process from 'node:process';

const ENV_FILES = ['.env.local', '.env.production.local', '.env.production', '.env'];
const SECRET_NAMES = new Set([
  'SUPABASE_SERVICE_ROLE',
  'GH_TOKEN',
  'GCP_CREDENTIALS',
  'SUPABASE_DB_URL'
]);

const ENV_MATRIX = [
  { name: 'SUPABASE_URL', target: 'vercel,cloud_run', required: true, secret: false, note: 'Supabase project URL' },
  { name: 'SUPABASE_SERVICE_ROLE', target: 'vercel,cloud_run', required: true, secret: true, note: 'Server-side service role only; never NEXT_PUBLIC' },
  { name: 'DEMO_REQUIRE_INVITE', target: 'vercel', required: true, secret: false, note: 'true for invitation demo' },
  { name: 'DEMO_TRIGGER_MODE', target: 'vercel', required: true, secret: false, note: 'mock locally, github for deployed invitation path' },
  { name: 'DEMO_MAX_ACTIVE_RUNS', target: 'vercel', required: true, secret: false, note: 'active queued/running cap' },
  { name: 'DEMO_RUN_TIMEOUT_SECONDS', target: 'vercel,cloud_run', required: true, secret: false, note: '30 or less' },
  { name: 'ARTIFACT_BUCKET', target: 'vercel,cloud_run', required: true, secret: false, note: 'default taiji-artifacts' },
  { name: 'GH_REPO', target: 'vercel', required: true, secret: false, note: 'owner/repo for workflow_dispatch' },
  { name: 'GH_TOKEN', target: 'vercel', required: true, secret: true, note: 'GitHub token with workflow dispatch permission' },
  { name: 'GH_REF', target: 'vercel', required: true, secret: false, note: 'usually main' },
  { name: 'GH_WORKFLOW', target: 'vercel', required: true, secret: false, note: 'ephemeral-run.yml' },
  { name: 'GCP_PROJECT_ID', target: 'github_actions', required: true, secret: false, note: 'GitHub Actions variable' },
  { name: 'GCP_REGION', target: 'github_actions', required: true, secret: false, note: 'GitHub Actions variable, e.g. us-central1' },
  { name: 'GCP_ARTIFACT_REPOSITORY', target: 'github_actions', required: true, secret: false, note: 'Artifact Registry repo name' },
  { name: 'CLOUD_RUN_JOB', target: 'github_actions', required: true, secret: false, note: 'Cloud Run Job name' },
  { name: 'AGENT_IMAGE_NAME', target: 'github_actions', required: true, secret: false, note: 'agent image name' },
  { name: 'GCP_CREDENTIALS', target: 'github_actions', required: false, manual_required: true, secret: true, note: 'GitHub Actions secret for google-github-actions/auth; do not store in .env.local just to satisfy local preflight' },
  { name: 'ARTIFACT_TTL_HOURS', target: 'cloud_run', required: false, secret: false, note: 'optional cleanup window, default 24' },
  { name: 'SUPABASE_DB_URL', target: 'local_operator', required: false, secret: true, note: 'optional local psql seed helper' }
];

const CLI_MATRIX = [
  { name: 'node', required: true, target: 'local_verify' },
  { name: 'npm', required: true, target: 'local_verify' },
  { name: 'python3', required: true, target: 'local_verify' },
  { name: 'git', required: true, target: 'local_verify' },
  { name: 'docker', required: true, target: 'agent_image_build' },
  { name: 'gcloud', required: true, target: 'cloud_run_job' },
  { name: 'vercel', required: false, target: 'vercel_deploy' }
];

const CLI_PROBE_TIMEOUT_MS = Number(process.env.TAIJI_CLI_PROBE_TIMEOUT_MS ?? 15000);

function usage() {
  return `Usage:
  npm run env:wiring
  npm run env:wiring -- --out-dir runs/env_wiring/manual

Options:
  --out-dir <path>  Output directory. Default: runs/env_wiring/<timestamp>.
  --help            Show this help.
`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--out-dir') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) throw new Error('--out-dir requires a value');
      args.outDir = value;
      i += 1;
    } else {
      throw new Error(`unknown option: ${arg}`);
    }
  }
  return args;
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
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

function collectEnvSources(root) {
  const sourcesByName = new Map();
  for (const [name, value] of Object.entries(process.env)) {
    if (value !== undefined && value !== '') sourcesByName.set(name, ['process.env']);
  }

  for (const file of ENV_FILES) {
    const path = join(root, file);
    for (const name of parseEnvNames(path)) {
      const sources = sourcesByName.get(name) ?? [];
      sources.push(file);
      sourcesByName.set(name, sources);
    }
  }

  return sourcesByName;
}

function commandStatus(command) {
  const result = spawnSync(command, ['--version'], {
    encoding: 'utf8',
    timeout: Number.isFinite(CLI_PROBE_TIMEOUT_MS) && CLI_PROBE_TIMEOUT_MS > 0 ? CLI_PROBE_TIMEOUT_MS : 15000
  });

  if (result.error) return { exists: false, reason: result.error.code || result.error.message };
  if (result.status !== 0) return { exists: false, reason: `exit_${result.status}` };
  const version = `${result.stdout || result.stderr}`.split(/\r?\n/).find(Boolean) ?? 'version_detected';
  return { exists: true, version: version.slice(0, 80) };
}

function renderMarkdown(summary) {
  const envRows = summary.env.map((item) => {
    const status = item.exists ? 'ok' : item.required ? 'missing' : item.manual_required ? 'manual_missing' : 'optional_missing';
    return `| ${item.name} | ${item.target} | ${item.secret ? 'yes' : 'no'} | ${item.required ? 'yes' : 'no'} | ${item.manual_required ? 'yes' : 'no'} | ${status} | ${item.sources.join(', ') || '-'} |`;
  }).join('\n');

  const cliRows = summary.cli.map((item) => {
    const status = item.exists ? 'ok' : item.required ? 'missing' : 'optional_missing';
    return `| ${item.name} | ${item.target} | ${item.required ? 'yes' : 'no'} | ${status} | ${item.version || item.reason || '-'} |`;
  }).join('\n');

  return `# Taiji Sandbox Env Wiring

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Boundary

- This is a manual wiring packet, not a deploy proof.
- No external API calls were performed.
- Secret values were not read or printed.
- Secret rows identify names only.

## Env Matrix

| Name | Target | Secret | Local Required | Manual Gate | Status | Sources |
| --- | --- | --- | --- | --- | --- | --- |
${envRows}

## CLI Matrix

| CLI | Target | Required | Status | Evidence |
| --- | --- | --- | --- | --- |
${cliRows}
`;
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    if (args.help) {
      process.stdout.write(usage());
      return;
    }

    const root = process.cwd();
    const generatedAt = new Date().toISOString();
    const outDir = args.outDir || join('runs', 'env_wiring', timestamp());
    const envSources = collectEnvSources(root);
    const env = ENV_MATRIX.map((item) => ({
      ...item,
      secret: item.secret || SECRET_NAMES.has(item.name),
      exists: envSources.has(item.name),
      sources: envSources.get(item.name) ?? []
    }));
    const cli = CLI_MATRIX.map((item) => ({
      ...item,
      ...commandStatus(item.name)
    }));

    const missingRequiredEnv = env.filter((item) => item.required && !item.exists);
    const missingManualEnv = env.filter((item) => item.manual_required && !item.exists);
    const missingRequiredCli = cli.filter((item) => item.required && !item.exists);
    const verdict = missingRequiredEnv.length === 0 && missingRequiredCli.length === 0
      ? 'env_wiring_ready_for_strict_preflight'
      : 'manual_env_wiring_required';

    const summary = {
      schema_version: 'taiji_sandbox.env_wiring.v0',
      verdict,
      generated_at: generatedAt,
      missing_required_env_count: missingRequiredEnv.length,
      missing_manual_env_count: missingManualEnv.length,
      missing_manual_env: missingManualEnv.map((item) => ({
        name: item.name,
        target: item.target,
        secret: item.secret,
        note: item.note
      })),
      missing_required_cli_count: missingRequiredCli.length,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      env_files_scanned_for_names_only: ENV_FILES.filter((file) => existsSync(join(root, file))),
      env,
      cli,
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        matrix: join(outDir, 'env_matrix.json'),
        report: join(outDir, 'env_wiring.md')
      },
      next_allowed_action: verdict === 'env_wiring_ready_for_strict_preflight'
        ? 'rerun npm run preflight:live:strict before any external action'
        : 'fill missing env names and install/provide missing CLI tools without exposing secret values'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'env_wiring_rendered',
        status: verdict,
        missing_required_env_count: missingRequiredEnv.length,
        missing_manual_env_count: missingManualEnv.length,
        missing_required_cli_count: missingRequiredCli.length,
        external_api_calls_performed: false,
        secret_values_read_or_printed: false
      }
    ];

    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${eventFlow.map((event) => JSON.stringify(event)).join('\n')}\n`);
    writeFileSync(join(outDir, 'env_matrix.json'), `${JSON.stringify({ generated_at: generatedAt, env, cli }, null, 2)}\n`);
    writeFileSync(join(outDir, 'env_wiring.md'), renderMarkdown(summary));
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`env:wiring failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

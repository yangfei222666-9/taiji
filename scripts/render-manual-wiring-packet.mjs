#!/usr/bin/env node
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

const TARGETS = [
  {
    id: 'supabase',
    label: 'Supabase project',
    required_env: ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE', 'ARTIFACT_BUCKET'],
    required_files: ['db/schema.sql', 'db/seed.sql'],
    required_checks: [
      'Apply db/schema.sql and db/seed.sql in the Supabase project.',
      'Confirm RLS is enabled on public.invites, public.runs, and public.run_artifacts.',
      'Confirm anon/authenticated grants remain revoked for runtime tables.',
      'Confirm bucket taiji-artifacts is private.'
    ],
    secret_boundary: 'SUPABASE_SERVICE_ROLE is server/agent only and must never use a NEXT_PUBLIC name.'
  },
  {
    id: 'vercel',
    label: 'Vercel project env',
    required_env: [
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
      'GH_WORKFLOW'
    ],
    required_files: ['app/api/start_run/route.ts', 'app/api/run_status/route.ts', 'app/api/artifacts/route.ts'],
    required_checks: [
      'Use DEMO_TRIGGER_MODE=github for deployed invitation path.',
      'Keep DEMO_RUN_TIMEOUT_SECONDS at 30 or less.',
      'Do not create NEXT_PUBLIC_SUPABASE_SERVICE_ROLE or any public service-role alias.'
    ],
    secret_boundary: 'GH_TOKEN and SUPABASE_SERVICE_ROLE are Vercel server-side env only.'
  },
  {
    id: 'github_actions',
    label: 'GitHub Actions variables and secrets',
    required_env: [
      'GCP_PROJECT_ID',
      'GCP_REGION',
      'GCP_ARTIFACT_REPOSITORY',
      'CLOUD_RUN_JOB',
      'AGENT_IMAGE_NAME',
      'GCP_CREDENTIALS'
    ],
    required_files: ['.github/workflows/ephemeral-run.yml', '.github/workflows/deploy-agent.yml'],
    required_checks: [
      'Store GCP_CREDENTIALS as a GitHub Actions secret, not a repo file.',
      'Keep deploy-agent.yml manual-only via workflow_dispatch.',
      'Run one workflow_dispatch only after live preflight is ready and human approval is explicit.'
    ],
    secret_boundary: 'GCP_CREDENTIALS is a GitHub secret only; do not paste it into local artifacts.'
  },
  {
    id: 'cloud_run',
    label: 'Cloud Run Job',
    required_env: ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE', 'ARTIFACT_BUCKET', 'DEMO_RUN_TIMEOUT_SECONDS'],
    required_files: ['agent/Dockerfile', 'agent/main.py', 'agent/requirements.txt'],
    required_checks: [
      'Job timeout must stay at 30 seconds.',
      'Max retries must stay 0 for demo cost control.',
      'Agent must upload artifacts to private Supabase Storage and record run_artifacts rows.'
    ],
    secret_boundary: 'Use Cloud Run secrets or trusted env injection; do not bake secrets into the image.'
  },
  {
    id: 'local_operator',
    label: 'Local operator machine',
    required_env: [],
    required_cli: ['node', 'npm', 'python3', 'git', 'docker', 'gcloud'],
    required_files: ['package.json', 'scripts/verify-local.mjs', 'scripts/preflight-live.mjs'],
    required_checks: [
      'Run npm run verify:full before any external gate.',
      'Run npm run preflight:live:strict before deploy or tester invite.',
      'If strict preflight is blocked, stop and update artifacts instead of dispatching workflows.'
    ],
    secret_boundary: 'Local checks may verify name presence only; they must not print secret values.'
  }
];

function usage() {
  return `Usage:
  npm run wiring:packet
  npm run wiring:packet -- --out-dir runs/manual_wiring/manual

Options:
  --out-dir <path>  Output directory. Default: runs/manual_wiring/<timestamp>.
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

function collectSummaryFiles(root, dir, files = []) {
  const absolute = join(root, dir);
  if (!existsSync(absolute)) return files;

  for (const entry of readdirSync(absolute)) {
    const full = join(absolute, entry);
    const stat = statSync(full);
    const rel = join(dir, entry).replaceAll('\\', '/');
    if (stat.isDirectory()) collectSummaryFiles(root, rel, files);
    else if (entry === 'summary.json') files.push({ path: rel, mtimeMs: stat.mtimeMs });
  }

  return files;
}

function latestJson(root, dir) {
  const files = collectSummaryFiles(root, dir).sort((a, b) => b.mtimeMs - a.mtimeMs);
  if (files.length === 0) return null;
  return {
    path: files[0].path,
    data: JSON.parse(readFileSync(join(root, files[0].path), 'utf8'))
  };
}

function envLookup(envWiring) {
  const map = new Map();
  for (const item of envWiring?.data?.env ?? []) map.set(item.name, item);
  return map;
}

function cliLookup(envWiring) {
  const map = new Map();
  for (const item of envWiring?.data?.cli ?? []) map.set(item.name, item);
  return map;
}

function targetStatus(target, envMap, cliMap) {
  const env = (target.required_env ?? []).map((name) => {
    const item = envMap.get(name);
    return {
      name,
      exists: item?.exists === true,
      secret: item?.secret === true,
      target: item?.target ?? target.id
    };
  });
  const cli = (target.required_cli ?? []).map((name) => {
    const item = cliMap.get(name);
    return {
      name,
      exists: item?.exists === true,
      reason: item?.reason ?? null
    };
  });
  const files = (target.required_files ?? []).map((path) => ({
    path,
    exists: existsSync(path)
  }));

  const missingEnv = env.filter((item) => !item.exists);
  const missingCli = cli.filter((item) => !item.exists);
  const missingFiles = files.filter((item) => !item.exists);

  return {
    ...target,
    env,
    cli,
    files,
    status: missingEnv.length === 0 && missingCli.length === 0 && missingFiles.length === 0 ? 'ready_for_manual_review' : 'blocked',
    missing_env: missingEnv.map((item) => item.name),
    missing_cli: missingCli.map((item) => item.name),
    missing_files: missingFiles.map((item) => item.path)
  };
}

function renderMarkdown(summary) {
  const targetSections = summary.targets.map((target) => {
    const envRows = target.env.map((item) => `| ${item.name} | ${item.exists ? 'exists' : 'missing'} | ${item.secret ? 'yes' : 'no'} |`).join('\n');
    const cliRows = target.cli.map((item) => `| ${item.name} | ${item.exists ? 'exists' : 'missing'} | ${item.reason || '-'} |`).join('\n');
    const fileRows = target.files.map((item) => `| ${item.path} | ${item.exists ? 'exists' : 'missing'} |`).join('\n');
    const checks = target.required_checks.map((item) => `- ${item}`).join('\n');
    return `## ${target.label}

Status: \`${target.status}\`

Secret boundary: ${target.secret_boundary}

### Env

| Name | Status | Secret |
| --- | --- | --- |
${envRows || '| - | - | - |'}

### CLI

| Name | Status | Evidence |
| --- | --- | --- |
${cliRows || '| - | - | - |'}

### Files

| Path | Status |
| --- | --- |
${fileRows || '| - | - |'}

### Checks

${checks}
`;
  }).join('\n');

  return `# Taiji Sandbox Manual Wiring Packet

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Boundary

- This packet is local-only handoff evidence, not a deploy proof.
- No external API calls were performed.
- Secret values were not read or printed.
- Do not paste service-role keys, GitHub tokens, GCP credentials, or DB URLs into repo artifacts.
- Supabase Data API grants and RLS are separate controls; this starter keeps browser access behind Next.js API routes.
- Supabase Storage private access uses Storage RLS; service keys bypass RLS and must stay server/agent-side.

## Evidence

- Env wiring: ${summary.evidence.env_wiring || 'missing'}
- Live preflight: ${summary.evidence.live_preflight || 'missing'}
- Next actions: ${summary.evidence.next_actions || 'missing'}

${targetSections}

## Command Order After Manual Wiring

1. npm run env:wiring
2. npm run preflight:live:strict
3. npm run readiness:report
4. npm run next:actions

## Prohibited Until Strict Preflight Passes

- Deploy
- GitHub workflow_dispatch
- Tester invites
- Public release links
- Git stage, commit, push, tag, or PR without explicit human confirmation
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
    const outDir = args.outDir || join('runs', 'manual_wiring', timestamp());
    const envWiring = latestJson(root, 'runs/env_wiring');
    const livePreflight = latestJson(root, 'runs/preflight');
    const nextActions = latestJson(root, 'runs/next_actions');
    const hasEvidence = envWiring && livePreflight && nextActions;
    const envMap = envLookup(envWiring);
    const cliMap = cliLookup(envWiring);
    const targets = TARGETS.map((target) => targetStatus(target, envMap, cliMap));
    const blockedTargets = targets.filter((target) => target.status === 'blocked');

    const verdict = !hasEvidence
      ? 'blocked_missing_manual_wiring_evidence'
      : blockedTargets.length === 0
        ? 'manual_wiring_packet_ready_for_human_review'
        : 'manual_wiring_required';

    const summary = {
      schema_version: 'taiji_sandbox.manual_wiring.v0',
      verdict,
      generated_at: generatedAt,
      blocked_target_count: blockedTargets.length,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      deploy_allowed: false,
      invite_testers_allowed: false,
      evidence: {
        env_wiring: envWiring?.path ?? null,
        live_preflight: livePreflight?.path ?? null,
        next_actions: nextActions?.path ?? null
      },
      targets,
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        checklist: join(outDir, 'manual_wiring_checklist.json'),
        report: join(outDir, 'manual_wiring_packet.md')
      },
      next_allowed_action: 'complete manual env/CLI wiring outside chat, then rerun the four-command gate chain'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'manual_wiring_packet_rendered',
        status: verdict,
        blocked_target_count: blockedTargets.length,
        external_api_calls_performed: false,
        secret_values_read_or_printed: false
      }
    ];

    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${eventFlow.map((event) => JSON.stringify(event)).join('\n')}\n`);
    writeFileSync(join(outDir, 'manual_wiring_checklist.json'), `${JSON.stringify({ generated_at: generatedAt, targets }, null, 2)}\n`);
    writeFileSync(join(outDir, 'manual_wiring_packet.md'), renderMarkdown(summary));
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`wiring:packet failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

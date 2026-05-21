#!/usr/bin/env node
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

function usage() {
  return `Usage:
  npm run next:actions
  npm run next:actions -- --out-dir runs/next_actions/manual

Options:
  --out-dir <path>  Output directory. Default: runs/next_actions/<timestamp>.
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

function namesFromEnvWiring(envWiring) {
  if (!envWiring?.data?.env) return [];
  return envWiring.data.env.filter((item) => item.required && !item.exists).map((item) => ({
    name: item.name,
    target: item.target,
    secret: item.secret
  }));
}

function manualNamesFromEnvWiring(envWiring) {
  if (!envWiring?.data?.env) return [];
  return envWiring.data.env.filter((item) => item.manual_required && !item.exists).map((item) => ({
    name: item.name,
    target: item.target,
    secret: item.secret,
    note: item.note
  }));
}

function cliFromEnvWiring(envWiring) {
  if (!envWiring?.data?.cli) return [];
  return envWiring.data.cli.filter((item) => item.required && !item.exists).map((item) => ({
    name: item.name,
    target: item.target,
    reason: item.reason
  }));
}

function renderMarkdown(summary) {
  const envRows = summary.missing_required_env.map((item) => `| ${item.name} | ${item.target} | ${item.secret ? 'yes' : 'no'} |`).join('\n');
  const manualEnvRows = summary.missing_manual_env.map((item) => `| ${item.name} | ${item.target} | ${item.secret ? 'yes' : 'no'} | ${item.note || '-'} |`).join('\n');
  const cliRows = summary.missing_required_cli.map((item) => `| ${item.name} | ${item.target} | ${item.reason || '-'} |`).join('\n');
  const allowed = summary.allowed_actions.map((item) => `- ${item}`).join('\n');
  const prohibited = summary.prohibited_actions.map((item) => `- ${item}`).join('\n');
  const commands = summary.command_order.map((item, index) => `${index + 1}. ${item}`).join('\n');

  return `# Taiji Sandbox Next Actions

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Evidence

- Release readiness: ${summary.evidence.release_readiness || 'missing'}
- Env wiring: ${summary.evidence.env_wiring || 'missing'}
- Live preflight: ${summary.evidence.live_preflight || 'missing'}

## Missing Env Names

| Name | Target | Secret |
| --- | --- | --- |
${envRows || '| - | - | - |'}

## Manual Gate Env

| Name | Target | Secret | Note |
| --- | --- | --- | --- |
${manualEnvRows || '| - | - | - | - |'}

## Missing CLI

| CLI | Target | Reason |
| --- | --- | --- |
${cliRows || '| - | - | - |'}

## Allowed Actions

${allowed}

## Prohibited Actions

${prohibited}

## Command Order

${commands}

## Boundary

This packet does not call external APIs, does not read or print secret values, does not install tools, does not deploy, and does not invite testers.
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
    const outDir = args.outDir || join('runs', 'next_actions', timestamp());
    const releaseReadiness = latestJson(root, 'runs/readiness');
    const envWiring = latestJson(root, 'runs/env_wiring');
    const livePreflight = latestJson(root, 'runs/preflight');
    const missingRequiredEnv = namesFromEnvWiring(envWiring);
    const missingManualEnv = manualNamesFromEnvWiring(envWiring);
    const missingRequiredCli = cliFromEnvWiring(envWiring);
    const cloudRuntimeReady = releaseReadiness?.data?.cloud_runtime_ready === true;
    const deployAllowed = releaseReadiness?.data?.deploy_allowed === true;
    const inviteTestersAllowed = releaseReadiness?.data?.invite_testers_allowed === true;
    const hasMissingEvidence = !releaseReadiness || !envWiring || !livePreflight;

    const releaseReady = deployAllowed && inviteTestersAllowed;
    const verdict = hasMissingEvidence
      ? 'blocked_missing_next_action_evidence'
      : releaseReady
        ? 'ready_for_manual_release_review_actions'
        : 'blocked_next_actions_available';

    const allowedActions = releaseReady
      ? [
        'request explicit human approval before any deploy, workflow_dispatch, push, or tester invite',
        'review release readiness evidence paths',
        'run one manual end-to-end verification after approved deploy'
      ]
      : [
        'fill missing env names outside chat without exposing secret values',
        'configure GitHub-only manual secrets in GitHub Actions, not in repo artifacts',
        'install or provide missing local CLI tools outside this run',
        'rerun npm run env:wiring',
        'rerun npm run preflight:live:strict',
        'rerun npm run readiness:report'
      ];

    const prohibitedActions = [
      'do not deploy',
      'do not dispatch GitHub workflows',
      'do not invite testers',
      'do not paste secret values into chat or repo artifacts',
      'do not mark cloud runtime ready while live preflight is blocked',
      'do not stage, commit, push, tag, or create PR without explicit confirmation'
    ];

    const commandOrder = [
      'npm run env:wiring',
      'npm run preflight:live:strict',
      'npm run readiness:report',
      'npm run next:actions',
      'npm run deploy:gate'
    ];

    const summary = {
      schema_version: 'taiji_sandbox.next_actions.v0',
      verdict,
      generated_at: generatedAt,
      cloud_runtime_ready: cloudRuntimeReady,
      deploy_allowed: deployAllowed,
      invite_testers_allowed: inviteTestersAllowed,
      missing_required_env_count: missingRequiredEnv.length,
      missing_manual_env_count: missingManualEnv.length,
      missing_required_cli_count: missingRequiredCli.length,
      missing_required_env: missingRequiredEnv,
      missing_manual_env: missingManualEnv,
      missing_required_cli: missingRequiredCli,
      allowed_actions: allowedActions,
      prohibited_actions: prohibitedActions,
      command_order: commandOrder,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      evidence: {
        release_readiness: releaseReadiness?.path ?? null,
        env_wiring: envWiring?.path ?? null,
        live_preflight: livePreflight?.path ?? null
      },
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        report: join(outDir, 'next_actions.md')
      },
      next_allowed_action: releaseReady
        ? 'request explicit human approval before external action'
        : 'manual env/CLI wiring outside chat, then rerun command order'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'next_actions_rendered',
        status: verdict,
        cloud_runtime_ready: cloudRuntimeReady,
        deploy_allowed: deployAllowed,
        invite_testers_allowed: inviteTestersAllowed,
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
    writeFileSync(join(outDir, 'next_actions.md'), renderMarkdown(summary));
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`next:actions failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

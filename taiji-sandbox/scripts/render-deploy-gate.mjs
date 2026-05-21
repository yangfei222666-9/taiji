#!/usr/bin/env node
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

function usage() {
  return `Usage:
  npm run deploy:gate
  npm run deploy:gate -- --remote-secret-confirmed
  npm run deploy:gate -- --out-dir runs/deploy_gate/manual

Options:
  --remote-secret-confirmed  Human confirms GCP_CREDENTIALS exists in GitHub Actions Secrets.
  --out-dir <path>           Output directory. Default: runs/deploy_gate/<timestamp>.
  --help                     Show this help.
`;
}

function parseArgs(argv) {
  const args = { remoteSecretConfirmed: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--remote-secret-confirmed') args.remoteSecretConfirmed = true;
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

function renderMarkdown(summary) {
  const evidenceRows = Object.entries(summary.evidence)
    .map(([name, path]) => `| ${name} | ${path || 'missing'} |`)
    .join('\n');
  const blockerRows = summary.blockers
    .map((item) => `| ${item.stage} | ${item.reason} | ${item.minimum_fix} |`)
    .join('\n');

  return `# Taiji Sandbox Deploy Gate

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Decision

- Local release readiness: ${summary.local_release_ready}
- Remote GitHub secret confirmed by human: ${summary.remote_secret_confirmed_by_human}
- Deploy gate ready for explicit external approval: ${summary.ready_for_explicit_external_action_approval}
- Deploy executed: ${summary.deploy_executed}
- Workflow dispatched: ${summary.workflow_dispatched}

## Evidence

| Gate | Summary |
| --- | --- |
${evidenceRows}

## Blockers

| Stage | Reason | Minimum Fix |
| --- | --- | --- |
${blockerRows || '| - | - | - |'}

## Boundary

This gate does not call external APIs, does not read or print secret values, does not dispatch GitHub Actions, and does not deploy.
`;
}

function manualWiringOnlyBlockedByGithubSecret(manualWiring) {
  if (!manualWiring?.data || manualWiring.data.verdict !== 'manual_wiring_required') return false;
  const blockedTargets = (manualWiring.data.targets ?? []).filter((target) => target.status === 'blocked');
  if (blockedTargets.length !== 1) return false;

  const [target] = blockedTargets;
  return target.id === 'github_actions'
    && (target.missing_env ?? []).length === 1
    && target.missing_env[0] === 'GCP_CREDENTIALS'
    && (target.missing_cli ?? []).length === 0
    && (target.missing_files ?? []).length === 0;
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
    const outDir = args.outDir || join('runs', 'deploy_gate', timestamp());
    const readiness = latestJson(root, 'runs/readiness');
    const manualWiring = latestJson(root, 'runs/manual_wiring');
    const livePreflight = latestJson(root, 'runs/preflight');
    const envWiring = latestJson(root, 'runs/env_wiring');
    const missingEvidence = [
      ['readiness', readiness],
      ['manual_wiring', manualWiring],
      ['live_preflight', livePreflight],
      ['env_wiring', envWiring]
    ].filter(([, item]) => !item).map(([name]) => name);

    const manualWiringReady = manualWiring?.data?.verdict === 'manual_wiring_packet_ready_for_human_review';
    const manualWiringSatisfiedByRemoteSecret = args.remoteSecretConfirmed
      && manualWiringOnlyBlockedByGithubSecret(manualWiring);
    const readinessCoreReady = readiness?.data?.local_source_review_ready === true
      && readiness?.data?.deploy_plan_ready === true
      && readiness?.data?.tester_packet_ready === true
      && readiness?.data?.cloud_runtime_ready === true
      && (readiness?.data?.required_missing_count ?? 0) === 0
      && (readiness?.data?.required_blocked_count ?? 0) === 0;
    const localReleaseReady = readinessCoreReady
      && (manualWiringReady || manualWiringSatisfiedByRemoteSecret)
      && livePreflight?.data?.verdict === 'ready_for_manual_external_gate';

    const blockers = [];
    if (missingEvidence.length > 0) {
      blockers.push({
        stage: 'deploy_gate.evidence',
        reason: `missing gate evidence: ${missingEvidence.join(', ')}`,
        minimum_fix: 'rerun npm run env:wiring, npm run preflight:live:strict, npm run wiring:packet, and npm run readiness:report'
      });
    }

    if (!localReleaseReady) {
      blockers.push({
        stage: 'deploy_gate.local_release_readiness',
        reason: `readiness=${readiness?.data?.verdict ?? 'missing'}, manual_wiring=${manualWiring?.data?.verdict ?? 'missing'}, live_preflight=${livePreflight?.data?.verdict ?? 'missing'}`,
        minimum_fix: 'clear local readiness and manual wiring gates before any deploy approval'
      });
    }

    if (!args.remoteSecretConfirmed) {
      blockers.push({
        stage: 'deploy_gate.remote_secret_confirmation',
        reason: 'GCP_CREDENTIALS has not been confirmed by a human in GitHub Actions Secrets for this gate artifact',
        minimum_fix: 'confirm the secret exists in GitHub UI, then rerun npm run deploy:gate -- --remote-secret-confirmed'
      });
    }

    const readyForApproval = blockers.length === 0;
    const verdict = missingEvidence.length > 0
      ? 'blocked_missing_deploy_gate_evidence'
      : !localReleaseReady
        ? 'blocked_local_release_readiness'
        : !args.remoteSecretConfirmed
          ? 'blocked_remote_secret_confirmation_required'
          : 'ready_for_explicit_external_action_approval';

    const summary = {
      schema_version: 'taiji_sandbox.deploy_gate.v0',
      verdict,
      generated_at: generatedAt,
      local_release_ready: localReleaseReady,
      readiness_core_ready: readinessCoreReady,
      manual_wiring_ready: manualWiringReady,
      manual_wiring_satisfied_by_remote_secret_confirmation: manualWiringSatisfiedByRemoteSecret,
      remote_secret_confirmed_by_human: args.remoteSecretConfirmed,
      ready_for_explicit_external_action_approval: readyForApproval,
      deploy_executed: false,
      workflow_dispatched: false,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      evidence: {
        readiness: readiness?.path ?? null,
        manual_wiring: manualWiring?.path ?? null,
        live_preflight: livePreflight?.path ?? null,
        env_wiring: envWiring?.path ?? null
      },
      blockers,
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        report: join(outDir, 'deploy_gate.md')
      },
      next_allowed_action: readyForApproval
        ? 'request explicit human approval before deploy-agent workflow_dispatch or any external deploy action'
        : 'clear deploy gate blockers without exposing secret values'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'deploy_gate_rendered',
        status: verdict,
        local_release_ready: localReleaseReady,
        remote_secret_confirmed_by_human: args.remoteSecretConfirmed,
        ready_for_explicit_external_action_approval: readyForApproval,
        deploy_executed: false,
        workflow_dispatched: false,
        external_api_calls_performed: false,
        secret_values_read_or_printed: false
      }
    ];

    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${eventFlow.map((event) => JSON.stringify(event)).join('\n')}\n`);
    writeFileSync(join(outDir, 'deploy_gate.md'), renderMarkdown(summary));
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`deploy:gate failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

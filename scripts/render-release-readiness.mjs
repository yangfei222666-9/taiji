#!/usr/bin/env node
import { parseOutputArgs as parseArgs, timestamp, latestJson } from './report-utils.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

const GATES = [
  {
    name: 'env_wiring',
    globRoot: 'runs/env_wiring',
    readyVerdicts: ['manual_env_wiring_required', 'env_wiring_ready_for_strict_preflight'],
    required: false
  },
  {
    name: 'fork_readiness',
    globRoot: 'runs/fork_readiness',
    readyVerdicts: ['ready_for_fork_source_review'],
    required: true
  },
  {
    name: 'deploy_plan',
    globRoot: 'runs/deploy_plan',
    readyVerdicts: ['ready_for_manual_review_not_deployed'],
    required: true
  },
  {
    name: 'tester_packet',
    globRoot: 'runs/tester_packet',
    readyVerdicts: ['ready_for_token_injection_not_sent'],
    required: true
  },
  {
    name: 'live_preflight',
    globRoot: 'runs/preflight',
    readyVerdicts: ['ready_for_manual_external_gate'],
    required: true
  },
  {
    name: 'next_actions',
    globRoot: 'runs/next_actions',
    readyVerdicts: ['blocked_next_actions_available', 'ready_for_manual_release_review_actions'],
    required: false
  },
  {
    name: 'manual_wiring',
    globRoot: 'runs/manual_wiring',
    readyVerdicts: ['manual_wiring_packet_ready_for_human_review'],
    required: false
  }
];

function usage() {
  return `Usage:
  npm run readiness:report
  npm run readiness:report -- --out-dir runs/readiness/manual

Options:
  --out-dir <path>  Output directory. Default: runs/readiness/<timestamp>.
  --help            Show this help.
`;
}

function latestSummary(root, gate) {
  const latest = latestJson(root, gate.globRoot);
  if (!latest) {
    return {
      gate: gate.name,
      status: 'missing',
      ready: false,
      required: gate.required,
      reason: `missing ${gate.globRoot}/**/summary.json`
    };
  }

  const { path: summaryPath, data } = latest;
  const ready = gate.readyVerdicts.includes(data.verdict);
  return {
    gate: gate.name,
    status: ready ? 'ready' : 'blocked',
    ready,
    required: gate.required,
    summary: summaryPath,
    verdict: data.verdict,
    generated_at: data.generated_at,
    blocked_count: data.blocked_count,
    missing_required_env_count: data.missing_required_env_count,
    missing_manual_env_count: data.missing_manual_env_count,
    blocked_target_count: data.blocked_target_count,
    source_file_count: data.source_file_count,
    raw_invite_token_matches: data.raw_invite_token_matches,
    external_api_calls_performed: data.external_api_calls_performed,
    secret_values_read_or_printed: data.secret_values_read_or_printed
  };
}

function renderMarkdown(summary) {
  const rows = summary.gates.map((gate) => {
    const evidence = gate.summary || gate.reason;
    return `| ${gate.gate} | ${gate.status} | ${gate.verdict || 'missing'} | ${evidence} |`;
  }).join('\n');

  return `# Taiji Sandbox Release Readiness

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Decision

- Local source review ready: ${summary.local_source_review_ready}
- Tester packet ready: ${summary.tester_packet_ready}
- Deploy plan ready for manual review: ${summary.deploy_plan_ready}
- Cloud runtime ready: ${summary.cloud_runtime_ready}
- Manual wiring ready: ${summary.manual_wiring_ready}
- Invite testers allowed: ${summary.invite_testers_allowed}
- Deploy allowed: ${summary.deploy_allowed}

## Gates

| Gate | Status | Verdict | Evidence |
| --- | --- | --- | --- |
${rows}

## Boundary

This report is an aggregator. It does not call external APIs, does not read or print secret values, does not dispatch GitHub Actions, and does not deploy.
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
    const outDir = args.outDir || join('runs', 'readiness', timestamp());
    const gates = GATES.map((gate) => latestSummary(root, gate));
    const byName = Object.fromEntries(gates.map((gate) => [gate.gate, gate]));
    const localSourceReviewReady = byName.fork_readiness?.ready === true;
    const envWiringAvailable = byName.env_wiring?.ready === true;
    const deployPlanReady = byName.deploy_plan?.ready === true;
    const testerPacketReady = byName.tester_packet?.ready === true;
    const cloudRuntimeReady = byName.live_preflight?.ready === true;
    const manualWiringReady = byName.manual_wiring?.ready === true;
    const manualWiringBlocked = byName.manual_wiring?.status === 'blocked' || byName.manual_wiring?.status === 'missing';
    const requiredMissing = gates.filter((gate) => gate.required && gate.status === 'missing');
    const requiredBlocked = gates.filter((gate) => gate.required && gate.status === 'blocked');
    const inviteTestersAllowed = localSourceReviewReady && deployPlanReady && testerPacketReady && cloudRuntimeReady && manualWiringReady;
    const deployAllowed = deployPlanReady && cloudRuntimeReady && manualWiringReady;

    const verdict = requiredMissing.length > 0
      ? 'blocked_missing_local_gate_artifacts'
      : cloudRuntimeReady && manualWiringBlocked
        ? 'local_release_packet_ready_manual_wiring_blocked'
        : cloudRuntimeReady
        ? 'ready_for_manual_release_review'
        : 'local_release_packet_ready_cloud_runtime_blocked';

    const summary = {
      schema_version: 'taiji_sandbox.release_readiness.v0',
      verdict,
      generated_at: generatedAt,
      local_source_review_ready: localSourceReviewReady,
      env_wiring_available: envWiringAvailable,
      deploy_plan_ready: deployPlanReady,
      tester_packet_ready: testerPacketReady,
      cloud_runtime_ready: cloudRuntimeReady,
      manual_wiring_ready: manualWiringReady,
      manual_wiring_blocked: manualWiringBlocked,
      invite_testers_allowed: inviteTestersAllowed,
      deploy_allowed: deployAllowed,
      required_missing_count: requiredMissing.length,
      required_blocked_count: requiredBlocked.length,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      gates,
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        report: join(outDir, 'release_readiness.md')
      },
      next_allowed_action: inviteTestersAllowed
        ? 'manual release review before deploy or tester invite'
        : 'fix blocked gates before deploy or tester invite'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'release_readiness_rendered',
        status: verdict,
        local_source_review_ready: localSourceReviewReady,
        env_wiring_available: envWiringAvailable,
        deploy_plan_ready: deployPlanReady,
        tester_packet_ready: testerPacketReady,
        cloud_runtime_ready: cloudRuntimeReady,
        manual_wiring_ready: manualWiringReady,
        manual_wiring_blocked: manualWiringBlocked,
        invite_testers_allowed: inviteTestersAllowed,
        external_api_calls_performed: false,
        secret_values_read_or_printed: false
      }
    ];

    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${eventFlow.map((event) => JSON.stringify(event)).join('\n')}\n`);
    writeFileSync(join(outDir, 'release_readiness.md'), renderMarkdown(summary));

    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`readiness:report failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

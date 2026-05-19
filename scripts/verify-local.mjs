#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = process.cwd();
const checks = [];

function pass(name, details = {}) {
  checks.push({ name, status: 'ok', ...details });
}

function fail(name, message, details = {}) {
  checks.push({ name, status: 'failed', message, ...details });
}

function requireFile(path) {
  const ok = existsSync(join(root, path));
  if (ok) pass(`file:${path}`);
  else fail(`file:${path}`, 'missing required file');
}

function read(path) {
  return readFileSync(join(root, path), 'utf8');
}

function expectIncludes(name, path, needles) {
  const body = read(path);
  const missing = needles.filter((needle) => !body.includes(needle));
  if (missing.length === 0) pass(name, { path });
  else fail(name, `missing: ${missing.join(', ')}`, { path });
}

function expectAbsent(name, path, needles) {
  const body = read(path);
  const found = needles.filter((needle) => body.includes(needle));
  if (found.length === 0) pass(name, { path });
  else fail(name, `forbidden text found: ${found.join(', ')}`, { path });
}

[
  'README.md',
  '.env.example',
  'package.json',
  'package-lock.json',
  'next.config.js',
  'app/page.tsx',
  'app/dashboard/page.tsx',
  'app/api/start_run/route.ts',
  'app/api/run_status/route.ts',
  'app/api/artifacts/route.ts',
  'components/RunButton.tsx',
  'components/StatusCard.tsx',
  'components/ArtifactList.tsx',
  'lib/supabase.ts',
  'lib/auth.ts',
  'lib/github.ts',
  'lib/cloudrun.ts',
  'db/schema.sql',
  'db/seed.sql',
  'agent/Dockerfile',
  'agent/main.py',
  'agent/requirements.txt',
  'scripts/create-invite.mjs',
  'scripts/render-env-wiring.mjs',
  'scripts/render-tester-packet.mjs',
  'scripts/render-fork-readiness.mjs',
  'scripts/render-release-readiness.mjs',
  'scripts/render-next-actions.mjs',
  'scripts/render-manual-wiring-packet.mjs',
  'scripts/verify-e2e-evidence-contract.mjs',
  'scripts/preflight-live.mjs',
  'scripts/render-deploy-plan.mjs',
  'scripts/render-deploy-gate.mjs',
  '.github/workflows/ephemeral-run.yml',
  '.github/workflows/deploy-agent.yml',
  '.github/workflows/ci.yml',
  'docs/architecture.md',
  'docs/env-wiring.md',
  'docs/invite-checklist.md',
  'docs/pricing.md',
  'docs/live-preflight.md',
  'docs/manual-wiring-packet.md',
  'docs/next-actions.md',
  'docs/deploy-agent-workflow.md',
  'docs/fork-readiness.md',
  'docs/release-readiness.md',
  'docs/deploy-gate.md',
  'docs/fork-deploy-runbook.md'
].forEach(requireFile);

try {
  const packageJson = JSON.parse(read('package.json'));
  const lockJson = JSON.parse(read('package-lock.json'));
  const requiredScripts = ['dev', 'build', 'start', 'typecheck', 'preflight:live', 'preflight:live:strict', 'e2e:evidence', 'env:wiring', 'deploy:plan', 'deploy:gate', 'invite:create', 'tester:packet', 'fork:readiness', 'readiness:report', 'next:actions', 'wiring:packet', 'verify:local', 'verify:full'];
  const missingScripts = requiredScripts.filter((name) => !packageJson.scripts?.[name]);
  if (missingScripts.length === 0) pass('package:scripts');
  else fail('package:scripts', `missing scripts: ${missingScripts.join(', ')}`);
  if (lockJson.packages?.['node_modules/postcss']?.version?.startsWith('8.5.')) {
    pass('package:postcss_override', { version: lockJson.packages['node_modules/postcss'].version });
  } else {
    fail('package:postcss_override', 'postcss lockfile version is not in expected fixed range');
  }
} catch (error) {
  fail('package:json_parse', error.message);
}

expectIncludes('env:required_names', '.env.example', [
  'SUPABASE_URL=',
  'SUPABASE_SERVICE_ROLE=',
  'DEMO_REQUIRE_INVITE=',
  'DEMO_MAX_ACTIVE_RUNS=',
  'DEMO_RUN_TIMEOUT_SECONDS=30',
  'ARTIFACT_BUCKET=',
  'ARTIFACT_TTL_HOURS=',
  'DEMO_TRIGGER_MODE=',
  'GH_REPO=',
  'GH_TOKEN=',
  'GH_REF=',
  'GH_WORKFLOW=',
  'GCP_PROJECT_ID=',
  'GCP_REGION=',
  'GCP_ARTIFACT_REPOSITORY=',
  'CLOUD_RUN_JOB=',
  'AGENT_IMAGE_NAME='
]);
expectAbsent('env:no_public_service_role', '.env.example', ['NEXT_PUBLIC_SUPABASE_SERVICE_ROLE']);

expectIncludes('schema:core_tables', 'db/schema.sql', [
  'create table if not exists public.invites',
  'create table if not exists public.runs',
  'create table if not exists public.run_artifacts',
  'create or replace function public.consume_invite_run',
  'alter table public.invites enable row level security',
  'alter table public.runs enable row level security',
  'alter table public.run_artifacts enable row level security',
  'revoke all on public.invites from anon, authenticated',
  'grant all on public.runs to service_role',
  "'taiji-artifacts'",
  'public,'
]);

expectIncludes('api:start_run_contract', 'app/api/start_run/route.ts', [
  'active_run_limit_reached',
  'consumeInviteToken(supabase, inviteToken)',
  "status: 'cancelled'",
  'triggerRun(data.id)',
  'completeMockRun(data.id)'
]);

const startRun = read('app/api/start_run/route.ts');
const capIndex = startRun.indexOf('active_run_limit_reached');
const consumeIndex = startRun.indexOf('consumeInviteToken(supabase, inviteToken)');
if (capIndex > -1 && consumeIndex > capIndex) {
  pass('api:quota_after_active_cap');
} else {
  fail('api:quota_after_active_cap', 'invite quota must not be consumed before active-run cap check');
}

expectIncludes('api:artifact_signed_urls', 'app/api/artifacts/route.ts', [
  'createSignedUrl',
  'assertRunAccess'
]);

expectIncludes('supabase:server_only_client', 'lib/supabase.ts', [
  'getSupabaseAdmin',
  'persistSession: false',
  'SUPABASE_SERVICE_ROLE'
]);

expectAbsent('supabase:no_public_service_role_in_source', 'lib/supabase.ts', ['NEXT_PUBLIC_SUPABASE_SERVICE_ROLE']);

expectIncludes('workflow:ephemeral_run', '.github/workflows/ephemeral-run.yml', [
  'workflow_dispatch',
  'run_id',
  'google-github-actions/auth@v2',
  'google-github-actions/setup-gcloud@v2',
  'gcloud run jobs execute',
  '--wait'
]);

expectIncludes('workflow:ci', '.github/workflows/ci.yml', [
  'npm ci --ignore-scripts',
  'npm run verify:full',
  'python-version'
]);

expectIncludes('workflow:deploy_agent', '.github/workflows/deploy-agent.yml', [
  'workflow_dispatch',
  'google-github-actions/auth@v2',
  'gcloud auth configure-docker',
  'docker build',
  'docker push',
  'gcloud run jobs',
  '--task-timeout=30s',
  '--max-retries=0'
]);
expectAbsent('workflow:deploy_agent_manual_only', '.github/workflows/deploy-agent.yml', ['push:', 'pull_request:']);

expectIncludes('agent:timeout_and_cleanup', 'agent/main.py', [
  'DEMO_RUN_TIMEOUT_SECONDS',
  'signal.alarm',
  'CLEANUP_MODE',
  'run_artifacts',
  'storage://'
]);

expectIncludes('docs:runbook', 'docs/fork-deploy-runbook.md', [
  'Fork Gate',
  'npm run fork:readiness',
  'npm run env:wiring',
  'npm run readiness:report',
  'npm run next:actions',
  'Deploy Gate',
  'Invite Gate',
  'Live Verification Gate'
]);

expectIncludes('docs:live_preflight', 'docs/live-preflight.md', [
  'No Secret Values',
  'blocked_missing_env',
  'preflight:live:strict'
]);

expectIncludes('script:env_wiring', 'scripts/render-env-wiring.mjs', [
  'manual_env_wiring_required',
  'env_wiring_ready_for_strict_preflight',
  'secret_values_read_or_printed: false',
  'external_api_calls_performed: false',
  'manual_required',
  'runs/env_wiring',
  'SUPABASE_SERVICE_ROLE',
  'GCP_CREDENTIALS'
]);

expectIncludes('docs:env_wiring', 'docs/env-wiring.md', [
  'npm run env:wiring',
  'manual_env_wiring_required',
  'does not call external APIs',
  'does not call external APIs, install tools, deploy'
]);

expectIncludes('script:next_actions', 'scripts/render-next-actions.mjs', [
  'blocked_next_actions_available',
  'prohibited_actions',
  'command_order',
  'missing_manual_env',
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'runs/next_actions'
]);

expectIncludes('script:manual_wiring_packet', 'scripts/render-manual-wiring-packet.mjs', [
  'manual_wiring_required',
  'manual_wiring_packet_ready_for_human_review',
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'runs',
  'manual_wiring',
  'SUPABASE_SERVICE_ROLE',
  'NEXT_PUBLIC_SUPABASE_SERVICE_ROLE',
  'GCP_CREDENTIALS'
]);

expectIncludes('docs:manual_wiring_packet', 'docs/manual-wiring-packet.md', [
  'npm run wiring:packet',
  'does not read or print secret values',
  'does not create `.env` files',
  'Supabase Data API access is controlled by both SQL grants and RLS'
]);

expectIncludes('docs:next_actions', 'docs/next-actions.md', [
  'npm run next:actions',
  'npm run deploy:gate',
  'blocked_next_actions_available',
  'Deploy, workflow dispatch, and tester invites remain forbidden'
]);

const envWiring = spawnSync('node', [
  'scripts/render-env-wiring.mjs',
  '--out-dir',
  'runs/env_wiring/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (envWiring.status !== 0) {
  fail('script:env_wiring_run', envWiring.stderr || envWiring.stdout || 'env wiring failed');
} else {
  try {
    const envSummary = JSON.parse(read('runs/env_wiring/verify-local/summary.json'));
    const envEvents = read('runs/env_wiring/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
    const secretRows = envSummary.env.filter((item) => item.secret);
    if (!['manual_env_wiring_required', 'env_wiring_ready_for_strict_preflight'].includes(envSummary.verdict)) {
      fail('script:env_wiring_run', 'unexpected env wiring verdict');
    } else if (envSummary.external_api_calls_performed !== false || envSummary.secret_values_read_or_printed !== false) {
      fail('script:env_wiring_run', 'env wiring must be local-only and secret-safe');
    } else if (secretRows.length < 3) {
      fail('script:env_wiring_run', 'secret rows missing from env matrix');
    } else if (envEvents.length < 1) {
      fail('script:env_wiring_run', 'missing env wiring event flow');
    } else {
      pass('script:env_wiring_run', {
        verdict: envSummary.verdict,
        missing_required_env_count: envSummary.missing_required_env_count,
        missing_required_cli_count: envSummary.missing_required_cli_count
      });
    }
  } catch (error) {
    fail('script:env_wiring_run', error.message);
  }
}

expectIncludes('docs:invite_checklist', 'docs/invite-checklist.md', [
  'npm run invite:create',
  'npm run tester:packet',
  '{{INVITE_TOKEN}}',
  '--print-token',
  'bearer secrets',
  'Store only `sha256(token)`'
]);

expectIncludes('script:create_invite', 'scripts/create-invite.mjs', [
  'randomBytes',
  'createHash',
  'sha256',
  '--print-token',
  'token_redacted',
  'insert into public.invites'
]);

const inviteCreate = spawnSync('node', ['scripts/create-invite.mjs', '--email', 'verify@example.com', '--max-runs', '1', '--expires-at', '2030-01-01T00:00:00.000Z'], {
  cwd: root,
  encoding: 'utf8'
});
if (inviteCreate.status !== 0) {
  fail('script:create_invite_redacted_run', inviteCreate.stderr || inviteCreate.stdout || 'invite create failed');
} else if (!inviteCreate.stdout.includes('token_redacted=true')) {
  fail('script:create_invite_redacted_run', 'redacted run did not mark token_redacted=true');
} else if (inviteCreate.stdout.includes('tj_inv_')) {
  fail('script:create_invite_redacted_run', 'redacted run printed an invite token');
} else if (!inviteCreate.stdout.includes('insert into public.invites')) {
  fail('script:create_invite_redacted_run', 'redacted run did not emit invite SQL');
} else {
  pass('script:create_invite_redacted_run');
}

expectIncludes('script:tester_packet', 'scripts/render-tester-packet.mjs', [
  'ready_for_token_injection_not_sent',
  '{{INVITE_TOKEN}}',
  'raw_invite_token_written: false',
  'external_api_calls_performed: false',
  'runs',
  'tester_packet'
]);

const testerPacket = spawnSync('node', [
  'scripts/render-tester-packet.mjs',
  '--email',
  'verify@example.com',
  '--app-url',
  'https://example.com',
  '--max-runs',
  '1',
  '--expires-at',
  '2030-01-01T00:00:00.000Z',
  '--out-dir',
  'runs/tester_packet/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (testerPacket.status !== 0) {
  fail('script:tester_packet_run', testerPacket.stderr || testerPacket.stdout || 'tester packet failed');
} else {
  try {
    const packetSummary = JSON.parse(read('runs/tester_packet/verify-local/summary.json'));
    const packetBody = read('runs/tester_packet/verify-local/tester_packet.md');
    if (packetSummary.verdict !== 'ready_for_token_injection_not_sent') {
      fail('script:tester_packet_run', 'unexpected packet verdict');
    } else if (packetSummary.raw_invite_token_written !== false) {
      fail('script:tester_packet_run', 'packet summary did not mark raw_invite_token_written=false');
    } else if (!packetBody.includes('{{INVITE_TOKEN}}')) {
      fail('script:tester_packet_run', 'packet body missing token placeholder');
    } else if (packetBody.includes('tj_inv_')) {
      fail('script:tester_packet_run', 'packet body contains raw invite token pattern');
    } else {
      pass('script:tester_packet_run');
    }
  } catch (error) {
    fail('script:tester_packet_run', error.message);
  }
}

expectIncludes('script:fork_readiness', 'scripts/render-fork-readiness.mjs', [
  'ready_for_fork_source_review',
  'source_manifest.json',
  'scripts/render-env-wiring.mjs',
  'scripts/render-release-readiness.mjs',
  'scripts/render-next-actions.mjs',
  'raw_invite_token_matches',
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'node_modules',
  'runs'
]);

expectIncludes('docs:fork_readiness', 'docs/fork-readiness.md', [
  'npm run fork:readiness',
  'source_manifest.json',
  'raw `tj_inv_*` invite token pattern',
  'does not call external APIs'
]);

const forkReadiness = spawnSync('node', [
  'scripts/render-fork-readiness.mjs',
  '--allow-local-env-files',
  '--out-dir',
  'runs/fork_readiness/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (forkReadiness.status !== 0) {
  fail('script:fork_readiness_run', forkReadiness.stderr || forkReadiness.stdout || 'fork readiness failed');
} else {
  try {
    const forkSummary = JSON.parse(read('runs/fork_readiness/verify-local/summary.json'));
    const forkManifest = JSON.parse(read('runs/fork_readiness/verify-local/source_manifest.json'));
    const manifestPaths = forkManifest.files.map((file) => file.path);
    const hasForbidden = manifestPaths.some((path) => path.startsWith('node_modules/') || path.startsWith('runs/') || path.startsWith('.next/'));
    if (forkSummary.verdict !== 'ready_for_fork_source_review') {
      fail('script:fork_readiness_run', 'unexpected fork readiness verdict');
    } else if (forkSummary.raw_invite_token_matches !== 0) {
      fail('script:fork_readiness_run', 'raw invite token pattern found');
    } else if (hasForbidden) {
      fail('script:fork_readiness_run', 'manifest contains forbidden generated path');
    } else if (!manifestPaths.includes('scripts/render-fork-readiness.mjs')) {
      fail('script:fork_readiness_run', 'manifest missing fork readiness script');
    } else {
      pass('script:fork_readiness_run', { source_file_count: forkSummary.source_file_count });
    }
  } catch (error) {
    fail('script:fork_readiness_run', error.message);
  }
}

const deployPlanRun = spawnSync('node', ['scripts/render-deploy-plan.mjs'], {
  cwd: root,
  encoding: 'utf8'
});
if (deployPlanRun.status !== 0) {
  fail('script:deploy_plan_run', deployPlanRun.stderr || deployPlanRun.stdout || 'deploy plan failed');
} else {
  try {
    const deployPlanSummary = JSON.parse(deployPlanRun.stdout);
    if (deployPlanSummary.verdict !== 'ready_for_manual_review_not_deployed') {
      fail('script:deploy_plan_run', 'unexpected deploy plan verdict');
    } else {
      pass('script:deploy_plan_run');
    }
  } catch (error) {
    fail('script:deploy_plan_run', error.message);
  }
}

const livePreflight = spawnSync('node', ['scripts/preflight-live.mjs'], {
  cwd: root,
  encoding: 'utf8'
});
if (livePreflight.status !== 0) {
  fail('script:live_preflight_run', livePreflight.stderr || livePreflight.stdout || 'live preflight failed');
} else {
  try {
    const preflightSummary = JSON.parse(livePreflight.stdout);
    if (!['blocked_missing_env', 'ready_for_manual_external_gate'].includes(preflightSummary.verdict)) {
      fail('script:live_preflight_run', 'unexpected live preflight verdict');
    } else if (preflightSummary.external_api_calls_performed !== false || preflightSummary.secret_values_read_or_printed !== false) {
      fail('script:live_preflight_run', 'live preflight must be local-only and secret-safe');
    } else {
      pass('script:live_preflight_run', {
        blocked_count: preflightSummary.blocked_count,
        missing_required_env_count: preflightSummary.missing_required_env_count
      });
      const e2eDir = join(root, 'runs/e2e_evidence_contract/verify-local');
      const e2eEvidencePath = join(e2eDir, 'evidence.json');
      const declaredSkips = ['external_api_call', 'secret_value_read', 'workflow_dispatch', 'cloud_run_job_execute', 'deployment'];
      const actualSkips = ['workflow_dispatch', 'cloud_run_job_execute', 'deployment'];
      if (preflightSummary.external_api_calls_performed === false) actualSkips.push('external_api_call');
      if (preflightSummary.secret_values_read_or_printed === false) actualSkips.push('secret_value_read');
      mkdirSync(e2eDir, { recursive: true });
      writeFileSync(e2eEvidencePath, `${JSON.stringify({
        live: 'off',
        declared_skips: declaredSkips,
        actual_skips: actualSkips.sort(),
        executed_stages: ['verify_local', 'live_preflight_local_check', 'e2e_evidence_written'],
        blocked_stage: null,
        source_artifacts: {
          live_preflight_summary: preflightSummary.artifacts?.summary ?? null,
          live_preflight_event_flow: preflightSummary.artifacts?.event_flow ?? null
        }
      }, null, 2)}\n`);
      const e2eEvidence = spawnSync('node', [
        'scripts/verify-e2e-evidence-contract.mjs',
        '--evidence',
        'runs/e2e_evidence_contract/verify-local/evidence.json',
        '--out-dir',
        'runs/e2e_evidence_contract/verify-local',
        '--expected-live',
        'off'
      ], {
        cwd: root,
        encoding: 'utf8'
      });
      if (e2eEvidence.status !== 0) {
        fail('script:e2e_evidence_contract_run', e2eEvidence.stderr || e2eEvidence.stdout || 'e2e evidence contract failed');
      } else {
        try {
          const e2eSummary = JSON.parse(read('runs/e2e_evidence_contract/verify-local/summary.json'));
          const e2eEvents = read('runs/e2e_evidence_contract/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
          if (e2eSummary.verdict !== 'ok_e2e_evidence_contract_verified') {
            fail('script:e2e_evidence_contract_run', 'unexpected e2e evidence verdict');
          } else if (e2eSummary.external_api_called !== false || e2eSummary.trade_or_paper_buy_performed !== false) {
            fail('script:e2e_evidence_contract_run', 'e2e evidence contract must stay offline and no-trade');
          } else if (e2eEvents.length < 1) {
            fail('script:e2e_evidence_contract_run', 'missing e2e evidence event flow');
          } else {
            pass('script:e2e_evidence_contract_run', { verdict: e2eSummary.verdict });
          }
        } catch (error) {
          fail('script:e2e_evidence_contract_run', error.message);
        }
      }
    }
  } catch (error) {
    fail('script:live_preflight_run', error.message);
  }
}

expectIncludes('script:release_readiness', 'scripts/render-release-readiness.mjs', [
  'local_release_packet_ready_cloud_runtime_blocked',
  'env_wiring_available',
  'invite_testers_allowed',
  'deploy_allowed',
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'runs/readiness'
]);

expectIncludes('docs:release_readiness', 'docs/release-readiness.md', [
  'npm run readiness:report',
  'local_release_packet_ready_cloud_runtime_blocked',
  'Do not invite testers or deploy'
]);

const releaseReadiness = spawnSync('node', [
  'scripts/render-release-readiness.mjs',
  '--out-dir',
  'runs/readiness/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (releaseReadiness.status !== 0) {
  fail('script:release_readiness_run', releaseReadiness.stderr || releaseReadiness.stdout || 'release readiness failed');
} else {
  try {
    const releaseSummary = JSON.parse(read('runs/readiness/verify-local/summary.json'));
    const releaseEvents = read('runs/readiness/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
    if (!['local_release_packet_ready_cloud_runtime_blocked', 'local_release_packet_ready_manual_wiring_blocked'].includes(releaseSummary.verdict)) {
      fail('script:release_readiness_run', 'unexpected release readiness verdict');
    } else if (releaseSummary.invite_testers_allowed !== false || releaseSummary.deploy_allowed !== false) {
      fail('script:release_readiness_run', 'blocked cloud runtime must not allow deploy or tester invites');
    } else if (releaseSummary.external_api_calls_performed !== false || releaseSummary.secret_values_read_or_printed !== false) {
      fail('script:release_readiness_run', 'release readiness must be local-only and secret-safe');
    } else if (releaseEvents.length < 1) {
      fail('script:release_readiness_run', 'missing release readiness event flow');
    } else {
      pass('script:release_readiness_run');
    }
  } catch (error) {
    fail('script:release_readiness_run', error.message);
  }
}

const nextActions = spawnSync('node', [
  'scripts/render-next-actions.mjs',
  '--out-dir',
  'runs/next_actions/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (nextActions.status !== 0) {
  fail('script:next_actions_run', nextActions.stderr || nextActions.stdout || 'next actions failed');
} else {
  try {
    const nextSummary = JSON.parse(read('runs/next_actions/verify-local/summary.json'));
    const nextEvents = read('runs/next_actions/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
    if (nextSummary.verdict !== 'blocked_next_actions_available') {
      fail('script:next_actions_run', 'unexpected next actions verdict');
    } else if (nextSummary.deploy_allowed !== false || nextSummary.invite_testers_allowed !== false) {
      fail('script:next_actions_run', 'blocked next actions must not allow deploy or tester invites');
    } else if (nextSummary.external_api_calls_performed !== false || nextSummary.secret_values_read_or_printed !== false) {
      fail('script:next_actions_run', 'next actions must be local-only and secret-safe');
    } else if (!nextSummary.prohibited_actions.some((item) => item.includes('do not deploy'))) {
      fail('script:next_actions_run', 'missing deploy prohibition');
    } else if (nextEvents.length < 1) {
      fail('script:next_actions_run', 'missing next actions event flow');
    } else {
      pass('script:next_actions_run', {
        verdict: nextSummary.verdict,
        missing_required_env_count: nextSummary.missing_required_env_count,
        missing_required_cli_count: nextSummary.missing_required_cli_count
      });
    }
  } catch (error) {
    fail('script:next_actions_run', error.message);
  }
}

const manualWiring = spawnSync('node', [
  'scripts/render-manual-wiring-packet.mjs',
  '--out-dir',
  'runs/manual_wiring/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (manualWiring.status !== 0) {
  fail('script:manual_wiring_packet_run', manualWiring.stderr || manualWiring.stdout || 'manual wiring packet failed');
} else {
  try {
    const wiringSummary = JSON.parse(read('runs/manual_wiring/verify-local/summary.json'));
    const wiringEvents = read('runs/manual_wiring/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
    const wiringReport = read('runs/manual_wiring/verify-local/manual_wiring_packet.md');
    if (!['manual_wiring_required', 'manual_wiring_packet_ready_for_human_review'].includes(wiringSummary.verdict)) {
      fail('script:manual_wiring_packet_run', 'unexpected manual wiring packet verdict');
    } else if (wiringSummary.deploy_allowed !== false || wiringSummary.invite_testers_allowed !== false) {
      fail('script:manual_wiring_packet_run', 'manual wiring packet must not allow deploy or tester invites');
    } else if (wiringSummary.external_api_calls_performed !== false || wiringSummary.secret_values_read_or_printed !== false) {
      fail('script:manual_wiring_packet_run', 'manual wiring packet must be local-only and secret-safe');
    } else if (!wiringSummary.targets.some((target) => target.id === 'supabase')) {
      fail('script:manual_wiring_packet_run', 'missing Supabase target');
    } else if (!wiringReport.includes('Supabase Data API grants and RLS are separate controls')) {
      fail('script:manual_wiring_packet_run', 'missing Supabase RLS/grant boundary');
    } else if (wiringReport.includes('tj_inv_')) {
      fail('script:manual_wiring_packet_run', 'manual wiring packet contains raw invite token pattern');
    } else if (wiringEvents.length < 1) {
      fail('script:manual_wiring_packet_run', 'missing manual wiring event flow');
    } else {
      pass('script:manual_wiring_packet_run', {
        verdict: wiringSummary.verdict,
        blocked_target_count: wiringSummary.blocked_target_count
      });
    }
  } catch (error) {
    fail('script:manual_wiring_packet_run', error.message);
  }
}

expectIncludes('script:live_preflight', 'scripts/preflight-live.mjs', [
  'SECRET_NAMES',
  'forbidden_public_secret_names',
  'blocked_missing_env',
  'runs/preflight',
  '--strict'
]);

expectIncludes('script:e2e_evidence_contract', 'scripts/verify-e2e-evidence-contract.mjs', [
  'declared_skips',
  'actual_skips',
  'executed_stages',
  'live_off_executed_live_stage',
  'external_api_called: false'
]);

expectIncludes('script:deploy_plan', 'scripts/render-deploy-plan.mjs', [
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'runs/deploy_plan',
  'deploy-agent.yml'
]);

expectIncludes('script:deploy_gate', 'scripts/render-deploy-gate.mjs', [
  'blocked_remote_secret_confirmation_required',
  'blocked_local_release_readiness',
  'ready_for_explicit_external_action_approval',
  'remote_secret_confirmed_by_human',
  'manual_wiring_satisfied_by_remote_secret_confirmation',
  'deploy_executed: false',
  'workflow_dispatched: false',
  'external_api_calls_performed: false',
  'secret_values_read_or_printed: false',
  'runs',
  'deploy_gate'
]);

expectIncludes('docs:deploy_gate', 'docs/deploy-gate.md', [
  'npm run deploy:gate',
  '--remote-secret-confirmed',
  'does not call external APIs',
  'deployment still requires explicit human approval'
]);

const deployGate = spawnSync('node', [
  'scripts/render-deploy-gate.mjs',
  '--out-dir',
  'runs/deploy_gate/verify-local'
], {
  cwd: root,
  encoding: 'utf8'
});
if (deployGate.status !== 0) {
  fail('script:deploy_gate_run', deployGate.stderr || deployGate.stdout || 'deploy gate failed');
} else {
  try {
    const gateSummary = JSON.parse(read('runs/deploy_gate/verify-local/summary.json'));
    const gateEvents = read('runs/deploy_gate/verify-local/event_flow.jsonl').trim().split(/\n/).map((line) => JSON.parse(line));
    if (!['blocked_missing_deploy_gate_evidence', 'blocked_local_release_readiness', 'blocked_remote_secret_confirmation_required', 'ready_for_explicit_external_action_approval'].includes(gateSummary.verdict)) {
      fail('script:deploy_gate_run', 'unexpected deploy gate verdict');
    } else if (gateSummary.deploy_executed !== false || gateSummary.workflow_dispatched !== false) {
      fail('script:deploy_gate_run', 'deploy gate must not execute deploy or dispatch workflow');
    } else if (gateSummary.external_api_calls_performed !== false || gateSummary.secret_values_read_or_printed !== false) {
      fail('script:deploy_gate_run', 'deploy gate must be local-only and secret-safe');
    } else if (gateEvents.length < 1) {
      fail('script:deploy_gate_run', 'missing deploy gate event flow');
    } else {
      pass('script:deploy_gate_run', { verdict: gateSummary.verdict });
    }
  } catch (error) {
    fail('script:deploy_gate_run', error.message);
  }
}

const deployGateRemoteConfirmed = spawnSync('node', [
  'scripts/render-deploy-gate.mjs',
  '--remote-secret-confirmed',
  '--out-dir',
  'runs/deploy_gate/verify-local-remote-confirmed'
], {
  cwd: root,
  encoding: 'utf8'
});
if (deployGateRemoteConfirmed.status !== 0) {
  fail('script:deploy_gate_remote_confirmed_run', deployGateRemoteConfirmed.stderr || deployGateRemoteConfirmed.stdout || 'deploy gate remote-confirmed run failed');
} else {
  try {
    const gateSummary = JSON.parse(read('runs/deploy_gate/verify-local-remote-confirmed/summary.json'));
    if (!['blocked_missing_deploy_gate_evidence', 'blocked_local_release_readiness', 'ready_for_explicit_external_action_approval'].includes(gateSummary.verdict)) {
      fail('script:deploy_gate_remote_confirmed_run', 'unexpected remote-confirmed deploy gate verdict');
    } else if (gateSummary.remote_secret_confirmed_by_human !== true) {
      fail('script:deploy_gate_remote_confirmed_run', 'remote-confirmed run did not record human confirmation');
    } else if (gateSummary.deploy_executed !== false || gateSummary.workflow_dispatched !== false) {
      fail('script:deploy_gate_remote_confirmed_run', 'remote-confirmed deploy gate must still not execute deploy or dispatch workflow');
    } else if (gateSummary.external_api_calls_performed !== false || gateSummary.secret_values_read_or_printed !== false) {
      fail('script:deploy_gate_remote_confirmed_run', 'remote-confirmed deploy gate must be local-only and secret-safe');
    } else {
      pass('script:deploy_gate_remote_confirmed_run', { verdict: gateSummary.verdict });
    }
  } catch (error) {
    fail('script:deploy_gate_remote_confirmed_run', error.message);
  }
}

expectIncludes('docs:deploy_agent_workflow', 'docs/deploy-agent-workflow.md', [
  'Manual Only',
  'workflow_dispatch',
  'GCP_CREDENTIALS',
  'not a deployment proof'
]);

const python = spawnSync('python3', ['-m', 'py_compile', 'agent/main.py'], {
  cwd: root,
  encoding: 'utf8'
});
if (python.status === 0) pass('python:agent_py_compile');
else fail('python:agent_py_compile', python.stderr || python.stdout || 'python compile failed');

const failed = checks.filter((check) => check.status !== 'ok');
const summary = {
  verdict: failed.length === 0 ? 'ok' : 'failed',
  generated_at: new Date().toISOString(),
  checked_count: checks.length,
  failed_count: failed.length,
  checks
};

console.log(JSON.stringify(summary, null, 2));
if (failed.length > 0) process.exit(1);

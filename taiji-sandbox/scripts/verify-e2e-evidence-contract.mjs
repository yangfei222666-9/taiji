#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const ROOT = process.cwd();
const DEFAULT_OUT_DIR = 'runs/e2e_evidence_contract/verify-local';
const DEFAULT_LIVE_STAGES = new Set([
  'live',
  'live_provider_call',
  'provider_live_probe',
  'external_provider_call',
  'external_api_call',
  'webhook_send',
  'telegram_send',
  'workflow_dispatch',
  'cloud_run_job_execute',
  'deployment',
  'paper_buy',
  'trade'
]);

const args = process.argv.slice(2);
const generatedAt = new Date().toISOString();
const events = [];

function argValue(name, fallback = null) {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

function argValues(name) {
  const values = [];
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === name && args[index + 1]) values.push(args[index + 1]);
  }
  return values;
}

function writeJson(path, payload) {
  mkdirSync(resolve(ROOT, path, '..'), { recursive: true });
  writeFileSync(resolve(ROOT, path), `${JSON.stringify(payload, null, 2)}\n`);
}

function event(name, extra = {}) {
  events.push({
    ts: new Date().toISOString(),
    event: name,
    ...extra,
    live_provider_called: false,
    secret_accessed: false,
    external_api_called: false,
    external_action_performed: false,
    deployment_performed: false,
    stage_commit_push_pr_performed: false,
    trade_or_paper_buy_performed: false,
    judgment_or_promote_performed: false
  });
}

function readJson(path) {
  return JSON.parse(readFileSync(resolve(ROOT, path), 'utf8'));
}

function stringList(payload, field, failures) {
  if (!Array.isArray(payload[field])) {
    failures.push(`${field}_missing_or_not_list`);
    return [];
  }
  const output = [];
  payload[field].forEach((item, index) => {
    if (typeof item !== 'string' || item.length === 0) failures.push(`${field}_invalid_item:${index}`);
    else output.push(item);
  });
  return output;
}

function defaultEvidence() {
  return {
    live: 'off',
    declared_skips: ['external_api_call', 'secret_value_read', 'workflow_dispatch', 'cloud_run_job_execute', 'deployment'],
    actual_skips: ['external_api_call', 'secret_value_read', 'workflow_dispatch', 'cloud_run_job_execute', 'deployment'],
    executed_stages: ['offline_e2e_contract', 'evidence_written'],
    blocked_stage: null
  };
}

function verify(evidencePath, expectedLive, liveStages) {
  const failures = [];
  let payload = {};

  if (!existsSync(resolve(ROOT, evidencePath))) {
    failures.push(`missing_evidence_json:${evidencePath}`);
  } else {
    try {
      payload = readJson(evidencePath);
    } catch (error) {
      failures.push(`evidence_json_parse_error:${error.message}`);
    }
  }

  const liveValue = payload.live ?? payload.live_mode;
  const liveMode = typeof liveValue === 'boolean' ? (liveValue ? 'on' : 'off') : liveValue;
  if (!['on', 'off'].includes(liveMode)) failures.push('live_mode_invalid_or_missing');
  if (expectedLive && liveMode !== expectedLive) failures.push(`live_mode_mismatch:expected_${expectedLive}:actual_${liveMode}`);

  const declaredSkips = stringList(payload, 'declared_skips', failures);
  const actualSkips = stringList(payload, 'actual_skips', failures);
  const executedStages = stringList(payload, 'executed_stages', failures);
  const blockedStage = payload.blocked_stage ?? null;
  if (blockedStage !== null && typeof blockedStage !== 'string') failures.push('blocked_stage_not_string_or_null');

  const declared = new Set(declaredSkips);
  const actual = new Set(actualSkips);
  const missingFromActual = [...declared].filter((item) => !actual.has(item)).sort();
  const unexpectedActual = [...actual].filter((item) => !declared.has(item)).sort();
  if (missingFromActual.length > 0 || unexpectedActual.length > 0) failures.push('skip_mismatch');

  const forbiddenLiveStages = new Set(liveStages.length > 0 ? liveStages : DEFAULT_LIVE_STAGES);
  const executedLiveStages = executedStages.filter((stage) => forbiddenLiveStages.has(stage)).sort();
  if (liveMode === 'off' && executedLiveStages.length > 0) failures.push('live_off_executed_live_stage');
  if (blockedStage && executedStages.includes(blockedStage)) failures.push('blocked_stage_also_executed');

  const verdict = failures.length > 0 ? 'blocked' : 'ok_e2e_evidence_contract_verified';
  return {
    schema_version: 'taiji_sandbox.e2e_evidence_contract.v0',
    generated_at: generatedAt,
    verdict,
    blocked_stage: failures.length > 0 ? 'e2e_evidence_contract_verification' : null,
    failure_cause: failures,
    evidence_path: evidencePath,
    live_mode: liveMode ?? null,
    expected_live: expectedLive,
    declared_skips: declaredSkips,
    actual_skips: actualSkips,
    executed_stages: executedStages,
    evidence_blocked_stage: blockedStage,
    skip_mismatch: {
      missing_from_actual: missingFromActual,
      unexpected_actual: unexpectedActual
    },
    executed_live_stages: executedLiveStages,
    live_provider_called: false,
    secret_accessed: false,
    external_api_called: false,
    external_action_performed: false,
    deployment_performed: false,
    stage_commit_push_pr_performed: false,
    trade_or_paper_buy_performed: false,
    judgment_or_promote_performed: false
  };
}

const outDir = argValue('--out-dir', DEFAULT_OUT_DIR);
const expectedLive = argValue('--expected-live', 'off');
const liveStages = argValues('--live-stage');
let evidencePath = argValue('--evidence');

event('e2e_evidence_contract_started', { expected_live: expectedLive });

if (!evidencePath) {
  evidencePath = join(outDir, 'evidence.json');
  writeJson(evidencePath, defaultEvidence());
  event('e2e_evidence_contract_default_evidence_written', { evidence_path: evidencePath });
}

const summary = verify(evidencePath, expectedLive, liveStages);
summary.artifacts = {
  evidence: evidencePath,
  summary: join(outDir, 'summary.json'),
  event_flow: join(outDir, 'event_flow.jsonl')
};

event('e2e_evidence_contract_done', {
  verdict: summary.verdict,
  failure_cause: summary.failure_cause,
  evidence_path: evidencePath
});

writeJson(join(outDir, 'summary.json'), summary);
writeFileSync(resolve(ROOT, outDir, 'event_flow.jsonl'), `${events.map((item) => JSON.stringify(item)).join('\n')}\n`);

console.log(JSON.stringify(summary, null, 2));
if (summary.verdict !== 'ok_e2e_evidence_contract_verified') process.exit(1);

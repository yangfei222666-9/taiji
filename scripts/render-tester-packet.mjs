#!/usr/bin/env node
import { timestamp } from './report-utils.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

function usage() {
  return `Usage:
  npm run tester:packet -- --email tester@example.com --app-url https://demo.example.com
  npm run tester:packet -- --email tester@example.com --app-url https://demo.example.com --max-runs 20 --expires-days 14

Options:
  --email <email>            Tester email for the packet.
  --app-url <url>            Deployed app URL or local smoke URL.
  --max-runs <number>       Run quota shown to the tester. Default: 20.
  --expires-days <number>   Expiry window from now. Default: 14.
  --expires-at <iso>        Explicit ISO timestamp. Overrides --expires-days.
  --support <text>          Support contact shown in the packet. Default: Taiji Sandbox operator.
  --out-dir <path>          Output directory. Default: runs/tester_packet/<timestamp>.
  --help                    Show this help.
`;
}

function parseArgs(argv) {
  const args = {
    maxRuns: 20,
    expiresDays: 14,
    support: 'Taiji Sandbox operator'
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) throw new Error(`${arg} requires a value`);
      i += 1;
      return value;
    };

    if (arg === '--email') args.email = next();
    else if (arg === '--app-url') args.appUrl = next();
    else if (arg === '--max-runs') args.maxRuns = Number.parseInt(next(), 10);
    else if (arg === '--expires-days') args.expiresDays = Number.parseInt(next(), 10);
    else if (arg === '--expires-at') args.expiresAt = next();
    else if (arg === '--support') args.support = next();
    else if (arg === '--out-dir') args.outDir = next();
    else if (arg === '--help' || arg === '-h') args.help = true;
    else throw new Error(`unknown option: ${arg}`);
  }

  return args;
}

function validate(args) {
  if (!args.email || !args.email.includes('@') || /[\r\n]/.test(args.email) || args.email.length > 320) {
    throw new Error('--email must be a single email-like value');
  }

  if (!args.appUrl) throw new Error('--app-url is required');
  const url = new URL(args.appUrl);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('--app-url must be http or https');

  if (!Number.isInteger(args.maxRuns) || args.maxRuns < 1 || args.maxRuns > 1000) {
    throw new Error('--max-runs must be an integer from 1 to 1000');
  }

  if (!args.expiresAt && (!Number.isInteger(args.expiresDays) || args.expiresDays < 1 || args.expiresDays > 365)) {
    throw new Error('--expires-days must be an integer from 1 to 365');
  }

  if (args.support && /[\r\n]/.test(args.support)) throw new Error('--support must be one line');
}

function buildExpiry(args) {
  if (args.expiresAt) {
    const date = new Date(args.expiresAt);
    if (Number.isNaN(date.getTime())) throw new Error('--expires-at must be a valid ISO timestamp');
    return date.toISOString();
  }

  return new Date(Date.now() + args.expiresDays * 24 * 60 * 60 * 1000).toISOString();
}

function safeSlug(input) {
  return input.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48) || 'tester';
}

function renderPacket({ email, appUrl, maxRuns, expiresAt, support }) {
  return `# Taiji Sandbox Tester Packet

## Access

- App URL: ${appUrl}
- Tester: ${email}
- Invite token: {{INVITE_TOKEN}}
- Max runs: ${maxRuns}
- Expires at: ${expiresAt}

## Test Path

1. Open the app URL.
2. Paste the invite token into the invite field.
3. Start one demo run.
4. Wait until the run reaches succeeded or failed.
5. Open any returned artifact links.
6. Send the run id and any failure text back to ${support}.

## Boundaries

- Do not share the invite token.
- Do not run load tests.
- Do not paste private credentials into the demo payload.
- Do not treat demo output as production advice.

## Feedback

- Did the run start?
- Did status polling update?
- Did artifacts open?
- Did any screen show an unclear error?
- Approximate time from Start Demo to final status:
`;
}

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    if (args.help) {
      process.stdout.write(usage());
      return;
    }

    validate(args);
    const expiresAt = buildExpiry(args);
    const generatedAt = new Date().toISOString();
    const outDir = args.outDir || join('runs', 'tester_packet', `${timestamp()}_${safeSlug(args.email)}`);
    mkdirSync(outDir, { recursive: true });

    const packet = renderPacket({
      email: args.email,
      appUrl: args.appUrl,
      maxRuns: args.maxRuns,
      expiresAt,
      support: args.support
    });

    const summary = {
      schema_version: 'taiji_sandbox.tester_packet.v0',
      verdict: 'ready_for_token_injection_not_sent',
      generated_at: generatedAt,
      email: args.email,
      app_url: args.appUrl,
      max_runs: args.maxRuns,
      expires_at: expiresAt,
      invite_token_placeholder: '{{INVITE_TOKEN}}',
      raw_invite_token_written: false,
      external_api_calls_performed: false,
      artifacts: {
        packet: join(outDir, 'tester_packet.md'),
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl')
      },
      next_allowed_action: 'manually replace placeholder outside repo when sending to the tester'
    };

    const events = [
      {
        ts: generatedAt,
        event: 'tester_packet_rendered',
        status: 'ok',
        email: args.email,
        app_url: args.appUrl,
        raw_invite_token_written: false,
        external_api_calls_performed: false
      }
    ];

    writeFileSync(join(outDir, 'tester_packet.md'), packet);
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${events.map((event) => JSON.stringify(event)).join('\n')}\n`);

    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`tester:packet failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

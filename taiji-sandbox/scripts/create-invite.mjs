#!/usr/bin/env node
import { createHash, randomBytes } from 'node:crypto';
import process from 'node:process';

function usage() {
  return `Usage:
  npm run invite:create -- --email tester@example.com
  npm run invite:create -- --email tester@example.com --max-runs 20 --expires-days 14
  npm run invite:create -- --email tester@example.com --print-token

Options:
  --email <email>          Tester email stored with the invite.
  --max-runs <number>     Run quota for this invite. Default: 20.
  --expires-days <number> Expiry window from now. Default: 14.
  --expires-at <iso>      Explicit ISO timestamp. Overrides --expires-days.
  --no-expiry             Store expires_at as null. Not recommended for public demos.
  --print-token           Print the bearer invite token once. Do not redirect to files.
  --json                  Emit JSON instead of SQL text.
  --help                  Show this help.
`;
}

function parseArgs(argv) {
  const args = {
    maxRuns: 20,
    expiresDays: 14,
    printToken: false,
    json: false,
    noExpiry: false
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`${arg} requires a value`);
      }
      i += 1;
      return value;
    };

    if (arg === '--email') args.email = next();
    else if (arg === '--max-runs') args.maxRuns = Number.parseInt(next(), 10);
    else if (arg === '--expires-days') args.expiresDays = Number.parseInt(next(), 10);
    else if (arg === '--expires-at') args.expiresAt = next();
    else if (arg === '--no-expiry') args.noExpiry = true;
    else if (arg === '--print-token') args.printToken = true;
    else if (arg === '--json') args.json = true;
    else if (arg === '--help' || arg === '-h') args.help = true;
    else throw new Error(`unknown option: ${arg}`);
  }

  return args;
}

function sqlLiteral(value) {
  if (value === null) return 'null';
  return `'${String(value).replaceAll("'", "''")}'`;
}

function validateEmail(email) {
  if (!email || typeof email !== 'string') throw new Error('--email is required');
  if (email.length > 320 || /[\r\n]/.test(email) || !email.includes('@')) {
    throw new Error('--email must be a single email-like value');
  }
}

function buildExpiry(args) {
  if (args.noExpiry) return null;

  if (args.expiresAt) {
    const date = new Date(args.expiresAt);
    if (Number.isNaN(date.getTime())) throw new Error('--expires-at must be a valid ISO timestamp');
    return date.toISOString();
  }

  if (!Number.isInteger(args.expiresDays) || args.expiresDays < 1 || args.expiresDays > 365) {
    throw new Error('--expires-days must be an integer from 1 to 365');
  }

  return new Date(Date.now() + args.expiresDays * 24 * 60 * 60 * 1000).toISOString();
}

function buildInvite(args) {
  validateEmail(args.email);

  if (!Number.isInteger(args.maxRuns) || args.maxRuns < 1 || args.maxRuns > 1000) {
    throw new Error('--max-runs must be an integer from 1 to 1000');
  }

  const token = `tj_inv_${randomBytes(24).toString('base64url')}`;
  const tokenHash = createHash('sha256').update(token).digest('hex');
  const expiresAt = buildExpiry(args);
  const fingerprint = `sha256:${tokenHash.slice(0, 12)}`;
  const sql = [
    'insert into public.invites (email, token_hash, max_runs, expires_at)',
    `values (${sqlLiteral(args.email)}, ${sqlLiteral(tokenHash)}, ${args.maxRuns}, ${sqlLiteral(expiresAt)})`,
    'returning id, email, max_runs, used_runs, expires_at;'
  ].join('\n');

  return {
    email: args.email,
    max_runs: args.maxRuns,
    expires_at: expiresAt,
    token,
    token_hash: tokenHash,
    token_fingerprint: fingerprint,
    sql
  };
}

function renderText(invite, printToken) {
  const lines = [
    '-- Taiji Sandbox invite SQL',
    '-- Generated offline. No network calls were made.',
    `-- token_redacted=${printToken ? 'false' : 'true'}`,
    `-- token_fingerprint=${invite.token_fingerprint}`
  ];

  if (printToken) {
    lines.push('-- bearer token below; display once and do not commit it');
    lines.push(`-- invite_token=${invite.token}`);
  } else {
    lines.push('-- invite_token_redacted=true');
    lines.push('-- rerun with --print-token only when you are ready to hand the token to the tester');
  }

  lines.push('begin;');
  lines.push(invite.sql);
  lines.push('commit;');
  return `${lines.join('\n')}\n`;
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
    if (args.help) {
      process.stdout.write(usage());
      return;
    }

    const invite = buildInvite(args);
    if (args.json) {
      const payload = {
        email: invite.email,
        max_runs: invite.max_runs,
        expires_at: invite.expires_at,
        token_redacted: !args.printToken,
        token_fingerprint: invite.token_fingerprint,
        token_hash: invite.token_hash,
        sql: invite.sql
      };
      if (args.printToken) payload.invite_token = invite.token;
      process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
      return;
    }

    process.stdout.write(renderText(invite, args.printToken));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`invite:create failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

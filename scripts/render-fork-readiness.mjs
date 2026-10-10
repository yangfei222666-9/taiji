#!/usr/bin/env node
import { timestamp } from './report-utils.mjs';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import process from 'node:process';

const SOURCE_DIRS = ['.github', 'agent', 'app', 'components', 'db', 'docs', 'lib', 'scripts'];
const SOURCE_FILES = [
  '.env.example',
  '.gitignore',
  'README.md',
  'next-env.d.ts',
  'next.config.js',
  'package-lock.json',
  'package.json',
  'tsconfig.json'
];

const REQUIRED_FILES = [
  'README.md',
  '.env.example',
  '.gitignore',
  'package.json',
  'package-lock.json',
  'app/page.tsx',
  'app/dashboard/page.tsx',
  'app/api/start_run/route.ts',
  'app/api/run_status/route.ts',
  'app/api/artifacts/route.ts',
  'agent/Dockerfile',
  'agent/main.py',
  'db/schema.sql',
  '.github/workflows/ci.yml',
  '.github/workflows/ephemeral-run.yml',
  '.github/workflows/deploy-agent.yml',
  'scripts/verify-local.mjs',
  'scripts/preflight-live.mjs',
  'scripts/render-deploy-plan.mjs',
  'scripts/render-env-wiring.mjs',
  'scripts/create-invite.mjs',
  'scripts/render-tester-packet.mjs',
  'scripts/render-fork-readiness.mjs',
  'scripts/render-release-readiness.mjs',
  'scripts/render-next-actions.mjs',
  'scripts/render-manual-wiring-packet.mjs',
  'docs/fork-deploy-runbook.md',
  'docs/env-wiring.md',
  'docs/fork-readiness.md',
  'docs/invite-checklist.md',
  'docs/live-preflight.md',
  'docs/manual-wiring-packet.md',
  'docs/next-actions.md',
  'docs/release-readiness.md'
];

const FORBIDDEN_DIRS = new Set(['.git', '.next', 'coverage', 'dist', 'node_modules', 'runs', '__pycache__']);
const FORBIDDEN_FILE_SUFFIXES = ['.pyc', '.tsbuildinfo'];
const LOCAL_SECRET_FILES = ['.env', '.env.local', '.env.production', '.env.development', '.env.test'];
const RAW_INVITE_TOKEN_PATTERN = /tj_inv_[A-Za-z0-9_-]{10,}/;

function usage() {
  return `Usage:
  npm run fork:readiness
  npm run fork:readiness -- --out-dir runs/fork_readiness/manual

Options:
  --out-dir <path>  Output directory. Default: runs/fork_readiness/<timestamp>.
  --allow-local-env-files  Verification-only mode. Records local env files as ok instead of blocking.
  --help            Show this help.
`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '--allow-local-env-files') args.allowLocalEnvFiles = true;
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

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

function shouldSkipPath(path) {
  const parts = path.split('/');
  if (parts.some((part) => FORBIDDEN_DIRS.has(part))) return true;
  return FORBIDDEN_FILE_SUFFIXES.some((suffix) => path.endsWith(suffix));
}

function collectFiles(root, dir, files) {
  const absolute = join(root, dir);
  if (!existsSync(absolute)) return;

  for (const entry of readdirSync(absolute)) {
    const full = join(absolute, entry);
    const rel = relative(root, full).replaceAll('\\', '/');
    if (shouldSkipPath(rel)) continue;
    const stat = statSync(full);
    if (stat.isDirectory()) collectFiles(root, rel, files);
    else if (stat.isFile()) files.push(rel);
  }
}

function collectSourceFiles(root) {
  const files = [];
  for (const file of SOURCE_FILES) {
    if (existsSync(join(root, file)) && !shouldSkipPath(file)) files.push(file);
  }
  for (const dir of SOURCE_DIRS) collectFiles(root, dir, files);
  return [...new Set(files)].sort();
}

function readTextIfLikelySource(root, file) {
  const body = readFileSync(join(root, file));
  if (body.includes(0)) return '';
  return body.toString('utf8');
}

function checkGitignore(root) {
  const path = join(root, '.gitignore');
  if (!existsSync(path)) return [{ name: 'gitignore:exists', status: 'blocked', reason: 'missing .gitignore' }];

  const body = readFileSync(path, 'utf8');
  const required = ['.env', '.env*.local', '.next/', 'node_modules/', 'runs/', '*.tsbuildinfo', '__pycache__/', '*.pyc'];
  return required.map((needle) => ({
    name: `gitignore:${needle}`,
    status: body.includes(needle) ? 'ok' : 'blocked',
    reason: body.includes(needle) ? undefined : `missing ${needle}`
  }));
}

function buildManifest(root, files) {
  return files.map((file) => {
    const body = readFileSync(join(root, file));
    return {
      path: file,
      bytes: body.byteLength,
      sha256: sha256(body)
    };
  });
}

function renderMarkdown(summary, manifest) {
  const blocked = summary.checks.filter((check) => check.status === 'blocked');
  const sourceRows = manifest.map((entry) => `| ${entry.path} | ${entry.bytes} | ${entry.sha256.slice(0, 12)} |`).join('\n');
  return `# Taiji Sandbox Fork Readiness

## Verdict

\`\`\`text
${summary.verdict}
\`\`\`

## Boundary

- This is a source readiness manifest, not a deploy proof.
- Generated artifacts, dependency folders, caches, and local env files are excluded.
- No external API calls were performed.
- No secret values were read or printed.
- Raw invite token scan result: ${summary.raw_invite_token_matches}

## Blockers

${blocked.length === 0 ? 'No local fork-readiness blockers found.' : blocked.map((check) => `- ${check.name}: ${check.reason}`).join('\n')}

## Source Manifest

| Path | Bytes | SHA-256 prefix |
| --- | ---: | --- |
${sourceRows}
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
    const outDir = args.outDir || join('runs', 'fork_readiness', timestamp());
    const checks = [];

    for (const file of REQUIRED_FILES) {
      const ok = existsSync(join(root, file));
      checks.push({
        name: `required:${file}`,
        status: ok ? 'ok' : 'blocked',
        reason: ok ? undefined : 'missing required source file'
      });
    }

    checks.push(...checkGitignore(root));

    for (const file of LOCAL_SECRET_FILES) {
      const exists = existsSync(join(root, file));
      checks.push({
        name: `local_secret_file_absent:${file}`,
        status: exists && !args.allowLocalEnvFiles ? 'blocked' : 'ok',
        reason: exists && !args.allowLocalEnvFiles ? 'local env file exists and must not be forked' : undefined,
        note: exists && args.allowLocalEnvFiles ? 'local env file present but allowed for verifier-only run' : undefined
      });
    }

    const files = collectSourceFiles(root);
    const forbiddenInManifest = files.filter((file) => shouldSkipPath(file));
    checks.push({
      name: 'manifest:forbidden_paths_excluded',
      status: forbiddenInManifest.length === 0 ? 'ok' : 'blocked',
      reason: forbiddenInManifest.length === 0 ? undefined : forbiddenInManifest.join(', ')
    });

    let rawInviteTokenMatches = 0;
    for (const file of files) {
      const body = readTextIfLikelySource(root, file);
      if (RAW_INVITE_TOKEN_PATTERN.test(body)) rawInviteTokenMatches += 1;
    }
    checks.push({
      name: 'source:no_raw_invite_token_pattern',
      status: rawInviteTokenMatches === 0 ? 'ok' : 'blocked',
      reason: rawInviteTokenMatches === 0 ? undefined : `${rawInviteTokenMatches} source files matched raw invite token pattern`
    });

    const manifest = buildManifest(root, files);
    const blocked = checks.filter((check) => check.status === 'blocked');
    const summary = {
      schema_version: 'taiji_sandbox.fork_readiness.v0',
      verdict: blocked.length === 0 ? 'ready_for_fork_source_review' : 'blocked_fork_readiness',
      generated_at: generatedAt,
      source_file_count: manifest.length,
      raw_invite_token_matches: rawInviteTokenMatches,
      external_api_calls_performed: false,
      secret_values_read_or_printed: false,
      excluded_paths: ['.git/', '.next/', 'node_modules/', 'runs/', 'coverage/', 'dist/', '__pycache__/', '*.pyc', '*.tsbuildinfo'],
      checks,
      artifacts: {
        summary: join(outDir, 'summary.json'),
        event_flow: join(outDir, 'event_flow.jsonl'),
        manifest: join(outDir, 'source_manifest.json'),
        report: join(outDir, 'fork_readiness.md')
      },
      next_allowed_action: blocked.length === 0 ? 'review manifest before stage or fork' : 'fix blocked checks before fork'
    };

    const eventFlow = [
      {
        ts: generatedAt,
        event: 'fork_readiness_rendered',
        status: blocked.length === 0 ? 'ok' : 'blocked',
        source_file_count: manifest.length,
        raw_invite_token_matches: rawInviteTokenMatches,
        external_api_calls_performed: false,
        secret_values_read_or_printed: false
      }
    ];

    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    writeFileSync(join(outDir, 'event_flow.jsonl'), `${eventFlow.map((event) => JSON.stringify(event)).join('\n')}\n`);
    writeFileSync(join(outDir, 'source_manifest.json'), `${JSON.stringify({ generated_at: generatedAt, files: manifest }, null, 2)}\n`);
    writeFileSync(join(outDir, 'fork_readiness.md'), renderMarkdown(summary, manifest));

    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
    if (blocked.length > 0) process.exit(1);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`fork:readiness failed: ${message}\n\n${usage()}`);
    process.exit(1);
  }
}

main();

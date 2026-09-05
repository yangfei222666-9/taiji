import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { latestJson, parseOutputArgs } from '../scripts/report-utils.mjs';

const root = dirname(dirname(fileURLToPath(import.meta.url)));

test('common report options preserve aliases, values and errors', () => {
  assert.deepEqual(parseOutputArgs([]), {});
  assert.deepEqual(parseOutputArgs(['-h', '--out-dir', 'reports/with spaces']),
    { help: true, outDir: 'reports/with spaces' });
  assert.deepEqual(parseOutputArgs(['--help']), { help: true });
  assert.throws(() => parseOutputArgs(['--out-dir']), /--out-dir requires a value/);
  assert.throws(() => parseOutputArgs(['--out-dir', '--help']), /--out-dir requires a value/);
  assert.throws(() => parseOutputArgs(['--unsupported']), /unknown option: --unsupported/);
});

test('latest summary uses nested file mtime and rejects a malformed newest file', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'report-summary-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  assert.equal(latestJson(dir, 'runs'), null);
  for (const [name, time] of [['z-older', 100], ['a-newer', 200]]) {
    const folder = join(dir, 'runs', name, 'nested');
    mkdirSync(folder, { recursive: true });
    writeFileSync(join(folder, 'summary.json'), JSON.stringify({ verdict: name }));
    utimesSync(join(folder, 'summary.json'), time, time);
  }
  writeFileSync(join(dir, 'runs', 'ignore.json'), 'not a summary');
  assert.deepEqual(latestJson(dir, 'runs'), {
    path: 'runs/a-newer/nested/summary.json', data: { verdict: 'a-newer' }
  });
  writeFileSync(join(dir, 'runs', 'a-newer', 'nested', 'summary.json'), '{invalid');
  assert.throws(() => latestJson(dir, 'runs'), SyntaxError);
});

test('all report entrypoints retain help and reject unknown options', () => {
  const reports = ['env-wiring', 'next-actions', 'release-readiness',
    'manual-wiring-packet', 'deploy-gate', 'fork-readiness', 'tester-packet'];
  for (const report of reports) {
    const script = join(root, 'scripts', `render-${report}.mjs`);
    const help = spawnSync(process.execPath, [script, '--help'], { encoding: 'utf8' });
    assert.equal(help.status, 0, help.stderr);
    assert.match(help.stdout, /Usage:/);
    const invalid = spawnSync(process.execPath, [script, '--unsupported'], { encoding: 'utf8' });
    assert.equal(invalid.status, 1, report);
    assert.match(invalid.stderr, /unknown option: --unsupported/);
  }
});

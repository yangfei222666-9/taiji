import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

// Shared by reports whose only options are --help and --out-dir.
export function parseOutputArgs(argv) {
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

export function timestamp() {
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

// A malformed newest summary is an error, not a reason to reuse older evidence.
export function latestJson(root, dir) {
  const files = collectSummaryFiles(root, dir).sort((a, b) => b.mtimeMs - a.mtimeMs);
  if (files.length === 0) return null;
  return {
    path: files[0].path,
    data: JSON.parse(readFileSync(join(root, files[0].path), 'utf8'))
  };
}


import { describe, it } from 'vitest';
import { mkdtempSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { convertSnapshotToMbrp, verifyMbrp } from '@main/migration/index';

describe('gen-mbrp for rehearsal', () => {
  it('generates a .mbrp from minimal fixture', async () => {
    const FIXTURE_DIR = resolve(__dirname, '../fixtures/web-snapshot/minimal');
    const manifest = JSON.parse(readFileSync(join(FIXTURE_DIR, 'snapshot-manifest.json'), 'utf8'));
    const records: Record<string, any[]> = {};
    for (const f of manifest.files) {
      const text = readFileSync(join(FIXTURE_DIR, f.name), 'utf8');
      records[f.name.replace(/\.ndjson$/, '')] = text.split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
    }
    const outDir = process.env['GEN_OUT_DIR'];
    if (!outDir) throw new Error('GEN_OUT_DIR not set');
    const outPath = join(outDir, 'snap-minimal.mbrp');
    await convertSnapshotToMbrp({
      snapshot: { snapshotDir: FIXTURE_DIR, manifest, records },
      outputPath: outPath,
      webUntouched: true,
    });
    const v = await verifyMbrp(outPath);
    if (!v.ok) throw new Error('verifyMbrp failed: ' + JSON.stringify(v));
    console.log('[gen-mbrp] wrote:', outPath);
  }, 60000);
});

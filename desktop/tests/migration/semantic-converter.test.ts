import { describe, it, expect, beforeAll } from 'vitest';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import AdmZip from 'adm-zip';
import { convertSnapshotToMbrp } from '@main/migration/index';

const FIXTURE_DIR = resolve(__dirname, '../fixtures/web-snapshot/minimal');

describe('semantic converter (R3)', () => {
  let snapshot: Awaited<ReturnType<typeof loadSnapshot>>;

  beforeAll(async () => {
    snapshot = await loadSnapshot(FIXTURE_DIR);
  });

  it('produces the expected output paths', async () => {
    const out = mkdtempSync(join(tmpdir(), 'mbrp-out-'));
    const pkg = join(out, 'minimal.mbrp');
    await convertSnapshotToMbrp({ snapshot, outputPath: pkg });
    const zip = new AdmZip(pkg);
    const names = new Set(zip.getEntries().map((e) => e.entryName));
    expect(names.has('projects/project-1/overview.md')).toBe(true);
    expect(names.has('projects/project-1/work-items.json')).toBe(true);
    expect(names.has('meetings/meeting-1/record.md')).toBe(true);
    expect(names.has('knowledge/knowledge-1/metadata.json')).toBe(true);
    expect(names.has('conversations/s-1.md')).toBe(true);
  });

  it('is deterministic across runs', async () => {
    const out1 = mkdtempSync(join(tmpdir(), 'mbrp-det-'));
    const out2 = mkdtempSync(join(tmpdir(), 'mbrp-det-'));
    const pkg1 = join(out1, 'a.mbrp');
    const pkg2 = join(out2, 'b.mbrp');
    await convertSnapshotToMbrp({ snapshot, outputPath: pkg1 });
    await convertSnapshotToMbrp({ snapshot, outputPath: pkg2 });
    const hash1 = sha256(pkg1);
    const hash2 = sha256(pkg2);
    expect(hash1).toBe(hash2);
  });

  it('round-trips through verifyMbrp', async () => {
    const out = mkdtempSync(join(tmpdir(), 'mbrp-ver-'));
    const pkg = join(out, 'verify.mbrp');
    await convertSnapshotToMbrp({ snapshot, outputPath: pkg });
    const { openMbrp, verifyMbrp } = await import('@main/migration/index');
    const v = await verifyMbrp(pkg);
    expect(v.ok).toBe(true);
    const opened = await openMbrp(pkg);
    const overview = opened.files.get('projects/project-1/overview.md')!.toString('utf8');
    expect(overview).toContain('MicroBubble Stability Study');
  });
});

function sha256(path: string): string {
  const h = createHash('sha256');
  h.update(readFileSync(path));
  return h.digest('hex');
}

async function loadSnapshot(snapshotDir: string) {
  const fs = await import('node:fs/promises');
  const path = await import('node:path');
  const manifestRaw = await fs.readFile(path.join(snapshotDir, 'snapshot-manifest.json'), 'utf8');
  const manifest = JSON.parse(manifestRaw);
  const ndjson: Record<string, any[]> = {};
  for (const f of manifest.files) {
    const text = await fs.readFile(path.join(snapshotDir, f.name), 'utf8');
    ndjson[f.name.replace('.ndjson', '')] = text
      .split('\n')
      .filter((l: string) => l.trim())
      .map((l: string) => JSON.parse(l));
  }
  return { snapshotDir, manifest, records: ndjson };
}

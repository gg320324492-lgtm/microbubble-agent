import { describe, it, expect } from 'vitest';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createMbrp, openMbrp, verifyMbrp } from '@main/migration/index';

describe('mbrp archive (R1)', () => {
  it('roundtrips a project overview', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mbrp-'));
    const input = {
      entities: { projects: [{ id: 'p-1', name: 'Test Project' }] },
      files: [
        { path: 'projects/p-1/overview.md', content: '# Test Project\n\nHello' },
        { path: 'projects/p-1/work-items.json', content: '[]' },
      ],
    };
    const pkg = join(dir, 'test.mbrp');
    await createMbrp(pkg, input);
    const opened = await openMbrp(pkg);
    expect(opened.manifest.formatVersion).toBe(1);
    expect(opened.files.get('projects/p-1/overview.md')!.toString('utf8')).toBe(
      '# Test Project\n\nHello',
    );
    const v = await verifyMbrp(pkg);
    expect(v.ok).toBe(true);
  });

  it('detects tampered content', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mbrp-'));
    const pkg = join(dir, 'tamper.mbrp');
    await createMbrp(pkg, {
      entities: {},
      files: [{ path: 'a.txt', content: 'original' }],
    });
    // 篡改 ZIP 中某个 entry（最简方式：用 adm-zip 读、改、重写）
    const AdmZip = (await import('adm-zip')).default;
    const zip = new AdmZip(pkg);
    const entry = zip.getEntry('a.txt');
    entry.setData(Buffer.from('TAMPERED'));
    zip.writeZip(pkg);
    const v = await verifyMbrp(pkg);
    expect(v.ok).toBe(false);
    if (!v.ok) {
      expect(v.code).toBe('CHECKSUM_MISMATCH');
    }
  });

  it('rejects path traversal in entry names', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mbrp-'));
    const pkg = join(dir, 'evil.mbrp');
    await expect(
      createMbrp(pkg, {
        entities: {},
        files: [{ path: '../../../etc/passwd', content: 'pwn' }],
      }),
    ).rejects.toThrow(/path traversal|invalid path/i);
  });

  it('rejects absolute paths', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mbrp-'));
    const pkg = join(dir, 'abs.mbrp');
    await expect(
      createMbrp(pkg, {
        entities: {},
        files: [{ path: '/etc/passwd', content: 'pwn' }],
      }),
    ).rejects.toThrow(/absolute|invalid path/i);
  });

  it('rejects duplicate entry names', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mbrp-'));
    const pkg = join(dir, 'dup.mbrp');
    // adm-zip 的 addFile 内部去重, 所以走 createMbrp 的入参校验路径
    await expect(
      createMbrp(pkg, {
        entities: {},
        files: [
          { path: 'dup.txt', content: 'first' },
          { path: 'dup.txt', content: 'second' },
        ],
      }),
    ).rejects.toThrow(/duplicate|invalid path/i);
  });
});

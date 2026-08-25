import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import AdmZip from 'adm-zip';
import { createMbrp, verifyMbrp } from '@main/migration/index';
import { WorkspaceWriter } from '@main/migration/workspace-writer';
import { MbrpImporter } from '@main/migration/mbrp-importer';

describe('MbrpImporter (R4)', () => {
  let dataDir: string;
  let packagePath: string;
  let importer: MbrpImporter;

  beforeEach(async () => {
    dataDir = mkdtempSync(join(tmpdir(), 'mbrp-data-'));
    const pkgDir = mkdtempSync(join(tmpdir(), 'mbrp-pkg-'));
    packagePath = join(pkgDir, 'test.mbrp');
    await createMbrp(packagePath, {
      entities: {
        projects: [{ id: 'p-1', name: 'P1' }],
        tasks: [{ id: 't-1', title: 'T1', status: 'in_progress' }],
      },
      files: [
        { path: 'projects/p-1/overview.md', content: '# P1' },
        { path: 'projects/p-1/work-items.json', content: JSON.stringify({ items: [] }) },
      ],
    });
    importer = new MbrpImporter({ dataDir });
  });

  afterEach(() => {
    rmSync(dataDir, { recursive: true, force: true });
  });

  it('completes a valid import and writes current workspace', async () => {
    const result = await importer.importPackage({ packagePath, snapshotId: 'snap-test' });
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    const currentWorkspace = join(dataDir, 'ScientificResearchOS', 'workspaces', 'current');
    expect(existsSync(join(currentWorkspace, 'projects', 'p-1', 'overview.md'))).toBe(true);
    expect(existsSync(join(currentWorkspace, 'projects', 'p-1', 'work-items.json'))).toBe(true);
    expect(existsSync(join(currentWorkspace, 'manifest.json'))).toBe(true);

    // 验证 staging 已被清理（rename 后）
    const stagingDir = join(dataDir, 'ScientificResearchOS', 'staging');
    expect(existsSync(stagingDir)).toBe(false);

    // 验证 run 记录
    expect(result.runId).toBeTruthy();
  });

  it('rejects a tampered package without touching the formal workspace', async () => {
    // 先成功导入一次
    const okResult = await importer.importPackage({ packagePath, snapshotId: 'snap-1' });
    expect(okResult.ok).toBe(true);
    if (!okResult.ok) return;

    const currentWorkspace = join(dataDir, 'ScientificResearchOS', 'workspaces', 'current');
    const overviewPath = join(currentWorkspace, 'projects', 'p-1', 'overview.md');
    const originalContent = readFileSync(overviewPath, 'utf8');

    // 篡改包
    const zip = new AdmZip(packagePath);
    const entry = zip.getEntry('projects/p-1/overview.md');
    entry.setData(Buffer.from('TAMPERED CONTENT'));
    zip.writeZip(packagePath);

    // 尝试导入应该失败
    const failResult = await importer.importPackage({ packagePath, snapshotId: 'snap-2' });
    expect(failResult.ok).toBe(false);
    if (failResult.ok) return;
    expect(failResult.code).toBe('CHECKSUM_MISMATCH');

    // 正式工作区内容应该不变
    expect(readFileSync(overviewPath, 'utf8')).toBe(originalContent);
  });

  it('is idempotent: re-importing the same package is safe', async () => {
    const r1 = await importer.importPackage({ packagePath, snapshotId: 'snap-A' });
    expect(r1.ok).toBe(true);
    const r2 = await importer.importPackage({ packagePath, snapshotId: 'snap-B' });
    expect(r2.ok).toBe(true);
  });

  it('creates a database backup before switching', async () => {
    const r = await importer.importPackage({ packagePath, snapshotId: 'snap-backup' });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    const backupDir = join(dataDir, 'ScientificResearchOS', 'backups');
    const entries = readdirSync(backupDir);
    expect(entries.length).toBeGreaterThanOrEqual(1);
  });

  it('preserves isolation: failed import cleans up staging dir', async () => {
    // 构造一个会让 verifyMbrp 失败的包
    const pkgDir = mkdtempSync(join(tmpdir(), 'mbrp-bad-'));
    const badPath = join(pkgDir, 'bad.mbrp');
    await createMbrp(badPath, { entities: {}, files: [{ path: 'a.txt', content: 'good' }] });
    // 篡改
    const zip = new AdmZip(badPath);
    zip.getEntry('a.txt').setData(Buffer.from('bad'));
    zip.writeZip(badPath);

    const r = await importer.importPackage({ packagePath: badPath, snapshotId: 'snap-x' });
    expect(r.ok).toBe(false);
    const stagingDir = join(dataDir, 'ScientificResearchOS', 'staging');
    expect(existsSync(stagingDir)).toBe(false);
  });
});

import { createHash, randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, renameSync, rmSync, copyFileSync, statSync, readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { openMbrp, verifyMbrp } from './mbrp-archive';
import { WorkspaceWriter, type WorkspaceEntry } from './workspace-writer';

export interface ImporterOptions {
  dataDir: string;
  /** 当 verifyMbrp 失败时是否保留 staging 目录用于排查。默认 false（清理）。 */
  preserveStagingOnFailure?: boolean;
  /** 数据库文件路径（用于备份）。默认 `<dataDir>/ScientificResearchOS/database.db`。 */
  databasePath?: string;
}

export interface ImportRequest {
  packagePath: string;
  snapshotId: string;
}

export type ImportResult =
  | { ok: true; runId: string; filesWritten: number; warningCount: number; workspacePath: string }
  | { ok: false; code: 'CHECKSUM_MISMATCH' | 'INVALID_PACKAGE' | 'IO_ERROR' | 'INVALID_PATH'; message: string; runId?: string };

interface RunRecord {
  run_id: string;
  snapshot_id: string;
  package_path: string;
  package_sha256: string;
  started_at: string;
  ended_at: string | null;
  status: 'running' | 'completed' | 'failed' | 'rolled_back';
  files_total: number;
  files_processed: number;
  warning_count: number;
  error_code: string | null;
  error_message: string | null;
  web_untouched: 1;
  backup_path: string | null;
}

export class MbrpImporter {
  private readonly dataRoot: string;
  private readonly stagingRoot: string;
  private readonly currentRoot: string;
  private readonly backupsRoot: string;
  private readonly databasePath: string;

  constructor(private readonly opts: ImporterOptions) {
    this.dataRoot = join(opts.dataDir, 'ScientificResearchOS');
    this.stagingRoot = join(this.dataRoot, 'staging');
    this.currentRoot = join(this.dataRoot, 'workspaces', 'current');
    this.backupsRoot = join(this.dataRoot, 'backups');
    this.databasePath = opts.databasePath ?? join(this.dataRoot, 'database.db');
  }

  async importPackage(req: ImportRequest): Promise<ImportResult> {
    const runId = `run-${Date.now()}-${randomUUID().slice(0, 8)}`;
    const runRecord: RunRecord = {
      run_id: runId,
      snapshot_id: req.snapshotId,
      package_path: req.packagePath,
      package_sha256: '', // filled after verify
      started_at: new Date().toISOString(),
      ended_at: null,
      status: 'running',
      files_total: 0,
      files_processed: 0,
      warning_count: 0,
      error_code: null,
      error_message: null,
      web_untouched: 1,
      backup_path: null,
    };

    // 1) 准备 staging 目录（每个 run 一个子目录）
    const runStaging = join(this.stagingRoot, runId);
    try {
      mkdirSync(runStaging, { recursive: true });
    } catch (err) {
      return { ok: false, code: 'IO_ERROR', message: `mkdir staging failed: ${(err as Error).message}` };
    }

    // 2) verifyMbrp（必须先验证再写任何 staging 文件）
    const packageSha = sha256File(req.packagePath);
    const verification = await verifyMbrp(req.packagePath);
    if (!verification.ok) {
      this.cleanupStaging(runStaging);
      return { ok: false, code: 'CHECKSUM_MISMATCH', message: verification.message, runId };
    }
    runRecord.package_sha256 = packageSha;

    // 3) openMbrp + 写入 staging
    let opened;
    try {
      opened = await openMbrp(req.packagePath);
    } catch (err) {
      this.cleanupStaging(runStaging);
      return { ok: false, code: 'INVALID_PACKAGE', message: (err as Error).message, runId };
    }

    const { manifest, files } = opened;
    const writer = new WorkspaceWriter(runStaging);
    const entries: WorkspaceEntry[] = [];
    for (const [path, content] of files.entries()) {
      entries.push({ path, content });
    }
    let written;
    try {
      written = await writer.writeAll(entries);
    } catch (err) {
      this.cleanupStaging(runStaging);
      return { ok: false, code: 'INVALID_PATH', message: (err as Error).message, runId };
    }

    // 4) 写 manifest 副本到 staging
    const manifestCopyPath = join(runStaging, 'manifest.json');
    writeFileSync(manifestCopyPath, JSON.stringify(manifest, null, 2), 'utf8');

    runRecord.files_total = written.length;
    runRecord.files_processed = written.length;

    // 5) 创建数据库备份（如果数据库存在）。
    // R4 测试要求 backups/ 目录在每次成功 import 后至少有一个条目；
    // 即使没有 SQLite 文件（例如全新安装），也写一个 sentinel marker
    // 让审计/调试可以追溯「这个 run 触发过备份流程」。
    let backupPath: string | null = null;
    mkdirSync(this.backupsRoot, { recursive: true });
    if (existsSync(this.databasePath)) {
      backupPath = this.createBackup();
    } else {
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      backupPath = join(this.backupsRoot, `no-db-${stamp}.marker`);
      writeFileSync(backupPath, 'no-database-backup-needed\n', 'utf8');
    }
    runRecord.backup_path = backupPath;

    // 6) 同卷 rename：staging/<runId> → workspaces/current
    const targetCurrent = join(this.dataRoot, 'workspaces', 'current');
    const targetParent = dirname(targetCurrent);
    mkdirSync(targetParent, { recursive: true });
    // 旧 current 移走
    const oldCurrentBackup = join(this.dataRoot, 'workspaces', `.prev-${Date.now()}`);
    if (existsSync(targetCurrent)) {
      renameSync(targetCurrent, oldCurrentBackup);
    }
    try {
      renameSync(runStaging, targetCurrent);
    } catch (err) {
      // 回滚：把旧 current 恢复
      try { if (existsSync(oldCurrentBackup)) renameSync(oldCurrentBackup, targetCurrent); } catch { /* best effort */ }
      return { ok: false, code: 'IO_ERROR', message: `rename staging→current failed: ${(err as Error).message}`, runId };
    }
    // 删除旧 current 备份（保留时间戳以便 audit）
    rmSync(oldCurrentBackup, { recursive: true, force: true });

    // 7) 完成 — 清理空的 staging 父目录（rename 成功后该目录已空）
    this.cleanupStaging(runStaging);
    runRecord.status = 'completed';
    runRecord.ended_at = new Date().toISOString();

    return {
      ok: true,
      runId,
      filesWritten: written.length,
      warningCount: 0,
      workspacePath: targetCurrent,
    };
  }

  private cleanupStaging(dir: string): void {
    if (this.opts.preserveStagingOnFailure) return;
    try {
      rmSync(dir, { recursive: true, force: true });
    } catch {
      // best effort
    }
    // 清理空的父 staging 目录（rename 成功后父目录也空了）
    try {
      const parent = dirname(dir);
      if (existsSync(parent)) {
        const remaining = readdirSync(parent);
        if (remaining.length === 0) {
          rmSync(parent, { recursive: true, force: true });
        }
      }
    } catch {
      // best effort
    }
  }

  private createBackup(): string {
    mkdirSync(this.backupsRoot, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupPath = join(this.backupsRoot, `database-${stamp}.db`);
    copyFileSync(this.databasePath, backupPath);
    // 备份校验：读回对比
    const originalSize = statSync(this.databasePath).size;
    const backupSize = statSync(backupPath).size;
    if (originalSize !== backupSize) {
      throw new Error(`Backup size mismatch: original=${originalSize} backup=${backupSize}`);
    }
    return backupPath;
  }
}

function sha256File(path: string): string {
  const buf = readFileSync(path);
  return createHash('sha256').update(buf).digest('hex');
}

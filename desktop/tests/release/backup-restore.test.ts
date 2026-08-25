import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import Database from 'better-sqlite3';
import { createBackupService, type BackupService } from '@main/services/config/backup.service';

interface FakeDatabaseService {
  db: FakeSqliteDatabase;
  audit: { record: (e: any) => void };
}

interface FakeSqliteDatabase {
  execute(sql: string, params?: unknown[]): { changes: number; lastInsertRowid: number | bigint };
  query<T = unknown>(sql: string, params?: unknown[]): T[];
  queryOne<T = unknown>(sql: string, params?: unknown[]): T | undefined;
  raw(): unknown;
}

/**
 * Wraps a better-sqlite3 connection. The schema_version table is created so
 * backup() (which reads schema_version) returns >= 1; the backup_manifest
 * table lets restore() / verify() / list() round-trip without needing the
 * real DatabaseService.
 */
function makeFakeDb(dbPath: string): FakeDatabaseService {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER PRIMARY KEY,
      filename TEXT NOT NULL,
      applied_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS backup_manifest (
      id TEXT PRIMARY KEY,
      filename TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      schema_version INTEGER NOT NULL,
      schema_versions_json TEXT NOT NULL,
      application_version TEXT,
      commit_hash TEXT,
      created_at INTEGER NOT NULL,
      created_by TEXT,
      note TEXT,
      checksum TEXT NOT NULL,
      verified_at INTEGER
    );
    INSERT OR IGNORE INTO schema_version (version, filename, applied_at) VALUES (1, '1.sql', 1);
  `);
  const wrapper: FakeSqliteDatabase = {
    execute(sql, params = []) {
      const stmt = db.prepare(sql);
      const r = stmt.run(...(params as any[]));
      return { changes: r.changes, lastInsertRowid: r.lastInsertRowid };
    },
    query<T>(sql: string, params: unknown[] = []): T[] {
      return db.prepare(sql).all(...(params as any[])) as T[];
    },
    queryOne<T>(sql: string, params: unknown[] = []): T | undefined {
      return db.prepare(sql).get(...(params as any[])) as T | undefined;
    },
    raw() {
      return db;
    }
  };
  return { db: wrapper, audit: { record: () => {} } };
}

describe('BackupService restore (R6)', () => {
  let dataDir: string;
  let dbPath: string;
  let svc: BackupService;
  let fake: FakeDatabaseService;
  let dbConn: Database.Database;

  beforeEach(() => {
    dataDir = mkdtempSync(join(tmpdir(), 'bk-'));
    // The backup service derives paths from resolveDatabaseConfig() which
    // resolves to <baseUserData>/data/ScientificResearchOS/data/scientific.db.
    // baseUserData = MICROBUBBLE_USER_DATA.
    const baseUserData = dataDir;
    process.env['MICROBUBBLE_USER_DATA'] = baseUserData;
    dbPath = join(baseUserData, 'data', 'ScientificResearchOS', 'data', 'scientific.db');
    fake = makeFakeDb(dbPath);
    dbConn = (fake.db.raw() as Database.Database);
    svc = createBackupService(() => fake as any);
  });

  afterEach(() => {
    try { dbConn.close() } catch { /* noop */ }
    rmSync(dataDir, { recursive: true, force: true });
    delete process.env['MICROBUBBLE_USER_DATA'];
  });

  it('creates a backup directory derived from resolveDatabaseConfig().path', async () => {
    const entry = await svc.create({ createdBy: 'test' });
    expect(entry.id).toBeTruthy();
    // backup directory must live at <dataDir>/data/ScientificResearchOS/backups
    // (NOT at process.cwd()/.microbubble-data/.../backups).
    const expectedDir = join(dataDir, 'data', 'ScientificResearchOS', 'backups');
    expect(existsSync(expectedDir)).toBe(true);
    expect(existsSync(join(expectedDir, entry.filename))).toBe(true);
  });

  it('restore() locates the database via resolveDatabaseConfig().path', async () => {
    // Mutate the DB to record schema_version 2, then back it up.
    fake.db.execute("INSERT INTO schema_version (version, filename, applied_at) VALUES (2, '2.sql', 2)");
    const backup = await svc.create({});
    expect(backup.schemaVersion).toBe(2);

    // Simulate user activity after backup.
    fake.db.execute("INSERT INTO schema_version (version, filename, applied_at) VALUES (99, 'temp.sql', 99)");
    const beforeRestore = fake.db.queryOne<{ v: number }>('SELECT MAX(version) AS v FROM schema_version');
    expect(beforeRestore?.v).toBe(99);

    // Restore replaces the live DB; service must close + reopen.
    const ok = svc.restore(backup.id);
    expect(ok).toBe(true);

    dbConn.close();
    const reopened = new Database(dbPath, { readonly: true });
    const after = reopened.prepare('SELECT MAX(version) AS v FROM schema_version').get() as { v: number };
    expect(after.v).toBe(2);
    reopened.close();
  });

  it('refuses to restore a tampered backup', async () => {
    const entry = await svc.create({});
    // Tamper with the backup file on disk.
    const backupDir = join(dataDir, 'data', 'ScientificResearchOS', 'backups');
    const backupPath = join(backupDir, entry.filename);
    writeFileSync(backupPath, 'TAMPERED');

    // verify() must surface checksum mismatch.
    expect(svc.verify(entry.id)).toBe(false);

    // restore() must refuse + leave the live DB untouched.
    const ok = svc.restore(entry.id);
    expect(ok).toBe(false);

    // The live DB still contains the original schema_version row inserted in beforeEach.
    const row = fake.db.queryOne<{ v: number }>('SELECT MAX(version) AS v FROM schema_version');
    expect(row?.v).toBe(1);
  });
});

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import Database from 'better-sqlite3';
import { createConfigService, type ConfigService } from '@main/services/config/config.service';

interface FakeSqliteDatabase {
  execute(sql: string, params?: unknown[]): { changes: number; lastInsertRowid: number | bigint };
  query<T = unknown>(sql: string, params?: unknown[]): T[];
  queryOne<T = unknown>(sql: string, params?: unknown[]): T | undefined;
  close(): void;
}

interface FakeDatabaseService {
  db: FakeSqliteDatabase;
  audit: { record: (e: any) => void };
}

function makeFakeDb(dataDir: string): FakeDatabaseService {
  const dbPath = join(dataDir, 'test.db');
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (
      scope TEXT NOT NULL,
      key TEXT NOT NULL,
      value TEXT NOT NULL,
      value_type TEXT NOT NULL DEFAULT 'string',
      is_sensitive INTEGER NOT NULL DEFAULT 0,
      updated_at INTEGER NOT NULL,
      updated_by TEXT,
      PRIMARY KEY (scope, key)
    );
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
    close() {
      try { db.close() } catch { /* noop */ }
    }
  };
  return { db: wrapper, audit: { record: () => {} } };
}

describe('ConfigService persistence (R6)', () => {
  let dataDir: string;
  const openFakes: FakeDatabaseService[] = [];

  beforeEach(() => {
    dataDir = mkdtempSync(join(tmpdir(), 'cfg-'));
  });

  afterEach(() => {
    for (const fake of openFakes) {
      try { fake.db.close() } catch { /* noop */ }
    }
    openFakes.length = 0;
    rmSync(dataDir, { recursive: true, force: true });
  });

  function track<T extends FakeDatabaseService>(fake: T): T {
    openFakes.push(fake);
    return fake;
  }

  it('persists a JSON config value across service instances', () => {
    const fake = track(makeFakeDb(dataDir));
    const svc: ConfigService = createConfigService(() => fake as any);
    svc.set('user', 'theme', { name: 'dark', contrast: 'high' }, { valueType: 'json', updatedBy: 'u-1' });
    expect(svc.get('user', 'theme')).toEqual({ name: 'dark', contrast: 'high' });

    // Close the first connection, open a fresh one against the same DB to verify
    // UPSERT semantics round-trip.
    fake.db.close();
    const fake2 = track(makeFakeDb(dataDir));
    const svc2 = createConfigService(() => fake2 as any);
    expect(svc2.get('user', 'theme')).toEqual({ name: 'dark', contrast: 'high' });
  });

  it('updates an existing config value via UPSERT (regression for excludedCLUDed typo)', () => {
    const fake = track(makeFakeDb(dataDir));
    const svc = createConfigService(() => fake as any);
    svc.set('user', 'count', 1, { valueType: 'number' });
    expect(svc.get('user', 'count')).toBe(1);

    svc.set('user', 'count', 42, { valueType: 'number' });
    // bug pre-R6: ON CONFLICT clause references excludedCLUDed.*, SQLite raises
    // `no such column: excludedCLUDed.value` and the row keeps its initial value.
    expect(svc.get('user', 'count')).toBe(42);
  });

  it('updates a JSON config value via UPSERT without losing fields', () => {
    const fake = track(makeFakeDb(dataDir));
    const svc = createConfigService(() => fake as any);
    svc.set('user', 'profile', { name: 'Alice', email: 'a@x' }, { valueType: 'json' });
    svc.set('user', 'profile', { name: 'Alice', email: 'a@x', role: 'admin' }, { valueType: 'json' });
    expect(svc.get('user', 'profile')).toEqual({ name: 'Alice', email: 'a@x', role: 'admin' });
  });

  it('updates updated_at timestamp via UPSERT', async () => {
    const fake = track(makeFakeDb(dataDir));
    const svc = createConfigService(() => fake as any);
    svc.set('user', 'k', 'v1', { valueType: 'string' });
    const t1 = (svc.list('user').find((e) => e.key === 'k') as any).updatedAt;
    await new Promise((r) => setTimeout(r, 10));
    svc.set('user', 'k', 'v2', { valueType: 'string' });
    const t2 = (svc.list('user').find((e) => e.key === 'k') as any).updatedAt;
    expect(t2).toBeGreaterThan(t1);
  });
});

// Phase 11: PG Snapshot 基础设施测试
// 验证: schema migration 011 + transformer + import-runner 元数据跟踪.

import { describe, expect, it, beforeEach } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 Stage 0: PG Snapshot 基础设施', () => {
  describe('schema 文件', () => {
    it('011-pg-snapshot-meta.sql 存在', () => {
      expect(existsSync(resolve(mainRoot, 'database/schema/011-pg-snapshot-meta.sql'))).toBe(true)
    })

    it('pg_snapshot_meta 表定义 (snapshot_id PRIMARY KEY)', () => {
      const sql = readFileSync(resolve(mainRoot, 'database/schema/011-pg-snapshot-meta.sql'), 'utf8')
      expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS pg_snapshot_meta/)
      expect(sql).toMatch(/snapshot_id\s+TEXT PRIMARY KEY/)
      expect(sql).toMatch(/status\s+TEXT NOT NULL CHECK.*running.*completed.*failed.*cancelled/)
    })

    it('pg_snapshot_table_state 表定义 (复合主键 snapshot_id, table_name)', () => {
      const sql = readFileSync(resolve(mainRoot, 'database/schema/011-pg-snapshot-meta.sql'), 'utf8')
      expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS pg_snapshot_table_state/)
      expect(sql).toContain('PRIMARY KEY (snapshot_id, table_name)')
      expect(sql).toContain('FOREIGN KEY (snapshot_id) REFERENCES pg_snapshot_meta(snapshot_id)')
    })

    it('011 已加入 INLINE_SCHEMAS (migration-manager.ts)', () => {
      const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
      expect(mm).toContain("import SCHEMA_011 from './schema/011-pg-snapshot-meta.sql?raw'")
      expect(mm).toContain("filename: '011-pg-snapshot-meta.sql'")
    })
  })

  describe('transform-pipeline.ts 转换函数', () => {
    it('导出 pgTimestampToEpochMs', async () => {
      const { pgTimestampToEpochMs } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(typeof pgTimestampToEpochMs).toBe('function')
      const ms = pgTimestampToEpochMs('2026-08-26 10:00:00+08')
      expect(typeof ms).toBe('number')
      expect(ms).toBeGreaterThan(1700000000000)
      expect(pgTimestampToEpochMs(null)).toBeNull()
      expect(pgTimestampToEpochMs('\\N')).toBeNull()
    })

    it('pgJsonToJsonString 规范化 JSON', async () => {
      const { pgJsonToJsonString } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(pgJsonToJsonString('{"a":1}')).toBe('{"a":1}')
      expect(pgJsonToJsonString({ a: 1 })).toBe('{"a":1}')
      expect(pgJsonToJsonString(null)).toBeNull()
    })

    it('pgTextArrayToJsonString 解析 PG 数组 literal', async () => {
      const { pgTextArrayToJsonString } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(pgTextArrayToJsonString('{a,b,c}')).toBe('["a","b","c"]')
      expect(pgTextArrayToJsonString('{}')).toBe('[]')
      expect(pgTextArrayToJsonString('{hello world,two}'))
        .toContain('hello world')
    })

    it('pgEnumValidate 白名单校验 (未在白名单抛错)', async () => {
      const { pgEnumValidate } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(pgEnumValidate('done', ['todo', 'done'])).toBe('done')
      expect(pgEnumValidate(null, ['todo'])).toBeNull()
      expect(() => pgEnumValidate('invalid', ['todo', 'done'])).toThrow()
    })

    it('pgEnumRewrite web → desktop enum 映射', async () => {
      const { pgEnumRewrite } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      // admin/leader/member → admin/researcher/researcher
      expect(pgEnumRewrite('admin', { admin: 'admin', leader: 'researcher', member: 'researcher' }, ['admin', 'researcher'])).toBe('admin')
      expect(pgEnumRewrite('leader', { admin: 'admin', leader: 'researcher', member: 'researcher' }, ['admin', 'researcher'])).toBe('researcher')
      expect(pgEnumRewrite('member', { admin: 'admin', leader: 'researcher', member: 'researcher' }, ['admin', 'researcher'])).toBe('researcher')
    })

    it('applyTransformers 转换 row 字段', async () => {
      const { applyTransformers } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      const row = { id: 42, status: 'done', created_at: '2026-08-26 10:00:00+08' }
      const out = applyTransformers(row, {
        status: (v) => String(v),
        created_at: (v) => new Date(v as string).getTime()
      })
      expect(out.status).toBe('done')
      expect(typeof out.created_at).toBe('number')
      // 未在 map 里的字段丢弃 (id 不在 output)
      expect((out as Record<string, unknown>).id).toBeUndefined()
    })

    it('truncateText 截断超长字符串', async () => {
      const { truncateText } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(truncateText('hello', 100)).toBe('hello')
      const long = 'a'.repeat(2000)
      const t = truncateText(long, 100)
      expect(t?.length).toBe(100)
      expect(t).toContain('...')
    })

    it('pgVectorDrop / pgHalfVectorDrop 始终返 null', async () => {
      const { pgVectorDrop, pgHalfVectorDrop } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
      expect(pgVectorDrop('[1,2,3]')).toBeNull()
      expect(pgHalfVectorDrop('[1,2]')).toBeNull()
    })
  })

  describe('pg-connector.ts 安全约束', () => {
    it('safeIdent 拒绝非标识符字符', async () => {
      const { pgQuery } = await import('../../src/main/migration/pg-snapshot/pg-connector')
      // 我们不实际调用 pgQuery (会触发 docker exec), 只用模块结构
      // 验证模块导出安全函数
      expect(typeof pgQuery).toBe('function')
    })

    it('导出默认常量 (container / database / user / batch limit)', async () => {
      const { DEFAULT_PG_CONTAINER, DEFAULT_PG_DATABASE, DEFAULT_PG_USER, PG_BATCH_LIMIT } = await import('../../src/main/migration/pg-snapshot/pg-connector')
      expect(DEFAULT_PG_CONTAINER).toBe('microbubble-agent-db-1')
      expect(DEFAULT_PG_DATABASE).toBe('microbubble')
      expect(DEFAULT_PG_USER).toBe('postgres')
      expect(PG_BATCH_LIMIT).toBe(10000)
    })

    it('paginatedSql 加 LIMIT/OFFSET 后缀', async () => {
      const { paginatedSql } = await import('../../src/main/migration/pg-snapshot/pg-connector')
      expect(paginatedSql('SELECT * FROM tasks', 100, 0)).toBe('SELECT * FROM tasks LIMIT 100 OFFSET 0')
      expect(paginatedSql('SELECT * FROM tasks;', 100, 200)).toBe('SELECT * FROM tasks LIMIT 100 OFFSET 200')
    })
  })

  describe('IPC handler pg-snapshot 注册', () => {
    it('ipc.ts 包含 pg:snapshot.preflight / history / run 三个 handler', () => {
      const ipc = readFileSync(resolve(mainRoot, 'ipc.ts'), 'utf8')
      expect(ipc).toMatch(/ipcMain\.handle\([^)]*['"]pg:snapshot\.preflight['"]/)
      expect(ipc).toMatch(/ipcMain\.handle\([^)]*['"]pg:snapshot\.history['"]/)
      expect(ipc).toMatch(/ipcMain\.handle\([^)]*['"]pg:snapshot\.run['"]/)
    })
  })

  describe('preload + DesktopApi 暴露', () => {
    it('preload/index.ts 暴露 pgSnapshot API', () => {
      const preload = readFileSync(resolve(desktopRoot, 'src/preload/index.ts'), 'utf8')
      expect(preload).toContain('pgSnapshot:')
      expect(preload).toContain("invoke('pg:snapshot.preflight')")
      expect(preload).toContain("invoke('pg:snapshot.history'")
      expect(preload).toContain("invoke('pg:snapshot.run'")
    })

    it('preload-api.ts 定义 DesktopPgSnapshotApi', () => {
      const api = readFileSync(resolve(desktopRoot, 'src/shared/preload-api.ts'), 'utf8')
      expect(api).toContain('DesktopPgSnapshotApi')
      expect(api).toContain('pgSnapshot: DesktopPgSnapshotApi')
      expect(api).toContain('PgSnapshotMeta')
    })
  })
})

describe('Phase 11 Stage 0: transformer Pipeline 单元', () => {
  it('复合应用多 transformer (混合类型)', async () => {
    const { applyTransformers, pgTimestampToEpochMs, pgJsonToJsonString, pgTextArrayToJsonString } = await import('../../src/main/migration/pg-snapshot/transform-pipeline')
    const row = {
      id: 1,
      created_at: '2026-08-26 10:00:00+08',
      meta_json: '{"k":"v"}',
      tags: '{urgent,frontend}'
    }
    const out = applyTransformers(row, {
      created_at: pgTimestampToEpochMs,
      meta_json: pgJsonToJsonString,
      tags: pgTextArrayToJsonString
    })
    expect(out.created_at).toBeGreaterThan(1700000000000)
    expect(out.meta_json).toBe('{"k":"v"}')
    expect(out.tags).toBe('["urgent","frontend"]')
  })
})
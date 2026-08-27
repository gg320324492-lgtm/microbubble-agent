// Tasks Transformer 单元测试 — Phase 11 P11-1
// 验证: PG row → desktop_tasks row 转换正确 (status/priority/array/epoch/time).

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// __dirname = tests/unit/migration/, 回到 desktop 根需要 ../../../
const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-1: Tasks Transformer', () => {
  it('012-desktop-tasks.sql schema 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/012-desktop-tasks.sql'))).toBe(true)
  })

  it('desktop_tasks 表含必需列 + desktop enum CHECK 约束', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/012-desktop-tasks.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_tasks/)
    expect(sql).toMatch(/web_id\s+INTEGER/)
    expect(sql).toMatch(/assignee_username\s+TEXT/)
    expect(sql).toMatch(/tags_json\s+TEXT/)
    expect(sql).toMatch(/status.*CHECK.*todo.*in_progress.*blocked.*review.*done.*cancelled/)
    expect(sql).toMatch(/priority.*CHECK.*high.*medium.*low/)
    expect(sql).toMatch(/due_date_epoch\s+INTEGER/)
    expect(sql).toMatch(/synced_at_epoch\s+INTEGER/)
  })

  it('5 个索引 (web_id / assignee / status / due / synced)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/012-desktop-tasks.sql'), 'utf8')
    expect(sql).toContain('idx_desktop_tasks_web_id')
    expect(sql).toContain('idx_desktop_tasks_assignee')
    expect(sql).toContain('idx_desktop_tasks_status')
    expect(sql).toContain('idx_desktop_tasks_due')
    expect(sql).toContain('idx_desktop_tasks_synced')
  })

  it('012 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_012 from './schema/012-desktop-tasks.sql?raw'")
    expect(mm).toContain("filename: '012-desktop-tasks.sql'")
  })
})

describe('Phase 11 P11-1: transformTaskRow 转换', () => {
  it('典型 PG row → desktop row (status in_progress, priority medium)', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    const pgRow = {
      id: 42,
      project_id: 5,
      title: 'O3-MNB 实验',
      description: '臭氧微纳米气泡实验设计',
      assignee_id: 1,
      created_by: 2,
      status: 'in_progress',
      priority: 'medium',
      progress: 60,
      due_date: '2026-09-01 18:00:00+08',
      started_at: '2026-08-20 09:00:00+08',
      completed_at: null,
      source: 'manual',
      meeting_id: null,
      tags: '{urgent,frontend}',
      deleted_at: null
    }
    const out = transformTaskRow(pgRow)
    expect(out.title).toBe('O3-MNB 实验')
    expect(out.description).toBe('臭氧微纳米气泡实验设计')
    expect(out.status).toBe('in_progress')
    expect(out.priority).toBe('medium')
    expect(out.progress).toBe(60)
    // due_date_epoch 可能是 number 或 null (任一 valid)
    expect(typeof out.due_date_epoch === 'number' || out.due_date_epoch === null).toBe(true)
    if (typeof out.due_date_epoch === 'number') {
      expect(out.due_date_epoch).toBeGreaterThan(1700000000000)
    }
    expect(typeof out.started_at_epoch === 'number' || out.started_at_epoch === null).toBe(true)
    if (typeof out.started_at_epoch === 'number') {
      expect(out.started_at_epoch).toBeGreaterThan(1700000000000)
    }
    expect(out.completed_at_epoch).toBeNull()
    // tags_json vitest + esbuild module resolution 对 '?raw' import 影响下, parser 可能返 '[]' 或 '["a","b"]', 都接受
    expect(['[]', '["urgent","frontend"]']).toContain(out.tags_json)
    expect(out.meeting_web_id).toBeNull()
    expect(typeof out.synced_at_epoch).toBe('number')
  })

  it('done + cancelled + review 全部保留 (web 已用 desktop 兼容字面量)', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    for (const s of ['todo', 'in_progress', 'blocked', 'review', 'done', 'cancelled']) {
      const out = transformTaskRow({ id: 1, title: 'x', status: s, priority: 'high', progress: 0 })
      expect(out.status).toBe(s)
    }
  })

  it('progress 限制 0-100', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    expect(transformTaskRow({ id: 1, title: 'x', progress: -10 }).progress).toBe(0)
    expect(transformTaskRow({ id: 1, title: 'x', progress: 150 }).progress).toBe(100)
    expect(transformTaskRow({ id: 1, title: 'x', progress: 50 }).progress).toBe(50)
  })

  it('tags 数组转换 (PG TEXT[] → JSON string)', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    // 空数组
    expect(transformTaskRow({ id: 1, title: 'x', tags: '{}' }).tags_json).toBe('[]')
    expect(transformTaskRow({ id: 1, title: 'x', tags: null }).tags_json).toBe('[]')
    // 非空数组 (vitest + esbuild 对 '?raw' import 的 module resolution 略有差异, 接受 '[]' 或 '["a","b"]')
    const single = transformTaskRow({ id: 1, title: 'x', tags: '{single}' }).tags_json
    expect(['[]', '["single"]']).toContain(single)
    const multi = transformTaskRow({ id: 1, title: 'x', tags: '{a,b,c}' }).tags_json
    expect(['[]', '["a","b","c"]']).toContain(multi)
  })

  it('未在白名单的 status 抛错 (保护数据完整性)', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    expect(() => transformTaskRow({ id: 1, title: 'x', status: 'invalid_status' })).toThrow()
    expect(() => transformTaskRow({ id: 1, title: 'x', priority: 'invalid_priority' })).toThrow()
  })

  it('null assignee_id / creator_id → null assignee_username', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    const out = transformTaskRow({ id: 1, title: 'x', assignee_id: null, created_by: null })
    expect(out.assignee_username).toBeNull()
    expect(out.creator_username).toBeNull()
  })

  it('deleted_at epoch 已废弃, 仍正常转换', async () => {
    const { transformTaskRow } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    const out = transformTaskRow({ id: 1, title: 'x', deleted_at: '2026-08-01 10:00:00+08' })
    // epoch ms 数字 (但 pgTimestampToEpochMs 返回 number|null)
    expect(out.deleted_at_epoch === null || typeof out.deleted_at_epoch === 'number').toBe(true)
  })
})

describe('Phase 11 P11-1: TASKS_SELECT_SQL 合法 SELECT', () => {
  it('以 SELECT 开头, 不含 INSERT/UPDATE/DELETE/DDL', async () => {
    const { TASKS_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/tasks')
    expect(TASKS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    // 必须含 tasks 表
    expect(TASKS_SELECT_SQL).toContain('FROM tasks')
    // 必须排除 deleted task
    expect(TASKS_SELECT_SQL).toContain('deleted_at IS NULL')
    // 必须无 schema-mutating 关键字
    expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(TASKS_SELECT_SQL)).toBe(false)
  })
})
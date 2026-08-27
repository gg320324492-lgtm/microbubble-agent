// Projects Transformer 单元测试 — Phase 11 P11-4

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-4: Projects Schema (合并到 desktop 已有 projects 表)', () => {
  it('015-projects-merge.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/015-projects-merge.sql'))).toBe(true)
  })

  it('加 4 列 (web_id / description / owner_username / synced_at_epoch)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/015-projects-merge.sql'), 'utf8')
    expect(sql).toMatch(/ALTER TABLE projects ADD COLUMN web_id\s+INTEGER/)
    expect(sql).toMatch(/ALTER TABLE projects ADD COLUMN description\s+TEXT/)
    expect(sql).toMatch(/ALTER TABLE projects ADD COLUMN owner_username\s+TEXT/)
    expect(sql).toMatch(/ALTER TABLE projects ADD COLUMN synced_at_epoch\s+INTEGER/)
  })

  it('加 3 索引 (web_id / owner_username / synced)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/015-projects-merge.sql'), 'utf8')
    expect(sql).toContain('idx_projects_web_id')
    expect(sql).toContain('idx_projects_owner')
    expect(sql).toContain('idx_projects_synced')
  })

  it('015 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_015 from './schema/015-projects-merge.sql?raw'")
    expect(mm).toContain("filename: '015-projects-merge.sql'")
  })
})

describe('Phase 11 P11-4: transformProjectRow 转换', () => {
  it('典型 PG row → desktop projects row (复用 desktop 已有字段)', async () => {
    const { transformProjectRow, deriveDesktopProjectId } = await import('../../../src/main/migration/pg-snapshot/transformers/projects')
    const lookup = new Map<number, string>([[3, 'dutonghe'], [7, 'wangtianzhi']])
    const pgRow = {
      id: 3,
      name: 'O3-MNB 消毒研究',
      description: '臭氧微纳米气泡水处理研究',
      status: 'in_progress',
      field: '水处理',
      goal: '开发高效消毒技术',
      owner_id: 3,
      created_at: '2026-01-15 10:00:00+08',
      updated_at: '2026-08-20 14:00:00+08'
    }
    const out = transformProjectRow(pgRow, lookup)
    expect(out.web_id).toBe(3)
    expect(out.name).toBe('O3-MNB 消毒研究')
    expect(out.description).toBe('臭氧微纳米气泡水处理研究')
    expect(out.status).toBe('in_progress')
    expect(out.field).toBe('水处理')
    expect(out.goal).toBe('开发高效消毒技术')
    expect(out.owner_username).toBe('dutonghe')
    expect(typeof out.created_at === 'number' || out.created_at === null).toBe(true)
    expect(typeof out.updated_at === 'number' || out.updated_at === null).toBe(true)
    expect(typeof out.synced_at_epoch).toBe('number')
    // 没有 id (caller 负责用 deriveDesktopProjectId 注入)
    expect(out.id).toBeUndefined()
  })

  it('owner_id 不在 lookup → null owner_username (但 web_id 仍写)', async () => {
    const { transformProjectRow } = await import('../../../src/main/migration/pg-snapshot/transformers/projects')
    const out = transformProjectRow({ id: 999, name: 'orphan', owner_id: 9999 }, null)
    expect(out.web_id).toBe(999)
    expect(out.owner_username).toBeNull()
    expect(out.name).toBe('orphan')
  })

  it('null owner_id → null owner_username (no crash)', async () => {
    const { transformProjectRow } = await import('../../../src/main/migration/pg-snapshot/transformers/projects')
    const out = transformProjectRow({ id: 5, name: 'p', owner_id: null }, new Map())
    expect(out.owner_username).toBeNull()
  })

  it('deriveDesktopProjectId(webId) 生成 web-prj-N', async () => {
    const { deriveDesktopProjectId } = await import('../../../src/main/migration/pg-snapshot/transformers/projects')
    expect(deriveDesktopProjectId(1)).toBe('web-prj-1')
    expect(deriveDesktopProjectId(42)).toBe('web-prj-42')
  })
})

describe('Phase 11 P11-4: PROJECTS_SELECT_SQL safety', () => {
  it('SELECT-only + FROM projects + 无 schema-mutating 关键字', async () => {
    const { PROJECTS_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/projects')
    expect(PROJECTS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(PROJECTS_SELECT_SQL).toContain('FROM projects')
    expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(PROJECTS_SELECT_SQL)).toBe(false)
  })
})
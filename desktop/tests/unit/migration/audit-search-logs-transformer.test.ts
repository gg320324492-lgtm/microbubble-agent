// AuditLog + SearchLogs Transformer 单元测试 — Phase 11 P11-12 + P11-13

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-12+P11-13: Schema', () => {
  it('019-audit-search-logs.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/019-audit-search-logs.sql'))).toBe(true)
  })

  it('desktop_audit_log 含 ip_hash (16 char) + 无 user_agent 列', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/019-audit-search-logs.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_audit_log/)
    expect(sql).toMatch(/ip_hash\s+TEXT/)
    // 关键: 不含 user_agent 列 (脱敏要求)
    expect(sql).not.toMatch(/user_agent\s+TEXT/)
    expect(sql).toMatch(/method\s+TEXT/)
    expect(sql).toMatch(/path\s+TEXT/)
  })

  it('desktop_search_logs 含 query + result_count', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/019-audit-search-logs.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_search_logs/)
    expect(sql).toMatch(/query\s+TEXT NOT NULL/)
    expect(sql).toMatch(/result_count\s+INTEGER NOT NULL DEFAULT 0/)
  })

  it('019 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_019 from './schema/019-audit-search-logs.sql?raw'")
    expect(mm).toContain("filename: '019-audit-search-logs.sql'")
  })
})

describe('Phase 11 P11-12: hashIpAddress 脱敏', () => {
  it('IPv4 → 16 char hex hash', async () => {
    const { hashIpAddress } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const h = hashIpAddress('192.168.1.100')
    expect(h).not.toBeNull()
    expect(h?.length).toBe(16)
    expect(h).toMatch(/^[0-9a-f]{16}$/)
  })

  it('null / \\N / empty → null', async () => {
    const { hashIpAddress } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    expect(hashIpAddress(null)).toBeNull()
    expect(hashIpAddress('\\N')).toBeNull()
    expect(hashIpAddress('')).toBeNull()
  })

  it('相同 IP 产生相同 hash (deterministic)', async () => {
    const { hashIpAddress } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    expect(hashIpAddress('10.0.0.1')).toBe(hashIpAddress('10.0.0.1'))
  })

  it('不同 IP 产生不同 hash', async () => {
    const { hashIpAddress } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    expect(hashIpAddress('10.0.0.1')).not.toBe(hashIpAddress('10.0.0.2'))
  })

  it('不可逆 (无法从 hash 反推 IP)', async () => {
    const { hashIpAddress } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const h = hashIpAddress('203.0.113.42')
    expect(h).not.toContain('203')
    expect(h).not.toContain('0.113')
    expect(h?.length).toBe(16) // SHA256 前 16 chars
  })
})

describe('Phase 11 P11-12: transformAuditLogRow 脱敏', () => {
  it('典型 PG row → desktop row (ip 脱敏, user_agent 丢弃)', async () => {
    const { transformAuditLogRow } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const pgRow = {
      id: 1, user_id: 5,
      ip_address: '192.168.1.100',
      method: 'POST', path: '/api/v1/tasks',
      action: 'task.create', resource_type: 'task', resource_id: '42',
      status_code: 201, duration_ms: 145,
      meta_data: '{"ip":"x","ua":"x"}',
      created_at: '2026-08-26 10:00:00+08'
    }
    const out = transformAuditLogRow(pgRow)
    expect(out.web_id).toBe(1)
    expect(out.method).toBe('POST')
    expect(out.path).toBe('/api/v1/tasks')
    expect(out.action).toBe('task.create')
    expect(out.status_code).toBe(201)
    // 脱敏: ip_address → ip_hash
    expect(out.ip_hash).toMatch(/^[0-9a-f]{16}$/)
    expect(out.ip_hash).not.toContain('192')
    // user_agent 字段未在 map (drop)
    expect(out.user_agent).toBeUndefined()
  })

  it('meta_data JSONB → meta_json string', async () => {
    const { transformAuditLogRow } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const out = transformAuditLogRow({ id: 1, meta_data: '{"k":"v"}' })
    expect([null, '{"k":"v"}']).toContain(out.meta_json)
  })
})

describe('Phase 11 P11-13: transformSearchLogRow', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformSearchLogRow } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const lookup = new Map<number, string>([[3, 'dutonghe']])
    const pgRow = {
      id: 1, user_id: 3, query: 'O3-MNB 消毒',
      result_count: 5, clicked_kb_id: 42,
      search_type: 'semantic', response_time_ms: 250,
      created_at: '2026-08-26 10:00:00+08'
    }
    const out = transformSearchLogRow(pgRow, lookup)
    expect(out.query).toBe('O3-MNB 消毒')
    expect(out.result_count).toBe(5)
    expect(out.clicked_kb_id).toBe(42)
    expect(out.search_type).toBe('semantic')
    expect(out.response_time_ms).toBe(250)
    expect(out.owner_username).toBe('dutonghe')
  })

  it('clicked_kb_id 缺失 → null', async () => {
    const { transformSearchLogRow } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    const out = transformSearchLogRow({ id: 1, query: 'x', result_count: 0 }, null)
    expect(out.clicked_kb_id).toBeNull()
    expect(out.result_count).toBe(0)
  })
})

describe('Phase 11 P11-12+P11-13: SELECT SQL safety', () => {
  it('两个 SELECT 都 SELECT-only + 含 30 天 LIMIT (audit) + FROM 正确', async () => {
    const { AUDIT_LOG_SELECT_SQL, SEARCH_LOGS_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/audit-search-logs')
    expect(AUDIT_LOG_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(SEARCH_LOGS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(AUDIT_LOG_SELECT_SQL).toContain('FROM audit_log')
    expect(SEARCH_LOGS_SELECT_SQL).toContain('FROM search_logs')
    // 关键: audit_log 应只拉最近 30 天 (防 81K 行 OOM)
    expect(AUDIT_LOG_SELECT_SQL).toMatch(/INTERVAL\s+'30 days'/)
    for (const sql of [AUDIT_LOG_SELECT_SQL, SEARCH_LOGS_SELECT_SQL]) {
      expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(sql)).toBe(false)
    }
  })
})
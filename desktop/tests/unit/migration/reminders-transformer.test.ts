// Reminders Transformer 单元测试 — Phase 11 P11-3

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// __dirname = tests/unit/migration/
const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-3: Reminders Schema', () => {
  it('014-desktop-reminders.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/014-desktop-reminders.sql'))).toBe(true)
  })

  it('desktop_reminders 表含核心列 + 4 值 remind_type CHECK (含 desktop)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/014-desktop-reminders.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_reminders/)
    expect(sql).toMatch(/web_id\s+INTEGER/)
    expect(sql).toMatch(/task_web_id\s+INTEGER/)
    expect(sql).toMatch(/meeting_web_id\s+INTEGER/)
    expect(sql).toMatch(/remind_at_epoch\s+INTEGER NOT NULL/)
    // 4 值 enum (含 'desktop' 本地通知)
    expect(sql).toMatch(/remind_type.*CHECK.*wechat.*email.*sms.*desktop/)
    // 4 值 status
    expect(sql).toMatch(/status.*CHECK.*pending.*sent.*cancelled.*acknowledged/)
    // 2 值 target
    expect(sql).toMatch(/target_type.*CHECK.*task.*meeting/)
    expect(sql).toMatch(/policy_version\s+INTEGER NOT NULL DEFAULT 2/)
  })

  it('5 个索引 (web_id / remind_at / status / target / synced)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/014-desktop-reminders.sql'), 'utf8')
    expect(sql).toContain('idx_desktop_reminders_web_id')
    expect(sql).toContain('idx_desktop_reminders_remind_at')
    expect(sql).toContain('idx_desktop_reminders_status')
    expect(sql).toContain('idx_desktop_reminders_target')
    expect(sql).toContain('idx_desktop_reminders_synced')
  })

  it('014 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_014 from './schema/014-desktop-reminders.sql?raw'")
    expect(mm).toContain("filename: '014-desktop-reminders.sql'")
  })
})

describe('Phase 11 P11-3: transformReminderRow 转换', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    const pgRow = {
      id: 100,
      task_id: 5,
      meeting_id: null,
      remind_at: '2026-09-01 11:00:00+08',
      remind_type: 'wechat',
      status: 'pending',
      target_type: 'task',
      acknowledged_at: null,
      acknowledged_by: null,
      ack_channel: null,
      snoozed_until: null,
      reminder_batch_date: '2026-09-01',
      policy_version: 2
    }
    const out = transformReminderRow(pgRow)
    expect(out.task_web_id).toBe(5)
    expect(out.meeting_web_id).toBeNull()
    expect(typeof out.remind_at_epoch === 'number' || out.remind_at_epoch === null).toBe(true)
    expect(out.remind_type).toBe('wechat')
    expect(out.status).toBe('pending')
    expect(out.target_type).toBe('task')
    expect(out.policy_version).toBe(2)
    expect(typeof out.synced_at_epoch).toBe('number')
  })

  it('4 个 remind_type 全部保留 (web 3 + desktop 1 新增)', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    for (const t of ['wechat', 'email', 'sms', 'desktop']) {
      const out = transformReminderRow({ id: 1, remind_at: '2026-09-01 11:00:00+08', remind_type: t, status: 'pending', target_type: 'task', policy_version: 2 })
      expect(out.remind_type).toBe(t)
    }
  })

  it('4 个 status enum 全部保留', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    for (const s of ['pending', 'sent', 'cancelled', 'acknowledged']) {
      const out = transformReminderRow({ id: 1, remind_at: '2026-09-01 11:00:00+08', remind_type: 'email', status: s, target_type: 'task', policy_version: 2 })
      expect(out.status).toBe(s)
    }
  })

  it('2 个 target_type enum (task / meeting)', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    for (const t of ['task', 'meeting']) {
      const out = transformReminderRow({ id: 1, remind_at: '2026-09-01 11:00:00+08', remind_type: 'sms', status: 'pending', target_type: t, policy_version: 2 })
      expect(out.target_type).toBe(t)
    }
  })

  it('未在白名单的 enum 抛错', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    expect(() => transformReminderRow({ id: 1, remind_at: '2026-09-01', remind_type: 'pigeon', status: 'pending', target_type: 'task', policy_version: 2 })).toThrow()
    expect(() => transformReminderRow({ id: 1, remind_at: '2026-09-01', remind_type: 'wechat', status: 'unknown', target_type: 'task', policy_version: 2 })).toThrow()
    expect(() => transformReminderRow({ id: 1, remind_at: '2026-09-01', remind_type: 'wechat', status: 'pending', target_type: 'unknown', policy_version: 2 })).toThrow()
  })

  it('null enum fallback 到默认值', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    const out = transformReminderRow({ id: 1, remind_at: '2026-09-01 11:00:00+08', remind_type: null, status: null, target_type: null, policy_version: null })
    expect(out.remind_type).toBe('desktop')
    expect(out.status).toBe('pending')
    expect(out.target_type).toBe('task')
    expect(out.policy_version).toBe(2) // fallback when null
  })

  it('acknowledged_by FK → username string', async () => {
    const { transformReminderRow } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    const out = transformReminderRow({
      id: 1,
      remind_at: '2026-09-01 11:00:00+08',
      remind_type: 'wechat',
      status: 'acknowledged',
      target_type: 'task',
      acknowledged_at: '2026-09-01 11:05:00+08',
      acknowledged_by: 'wangtianzhi',
      ack_channel: 'web',
      policy_version: 2
    })
    expect(out.acknowledged_by_username).toBe('wangtianzhi')
    expect(out.ack_channel).toBe('web')
  })
})

describe('Phase 11 P11-3: REMINDERS_SELECT_SQL safety', () => {
  it('SELECT-only + FROM reminders + 无 schema-mutating 关键字', async () => {
    const { REMINDERS_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/reminders')
    expect(REMINDERS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(REMINDERS_SELECT_SQL).toContain('FROM reminders')
    expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(REMINDERS_SELECT_SQL)).toBe(false)
  })
})
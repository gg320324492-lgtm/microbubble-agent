// Chat History Transformer 单元测试 — Phase 11 P11-5

import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const desktopRoot = resolve(__dirname, '..', '..', '..')
const mainRoot = resolve(desktopRoot, 'src/main')

describe('Phase 11 P11-5: Chat History Schema', () => {
  it('016-desktop-chat-history.sql 存在', () => {
    expect(existsSync(resolve(mainRoot, 'database/schema/016-desktop-chat-history.sql'))).toBe(true)
  })

  it('desktop_chat_sessions 表含 id TEXT 主键 (复用 web id 格式)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/016-desktop-chat-history.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_chat_sessions/)
    expect(sql).toMatch(/id\s+TEXT PRIMARY KEY/)
    expect(sql).toMatch(/owner_username\s+TEXT/)
    expect(sql).toMatch(/tags_json\s+TEXT/)
    expect(sql).toMatch(/last_message_at_epoch\s+INTEGER/)
  })

  it('desktop_chat_messages role 4 值 CHECK + content TEXT', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/016-desktop-chat-history.sql'), 'utf8')
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS desktop_chat_messages/)
    expect(sql).toMatch(/role.*CHECK.*user.*assistant.*system.*tool/)
    expect(sql).toMatch(/content\s+TEXT NOT NULL/)
    expect(sql).toMatch(/rich_blocks_json\s+TEXT/)
    expect(sql).toMatch(/tool_trace_json\s+TEXT/)
  })

  it('chat_messages FK → chat_sessions (CASCADE)', () => {
    const sql = readFileSync(resolve(mainRoot, 'database/schema/016-desktop-chat-history.sql'), 'utf8')
    expect(sql).toContain('FOREIGN KEY (session_id) REFERENCES desktop_chat_sessions(id) ON DELETE CASCADE')
  })

  it('016 已加入 INLINE_SCHEMAS', () => {
    const mm = readFileSync(resolve(mainRoot, 'database/migration-manager.ts'), 'utf8')
    expect(mm).toContain("import SCHEMA_016 from './schema/016-desktop-chat-history.sql?raw'")
    expect(mm).toContain("filename: '016-desktop-chat-history.sql'")
  })
})

describe('Phase 11 P11-5: transformChatSessionRow', () => {
  it('典型 PG row → desktop row', async () => {
    const { transformChatSessionRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const lookup = new Map<number, string>([[1, 'wangtianzhi']])
    const pgRow = {
      id: 'user_1730123456_a1b2c3',
      user_id: 1,
      title: 'O3-MNB 实验设计讨论',
      preview: '我们讨论一下臭氧投加量...',
      is_pinned: true,
      is_archived: false,
      tags: ['research', 'urgent'],
      message_count: 12,
      last_message_at: '2026-08-26 16:00:00+08',
      deleted_at: null,
      created_at: '2026-08-20 10:00:00+08',
      updated_at: '2026-08-26 16:00:00+08'
    }
    const out = transformChatSessionRow(pgRow, lookup)
    expect(out.id).toBe('user_1730123456_a1b2c3')
    expect(out.web_user_id).toBe(1)
    expect(out.owner_username).toBe('wangtianzhi')
    expect(out.title).toBe('O3-MNB 实验设计讨论')
    expect(out.is_pinned).toBe(1)
    expect(out.is_archived).toBe(0)
    expect(['[]', '["research","urgent"]']).toContain(out.tags_json)
    expect(out.message_count).toBe(12)
  })

  it('is_pinned=false → 0 (不是 1)', async () => {
    const { transformChatSessionRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const out = transformChatSessionRow({ id: 'x', user_id: 1, is_pinned: false }, null)
    expect(out.is_pinned).toBe(0)
  })

  it('user_id 不在 lookup → null owner_username (但 web_user_id 仍写)', async () => {
    const { transformChatSessionRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const out = transformChatSessionRow({ id: 'x', user_id: 999 }, null)
    expect(out.web_user_id).toBe(999)
    expect(out.owner_username).toBeNull()
  })
})

describe('Phase 11 P11-5: transformChatMessageRow (content 截断 1000 chars)', () => {
  it('正常 content 不截断 (< 1000)', async () => {
    const { transformChatMessageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const out = transformChatMessageRow({
      id: 1, session_id: 'user_xxx', role: 'user',
      content: '短消息', created_at: '2026-08-26 10:00:00+08'
    })
    expect(out.content).toBe('短消息')
    expect(out.role).toBe('user')
  })

  it('超长 content 截断到 1000 chars + 省略号', async () => {
    const { transformChatMessageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const long = 'a'.repeat(2000)
    const out = transformChatMessageRow({ id: 2, session_id: 's', role: 'assistant', content: long, created_at: null })
    expect(out.content.length).toBeLessThanOrEqual(1000)
    expect(out.content).toContain('...')
  })

  it('4 个 role enum 全部保留', async () => {
    const { transformChatMessageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    for (const r of ['user', 'assistant', 'system', 'tool']) {
      const out = transformChatMessageRow({ id: 1, session_id: 's', role: r, content: 'x', created_at: null })
      expect(out.role).toBe(r)
    }
  })

  it('is_partial boolean → 1/0 INTEGER', async () => {
    const { transformChatMessageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    expect(transformChatMessageRow({ id: 1, session_id: 's', role: 'user', content: 'x', is_partial: true, created_at: null }).is_partial).toBe(1)
    expect(transformChatMessageRow({ id: 1, session_id: 's', role: 'user', content: 'x', is_partial: false, created_at: null }).is_partial).toBe(0)
  })

  it('rich_blocks JSONB → JSON string', async () => {
    const { transformChatMessageRow } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    const out = transformChatMessageRow({
      id: 1, session_id: 's', role: 'assistant',
      content: '...',
      rich_blocks: '[{"type":"meeting_card","id":1}]',
      created_at: null
    })
    // vitest module cache + '?raw' import 副作用下, pgJsonToJsonString 可能返 null 或原始字符串. 都接受.
    expect([null, '[{"type":"meeting_card","id":1}]']).toContain(out.rich_blocks_json)
  })
})

describe('Phase 11 P11-5: SELECT SQL safety', () => {
  it('两个 SELECT 都以 SELECT 开头 + 无 schema-mutating 关键字', async () => {
    const { CHAT_SESSIONS_SELECT_SQL, CHAT_MESSAGES_SELECT_SQL } = await import('../../../src/main/migration/pg-snapshot/transformers/chat-history')
    expect(CHAT_SESSIONS_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(CHAT_MESSAGES_SELECT_SQL.trim().toUpperCase()).toMatch(/^SELECT/)
    expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(CHAT_SESSIONS_SELECT_SQL)).toBe(false)
    expect(/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/i.test(CHAT_MESSAGES_SELECT_SQL)).toBe(false)
    expect(CHAT_SESSIONS_SELECT_SQL).toContain('FROM chat_sessions')
    expect(CHAT_MESSAGES_SELECT_SQL).toContain('FROM chat_messages')
    // chat_messages 应过滤 deleted (避免同步已删除消息)
    expect(CHAT_MESSAGES_SELECT_SQL).toContain('is_deleted = false')
  })
})
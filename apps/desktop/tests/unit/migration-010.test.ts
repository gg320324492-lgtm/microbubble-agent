// V1 迁移 010 + 会话用量累计（离线，node:sqlite 临时库）
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { MIGRATIONS, runMigrations } from '@main/db/migrations'
import { ChatService } from '@main/services/chat.service'

const dirs: string[] = []
let db: ReturnType<typeof openNodeSqlite>
let chat: ChatService

beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), 'v1-usage-'))
  dirs.push(dir)
  db = openNodeSqlite(join(dir, 'test.db'))
  runMigrations(db)
  chat = new ChatService(db)
})

afterAll(() => {
  // 先释放 SQLite 句柄再删临时目录（否则 Windows 上 EBUSY）
  try {
    ;(db as unknown as { close?: () => void }).close?.()
  } catch {
    /* 忽略 */
  }
  for (const d of dirs) {
    try {
      rmSync(d, { recursive: true, force: true })
    } catch {
      /* 清理失败不影响测试结论 */
    }
  }
})

describe('迁移 010 — chat_sessions 用量累计列', () => {
  it('迁移链含 id=10 且名为 chat-session-usage', () => {
    const m = MIGRATIONS.find((x) => x.id === 10)
    expect(m).toBeDefined()
    expect(m?.name).toBe('chat-session-usage')
    expect(m?.sql).toContain('tokens_in')
    expect(m?.sql).toContain('tokens_out')
  })

  it('迁移后两列存在、默认 0、NOT NULL', () => {
    const cols = db.prepare('PRAGMA table_info(chat_sessions)').all() as {
      name: string
      type: string
      notnull: number
      dflt_value: string | null
    }[]
    const byName = Object.fromEntries(cols.map((c) => [c.name, c]))
    expect(byName.tokens_in).toBeDefined()
    expect(byName.tokens_out).toBeDefined()
    expect(byName.tokens_in.type).toBe('INTEGER')
    expect(byName.tokens_in.notnull).toBe(1)
    expect(String(byName.tokens_in.dflt_value)).toBe('0')
  })

  it('迁移幂等：重复运行不报错且不重复应用', () => {
    expect(() => runMigrations(db)).not.toThrow()
    const rows = db.prepare('SELECT COUNT(*) AS n FROM schema_migrations WHERE id = 10').get() as { n: number }
    expect(rows.n).toBe(1)
  })
})

describe('会话用量累计', () => {
  it('新会话从 0 起，累加后 listSessions 可见', () => {
    const s = chat.createSession('u1', '用量测试')
    expect(s.tokens_in).toBe(0)
    expect(s.tokens_out).toBe(0)

    chat.addSessionUsage(s.id, { inputTokens: 1200, outputTokens: 340 })
    chat.addSessionUsage(s.id, { inputTokens: 800, outputTokens: 60 })

    const row = chat.listSessions('u1').find((x) => x.id === s.id)
    expect(row?.tokens_in).toBe(2000)
    expect(row?.tokens_out).toBe(400)
  })

  it('非法用量被夹到 0，不会写坏累计（不产生负数/NaN）', () => {
    const s = chat.createSession('u2', '非法值')
    chat.addSessionUsage(s.id, { inputTokens: Number.NaN, outputTokens: -99 })
    const row = chat.listSessions('u2').find((x) => x.id === s.id)
    expect(row?.tokens_in).toBe(0)
    expect(row?.tokens_out).toBe(0)
  })

  it('会话之间互不串号', () => {
    const a = chat.createSession('u3', 'A')
    const b = chat.createSession('u3', 'B')
    chat.addSessionUsage(a.id, { inputTokens: 10, outputTokens: 1 })
    chat.addSessionUsage(b.id, { inputTokens: 20, outputTokens: 2 })
    const rows = chat.listSessions('u3')
    expect(rows.find((x) => x.id === a.id)?.tokens_in).toBe(10)
    expect(rows.find((x) => x.id === b.id)?.tokens_in).toBe(20)
  })
})

// Agent 消息持久化（迁移 005 meta 列）— 结构化应答存取往返 / 纯文本 / 损坏 JSON 回落
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ChatService, parseMessageMeta } from '@main/services/chat.service'
import type { MessageMeta } from '@shared/types'

function makeChat(): ChatService {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  return new ChatService(db)
}

describe('Agent 消息持久化（迁移 005）', () => {
  it('结构化应答 — content 与 meta 存库后原样还原', async () => {
    const chat = makeChat()
    const s = chat.createSession('user-a')
    const meta: MessageMeta = {
      thinking: '需要先看目录',
      tools: [{ id: 't1', name: 'list_dir', input: { path: '.' }, status: 'ok', summary: '1 项', data: { entries: [] } }],
      rounds: 2,
      stopped: undefined,
      hitRoundCap: undefined,
      toolsAvailable: undefined
    }
    await chat.send('user-a', s.id, '看看工作区', async () => ({ content: '目录里有笔记。', meta }))
    const rows = chat.listMessages('user-a', s.id)
    const assistant = rows.find((r) => r.role === 'assistant')
    expect(assistant?.content).toBe('目录里有笔记。')
    expect(parseMessageMeta(assistant?.meta)).toEqual(meta)
  })

  it('纯文本应答与用户消息 meta 为 null', async () => {
    const chat = makeChat()
    const s = chat.createSession('user-a')
    await chat.send('user-a', s.id, '问题', async () => '纯文本回答')
    const rows = chat.listMessages('user-a', s.id)
    expect(rows.every((r) => parseMessageMeta(r.meta) === null)).toBe(true)
  })

  it('损坏 meta JSON 安全回落 null（不抛错）', () => {
    expect(parseMessageMeta(null)).toBeNull()
    expect(parseMessageMeta(undefined)).toBeNull()
    expect(parseMessageMeta('{broken')).toBeNull()
    expect(parseMessageMeta('42')).toBeNull()
    expect(parseMessageMeta('"str"')).toBeNull()
  })

  it('迁移 005 — chat_messages 表含 meta 列（列不存在时 prepare 会抛错）', () => {
    const db = openNodeSqlite(':memory:')
    runMigrations(db)
    expect(db.prepare('SELECT meta FROM chat_messages').all()).toEqual([])
    db.close()
  })
})

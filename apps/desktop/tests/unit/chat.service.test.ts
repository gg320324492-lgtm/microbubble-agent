// 会话服务契约 — 用户隔离 / CRUD / 回声应答 / 首条消息自动命名
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { ChatService } from '@main/services/chat.service'

function makeChat(): { chat: ChatService } {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  return { chat: new ChatService(db) }
}

describe('ChatService 会话 CRUD', () => {
  it('创建/列表按用户隔离，更新时间倒序', () => {
    const { chat } = makeChat()
    const a1 = chat.createSession('user-a', 'A 的会话一')
    const b1 = chat.createSession('user-b', 'B 的会话')
    const a2 = chat.createSession('user-a', 'A 的会话二')

    const listA = chat.listSessions('user-a')
    expect(listA.map((s) => s.id)).toEqual([a2.id, a1.id]) // 新的在前
    expect(listA.every((s) => s.user_id === 'user-a')).toBe(true)
    expect(chat.listSessions('user-b').map((s) => s.id)).toEqual([b1.id])
  })

  it('重命名与删除校验归属，他人会话不可触碰', () => {
    const { chat } = makeChat()
    const a = chat.createSession('user-a')
    expect(() => chat.renameSession('user-b', a.id, '劫持')).toThrow('会话不存在')
    chat.renameSession('user-a', a.id, '改名了')
    expect(chat.listSessions('user-a')[0].title).toBe('改名了')
    expect(() => chat.deleteSession('user-b', a.id)).toThrow('会话不存在')
    chat.deleteSession('user-a', a.id)
    expect(chat.listSessions('user-a')).toHaveLength(0)
  })

  it('重命名空标题拒绝', () => {
    const { chat } = makeChat()
    const s = chat.createSession('user-a')
    expect(() => chat.renameSession('user-a', s.id, '   ')).toThrow('不能为空')
  })
})

describe('ChatService.send（本地回声）', () => {
  it('存用户消息+回声消息，首条自动命名，更新时间前移', async () => {
    const { chat } = makeChat()
    const s = chat.createSession('user-a')
    await new Promise((r) => setTimeout(r, 5)) // 保证 updated_at 时间差
    const { userMessage, assistantMessage } = await chat.send('user-a', s.id, '什么是臭氧微纳米气泡？')

    expect(userMessage.role).toBe('user')
    expect(userMessage.content).toBe('什么是臭氧微纳米气泡？')
    expect(assistantMessage.role).toBe('assistant')
    expect(assistantMessage.content).toContain('臭氧微纳米气泡')

    const [session] = chat.listSessions('user-a')
    expect(session.title).toBe('什么是臭氧微纳米气泡？'.slice(0, 24))
    expect(session.updated_at).toBeGreaterThanOrEqual(s.updated_at)

    const msgs = chat.listMessages('user-a', s.id)
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant'])
  })

  it('空消息/超长消息拒绝，他人会话不可发送', async () => {
    const { chat } = makeChat()
    const s = chat.createSession('user-a')
    await expect(chat.send('user-a', s.id, '   ')).rejects.toThrow('不能为空')
    await expect(chat.send('user-a', s.id, 'x'.repeat(8001))).rejects.toThrow('过长')
    await expect(chat.send('user-b', s.id, 'hi')).rejects.toThrow('会话不存在')
  })

  it('多轮消息按时间升序排列', async () => {
    const { chat } = makeChat()
    const s = chat.createSession('user-a')
    await chat.send('user-a', s.id, '第一问')
    await chat.send('user-a', s.id, '第二问')
    const msgs = chat.listMessages('user-a', s.id)
    expect(msgs).toHaveLength(4) // 2 轮 × (user + assistant)
    expect(msgs.filter((m) => m.role === 'user').map((m) => m.content)).toEqual(['第一问', '第二问'])
    expect(msgs[0].role).toBe('user')
    expect(msgs[1].role).toBe('assistant')
  })
})

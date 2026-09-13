// 会话服务 — 会话 CRUD + 消息存取（按 user_id 强隔离）。
// M1-A 阶段 send() 为本地回声应答（断网可测全链路）；M1-B 接模型网关后替换 responder。
import { randomBytes } from 'node:crypto'
import type { SqlDatabase } from '../db/adapters'

export interface SessionRow {
  id: string
  user_id: string
  title: string
  created_at: number
  updated_at: number
}

export interface MessageRow {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: number
}

const genId = (prefix: string) => `${prefix}-${Date.now()}-${randomBytes(3).toString('hex')}`

export class ChatService {
  constructor(private readonly db: SqlDatabase) {}

  listSessions(userId: string): SessionRow[] {
    return this.db
      .prepare('SELECT id, user_id, title, created_at, updated_at FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC')
      .all(userId) as SessionRow[]
  }

  createSession(userId: string, title = '新会话'): SessionRow {
    const now = Date.now()
    const row: SessionRow = { id: genId('cs'), user_id: userId, title, created_at: now, updated_at: now }
    this.db
      .prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)')
      .run(row.id, row.user_id, row.title, row.created_at, row.updated_at)
    return row
  }

  renameSession(userId: string, sessionId: string, title: string): void {
    const clean = title.trim().slice(0, 64)
    if (!clean) throw new Error('会话名称不能为空')
    const res = this.db
      .prepare('UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?')
      .run(clean, Date.now(), sessionId, userId)
    if (res.changes === 0) throw new Error('会话不存在')
  }

  deleteSession(userId: string, sessionId: string): void {
    // chat_messages 由 ON DELETE CASCADE 级联清除
    const res = this.db.prepare('DELETE FROM chat_sessions WHERE id = ? AND user_id = ?').run(sessionId, userId)
    if (res.changes === 0) throw new Error('会话不存在')
  }

  listMessages(userId: string, sessionId: string): MessageRow[] {
    this.requireOwned(userId, sessionId)
    // rowid = 插入顺序：同毫秒多条消息也能稳定保序（created_at 只精确到 ms）
    return this.db
      .prepare('SELECT id, session_id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY rowid ASC')
      .all(sessionId) as MessageRow[]
  }

  /**
   * 发送一条用户消息并生成回复。
   * M1-A: 无模型配置 → 本地回声（含会话统计），保证离线可验收全链路；
   * M1-B: 在此处接入模型网关流式输出。
   */
  send(userId: string, sessionId: string, content: string): { userMessage: MessageRow; assistantMessage: MessageRow } {
    const text = content.trim()
    if (!text) throw new Error('消息不能为空')
    if (text.length > 8000) throw new Error('消息过长（上限 8000 字符）')
    this.requireOwned(userId, sessionId)

    const now = Date.now()
    const userMessage: MessageRow = { id: genId('m'), session_id: sessionId, role: 'user', content: text, created_at: now }
    this.db
      .prepare('INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(userMessage.id, sessionId, 'user', text, now)

    // 首条消息自动生成会话标题
    if (this.countMessages(sessionId) === 1) {
      this.db.prepare('UPDATE chat_sessions SET title = ? WHERE id = ?').run(text.slice(0, 24), sessionId)
    }

    const reply = this.echoResponder(sessionId, text)
    const assistantMessage: MessageRow = {
      id: genId('m'),
      session_id: sessionId,
      role: 'assistant',
      content: reply,
      created_at: Date.now()
    }
    this.db
      .prepare('INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)')
      .run(assistantMessage.id, sessionId, 'assistant', assistantMessage.content, assistantMessage.created_at)

    this.db.prepare('UPDATE chat_sessions SET updated_at = ? WHERE id = ?').run(Date.now(), sessionId)
    return { userMessage, assistantMessage }
  }

  private countMessages(sessionId: string): number {
    const row = this.db.prepare('SELECT COUNT(*) AS c FROM chat_messages WHERE session_id = ?').get(sessionId) as { c: number }
    return row.c
  }

  private requireOwned(userId: string, sessionId: string): void {
    const row = this.db.prepare('SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?').get(sessionId, userId)
    if (!row) throw new Error('会话不存在')
  }

  private echoResponder(sessionId: string, text: string): string {
    const stats = this.db
      .prepare('SELECT COUNT(*) AS msgs FROM chat_messages WHERE session_id = ?')
      .get(sessionId) as { msgs: number }
    return [
      `（本地回声 · 模型网关 M1-B 接入）已收到你的消息：`,
      ``,
      `> ${text}`,
      ``,
      `本会话消息数：${stats.msgs}。这条回复由本地生成——断网状态下完整链路可用：会话持久化在 SQLite，杀掉进程重开依然在。`
    ].join('\n')
  }
}

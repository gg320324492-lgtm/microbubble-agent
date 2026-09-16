// 会话服务 — 会话 CRUD + 消息存取（按 user_id 强隔离）。
// M1-B 起接模型网关流式应答；C-2 起应答可为结构化结果（meta 携带 thinking/工具轮次）。
import { randomBytes } from 'node:crypto'
import type { SqlDatabase } from '../db/adapters'
import type { ChatTurn } from './model-gateway.service'
import type { MessageMeta } from '@shared/types'

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
  /** JSON 序列化的 MessageMeta；null = 纯文本消息 */
  meta: string | null
  created_at: number
}

/** 应答器返回：纯文本，或带 meta 的结构化结果（Agent 循环） */
export type ResponderResult = string | { content: string; meta?: MessageMeta | null }

/** meta 列安全解析 — 损坏 JSON 一律按无 meta 处理（ipc 投影与测试共用） */
export function parseMessageMeta(raw: string | null | undefined): MessageMeta | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as MessageMeta
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
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
      .prepare('SELECT id, session_id, role, content, meta, created_at FROM chat_messages WHERE session_id = ? ORDER BY rowid ASC')
      .all(sessionId) as MessageRow[]
  }

  /**
   * 发送一条用户消息并生成回复。
   * 传 respond（模型网关/Agent 循环回调）时走真实模型，否则本地回声（断网可验收全链路）。
   * respond 可返回纯文本或 { content, meta } 结构化结果（meta 持久化到 meta 列）。
   * 流式期间 assistant 消息先以空内容落库，增量经流事件推给 renderer，完成后回写全文。
   */
  async send(
    userId: string,
    sessionId: string,
    content: string,
    respond?: (turns: ChatTurn[], assistantMessageId: string) => Promise<ResponderResult>,
    onDelta?: (assistantMessageId: string, delta: string) => void
  ): Promise<{ userMessage: MessageRow; assistantMessage: MessageRow }> {
    const text = content.trim()
    if (!text) throw new Error('消息不能为空')
    if (text.length > 8000) throw new Error('消息过长（上限 8000 字符）')
    this.requireOwned(userId, sessionId)

    const now = Date.now()
    const userMessage: MessageRow = { id: genId('m'), session_id: sessionId, role: 'user', content: text, meta: null, created_at: now }
    this.db
      .prepare('INSERT INTO chat_messages (id, session_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, NULL, ?)')
      .run(userMessage.id, sessionId, 'user', text, now)

    // 首条消息自动生成会话标题
    if (this.countMessages(sessionId) === 1) {
      this.db.prepare('UPDATE chat_sessions SET title = ? WHERE id = ?').run(text.slice(0, 24), sessionId)
    }

    const assistantMessage: MessageRow = {
      id: genId('m'),
      session_id: sessionId,
      role: 'assistant',
      content: '',
      meta: null,
      created_at: Date.now()
    }
    this.db
      .prepare('INSERT INTO chat_messages (id, session_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, NULL, ?)')
      .run(assistantMessage.id, sessionId, 'assistant', '', assistantMessage.created_at)

    try {
      if (respond) {
        // assistant 行此刻已落库（先占位后回写），把 id 交给 respond 供流事件标记消息归属
        const turns = this.buildTurns(sessionId, text)
        const res = await respond(turns, assistantMessage.id)
        if (typeof res === 'string') {
          assistantMessage.content = res
        } else {
          assistantMessage.content = res.content
          assistantMessage.meta = res.meta ? JSON.stringify(res.meta) : null
        }
      } else {
        assistantMessage.content = this.echoResponder(sessionId, text)
      }
    } catch (e) {
      assistantMessage.content = `⚠️ 生成失败：${e instanceof Error ? e.message : '未知错误'}`
    }
    // meta 在结构化应答分支里已是 JSON 字符串，这里直接落列
    this.db
      .prepare('UPDATE chat_messages SET content = ?, meta = ? WHERE id = ?')
      .run(assistantMessage.content, assistantMessage.meta, assistantMessage.id)
    this.db.prepare('UPDATE chat_sessions SET updated_at = ? WHERE id = ?').run(Date.now(), sessionId)

    void onDelta
    return { userMessage, assistantMessage }
  }

  /** 组装模型上下文：最近 20 条历史 + 本条新消息 */
  private buildTurns(sessionId: string, newText: string): ChatTurn[] {
    const history = this.db
      .prepare("SELECT role, content FROM chat_messages WHERE session_id = ? AND role IN ('user','assistant') ORDER BY rowid DESC LIMIT 19")
      .all(sessionId) as { role: 'user' | 'assistant'; content: string }[]
    const turns: ChatTurn[] = history.reverse().map((m) => ({ role: m.role, content: m.content }))
    turns.push({ role: 'user', content: newText })
    return turns
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
      `（本地回声 · 尚未配置模型服务）已收到你的消息：`,
      ``,
      `> ${text}`,
      ``,
      `本会话消息数：${stats.msgs}。到「设置 → 模型服务」配置 API Key 后即为真实模型对话；这条回复由本地生成，断网可完整验收。`
    ].join('\n')
  }
}

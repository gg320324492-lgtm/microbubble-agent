// Agent Memory Layer — Phase 8-M1-E
// 跨会话对话历史 (SQLite-backed via AgentHistoryRepository).
// agent_history.action 语义: chat.user / chat.assistant / tool.invoke / memory.recall

import type { DatabaseService } from '../database.service'

export interface ChatMessage {
  id: number
  agent: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  timestamp: number
  toolName?: string
  toolResult?: string
}

export interface AgentMemory {
  recordMessage(sessionId: string, role: ChatMessage['role'], content: string, toolName?: string, toolResult?: string): void
  history(sessionId: string, limit?: number): ChatMessage[]
  search(query: string, limit?: number): ChatMessage[]
  clear(sessionId: string): number
  summary(sessionId: string): { total: number; lastActivityAt: number | null }
}

class AgentMemoryImpl implements AgentMemory {
  constructor(private readonly getService: () => DatabaseService | null) {}

  recordMessage(sessionId: string, role: ChatMessage['role'], content: string, toolName?: string, toolResult?: string): void {
    const svc = this.getService()
    if (!svc) return
    const agent = `${role === 'user' ? 'chat.user' : role === 'assistant' ? 'chat.assistant' : 'chat.tool'}:${sessionId}`
    const action = toolName ? `tool.${toolName}` : `chat.${role}`
    const input = JSON.stringify({ sessionId, content: content.slice(0, 4000) })
    const output = toolResult ? JSON.stringify({ result: toolResult.slice(0, 4000) }) : null
    svc.db.execute(
      `INSERT INTO agent_history (agent, action, input, output, timestamp) VALUES (?, ?, ?, ?, ?)`,
      [agent, action, input, output, Date.now()]
    )
  }

  history(sessionId: string, limit: number = 50): ChatMessage[] {
    const svc = this.getService()
    if (!svc) return []
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT id, agent, input, output, timestamp FROM agent_history
       WHERE agent LIKE 'chat.%:' || ?1 OR agent LIKE 'chat.tool:%' || ?1
       ORDER BY timestamp DESC LIMIT ?2`,
      [sessionId, limit]
    )
    return rows.map((r) => parseRow(r, sessionId)).reverse()
  }

  search(query: string, limit: number = 20): ChatMessage[] {
    const svc = this.getService()
    if (!svc) return []
    if (!query) return []
    const like = `%${query.replace(/[%_]/g, '\\$&')}%`
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT id, agent, input, output, timestamp FROM agent_history
       WHERE input LIKE ? ESCAPE '\\' OR output LIKE ? ESCAPE '\\'
       ORDER BY timestamp DESC LIMIT ?`,
      [like, like, limit]
    )
    return rows.map((r) => parseRow(r, r['agent']?.toString().split(':').pop() ?? ''))
  }

  clear(sessionId: string): number {
    const svc = this.getService()
    if (!svc) return 0
    const result = svc.db.execute(
      `DELETE FROM agent_history WHERE agent LIKE 'chat.%:' || ? OR agent LIKE 'chat.tool:%' || ?`,
      [sessionId, sessionId]
    )
    return result.changes
  }

  summary(sessionId: string): { total: number; lastActivityAt: number | null } {
    const svc = this.getService()
    if (!svc) return { total: 0, lastActivityAt: null }
    const row = svc.db.queryOne<{ c: number; t: number | null }>(
      `SELECT COUNT(*) AS c, MAX(timestamp) AS t FROM agent_history
       WHERE agent LIKE 'chat.%:' || ? OR agent LIKE 'chat.tool:%' || ?`,
      [sessionId, sessionId]
    )
    return { total: Number(row?.c ?? 0), lastActivityAt: row?.t == null ? null : Number(row.t) }
  }
}

function parseRow(r: Record<string, unknown>, sessionId: string): ChatMessage {
  const agent = String(r['agent'] ?? '')
  let role: ChatMessage['role'] = 'assistant'
  if (agent.startsWith('chat.user:')) role = 'user'
  else if (agent.startsWith('chat.tool:')) role = 'tool'
  let content = ''
  let toolName: string | undefined
  let toolResult: string | undefined
  if (r['input'] && typeof r['input'] === 'string') {
    try {
      const parsed = JSON.parse(r['input']) as { content?: string }
      content = parsed.content ?? ''
    } catch { content = String(r['input']) }
  }
  if (r['output'] && typeof r['output'] === 'string') {
    try {
      const parsed = JSON.parse(r['output']) as { result?: string }
      toolResult = parsed.result
    } catch { toolResult = String(r['output']) }
  }
  // 从 agent 字符串反推 action 中的 tool name (chat.tool:xxx:session)
  const m = agent.match(/^chat\.tool:([^:]+):/)
  if (m) toolName = m[1]
  void sessionId
  return {
    id: Number(r['id']),
    agent,
    role,
    content,
    timestamp: Number(r['timestamp']),
    toolName,
    toolResult
  }
}

export function createAgentMemory(getService: () => DatabaseService | null): AgentMemory {
  return new AgentMemoryImpl(getService)
}
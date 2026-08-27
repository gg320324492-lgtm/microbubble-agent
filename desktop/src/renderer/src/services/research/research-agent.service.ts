// Research Agent Service — AI 研究助手 adapter (真实数据源)
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite.
// 数据源:
//   - desktop_chat_sessions (225 行) — 主表, 真实研究会话
//   - chat_messages (空) — 消息暂未同步
//   - experiments / samples / analysis_results (空) — 数据待 sample import 导入
// 替代 NotWiredError, 真正调 SQL 查数据.

import type { ResearchSession, AgentMessage, CitationItem, EvidenceItem, ResearchDesignResult } from './research-agent.service'

interface SessionRow {
  id: string
  web_id: number | null
  owner_username: string | null
  title: string | null
  preview: string | null
  is_pinned: number
  is_archived: number
  tags_json: string | null
  model_name: string | null
  message_count: number | null
  created_at: number | null
  updated_at: number | null
}

function parseJsonArray<T = string>(raw: string | null): T[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function mapSessionRow(r: SessionRow): ResearchSession {
  return {
    id: r.id,
    name: r.title || r.id.slice(0, 8),
    createdAt: r.created_at ? r.created_at * 1000 : Date.now(),
    messages: [], // TODO: chat_messages 表同步后填充
    events: [],
    status: r.is_archived ? 'completed' : (r.message_count && r.message_count > 0 ? 'paused' : 'active')
  }
}

interface ResearchAgentAdapter {
  getSessions(): Promise<ResearchSession[]>
  getSession(id: string): Promise<ResearchSession | undefined>
  sendMessage(sessionId: string, content: string): Promise<AgentMessage>
  getCitations(sessionId: string): Promise<CitationItem[]>
  getEvidence(sessionId: string): Promise<EvidenceItem[]>
  getEvents(sessionId: string): Promise<AgentEvent[]>
  runResearch(problem: string): Promise<ResearchDesignResult>
  cancelTask(taskId: string): Promise<void>
}

class SqliteResearchAgentAdapter implements ResearchAgentAdapter {
  async getSessions(): Promise<ResearchSession[]> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<SessionRow>({
      sql: `SELECT id, web_id, owner_username, title, preview, is_pinned, is_archived,
                   tags_json, model_name, message_count, created_at, updated_at
            FROM desktop_chat_sessions
            ORDER BY updated_at DESC
            LIMIT 500`
    })
    return rows.map(mapSessionRow)
  }
  async getSession(id: string): Promise<ResearchSession | undefined> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<SessionRow>({
      sql: `SELECT id, web_id, owner_username, title, preview, is_pinned, is_archived,
                   tags_json, model_name, message_count, created_at, updated_at
            FROM desktop_chat_sessions WHERE id = ?`,
      params: [id]
    })
    if (rows.length === 0) return undefined
    return mapSessionRow(rows[0])
  }
  async sendMessage(_sessionId: string, content: string): Promise<AgentMessage> {
    // 真实 LLM 调用待 R6 接入. 当前返回 echo (与之前 mock 行为类似, 但显式标记).
    return {
      id: `m-${Date.now()}`,
      role: 'assistant',
      content: '[类 20.196] 当前未接 LLM. 待 R6 hardening 接入真实模型后, 此处将调用 MiMo / OpenAI / Anthropic 等 provider.',
      timestamp: Date.now()
    }
  }
  async getCitations(_sessionId: string): Promise<CitationItem[]> {
    // citations 实际在 messages.metadata.citations 字段里. 暂无 messages 同步.
    return []
  }
  async getEvidence(_sessionId: string): Promise<EvidenceItem[]> {
    // evidence 同上.
    return []
  }
  async getEvents(_sessionId: string): Promise<AgentEvent[]> {
    // events 暂无 source. 返回空数组.
    return []
  }
  async runResearch(problem: string): Promise<ResearchDesignResult> {
    // TODO: 接入真实研究设计. 当前返回 stub (因为 experiments 表空).
    return {
      problemAnalysis: {
        keyScientificQuestion: problem,
        possibleMechanisms: ['(待导入 experiment 数据后, runResearch 才能产生真实设计)']
      },
      hypotheses: [],
      experimentPlan: { variables: [] },
      modelSelection: { model: '待选', confidence: 0 }
    }
  }
  async cancelTask(_taskId: string): Promise<void> {
    // no-op (没任务在跑)
  }
}

const realAdapter: ResearchAgentAdapter = new SqliteResearchAgentAdapter()
let currentAdapter: ResearchAgentAdapter = realAdapter

export const researchAgentService = {
  setAdapter(a: ResearchAgentAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  getAdapter(): ResearchAgentAdapter { return currentAdapter },
  getSessions: () => currentAdapter.getSessions(),
  getSession: (id: string) => currentAdapter.getSession(id),
  sendMessage: (sessionId: string, content: string) => currentAdapter.sendMessage(sessionId, content),
  getCitations: (sessionId: string) => currentAdapter.getCitations(sessionId),
  getEvidence: (sessionId: string) => currentAdapter.getEvidence(sessionId),
  getEvents: (sessionId: string) => currentAdapter.getEvents(sessionId),
  runResearch: (problem: string) => currentAdapter.runResearch(problem),
  cancelTask: (taskId: string) => currentAdapter.cancelTask(taskId),
}

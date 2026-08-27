// Research Agent Service — AI 研究助手服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 MOCK_SESSIONS / MOCK_CITATIONS / MOCK_EVIDENCE / MOCK_DESIGN
// (含 sendMessage() echo 用户输入 + delay 50ms 假装 AI 思考).
// 这些假数据被 Assistant / AgentCenter 页面渲染为"AI 助手真实响应".
// 改为: 默认 adapter 抛 NotWiredError.

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  toolCalls?: ToolCallResult[]
}

export interface ToolCallResult {
  name: string
  status: 'running' | 'completed' | 'error'
  result?: string
  error?: string
}

export interface AgentEvent {
  type: 'planner' | 'retrieval' | 'tool_call' | 'analysis' | 'response'
  label: string
  detail: string
  timestamp: number
  status: 'pending' | 'running' | 'completed' | 'error'
}

export interface ResearchSession {
  id: string
  name: string
  createdAt: number
  messages: AgentMessage[]
  events: AgentEvent[]
  status: 'active' | 'paused' | 'completed'
}

export interface CitationItem {
  id: number
  authors: string
  title: string
  journal: string
  year: number
  tags: string[]
  citedBy: number
  confidence: number
}

export interface EvidenceItem {
  label: string
  value: string
  source: string
  confidence: number
}

export interface ResearchDesignResult {
  problemAnalysis: { keyScientificQuestion: string; possibleMechanisms: string[] }
  hypotheses: Array<{ statement: string; confidence: number }>
  experimentPlan: { variables: Array<{ name: string; type: string; range: string }> }
  modelSelection: { model: string; confidence: number }
}

// ============ Adapter Interface ============

export interface AgentAdapter {
  getSessions(): Promise<ResearchSession[]>
  getSession(id: string): Promise<ResearchSession | undefined>
  sendMessage(sessionId: string, content: string): Promise<AgentMessage>
  getCitations(sessionId: string): Promise<CitationItem[]>
  getEvidence(sessionId: string): Promise<EvidenceItem[]>
  getEvents(sessionId: string): Promise<AgentEvent[]>
  runResearch(problem: string): Promise<ResearchDesignResult>
  cancelTask(taskId: string): Promise<void>
}

export class ResearchAgentNotWiredError extends Error {
  constructor() {
    super(
      '[ResearchAgentService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning fake 3 sessions (分析降解动力学 / 文献综述整理 / 实验变量优化) + sendMessage() echo of user content with 50ms delay. ' +
      'Real data path: 1) local desktop_research_sessions table, 2) FastAPI /api/v1/research-agent/* with real LLM. ' +
      'Call researchAgentService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'ResearchAgentNotWiredError'
  }
}

const notWiredAdapter: AgentAdapter = {
  async getSessions() { throw new ResearchAgentNotWiredError() },
  async getSession() { throw new ResearchAgentNotWiredError() },
  async sendMessage() { throw new ResearchAgentNotWiredError() },
  async getCitations() { throw new ResearchAgentNotWiredError() },
  async getEvidence() { throw new ResearchAgentNotWiredError() },
  async getEvents() { throw new ResearchAgentNotWiredError() },
  async runResearch() { throw new ResearchAgentNotWiredError() },
  async cancelTask() { throw new ResearchAgentNotWiredError() },
}

let currentAdapter: AgentAdapter = notWiredAdapter

// ============ Service ============

export const researchAgentService = {
  setAdapter(adapter: AgentAdapter) { currentAdapter = adapter },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  getAdapter() { return currentAdapter },
  getSessions: () => currentAdapter.getSessions(),
  getSession: (id: string) => currentAdapter.getSession(id),
  sendMessage: (sessionId: string, content: string) => currentAdapter.sendMessage(sessionId, content),
  getCitations: (sessionId: string) => currentAdapter.getCitations(sessionId),
  getEvidence: (sessionId: string) => currentAdapter.getEvidence(sessionId),
  getEvents: (sessionId: string) => currentAdapter.getEvents(sessionId),
  runResearch: (problem: string) => currentAdapter.runResearch(problem),
  cancelTask: (taskId: string) => currentAdapter.cancelTask(taskId),
}

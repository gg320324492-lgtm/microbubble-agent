// Research Agent Service — AI 研究助手服务层。
// 抽象层：UI 不直接调 runtime，通过此服务中转。
// 当前 mock 适配器，未来替换为 IPC/后端。

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
  status: 'running' | 'completed' | 'error'
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

// ============ Service API ============

const MOCK_SESSIONS: ResearchSession[] = [
  {
    id: 's1', name: '分析降解动力学', createdAt: Date.now() - 3600000, status: 'active',
    messages: [
      { id: 'm1', role: 'user', content: '请分析这组臭氧微纳米气泡在降解四环素（TC）的实验数据，包括动力学拟合、机理讨论和关键影响因素。', timestamp: Date.now() - 300000 },
      { id: 'm2', role: 'assistant', content: '好的，我已经对实验数据和相关文献进行了综合分析，结果如下：', timestamp: Date.now() - 280000, toolCalls: [
        { name: '文献检索', status: 'completed', result: '筛选 12 篇核心文献' },
        { name: '动力学拟合', status: 'completed', result: '一级动力学 R²=0.9887' }
      ]}
    ],
    events: [
      { type: 'planner', label: 'Planner', detail: '理解用户问题，生成研究计划', timestamp: Date.now() - 300000, status: 'completed' },
      { type: 'retrieval', label: 'Retrieval', detail: '检索相关文献与实验数据', timestamp: Date.now() - 280000, status: 'completed' },
      { type: 'tool_call', label: 'Tool Call', detail: '读取实验数据文件 TC_O3_MNBs_data.csv', timestamp: Date.now() - 260000, status: 'completed' },
      { type: 'analysis', label: 'Analysis', detail: '动力学拟合与统计分析', timestamp: Date.now() - 240000, status: 'completed' },
      { type: 'response', label: 'Model Response', detail: '生成结构化分析结果', timestamp: Date.now() - 220000, status: 'completed' },
    ]
  },
  { id: 's2', name: '文献综述整理', createdAt: Date.now() - 86400000, status: 'paused', messages: [], events: [] },
  { id: 's3', name: '实验变量优化', createdAt: Date.now() - 172800000, status: 'completed', messages: [], events: [] },
]

const MOCK_CITATIONS: CitationItem[] = [
  { id: 1, authors: 'Li, X., et al.', title: 'Ozonation with micro-nano bubbles for tetracycline degradation in water', journal: 'Chemosphere, 286', year: 2022, tags: ['O₃-MNBs', 'TC', '动力学'], citedBy: 128, confidence: 0.92 },
  { id: 2, authors: 'Wang, Y., et al.', title: 'Degradation mechanism of tetracycline by ozone microbubble process', journal: 'Water Research, 188', year: 2021, tags: ['机制', 'ROS', '·OH'], citedBy: 86, confidence: 0.88 },
  { id: 3, authors: 'Zhang, J., et al.', title: 'Impact of microbubble size on ozonation performance', journal: 'Sep. Purif. Technol., 246', year: 2020, tags: ['O₃-MNBs', '粒径', '影响因素'], citedBy: 71, confidence: 0.85 },
]

const MOCK_EVIDENCE: EvidenceItem[] = [
  { label: 'kLa 测量', value: '0.45 min⁻¹', source: 'Li 2022', confidence: 0.85 },
  { label: 'R² 拟合度', value: '0.9887', source: '实验数据', confidence: 0.95 },
  { label: '半衰期', value: '28.5 min', source: '一级动力学拟合', confidence: 0.90 },
]

function delay(ms: number): Promise<void> { return new Promise(r => setTimeout(r, ms)) }

export const researchAgentService = {
  async getSessions(): Promise<ResearchSession[]> {
    await delay(50)
    return [...MOCK_SESSIONS]
  },

  async getSession(id: string): Promise<ResearchSession | undefined> {
    await delay(30)
    return MOCK_SESSIONS.find(s => s.id === id)
  },

  async sendMessage(sessionId: string, content: string): Promise<AgentMessage> {
    await delay(100)
    return { id: `m-${Date.now()}`, role: 'user', content, timestamp: Date.now() }
  },

  async getCitations(sessionId: string): Promise<CitationItem[]> {
    await delay(30)
    return [...MOCK_CITATIONS]
  },

  async getEvidence(sessionId: string): Promise<EvidenceItem[]> {
    await delay(30)
    return [...MOCK_EVIDENCE]
  },

  async getEvents(sessionId: string): Promise<AgentEvent[]> {
    await delay(30)
    const session = MOCK_SESSIONS.find(s => s.id === sessionId)
    return session ? [...session.events] : []
  },
}

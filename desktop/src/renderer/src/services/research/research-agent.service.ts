// Research Agent Service — AI 研究助手服务层（带适配器模式）。
// mockAdapter → realAdapter (future IPC/后端)。

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

// ============ Mock Adapter ============

function delay(ms: number): Promise<void> { return new Promise(r => setTimeout(r, ms)) }

const MOCK_SESSIONS: ResearchSession[] = [
  {
    id: 's1', name: '分析降解动力学', createdAt: Date.now() - 3600000, status: 'active',
    messages: [
      { id: 'm1', role: 'user', content: '请分析这组臭氧微纳米气泡在降解四环素（TC）的实验数据，包括动力学拟合、机理讨论和关键影响因素。', timestamp: Date.now() - 300000 },
      { id: 'm2', role: 'assistant', content: '好的，我已经对实验数据和相关文献进行了综合分析，结果如下：\n\n1. 文献检索与证据汇总\n基于关键词检索到 128 篇相关文献，筛选出与臭氧微纳米气泡（O₃-MNBs）降解四环素机制、动力学及影响因素强相关的 12 篇核心文献。\n\n2. 动力学拟合结果\n最佳拟合模型：伪一级动力学模型\nkobs = 0.0243 min⁻¹\nR² = 0.9887\n半衰期 t₁/₂ = 28.5 min\n\n3. 机理与结论\n主要活性物种：·OH（占主导），其次为 ¹O₂ 等。\n最优条件预测：粒径 ~150nm，臭氧 20 mg/L，pH 7，温度 25°C，可获得 >95% TC 去除率。', timestamp: Date.now() - 280000,
        toolCalls: [
          { name: '文献检索', status: 'completed', result: '筛选 12 篇核心文献' },
          { name: '动力学拟合', status: 'completed', result: '一级动力学 R²=0.9887' },
          { name: '机理分析', status: 'completed', result: '·OH 主导机制' }
        ]
      }
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

const MOCK_DESIGN: ResearchDesignResult = {
  problemAnalysis: { keyScientificQuestion: '如何优化臭氧微纳米气泡强化四环素降解效率？', possibleMechanisms: ['传质增强', '自由基生成'] },
  hypotheses: [
    { statement: '更小气泡直径增加气液界面面积，提高臭氧传质效率', confidence: 0.80 },
    { statement: '自由基（·OH）途径是 TC 降解的主要活性机制', confidence: 0.65 },
  ],
  experimentPlan: { variables: [
    { name: '气泡直径', type: 'independent', range: '50-500 nm' },
    { name: '臭氧浓度', type: 'independent', range: '5-25 mg/L' },
    { name: 'pH', type: 'control', range: '5.0-9.0' },
  ]},
  modelSelection: { model: '伪一级动力学', confidence: 0.85 },
}

const mockAdapter: AgentAdapter = {
  async getSessions() { await delay(30); return [...MOCK_SESSIONS] },
  async getSession(id) { await delay(20); return MOCK_SESSIONS.find(s => s.id === id) },
  async sendMessage(_sid, content) { await delay(50); return { id: `m-${Date.now()}`, role: 'user', content, timestamp: Date.now() } },
  async getCitations() { await delay(20); return [...MOCK_CITATIONS] },
  async getEvidence() { await delay(20); return [...MOCK_EVIDENCE] },
  async getEvents(id) { await delay(20); return MOCK_SESSIONS.find(s => s.id === id)?.events ?? [] },
  async runResearch() { await delay(80); return MOCK_DESIGN },
  async cancelTask() { await delay(10) },
}

// ============ Service ============

let currentAdapter: AgentAdapter = mockAdapter

export const researchAgentService = {
  setAdapter(adapter: AgentAdapter) { currentAdapter = adapter },
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

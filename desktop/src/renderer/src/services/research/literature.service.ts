// Literature Service — 文献智能库服务层（带适配器模式）。

export interface PaperAssessment {
  documentId: string
  reliabilityScore: number
  evidenceScore: number
  methodologyScore: number
  limitations: string[]
  concerns: string[]
}

export interface PaperEvidence {
  evidenceId: string
  type: 'experiment' | 'simulation' | 'theory' | 'statistical' | 'review'
  description: string
  strength: number
}

export interface LiteratureAdapter {
  assessPaper(documentId: string): Promise<PaperAssessment | null>
  extractEvidence(documentId: string): Promise<PaperEvidence[]>
  getDocumentAssessments(): Promise<PaperAssessment[]>
  summarizePaper(documentId: string): Promise<string>
}

const MOCK_ASSESSMENTS: Record<string, PaperAssessment> = {
  d1: { documentId: 'd1', reliabilityScore: 0.82, evidenceScore: 0.78, methodologyScore: 0.65, limitations: ['统计方法不充分', '样本量偏小'], concerns: ['缺少重复实验验证'] },
  d2: { documentId: 'd2', reliabilityScore: 0.65, evidenceScore: 0.60, methodologyScore: 0.55, limitations: ['机制证据薄弱'], concerns: ['表征方法单一'] },
  d3: { documentId: 'd3', reliabilityScore: 0.90, evidenceScore: 0.88, methodologyScore: 0.82, limitations: [], concerns: [] },
}

const mockAdapter: LiteratureAdapter = {
  async assessPaper(id) { return MOCK_ASSESSMENTS[id] ?? null },
  async extractEvidence() {
    return [
      { evidenceId: 'e1', type: 'experiment', description: 'kLa 测量方法', strength: 0.85 },
      { evidenceId: 'e2', type: 'statistical', description: '去除效率数据统计', strength: 0.78 },
    ]
  },
  async getDocumentAssessments() { return Object.values(MOCK_ASSESSMENTS) },
  async summarizePaper() { return '本文研究了微纳米气泡臭氧技术对四环素的降解效果，结果表明在最优条件下去除率可达98.6%。' },
}

let currentAdapter: LiteratureAdapter = mockAdapter

export const literatureService = {
  setAdapter(a: LiteratureAdapter) { currentAdapter = a },
  assessPaper: (id: string) => currentAdapter.assessPaper(id),
  extractEvidence: (id: string) => currentAdapter.extractEvidence(id),
  getDocumentAssessments: () => currentAdapter.getDocumentAssessments(),
  summarizePaper: (id: string) => currentAdapter.summarizePaper(id),
}

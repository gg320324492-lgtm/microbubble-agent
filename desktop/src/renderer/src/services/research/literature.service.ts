// Literature Service — 文献智能库服务层。
// 封装 Phase 8-G0 科学推理层的文献评估能力。

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

const MOCK_ASSESSMENTS: Record<string, PaperAssessment> = {
  d1: { documentId: 'd1', reliabilityScore: 0.82, evidenceScore: 0.78, methodologyScore: 0.65, limitations: ['统计方法不充分', '样本量偏小'], concerns: ['缺少重复实验验证'] },
  d2: { documentId: 'd2', reliabilityScore: 0.65, evidenceScore: 0.60, methodologyScore: 0.55, limitations: ['机制证据薄弱'], concerns: ['表征方法单一'] },
  d3: { documentId: 'd3', reliabilityScore: 0.90, evidenceScore: 0.88, methodologyScore: 0.82, limitations: [], concerns: [] },
}

export const literatureService = {
  async assessPaper(documentId: string): Promise<PaperAssessment | null> {
    return MOCK_ASSESSMENTS[documentId] ?? null
  },

  async extractEvidence(documentId: string): Promise<PaperEvidence[]> {
    return [
      { evidenceId: 'e1', type: 'experiment', description: 'kLa 测量方法', strength: 0.85 },
      { evidenceId: 'e2', type: 'statistical', description: '去除效率数据统计', strength: 0.78 },
    ]
  },

  async getDocumentAssessments(): Promise<PaperAssessment[]> {
    return Object.values(MOCK_ASSESSMENTS)
  },
}

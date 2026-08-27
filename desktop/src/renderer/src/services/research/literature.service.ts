// Literature Service — 文献智能库服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 MOCK_ASSESSMENTS / 假 evidence / 假 "去除率98.6%" 摘要.
// 这些假数据被 Literature 页面渲染为"文献评估" + "证据链".
// 改为: 默认 adapter 抛 NotWiredError.

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

export class LiteratureNotWiredError extends Error {
  constructor() {
    super(
      '[LiteratureService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning fake "去除率98.6%" summary and paper assessments. ' +
      'Real data path: 1) local desktop_documents + manual assessment records, 2) FastAPI /api/v1/literature/* with RAG extraction ' +
      'Call literatureService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'LiteratureNotWiredError'
  }
}

const notWiredAdapter: LiteratureAdapter = {
  async assessPaper() { throw new LiteratureNotWiredError() },
  async extractEvidence() { throw new LiteratureNotWiredError() },
  async getDocumentAssessments() { throw new LiteratureNotWiredError() },
  async summarizePaper() { throw new LiteratureNotWiredError() },
}

let currentAdapter: LiteratureAdapter = notWiredAdapter

export const literatureService = {
  setAdapter(a: LiteratureAdapter) { currentAdapter = a },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  assessPaper: (id: string) => currentAdapter.assessPaper(id),
  extractEvidence: (id: string) => currentAdapter.extractEvidence(id),
  getDocumentAssessments: () => currentAdapter.getDocumentAssessments(),
  summarizePaper: (id: string) => currentAdapter.summarizePaper(id),
}

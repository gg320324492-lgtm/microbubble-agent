// Manuscript Service — 论文助手服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 MOCK_MANUSCRIPT / MOCK_ISSUES / 假 generateSection 模板
// (e.g. '科学研究需要系统性调查来解决知识空白' / '内容生成中...').
// 这些模板被 Manuscript 页面渲染为"真实论文" (R²=0.9887, 去除率98.6%).
// 改为: 默认 adapter 抛 NotWiredError.

export interface ManuscriptSection { sectionType: string; title: string; content: string; citations: string[] }
export interface FigureCaption { figureId: string; caption: string; description: string }
export interface WritingIssue { type: string; location: string; description: string; severity: 'low' | 'medium' | 'high'; suggestion: string }
export interface Manuscript { manuscriptId: string; title: string; abstract: string; sections: ManuscriptSection[]; figures: FigureCaption[]; highlights: string[]; wordCount: number }

export interface ManuscriptAdapter {
  getManuscript(): Promise<Manuscript>
  getWritingIssues(): Promise<WritingIssue[]>
  getSections(): Promise<ManuscriptSection[]>
  generateSection(sectionType: string, outline: string): Promise<string>
  reviewSection(sectionType: string, content: string): Promise<WritingIssue[]>
}

export class ManuscriptNotWiredError extends Error {
  constructor() {
    super(
      '[ManuscriptService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning fake "O₃-MNBs 降解四环素" paper + "R²=0.9887 去除率98.6%" abstract. ' +
      'Real data path: 1) local desktop_manuscripts table, 2) FastAPI /api/v1/manuscript/* with LLM generation ' +
      'Call manuscriptService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'ManuscriptNotWiredError'
  }
}

const notWiredAdapter: ManuscriptAdapter = {
  async getManuscript() { throw new ManuscriptNotWiredError() },
  async getWritingIssues() { throw new ManuscriptNotWiredError() },
  async getSections() { throw new ManuscriptNotWiredError() },
  async generateSection() { throw new ManuscriptNotWiredError() },
  async reviewSection() { throw new ManuscriptNotWiredError() },
}

let currentAdapter: ManuscriptAdapter = notWiredAdapter

export const manuscriptService = {
  setAdapter(a: ManuscriptAdapter) { currentAdapter = a },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  getManuscript: () => currentAdapter.getManuscript(),
  getWritingIssues: () => currentAdapter.getWritingIssues(),
  getSections: () => currentAdapter.getSections(),
  generateSection: (t: string, o: string) => currentAdapter.generateSection(t, o),
  reviewSection: (t: string, c: string) => currentAdapter.reviewSection(t, c),
}

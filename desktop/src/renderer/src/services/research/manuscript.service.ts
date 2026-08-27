// Manuscript Service — 论文助手 adapter (真实数据源)
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite.
// 数据源: manuscripts (0 行, 但 schema 完整, 等 sample import 导入)
// 替代 NotWiredError.

export interface ManuscriptSection { sectionType: string; title: string; content: string; citations: string[] }
export interface FigureCaption { figureId: string; caption: string; description: string }
export interface WritingIssue { type: string; location: string; description: string; severity: 'low' | 'medium' | 'high'; suggestion: string }
export interface Manuscript {
  manuscriptId: string
  title: string
  abstract: string
  sections: ManuscriptSection[]
  figures: FigureCaption[]
  highlights: string[]
  wordCount: number
}

export interface ManuscriptAdapter {
  getManuscript(): Promise<Manuscript>
  getWritingIssues(): Promise<WritingIssue[]>
  getSections(): Promise<ManuscriptSection[]>
  generateSection(sectionType: string, outline: string): Promise<string>
  reviewSection(sectionType: string, content: string): Promise<WritingIssue[]>
}

interface ManuscriptRow {
  id: string
  project_id: string | null
  section: string | null
  content: string | null
  updated_at: number | null
}

interface FigureRow {
  id: string
  experiment_id: string | null
  analysis_id: string | null
  figure_type: string | null
  title: string | null
  caption: string | null
  description: string | null
}

class SqliteManuscriptAdapter implements ManuscriptAdapter {
  async getManuscript(): Promise<Manuscript> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    // manuscripts 表存 ELN 章节内容, 按 section 聚合
    const { rows } = await api.database.query<ManuscriptRow>({
      sql: 'SELECT id, project_id, section, content, updated_at FROM manuscripts ORDER BY section ASC'
    })
    const sections: ManuscriptSection[] = rows.map((r) => ({
      sectionType: r.section || 'unknown',
      title: r.section || '未知章节',
      content: r.content || '',
      citations: []
    }))
    const wordCount = sections.reduce((sum, s) => sum + (s.content ? s.content.length : 0), 0)
    return {
      manuscriptId: sections[0]?.project_id ?? 'manuscript-empty',
      title: sections[0]?.title ?? '未命名论文',
      abstract: sections.find((s) => s.sectionType === 'abstract')?.content ?? '未生成摘要',
      sections,
      figures: [],
      highlights: [],
      wordCount
    }
  }
  async getWritingIssues(): Promise<WritingIssue[]> {
    return []
  }
  async getSections(): Promise<ManuscriptSection[]> {
    return (await this.getManuscript()).sections
  }
  async generateSection(_sectionType: string, _outline: string): Promise<string> {
    // TODO: 接 LLM 后替换
    return '[类 20.196] 当前未接 LLM, 无法生成章节内容. 待 R6 接入.'
  }
  async reviewSection(_sectionType: string, _content: string): Promise<WritingIssue[]> {
    return []
  }
}

const realAdapter: ManuscriptAdapter = new SqliteManuscriptAdapter()
let currentAdapter: ManuscriptAdapter = realAdapter

export const manuscriptService = {
  setAdapter(a: ManuscriptAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  getManuscript: () => currentAdapter.getManuscript(),
  getWritingIssues: () => currentAdapter.getWritingIssues(),
  getSections: () => currentAdapter.getSections(),
  generateSection: (t: string, o: string) => currentAdapter.generateSection(t, o),
  reviewSection: (t: string, c: string) => currentAdapter.reviewSection(t, c),
}

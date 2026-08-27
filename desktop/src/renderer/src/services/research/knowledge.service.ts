// Knowledge Service — 文献/知识库服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 MOCK_DOCUMENTS (5 个假文献/李小红 张伟 陈晨 不存在作者)
// + MOCK_FOLDERS (假目录计数 128/236/189).
// 改为: 默认 adapter 抛 NotWiredError, 强制 wire 真实数据源.

export interface DocumentItem {
  id: string
  title: string
  authors: string
  journal: string
  year: number
  type: 'paper' | 'experiment' | 'dataset' | 'report'
  tags: string[]
  credibility: number
  citations: number
  relevance?: number
  location?: string
  summary?: string
}

export interface SearchResult { documentId: string; score: number; excerpt: string }
export interface KnowledgeFolder { id: string; name: string; count: number; children?: KnowledgeFolder[] }

export interface KnowledgeAdapter {
  getDocuments(): Promise<DocumentItem[]>
  getDocument(id: string): Promise<DocumentItem | undefined>
  searchDocuments(query: string): Promise<SearchResult[]>
  getFolders(): Promise<KnowledgeFolder[]>
  getDocumentCount(): Promise<number>
  importDocument(file: File): Promise<DocumentItem | null>
}

export class KnowledgeNotWiredError extends Error {
  constructor() {
    super(
      '[KnowledgeService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning 5 fake papers (李小红/张伟/陈晨 etc.) and 3 fake folders with hardcoded counts 128/236/189. ' +
      'Real data path: 1) local desktop_knowledge table (017-memories-knowledge.sql), 2) FastAPI /api/v1/knowledge/* with RAG. ' +
      'Call knowledgeService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'KnowledgeNotWiredError'
  }
}

const notWiredAdapter: KnowledgeAdapter = {
  async getDocuments() { throw new KnowledgeNotWiredError() },
  async getDocument() { throw new KnowledgeNotWiredError() },
  async searchDocuments() { throw new KnowledgeNotWiredError() },
  async getFolders() { throw new KnowledgeNotWiredError() },
  async getDocumentCount() { throw new KnowledgeNotWiredError() },
  async importDocument() { throw new KnowledgeNotWiredError() },
}

let currentAdapter: KnowledgeAdapter = notWiredAdapter

export const knowledgeService = {
  setAdapter(a: KnowledgeAdapter) { currentAdapter = a },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  getDocuments: () => currentAdapter.getDocuments(),
  getDocument: (id: string) => currentAdapter.getDocument(id),
  searchDocuments: (q: string) => currentAdapter.searchDocuments(q),
  getFolders: () => currentAdapter.getFolders(),
  getDocumentCount: () => currentAdapter.getDocumentCount(),
  importDocument: (f: File) => currentAdapter.importDocument(f),
}

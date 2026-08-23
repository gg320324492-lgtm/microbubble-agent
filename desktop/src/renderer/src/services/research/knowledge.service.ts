// Knowledge Service — 文献/知识库服务层（带适配器模式）。

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

const MOCK_DOCUMENTS: DocumentItem[] = [
  { id: 'd1', title: '臭氧微纳米气泡降解四环素的动力学与机理研究', authors: '李小红, 张伟, 陈晨', journal: '环境科学学报', year: 2021, type: 'paper', tags: ['O₃-MNBs', 'TC', '降解动力学'], credibility: 0.82, citations: 48, relevance: 0.94 },
  { id: 'd2', title: 'Nanobubble characterization methods and applications', authors: 'Li, X., et al.', journal: 'Ultrasonics', year: 2023, type: 'paper', tags: ['纳米气泡', '表征'], credibility: 0.65, citations: 32, relevance: 0.88 },
  { id: 'd3', title: 'Ozone mass transfer in microbubble systems', authors: 'Wang, Y., et al.', journal: 'Water Research', year: 2023, type: 'paper', tags: ['传质', '臭氧'], credibility: 0.90, citations: 56, relevance: 0.91 },
  { id: 'd4', title: '四环素在水体中的降解行为与机理研究', authors: '李某, 等', journal: '化学工程学报', year: 2021, type: 'paper', tags: ['TC', '动力学', '机理'], credibility: 0.72, citations: 24, relevance: 0.85 },
  { id: 'd5', title: 'CFD模拟微纳米气泡流动特性', authors: 'Chen X., et al.', journal: 'Chem. Eng. J.', year: 2019, type: 'paper', tags: ['CFD', '模拟', '气泡'], credibility: 0.78, citations: 18, relevance: 0.79 },
]

const MOCK_FOLDERS: KnowledgeFolder[] = [
  { id: 'f1', name: 'O₃-MNBs TC 降解研究', count: 128, children: [
    { id: 'f1-1', name: '机理研究', count: 46 },
    { id: 'f1-2', name: '反应动力学', count: 28 },
    { id: 'f1-3', name: '影响因素', count: 24 },
  ]},
  { id: 'f2', name: '臭氧-微纳米气泡基础', count: 236 },
  { id: 'f3', name: '催化与活化', count: 189 },
]

const mockAdapter: KnowledgeAdapter = {
  async getDocuments() { return [...MOCK_DOCUMENTS] },
  async getDocument(id) { return MOCK_DOCUMENTS.find(d => d.id === id) },
  async searchDocuments(q) { return MOCK_DOCUMENTS.filter(d => d.title.toLowerCase().includes(q.toLowerCase()) || d.tags.some(t => t.includes(q))).map(d => ({ documentId: d.id, score: d.credibility, excerpt: d.title })) },
  async getFolders() { return [...MOCK_FOLDERS] },
  async getDocumentCount() { return MOCK_DOCUMENTS.length },
  async importDocument() { return null },
}

let currentAdapter: KnowledgeAdapter = mockAdapter

export const knowledgeService = {
  setAdapter(a: KnowledgeAdapter) { currentAdapter = a },
  getDocuments: () => currentAdapter.getDocuments(),
  getDocument: (id: string) => currentAdapter.getDocument(id),
  searchDocuments: (q: string) => currentAdapter.searchDocuments(q),
  getFolders: () => currentAdapter.getFolders(),
  getDocumentCount: () => currentAdapter.getDocumentCount(),
  importDocument: (f: File) => currentAdapter.importDocument(f),
}

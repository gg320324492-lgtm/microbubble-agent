// Knowledge Service — 文献/知识库服务层。
// Mock 适配器，未来替换为 IPC 调用后端 Phase 8-C knowledge 层。

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
}

export interface SearchResult {
  documentId: string
  score: number
  excerpt: string
}

export interface KnowledgeFolder {
  id: string
  name: string
  count: number
  children?: KnowledgeFolder[]
}

const MOCK_DOCUMENTS: DocumentItem[] = [
  { id: 'd1', title: '臭氧微纳米气泡降解四环素的动力学与机理研究', authors: '李小红, 张伟, 陈晨', journal: '环境科学学报', year: 2021, type: 'paper', tags: ['O₃-MNBs', 'TC', '降解动力学'], credibility: 0.82, citations: 48 },
  { id: 'd2', title: 'Nanobubble characterization methods and applications', authors: 'Li, X., et al.', journal: 'Ultrasonics', year: 2023, type: 'paper', tags: ['纳米气泡', '表征'], credibility: 0.65, citations: 32 },
  { id: 'd3', title: 'Ozone mass transfer in microbubble systems', authors: 'Wang, Y., et al.', journal: 'Water Research', year: 2023, type: 'paper', tags: ['传质', '臭氧'], credibility: 0.90, citations: 56 },
  { id: 'd4', title: '四环素在水体中的降解行为与机理研究', authors: '李某, 等', journal: '化学工程学报', year: 2021, type: 'paper', tags: ['TC', '动力学', '机理'], credibility: 0.72, citations: 24 },
  { id: 'd5', title: 'CFD模拟微纳米气泡流动特性', authors: 'Chen X., et al.', journal: 'Chem. Eng. J.', year: 2019, type: 'paper', tags: ['CFD', '模拟', '气泡'], credibility: 0.78, citations: 18 },
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

export const knowledgeService = {
  async getDocuments(): Promise<DocumentItem[]> {
    return [...MOCK_DOCUMENTS]
  },

  async getDocument(id: string): Promise<DocumentItem | undefined> {
    return MOCK_DOCUMENTS.find(d => d.id === id)
  },

  async searchDocuments(query: string): Promise<SearchResult[]> {
    return MOCK_DOCUMENTS
      .filter(d => d.title.toLowerCase().includes(query.toLowerCase()) || d.tags.some(t => t.includes(query)))
      .map(d => ({ documentId: d.id, score: d.credibility, excerpt: d.title }))
  },

  async getFolders(): Promise<KnowledgeFolder[]> {
    return [...MOCK_FOLDERS]
  },

  async getDocumentCount(): Promise<number> {
    return MOCK_DOCUMENTS.length
  },
}

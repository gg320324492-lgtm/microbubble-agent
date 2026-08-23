// Manuscript Service — 论文助手服务层（带适配器模式）。

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

const MOCK_MANUSCRIPT: Manuscript = {
  manuscriptId: 'ms-1', title: '臭氧微纳米气泡降解四环素的效率与机理研究',
  abstract: '本研究系统探讨了臭氧微纳米气泡（O₃-MNBs）对四环素（TC）的降解性能及其作用机理。结果表明，在最优条件下，O₃-MNBs 对 TC 的去除率高达 98.6%，主要活性物种为 ·OH 与 ¹O₂。降解过程符合准一级动力学模型，表观速率常数为 0.0243 min⁻¹。',
  sections: [
    { sectionType: 'introduction', title: '1 引言', content: '四环素（TC）是一种广谱抗生素，广泛用于人类疾病治疗和动物养殖，其在水体中的残留会对生态环境和人类健康造成潜在风险。臭氧微纳米气泡技术通过界面效应提高臭氧利用效率，增强传质与反应速率。', citations: ['[1]', '[2]', '[3]'] },
    { sectionType: 'methods', title: '2 材料与方法', content: '实验材料：四环素（纯度≥98%，上海阿拉丁）；臭氧由臭氧发生器（GL-3180，产量1 gh⁻¹）制备。实验装置由臭氧发生器、气液混合器、微纳米气泡发生器及反应器组成。', citations: [] },
    { sectionType: 'results', title: '3 结果与讨论', content: '动力学拟合表明 TC 降解符合准一级动力学模型（R²=0.9887），表观速率常数 kobs = 0.0243 min⁻¹，半衰期 t₁/₂ = 28.5 min。', citations: ['[4]', '[5]'] },
    { sectionType: 'discussion', title: '4 讨论', content: '一级动力学模型提供了优异的拟合，表明降解过程遵循浓度依赖行为。·OH 是主要活性物种，贡献率约 68%。', citations: ['[6]'] },
    { sectionType: 'conclusion', title: '5 结论', content: '本研究证明了 O₃-MNBs 技术对四环素具有高效、快速、可调控的降解效果，具备工程应用潜力。', citations: [] },
  ],
  figures: [
    { figureId: 'fig-1', caption: 'TC 浓度随反应时间的变化曲线', description: '一级动力学拟合' },
    { figureId: 'fig-2', caption: '不同气泡粒径下的降解效率对比', description: '变量重要性分析' },
  ],
  highlights: ['O₃-MNBs 对 TC 去除率达 98.6%', '主要活性物种为 ·OH（68%）与 ¹O₂（18%）', '一级动力学模型 R²=0.9887', '最优条件：粒径 ~150nm，O₃ 20 mg/L，pH 7'],
  wordCount: 6842,
}

const MOCK_ISSUES: WritingIssue[] = [
  { type: 'repetition', location: '引言', description: '文献中部分数据尚未进行重复性分析', severity: 'medium', suggestion: '补充重复实验验证' },
  { type: 'missing_evidence', location: '讨论', description: '建议补充自然水体中基质效应讨论', severity: 'medium', suggestion: '增加基质效应实验数据' },
  { type: 'weak_citation', location: '参考文献', description: '参考文献中近三年文献占比偏低', severity: 'low', suggestion: '补充最新文献引用' },
]

const mockAdapter: ManuscriptAdapter = {
  async getManuscript() { return { ...MOCK_MANUSCRIPT } },
  async getWritingIssues() { return [...MOCK_ISSUES] },
  async getSections() { return [...MOCK_MANUSCRIPT.sections] },
  async generateSection(type, _outline) {
    const defaults: Record<string, string> = {
      introduction: '科学研究需要系统性调查来解决知识空白。本研究旨在探讨...',
      methods: '实验采用标准化流程，材料与试剂信息如下...',
      results: '实验数据表明...',
      discussion: '上述结果表明...',
      conclusion: '本研究的主要贡献如下...',
    }
    return defaults[type] ?? '内容生成中...'
  },
  async reviewSection() { return [] },
}

let currentAdapter: ManuscriptAdapter = mockAdapter

export const manuscriptService = {
  setAdapter(a: ManuscriptAdapter) { currentAdapter = a },
  getManuscript: () => currentAdapter.getManuscript(),
  getWritingIssues: () => currentAdapter.getWritingIssues(),
  getSections: () => currentAdapter.getSections(),
  generateSection: (t: string, o: string) => currentAdapter.generateSection(t, o),
  reviewSection: (t: string, c: string) => currentAdapter.reviewSection(t, c),
}

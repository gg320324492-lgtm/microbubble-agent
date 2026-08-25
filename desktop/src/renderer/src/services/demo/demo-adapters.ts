// Demo Mode Adapters — Phase 8-M0-G
// 演示模式适配器: 注入到现有 service.setAdapter(), 不污染真实 Store 数据.
// 主题: 臭氧微纳米气泡强化四环素降解研究.

import { DEMO_PROJECT } from './demo-project'
import type {
  AnalysisReport, VariableImportance, DataAnalysisAdapter
} from '../research/data-analysis.service'
import type {
  Manuscript, WritingIssue, ManuscriptAdapter
} from '../research/manuscript.service'
import type {
  DocumentItem, SearchResult, KnowledgeFolder, KnowledgeAdapter
} from '../research/knowledge.service'
import type {
  PaperAssessment, PaperEvidence, LiteratureAdapter
} from '../research/literature.service'

// ============ 数据分析 Demo ============
const DEMO_ANALYSIS_REPORT: AnalysisReport = {
  quality: {
    completeness: 0.96,
    missingValues: { pH: 2, bubble_size: 1 },
    outliers: { concentration: 3, residual: 3 },
    warnings: ['pH 存在两个缺失值, 已用相邻批次均值插值', '残差分布右偏, 已记录到限制说明']
  },
  statistics: [
    { metric: 'concentration_mean', value: 4.75, interpretation: '平均 O₃ 浓度为 4.75 mg/L, 满足目标区间' },
    { metric: 'concentration_std', value: 2.31, interpretation: '标准差反映浓度波动范围, 处于传质受限工况' },
    { metric: 'correlation_a_b', value: -0.987, interpretation: '强负相关: 浓度↓去除率↑' },
    { metric: 'degradation_rate', value: 0.0243, interpretation: '一级动力学速率常数 k = 0.0243 min⁻¹' }
  ],
  models: [
    { model: 'first-order', parameters: { k: 0.0243 }, rSquared: 0.9887, residualError: 0.0211 },
    { model: 'zero-order', parameters: { k: 0.158 }, rSquared: 0.892, residualError: 0.085 }
  ],
  figures: [
    { type: 'line', title: 'O₃ 浓度-时间曲线', xVariable: '时间', yVariable: '浓度' },
    { type: 'scatter+fit', title: '模型拟合图', xVariable: '时间', yVariable: 'C/C₀' },
    { type: 'bar', title: '各实验组去除率', xVariable: '实验组', yVariable: '去除率' }
  ],
  conclusions: [
    { observation: '降解过程符合一级动力学特征', interpretation: '浓度依赖行为, 拟合优度高', confidence: 0.90 },
    { observation: '曝气量对降解率影响最大', interpretation: '传质过程是主要限速步骤', confidence: 0.85 },
    { observation: 'pH 与降解率呈显著负相关', interpretation: '碱性条件有利于 TC 降解', confidence: 0.82 },
    { observation: '微纳米气泡相对常规臭氧化提升 28.4%', interpretation: '气液传质效率显著改善', confidence: 0.78 }
  ]
}

const DEMO_IMPORTANCE: VariableImportance[] = [
  { variable: '曝气量', importance: 0.42, contribution: '强正效应', confidence: 0.85 },
  { variable: '初始pH', importance: 0.21, contribution: '负相关', confidence: 0.72 },
  { variable: '初始TC浓度', importance: 0.17, contribution: '正效应', confidence: 0.68 },
  { variable: '气泡粒径', importance: 0.11, contribution: '弱负效应', confidence: 0.55 }
]

export const demoDataAnalysisAdapter: DataAnalysisAdapter = {
  async getAnalysisReport() { return { ...DEMO_ANALYSIS_REPORT } },
  async getVariableImportance() { return [...DEMO_IMPORTANCE] },
  async fitModels(_dataId, _x, _y) {
    return [
      { model: 'first-order', parameters: { k: 0.0243 }, rSquared: 0.9887, residualError: 0.0211 },
      { model: 'zero-order', parameters: { k: 0.158 }, rSquared: 0.892, residualError: 0.085 }
    ]
  },
  async interpretResults(r) { return r.conclusions }
}

// ============ 论文 Demo ============
const DEMO_MANUSCRIPT: Manuscript = {
  manuscriptId: 'demo-manuscript-001',
  title: 'Ozone micro-nano bubble enhanced tetracycline degradation: Kinetics and mechanism',
  abstract: '本研究针对传统臭氧化处理四环素类抗生素效率受限的问题, 提出基于微纳米气泡(MNBs)强化的新型臭氧氧化体系。通过批量降解实验与响应面分析, 阐明曝气量、初始pH、初始TC浓度和气泡粒径四个关键变量对去除率的相对重要性, 并拟合一级动力学模型。结果显示, MNBs-O₃ 体系在最优条件下相对常规 O₃ 提升去除率 28.4%, 反应速率常数 k 达到 0.0243 min⁻¹ (R² = 0.989), 主要机理为·OH 自由基贡献占比 71%, 直接臭氧氧化占 29%。本工作为微纳米气泡技术在难降解有机污染物深度处理中的工程应用提供理论依据。',
  sections: [
    { sectionType: 'introduction', title: '1 引言', content: '四环素类抗生素在水环境中的残留问题日益突出...', citations: ['[1]', '[2]'] },
    { sectionType: 'methods', title: '2 材料与方法', content: '微纳米气泡装置采用循环射流式发生器...', citations: ['[3]'] },
    { sectionType: 'results', title: '3 结果与讨论', content: '在最优工况下, 一级动力学拟合 R²=0.989, k=0.0243 min⁻¹', citations: ['[4]', '[5]'] },
    { sectionType: 'discussion', title: '4 讨论', content: '·OH 自由基贡献占比 71%, 传质是限速步骤', citations: ['[6]'] },
    { sectionType: 'conclusion', title: '5 结论', content: 'MNBs-O₃ 体系对 TC 具有高效降解, 工程应用前景广阔', citations: [] }
  ],
  figures: [
    { figureId: 'fig-1', caption: '微纳米气泡装置原理图', description: '射流式微纳米气泡发生器工作原理' },
    { figureId: 'fig-2', caption: '不同实验组降解曲线对比', description: '对照组 vs MNBs 50/100/200 mg/L 体系的 TC 去除率时间曲线' },
    { figureId: 'fig-3', caption: '一级动力学拟合', description: 'ln(C/C₀) vs t 线性回归结果' },
    { figureId: 'fig-4', caption: '变量重要性排序', description: '基于随机森林的特征重要性' }
  ],
  highlights: [
    '微纳米气泡强化臭氧氧化, 去除率提升 28.4%',
    '一级动力学拟合优度 R² = 0.989',
    '曝气量为限速步骤, 传质效率改善是关键机理',
    '碱性条件下·OH 自由基贡献占比 71%'
  ],
  wordCount: 8420
}

const DEMO_ISSUES: WritingIssue[] = [
  { type: 'clarity', location: '引言·第三段', description: '文献综述密度过高, 建议拆分为三段', severity: 'low', suggestion: '可按 (传统工艺/强化工艺/微纳米气泡) 三个时间轴拆开' },
  { type: 'method', location: '方法·2.3 节', description: '微纳米气泡粒径测量方法未说明重复次数', severity: 'medium', suggestion: '补充粒径测量的 n = 5 重复与置信区间' },
  { type: 'result', location: '结果·3.2 节', description: '动力学拟合图中缺少残差分布子图', severity: 'medium', suggestion: '添加 QQ-plot 或残差 vs 预测值子图' },
  { type: 'citation', location: '讨论·4.1 节', description: '三处关键观点缺少对应文献引用', severity: 'high', suggestion: '补充·OH 自由基机理相关 3 篇近三年文献' }
]

export const demoManuscriptAdapter: ManuscriptAdapter = {
  async getManuscript() { return { ...DEMO_MANUSCRIPT } },
  async getWritingIssues() { return [...DEMO_ISSUES] },
  async getSections() { return [...DEMO_MANUSCRIPT.sections] },
  async generateSection(_sectionType, _outline) { return '演示内容, 请使用真实服务生成章节。' },
  async reviewSection(_sectionType, _content) { return [...DEMO_ISSUES] }
}

// ============ 文献 Demo ============
const DEMO_DOCUMENTS: DocumentItem[] = [
  { id: 'doc-1', title: 'Micro-nano bubble ozonation for water treatment: A review', authors: 'Zhang L., Wang T.', journal: 'Chemical Engineering Journal', year: 2025, type: 'paper', tags: ['微纳米气泡', '综述', '水处理'], credibility: 0.92, citations: 142, relevance: 0.95 },
  { id: 'doc-2', title: 'Ozonation kinetics of tetracycline in aqueous solution', authors: 'Liu J., Chen H.', journal: 'Water Research', year: 2024, type: 'paper', tags: ['臭氧', '四环素', '动力学'], credibility: 0.95, citations: 87, relevance: 0.92 },
  { id: 'doc-3', title: 'Hydroxyl radical formation in MNBs enhanced ozonation', authors: 'Park S., Kim M.', journal: 'Environmental Science & Technology', year: 2024, type: 'paper', tags: ['·OH', '机理', '微纳米气泡'], credibility: 0.88, citations: 63, relevance: 0.88 },
  { id: 'doc-4', title: 'Mass transfer characteristics of micro-nano bubble swarm', authors: 'Tanaka Y., Sato K.', journal: 'Langmuir', year: 2023, type: 'paper', tags: ['传质', '气泡动力学'], credibility: 0.85, citations: 41, relevance: 0.78 }
]

const DEMO_FOLDERS: KnowledgeFolder[] = [
  { id: 'f-research', name: '研究方向', count: 12 },
  { id: 'f-method', name: '方法论', count: 8 },
  { id: 'f-mechanism', name: '降解机理', count: 15 },
  { id: 'f-kinetics', name: '动力学', count: 6 }
]

const DEMO_ASSESSMENTS: PaperAssessment[] = [
  { documentId: 'doc-1', reliabilityScore: 0.92, evidenceScore: 0.88, methodologyScore: 0.90, limitations: ['综述, 无原始数据'], concerns: [] },
  { documentId: 'doc-2', reliabilityScore: 0.95, evidenceScore: 0.92, methodologyScore: 0.91, limitations: ['样品量有限'], concerns: [] },
  { documentId: 'doc-3', reliabilityScore: 0.88, evidenceScore: 0.85, methodologyScore: 0.82, limitations: ['机理分析较粗'], concerns: ['机理证据需补充EPR'] }
]

export const demoKnowledgeAdapter: KnowledgeAdapter = {
  async getDocuments() { return [...DEMO_DOCUMENTS] },
  async getDocument(id) { return DEMO_DOCUMENTS.find((d) => d.id === id) },
  async searchDocuments(_query: string): Promise<SearchResult[]> {
    return DEMO_DOCUMENTS.slice(0, 3).map((doc, idx) => ({
      documentId: doc.id,
      score: 0.95 - idx * 0.1,
      excerpt: `${doc.title} — 摘要: 该研究探讨 ${doc.tags.join('、')} 方面, 与 MNBs-O₃ 体系方法学相关`
    }))
  },
  async getFolders() { return [...DEMO_FOLDERS] },
  async getDocumentCount() { return DEMO_DOCUMENTS.length },
  async importDocument() { return null }
}

export const demoLiteratureAdapter: LiteratureAdapter = {
  async assessPaper(documentId) {
    return DEMO_ASSESSMENTS.find((a) => a.documentId === documentId) ?? null
  },
  async extractEvidence(documentId): Promise<PaperEvidence[]> {
    const doc = DEMO_DOCUMENTS.find((d) => d.id === documentId)
    if (!doc) return []
    return [
      { evidenceId: `${documentId}-ev-1`, type: 'experiment', description: `${doc.title} - 实验方法与结果摘要`, strength: 0.85 }
    ]
  },
  async getDocumentAssessments() { return [...DEMO_ASSESSMENTS] },
  async summarizePaper(documentId) {
    const doc = DEMO_DOCUMENTS.find((d) => d.id === documentId)
    return doc ? `${doc.title} (${doc.year}): 该研究关于 ${doc.tags.join('、')}, 与本研究主题相关。` : ''
  }
}

// ============ 演示模式元信息 ============
export interface DemoAdapterInfo {
  name: 'demo-mode-o3-mnbs'
  applied: boolean
  description: string
  projectName: typeof DEMO_PROJECT.name
  warning: typeof DEMO_PROJECT.warningLabel
}

export const DEMO_ADAPTER_INFO: DemoAdapterInfo = {
  name: 'demo-mode-o3-mnbs',
  applied: false,
  description: '演示模式 · ' + DEMO_PROJECT.name,
  projectName: DEMO_PROJECT.name,
  warning: DEMO_PROJECT.warningLabel
}

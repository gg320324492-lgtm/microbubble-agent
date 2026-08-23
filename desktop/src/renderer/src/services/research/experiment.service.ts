// Experiment Service — 实验设计服务层（带适配器模式）。

export interface ExperimentDesign {
  id: string
  title: string
  question: string
  hypotheses: Array<{ statement: string; confidence: number }>
  variables: Array<{ name: string; type: 'independent' | 'dependent' | 'control'; range: string; unit: string }>
  groups: Array<{ name: string; condition: string; purpose?: string }>
  metrics: string[]
  model: { name: string; confidence: number }
  status: 'designing' | 'running' | 'completed'
}

export interface ExperimentAdapter {
  getDesign(): Promise<ExperimentDesign>
  getDesignStatus(): Promise<ExperimentDesign['status']>
  generateHypotheses(problem: string): Promise<Array<{ statement: string; confidence: number }>>
  updateDesign(patch: Partial<ExperimentDesign>): Promise<void>
}

const MOCK_DESIGN: ExperimentDesign = {
  id: 'exp-1',
  title: 'O₃微纳米气泡降解四环素效率优化',
  question: '如何优化微纳米气泡臭氧技术对四环素的降解效率？',
  hypotheses: [
    { statement: '更小气泡直径增加气液界面面积，提高臭氧传质效率', confidence: 0.80 },
    { statement: '自由基（·OH）途径是 TC 降解的主要活性机制', confidence: 0.65 },
  ],
  variables: [
    { name: '气泡直径', type: 'independent', range: '50 – 500 nm', unit: 'nm' },
    { name: '臭氧浓度', type: 'independent', range: '5 – 25 mg/L', unit: 'mg/L' },
    { name: 'pH', type: 'control', range: '5.0 – 9.0', unit: '' },
    { name: 'TC 去除率', type: 'dependent', range: '0 – 100%', unit: '%' },
  ],
  groups: [
    { name: '对照组', condition: '常规曝气（无微纳米气泡）', purpose: '基线对比' },
    { name: '实验组 1', condition: '200 nm 微纳米气泡 + 10 mg/L O₃', purpose: '中等条件' },
    { name: '实验组 2', condition: '100 nm 微纳米气泡 + 15 mg/L O₃', purpose: '较高条件' },
    { name: '实验组 3', condition: '50 nm 微纳米气泡 + 20 mg/L O₃', purpose: '最优条件' },
  ],
  metrics: ['TC 去除率 (%)', 'TOC 去除率 (%)', '动力学常数 k (min⁻¹)', '半衰期 t₁/₂ (min)'],
  model: { name: '伪一级动力学', confidence: 0.85 },
  status: 'running',
}

const mockAdapter: ExperimentAdapter = {
  async getDesign() { return { ...MOCK_DESIGN } },
  async getDesignStatus() { return MOCK_DESIGN.status },
  async generateHypotheses(problem) {
    return [
      { statement: `基于「${problem}」的分析，提高气液传质效率可增强反应物利用率`, confidence: 0.75 },
      { statement: '优化工艺参数可显著提升降解效率', confidence: 0.70 },
    ]
  },
  async updateDesign() {},
}

let currentAdapter: ExperimentAdapter = mockAdapter

export const experimentService = {
  setAdapter(a: ExperimentAdapter) { currentAdapter = a },
  getDesign: () => currentAdapter.getDesign(),
  getDesignStatus: () => currentAdapter.getDesignStatus(),
  generateHypotheses: (problem: string) => currentAdapter.generateHypotheses(problem),
  updateDesign: (patch: Partial<ExperimentDesign>) => currentAdapter.updateDesign(patch),
}

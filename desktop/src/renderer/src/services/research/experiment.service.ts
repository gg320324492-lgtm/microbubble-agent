// Experiment Service — 实验设计服务层。
// 封装 Phase 8-H0 研究设计 Agent 能力。

export interface ExperimentDesign {
  id: string
  title: string
  question: string
  hypotheses: Array<{ statement: string; confidence: number }>
  variables: Array<{ name: string; type: 'independent' | 'dependent' | 'control'; range: string; unit: string }>
  groups: Array<{ name: string; condition: string }>
  metrics: string[]
  model: { name: string; confidence: number }
  status: 'designing' | 'running' | 'completed'
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
    { name: '对照组', condition: '常规曝气（无微纳米气泡）' },
    { name: '实验组 1', condition: '200 nm 微纳米气泡 + 10 mg/L O₃' },
    { name: '实验组 2', condition: '100 nm 微纳米气泡 + 15 mg/L O₃' },
    { name: '实验组 3', condition: '50 nm 微纳米气泡 + 20 mg/L O₃' },
  ],
  metrics: ['TC 去除率 (%)', 'TOC 去除率 (%)', '动力学常数 k (min⁻¹)', '半衰期 t₁/₂ (min)'],
  model: { name: '伪一级动力学', confidence: 0.85 },
  status: 'running',
}

export const experimentService = {
  async getDesign(): Promise<ExperimentDesign> {
    return { ...MOCK_DESIGN }
  },

  async getDesignStatus(): Promise<ExperimentDesign['status']> {
    return MOCK_DESIGN.status
  },
}

// Data Analysis Service — 数据分析服务层。
// 封装 Phase 8-H2 科学数据分析能力。

export interface DataQualityReport {
  completeness: number
  missingValues: Record<string, number>
  outliers: Record<string, number>
  warnings: string[]
}

export interface StatisticalResult {
  metric: string
  value: number
  interpretation: string
}

export interface ModelFitResult {
  model: string
  parameters: Record<string, number>
  rSquared: number
  residualError: number
}

export interface FigureRecommendation {
  type: string
  title: string
  xVariable: string
  yVariable: string
}

export interface ScientificConclusion {
  observation: string
  interpretation: string
  confidence: number
}

export interface AnalysisReport {
  quality: DataQualityReport
  statistics: StatisticalResult[]
  models: ModelFitResult[]
  figures: FigureRecommendation[]
  conclusions: ScientificConclusion[]
}

const MOCK_REPORT: AnalysisReport = {
  quality: { completeness: 1.0, missingValues: {}, outliers: {}, warnings: [] },
  statistics: [
    { metric: 'concentration_mean', value: 4.75, interpretation: '平均 O₃ 浓度为 4.75 mg/L' },
    { metric: 'concentration_std', value: 2.31, interpretation: '标准差反映浓度波动范围' },
    { metric: 'correlation_a_b', value: -0.987, interpretation: '强负相关：浓度↓去除率↑' },
  ],
  models: [
    { model: 'first-order', parameters: { k: 0.0243 }, rSquared: 0.9887, residualError: 0.0211 },
    { model: 'zero-order', parameters: { k: 0.158 }, rSquared: 0.892, residualError: 0.085 },
  ],
  figures: [
    { type: 'line', title: 'O₃ 浓度-时间曲线', xVariable: '时间', yVariable: '浓度' },
    { type: 'scatter+fit', title: '模型拟合图', xVariable: '时间', yVariable: 'C/C₀' },
  ],
  conclusions: [
    { observation: '降解过程符合一级动力学特征', interpretation: '浓度依赖行为，拟合优度高', confidence: 0.90 },
    { observation: '曝气量对降解率影响最大', interpretation: '传质过程是主要限速步骤', confidence: 0.85 },
    { observation: 'pH 与降解率呈显著负相关', interpretation: '碱性条件有利于 TC 降解', confidence: 0.82 },
  ],
}

export const dataAnalysisService = {
  async getAnalysisReport(): Promise<AnalysisReport> {
    return { ...MOCK_REPORT }
  },

  async getQualityReport(): Promise<DataQualityReport> {
    return { ...MOCK_REPORT.quality }
  },

  async getStatistics(): Promise<StatisticalResult[]> {
    return [...MOCK_REPORT.statistics]
  },

  async getModelFits(): Promise<ModelFitResult[]> {
    return [...MOCK_REPORT.models]
  },

  async getConclusions(): Promise<ScientificConclusion[]> {
    return [...MOCK_REPORT.conclusions]
  },
}

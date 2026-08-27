// Data Analysis Service — 数据分析服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 hardcoded MOCK_REPORT / MOCK_IMPORTANCE / 假 fitModels
// 这些假数据曾被 UI 渲染为"真实分析结果" (k=0.0243, R²=0.9887, "传质是限速步骤" 等).
// 改为: 默认 adapter 抛 NotImplemented, 强制要求 wire 真实数据源.
// 真实实现路径:
//   1. local: 通过 IPC `analysis:*` 调用 main process SQLite 查询 desktop_analysis_results 表
//   2. remote: 通过 IPC `data:analysis.*` 调 FastAPI `/api/v1/analysis/*` 后端
// 任一路径接入后, 调 dataAnalysisService.setAdapter(realAdapter) 即生效.

export interface DataQualityReport { completeness: number; missingValues: Record<string, number>; outliers: Record<string, number>; warnings: string[] }
export interface StatisticalResult { metric: string; value: number; interpretation: string }
export interface ModelFitResult { model: string; parameters: Record<string, number>; rSquared: number; residualError: number }
export interface FigureRecommendation { type: string; title: string; xVariable: string; yVariable: string }
export interface ScientificConclusion { observation: string; interpretation: string; confidence: number }
export interface AnalysisReport { quality: DataQualityReport; statistics: StatisticalResult[]; models: ModelFitResult[]; figures: FigureRecommendation[]; conclusions: ScientificConclusion[] }
export interface VariableImportance { variable: string; importance: number; contribution: string; confidence: number }

export interface DataAnalysisAdapter {
  getAnalysisReport(): Promise<AnalysisReport>
  getVariableImportance(): Promise<VariableImportance[]>
  fitModels(dataId: string, x: string, y: string): Promise<ModelFitResult[]>
  interpretResults(report: AnalysisReport): Promise<ScientificConclusion[]>
}

/** Error thrown when no real adapter has been wired. */
export class DataAnalysisNotWiredError extends Error {
  constructor() {
    super(
      '[DataAnalysisService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning fake k=0.0243 R²=0.9887. ' +
      'Real data path: 1) local SQLite via main IPC analysis:* channels, or 2) FastAPI /api/v1/analysis/* via api.service. ' +
      'Call dataAnalysisService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'DataAnalysisNotWiredError'
  }
}

const notWiredAdapter: DataAnalysisAdapter = {
  async getAnalysisReport() { throw new DataAnalysisNotWiredError() },
  async getVariableImportance() { throw new DataAnalysisNotWiredError() },
  async fitModels() { throw new DataAnalysisNotWiredError() },
  async interpretResults() { throw new DataAnalysisNotWiredError() },
}

let currentAdapter: DataAnalysisAdapter = notWiredAdapter

export const dataAnalysisService = {
  setAdapter(a: DataAnalysisAdapter) { currentAdapter = a },
  /** True iff a real adapter is wired (setAdapter called at least once). */
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  getAnalysisReport: () => currentAdapter.getAnalysisReport(),
  getVariableImportance: () => currentAdapter.getVariableImportance(),
  fitModels: (d: string, x: string, y: string) => currentAdapter.fitModels(d, x, y),
  interpretResults: (r: AnalysisReport) => currentAdapter.interpretResults(r),
}

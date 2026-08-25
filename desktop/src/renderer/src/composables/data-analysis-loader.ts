// Data Analysis Loader Composable — Phase 8-M0-D 适配层.
// 包装 dataAnalysisService, 让页面不直接接触 service 路径.
import { dataAnalysisService } from '../services/research/data-analysis.service'
import type { AnalysisReport, VariableImportance } from '../services/research/data-analysis.service'

export type { AnalysisReport, VariableImportance } from '../services/research/data-analysis.service'

export function useDataAnalysisLoader() {
  return {
    fetchAnalysisReport: () => dataAnalysisService.getAnalysisReport() as unknown as Promise<AnalysisReport>,
    fetchVariableImportance: () => dataAnalysisService.getVariableImportance() as unknown as Promise<VariableImportance[]>
  }
}

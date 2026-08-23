// Scientific Data Analyst Facade (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: dependency-injection facade that composes data quality analysis,
// statistics, model fitting, visualization planning, and interpretation into
// a single coherent API. All components are deterministic — no LLM, no backend,
// no SDK, no auth.

import type {
  ScientificDataset,
  AnalysisReport
} from '../../../shared/science/scientific-data-schema'

import { analyzeDataQuality } from './data-quality-analyzer'
import { computeStatistics } from './statistical-analyzer'
import { fitModels } from './model-fitting-engine'
import { planVisualizations } from './visualization-planner'
import { interpretAnalysis } from './data-interpreter'

// ============ Facade ============

/**
 * Phase 8-H2: the Scientific Data Analyst composes all analysis components.
 * Input: ScientificDataset. Output: complete AnalysisReport.
 */
export class ScientificDataAnalyst {
  constructor() {}

  /**
   * Full analysis pipeline: quality → statistics → model → visualization → interpretation.
   */
  analyzeDataset(
    dataset: ScientificDataset,
    xVariable?: string,
    yVariable?: string
  ): AnalysisReport {
    const quality = analyzeDataQuality(dataset)
    const statistics = computeStatistics(dataset)

    // Auto-select x/y from first two numeric variables if not specified
    const numVars = dataset.variables.filter(v => v.type === 'number')
    const xVar = xVariable ?? numVars[0]?.name
    const yVar = yVariable ?? numVars[1]?.name

    const models = (xVar && yVar) ? fitModels(dataset, xVar, yVar) : []
    const figures = planVisualizations(dataset, models)

    const tempReport: AnalysisReport = { quality, statistics, models, figures, conclusions: [] }
    const conclusions = interpretAnalysis(tempReport)

    return { quality, statistics, models, figures, conclusions }
  }

  /**
   * Analyze data quality only (step 1).
   */
  analyzeQuality(dataset: ScientificDataset) {
    return analyzeDataQuality(dataset)
  }

  /**
   * Compute statistics only (step 2).
   */
  computeStatistics(dataset: ScientificDataset) {
    return computeStatistics(dataset)
  }

  /**
   * Fit models only (step 3).
   */
  fitModels(dataset: ScientificDataset, xVariable: string, yVariable: string) {
    return fitModels(dataset, xVariable, yVariable)
  }

  /**
   * Plan visualizations only (step 4).
   */
  planVisualizations(dataset: ScientificDataset, models: Parameters<typeof planVisualizations>[1] = []) {
    return planVisualizations(dataset, models)
  }

  /**
   * Interpret analysis only (step 5).
   */
  interpretAnalysis(report: AnalysisReport) {
    return interpretAnalysis(report)
  }
}

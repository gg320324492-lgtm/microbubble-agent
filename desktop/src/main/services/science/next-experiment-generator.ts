// Next Experiment Generator (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: deterministic recommendation of follow-up experiments based on
// variable importance and uncertainty analysis. Prioritizes the variable with
// highest importance and lowest data coverage — no LLM.

import type {
  ExperimentObservation,
  VariableImportance,
  NextExperimentRecommendation
} from '../../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../../shared/science/research-design-schema'

// ============ Range estimation ============

function estimateCurrentRange(
  varName: string,
  observations: ExperimentObservation[]
): { min: number; max: number; count: number } {
  const values: number[] = []
  for (const obs of observations) {
    const v = obs.variableValues[varName]
    if (v !== undefined) values.push(v)
  }
  if (values.length === 0) return { min: 0, max: 0, count: 0 }
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    count: values.length
  }
}

function suggestNewRange(
  currentMin: number,
  currentMax: number,
  _variable: VariableImportance
): string {
  const range = currentMax - currentMin
  if (range === 0) {
    // Single point tested — suggest exploration on both sides
    const delta = Math.abs(currentMin) * 0.2 || 0.1
    return `${(currentMin - delta).toFixed(2)}-${(currentMin + delta).toFixed(2)}`
  }
  // Suggest extending range by 20% in the direction of higher importance
  const extension = range * 0.2
  const newMin = currentMin - extension
  const newMax = currentMax + extension
  return `${newMin.toFixed(2)}-${newMax.toFixed(2)}`
}

// ============ Public API ============

/**
 * Phase 8-H1: generate next experiment recommendations based on variable
 * importance and current data coverage. Prioritizes high-importance,
 * low-coverage variables. Deterministic.
 */
export function generateNextExperiments(
  plan: ExperimentPlan,
  observations: ExperimentObservation[],
  importantVariables: VariableImportance[]
): NextExperimentRecommendation[] {
  const recommendations: NextExperimentRecommendation[] = []
  const independentVars = plan.variables.filter((v: { type: string; name: string }) => v.type === 'independent')

  // Score each variable: importance * (1 / coverage)
  const scored = independentVars.map((v: { type: string; name: string }) => {
    const importance = importantVariables.find((iv: { variable: string }) => iv.variable === v.name)
    const { min, max, count } = estimateCurrentRange(v.name, observations)
    const coverage = Math.min(count / 5, 1) // 5 data points = full coverage
    const score = (importance?.importance ?? 0.5) * (1 - coverage * 0.5)
    return { variable: v, importance: importance ?? { variable: v.name, importance: 0.5, contribution: 'unknown', confidence: 0.3 }, min, max, count, score }
  })

  // Sort by score descending — highest priority first
  scored.sort((a: { score: number }, b: { score: number }) => b.score - a.score)

  // Generate recommendations for top 3 variables
  for (const item of scored.slice(0, 3)) {
    const suggestedRange = suggestNewRange(item.min, item.max, item.importance)
    recommendations.push({
      changeVariable: item.variable.name,
      currentValue: (item.min + item.max) / 2,
      suggestedRange,
      purpose: `Investigate ${item.variable.name} influence with expanded range (${item.importance.contribution})`
    })
  }

  return recommendations
}

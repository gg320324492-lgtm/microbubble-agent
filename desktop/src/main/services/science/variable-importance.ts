// Variable Importance Analyzer (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: deterministic calculation of variable importance from experiment
// observations. Uses range-sensitivity analysis — the ratio of metric change
// to variable change — no LLM.

import type {
  ExperimentObservation,
  VariableImportance
} from '../../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../../shared/science/research-design-schema'

// ============ Sensitivity calculation ============

function calculateRangeSensitivity(
  varName: string,
  observations: ExperimentObservation[],
  metricName: string
): { sensitivity: number; confidence: number } {
  // Collect (variable_value, metric_value) pairs
  const pairs: Array<{ x: number; y: number }> = []
  for (const obs of observations) {
    const x = obs.variableValues[varName]
    const metric = obs.metrics.find((m: { name: string; value: number }) => m.name === metricName)
    if (x !== undefined && metric) {
      pairs.push({ x, y: metric.value })
    }
  }

  if (pairs.length < 2) return { sensitivity: 0, confidence: 0 }

  // Sort by variable value
  pairs.sort((a, b) => a.x - b.x)

  // Calculate range sensitivity: max metric change / variable range
  const xMin = pairs[0].x
  const xMax = pairs[pairs.length - 1].x
  const xRange = xMax - xMin

  if (xRange === 0) return { sensitivity: 0, confidence: 0.1 }

  const yValues = pairs.map(p => p.y)
  const yMax = Math.max(...yValues)
  const yMin = Math.min(...yValues)
  const yRange = yMax - yMin

  // Normalized sensitivity: metric change relative to variable change
  const sensitivity = yRange / (xRange || 1)

  // Confidence based on number of data points and monotonicity
  let monotonicCount = 0
  for (let i = 1; i < pairs.length; i++) {
    const xInc = pairs[i].x > pairs[i - 1].x
    const yInc = pairs[i].y > pairs[i - 1].y
    if (xInc === yInc || pairs[i].x === pairs[i - 1].x) monotonicCount++
  }
  const monotonicity = monotonicCount / (pairs.length - 1)
  const dataConfidence = Math.min(pairs.length / 5, 1) * 0.5
  const confidence = Math.min(monotonicity * 0.5 + dataConfidence, 1)

  return { sensitivity: Math.abs(sensitivity), confidence }
}

// ============ Contribution description ============

function describeContribution(
  varName: string,
  sensitivity: number,
  observations: ExperimentObservation[],
  metricName: string
): string {
  // Determine direction of effect
  const pairs: Array<{ x: number; y: number }> = []
  for (const obs of observations) {
    const x = obs.variableValues[varName]
    const metric = obs.metrics.find((m: { name: string; value: number }) => m.name === metricName)
    if (x !== undefined && metric) pairs.push({ x, y: metric.value })
  }
  if (pairs.length < 2) return `${varName} has insufficient data for ${metricName}`

  pairs.sort((a, b) => a.x - b.x)
  const firstHalf = pairs.slice(0, Math.ceil(pairs.length / 2))
  const secondHalf = pairs.slice(Math.floor(pairs.length / 2))
  const avgFirst = firstHalf.reduce((s, p) => s + p.y, 0) / firstHalf.length
  const avgSecond = secondHalf.reduce((s, p) => s + p.y, 0) / secondHalf.length

  const direction = avgSecond > avgFirst ? 'positive' : 'negative'
  const magnitude = sensitivity > 0.5 ? 'strong' : sensitivity > 0.1 ? 'moderate' : 'weak'

  return `${varName} has ${magnitude} ${direction} effect on ${metricName}`
}

// ============ Public API ============

/**
 * Phase 8-H1: calculate variable importance from experiment plan and observations.
 * Returns variables sorted by importance (descending). Deterministic.
 */
export function calculateImportance(
  plan: ExperimentPlan,
  observations: ExperimentObservation[]
): VariableImportance[] {
  const independentVars = plan.variables.filter((v: { type: string }) => v.type === 'independent')
  const dependentMetrics = plan.measurements.map((m: { name: string }) => m.name)

  const results: VariableImportance[] = []

  for (const variable of independentVars) {
    let totalSensitivity = 0
    let totalConfidence = 0
    let metricCount = 0

    for (const metricName of dependentMetrics) {
      const { sensitivity, confidence } = calculateRangeSensitivity(
        variable.name, observations, metricName
      )
      totalSensitivity += sensitivity
      totalConfidence += confidence
      metricCount++
    }

    const avgSensitivity = metricCount > 0 ? totalSensitivity / metricCount : 0
    const avgConfidence = metricCount > 0 ? totalConfidence / metricCount : 0

    // Normalize importance to 0..1 using tanh-like scaling
    const importance = Math.min(Math.tanh(avgSensitivity) * 0.8 + avgConfidence * 0.2, 1)

    results.push({
      variable: variable.name,
      importance: Math.round(importance * 100) / 100,
      contribution: describeContribution(
        variable.name, avgSensitivity, observations, dependentMetrics[0] ?? 'unknown'
      ),
      confidence: Math.round(avgConfidence * 100) / 100
    })
  }

  // Sort by importance descending
  results.sort((a, b) => b.importance - a.importance)
  return results
}

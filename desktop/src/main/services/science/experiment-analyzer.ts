// Experiment Analyzer (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: deterministic detection of anomalies in experiment observations.
// Detects outliers, contradictions, missing data, and unexpected trends using
// statistical heuristics — no LLM.

import type {
  ExperimentObservation,
  MetricObservation,
  OptimizationIssue
} from '../../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../../shared/science/research-design-schema'

// ============ Outlier detection ============

function detectOutliers(observations: ExperimentObservation[]): OptimizationIssue[] {
  const issues: OptimizationIssue[] = []
  // Group observations by metric name
  const metricGroups = new Map<string, MetricObservation[]>()
  for (const obs of observations) {
    for (const m of obs.metrics) {
      const existing = metricGroups.get(m.name) ?? []
      existing.push(m)
      metricGroups.set(m.name, existing)
    }
  }

  for (const [metricName, metrics] of metricGroups) {
    if (metrics.length < 3) continue
    const values = metrics.map(m => m.value)
    const mean = values.reduce((s, v) => s + v, 0) / values.length
    const std = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length)
    if (std === 0) continue

    for (let i = 0; i < values.length; i++) {
      const zScore = Math.abs(values[i] - mean) / std
      if (zScore > 2.0) {
        issues.push({
          type: 'outlier',
          description: `Observation ${observations[i].observationId} has ${metricName}=${values[i]} which deviates significantly from mean=${mean.toFixed(2)} (z-score=${zScore.toFixed(2)})`,
          severity: Math.min(zScore / 5, 1),
          evidence: `metric=${metricName}, value=${values[i]}, mean=${mean.toFixed(2)}, std=${std.toFixed(2)}, z=${zScore.toFixed(2)}`
        })
      }
    }
  }
  return issues
}

// ============ Contradiction detection ============

function detectContradictions(
  plan: ExperimentPlan,
  observations: ExperimentObservation[]
): OptimizationIssue[] {
  const issues: OptimizationIssue[] = []
  const independentVars = plan.variables.filter(v => v.type === 'independent')
  const dependentVars = plan.variables.filter(v => v.type === 'dependent')

  for (const depVar of dependentVars) {
    // For each dependent variable, check if increasing independent vars
    // leads to unexpected direction changes
    for (const indVar of independentVars) {
      const pairs: Array<{ indVal: number; depVal: number; obsId: string }> = []
      for (const obs of observations) {
        const indVal = obs.variableValues[indVar.name]
        const depMetric = obs.metrics.find(m => m.name === depVar.name)
        if (indVal !== undefined && depMetric) {
          pairs.push({ indVal, depVal: depMetric.value, obsId: obs.observationId })
        }
      }
      if (pairs.length < 2) continue
      // Check for contradictions: sorted by independent variable,
      // dependent should follow expected direction
      pairs.sort((a, b) => a.indVal - b.indVal)
      let contradictions = 0
      for (let i = 1; i < pairs.length; i++) {
        const indIncrease = pairs[i].indVal > pairs[i - 1].indVal
        const depIncrease = pairs[i].depVal > pairs[i - 1].depVal
        if (indIncrease && !depIncrease) contradictions++
      }
      if (contradictions > 0 && contradictions >= pairs.length / 2) {
        issues.push({
          type: 'contradiction',
          description: `Increasing ${indVar.name} does not consistently improve ${depVar.name} — ${contradictions} contradictory transitions found`,
          severity: Math.min(contradictions / pairs.length + 0.2, 1),
          evidence: `variable=${indVar.name}, dependent=${depVar.name}, transitions=${pairs.length}, contradictions=${contradictions}`
        })
      }
    }
  }
  return issues
}

// ============ Missing data detection ============

function detectMissingData(
  plan: ExperimentPlan,
  observations: ExperimentObservation[]
): OptimizationIssue[] {
  const issues: OptimizationIssue[] = []
  const plannedMetrics = plan.measurements.map(m => m.name)
  for (const obs of observations) {
    const observedMetrics = new Set(obs.metrics.map(m => m.name))
    const missing = plannedMetrics.filter(m => !observedMetrics.has(m))
    if (missing.length > 0) {
      issues.push({
        type: 'missing-data',
        description: `Observation ${obs.observationId} is missing metrics: ${missing.join(', ')}`,
        severity: Math.min(missing.length / plannedMetrics.length, 1),
        evidence: `observation=${obs.observationId}, missing=${missing.join(',')}, planned=${plannedMetrics.length}`
      })
    }
  }
  return issues
}

// ============ Unexpected trend detection ============

function detectUnexpectedTrends(
  observations: ExperimentObservation[]
): OptimizationIssue[] {
  const issues: OptimizationIssue[] = []
  // Check if metrics show high variance (weak/unclear signal)
  const metricGroups = new Map<string, number[]>()
  for (const obs of observations) {
    for (const m of obs.metrics) {
      const existing = metricGroups.get(m.name) ?? []
      existing.push(m.value)
      metricGroups.set(m.name, existing)
    }
  }

  for (const [metricName, values] of metricGroups) {
    if (values.length < 3) continue
    const mean = values.reduce((s, v) => s + v, 0) / values.length
    if (mean === 0) continue
    const cv = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length) / Math.abs(mean)
    if (cv > 0.3) {
      issues.push({
        type: 'unexpected-trend',
        description: `Metric ${metricName} shows high variability (CV=${(cv * 100).toFixed(1)}%) — trend may be unreliable`,
        severity: Math.min(cv, 1),
        evidence: `metric=${metricName}, cv=${cv.toFixed(3)}, n=${values.length}, mean=${mean.toFixed(2)}`
      })
    }
  }
  return issues
}

// ============ Public API ============

/**
 * Phase 8-H1: analyze experiment observations for anomalies.
 * Detects outliers, contradictions, missing data, and unexpected trends.
 * Deterministic — statistical heuristics, no LLM.
 */
export function analyzeExperiment(
  plan: ExperimentPlan,
  observations: ExperimentObservation[]
): OptimizationIssue[] {
  const issues: OptimizationIssue[] = [
    ...detectOutliers(observations),
    ...detectContradictions(plan, observations),
    ...detectMissingData(plan, observations),
    ...detectUnexpectedTrends(observations)
  ]
  return issues
}

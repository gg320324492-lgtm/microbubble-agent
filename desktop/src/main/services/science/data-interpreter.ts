// Scientific Interpretation (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: deterministic interpretation of analysis results into
// scientific conclusions. Uses statistical significance and model quality
// heuristics — no hallucinated values.

import type {
  AnalysisReport,
  ScientificConclusion
} from '../../../shared/science/scientific-data-schema'

// ============ Interpretation rules ============

function interpretQuality(report: AnalysisReport): ScientificConclusion[] {
  const conclusions: ScientificConclusion[] = []
  const q = report.quality

  if (q.completeness >= 0.95) {
    conclusions.push({
      observation: 'Dataset has high completeness',
      interpretation: 'Data quality is sufficient for reliable analysis',
      confidence: 0.9
    })
  } else if (q.completeness < 0.8) {
    conclusions.push({
      observation: `Dataset completeness is ${(q.completeness * 100).toFixed(1)}%`,
      interpretation: 'Significant missing data may affect analysis reliability — consider imputation or data collection',
      confidence: 0.85
    })
  }

  if (q.warnings.length > 5) {
    conclusions.push({
      observation: `${q.warnings.length} quality warnings detected`,
      interpretation: 'Multiple data quality issues suggest careful review before drawing conclusions',
      confidence: 0.7
    })
  }

  return conclusions
}

function interpretStatistics(report: AnalysisReport): ScientificConclusion[] {
  const conclusions: ScientificConclusion[] = []
  const corrs = report.statistics.filter(s => s.metric.startsWith('correlation_'))

  for (const corr of corrs) {
    const absR = Math.abs(corr.value)
    if (absR > 0.7) {
      const parts = corr.metric.replace('correlation_', '').split('_')
      const direction = corr.value > 0 ? 'positive' : 'negative'
      conclusions.push({
        observation: `Strong ${direction} correlation (${corr.value.toFixed(3)}) detected between variables`,
        interpretation: `${parts[0]} and ${parts[1]} are strongly ${direction}ly related — investigate causal mechanism`,
        confidence: Math.min(0.6 + absR * 0.3, 0.95)
      })
    }
  }

  // Check for high variability
  const cvs = report.statistics.filter(s => s.metric.endsWith('_cv'))
  for (const cvStat of cvs) {
    if (cvStat.value > 0.3) {
      const varName = cvStat.metric.replace('_cv', '')
      conclusions.push({
        observation: `${varName} has high variability (CV=${(cvStat.value * 100).toFixed(1)}%)`,
        interpretation: `High coefficient of variation in ${varName} suggests process instability or measurement noise`,
        confidence: 0.75
      })
    }
  }

  return conclusions
}

function interpretModels(report: AnalysisReport): ScientificConclusion[] {
  const conclusions: ScientificConclusion[] = []

  if (report.models.length > 0) {
    const best = report.models[0]
    if (best.rSquared > 0.9) {
      conclusions.push({
        observation: `Best model "${best.model}" fits data well (R²=${best.rSquared.toFixed(3)})`,
        interpretation: `The ${best.model} model accurately describes the data relationship with low residual error`,
        confidence: Math.min(0.7 + best.rSquared * 0.2, 0.95)
      })
    } else if (best.rSquared < 0.5) {
      conclusions.push({
        observation: `Best model "${best.model}" has poor fit (R²=${best.rSquared.toFixed(3)})`,
        interpretation: 'No tested model adequately describes the data — consider alternative models or underlying complexity',
        confidence: 0.8
      })
    }
  }

  // Compare kinetic models
  const kinetics = report.models.filter(m => ['zero-order', 'first-order', 'second-order'].includes(m.model))
  if (kinetics.length >= 2) {
    const bestKinetic = kinetics[0]
    conclusions.push({
      observation: `${bestKinetic.model} kinetics best describe the data (R²=${bestKinetic.rSquared.toFixed(3)})`,
      interpretation: `The reaction or process follows ${bestKinetic.model} kinetics, suggesting ${bestKinetic.model === 'first-order' ? 'concentration-dependent' : bestKinetic.model === 'zero-order' ? 'concentration-independent' : 'bimolecular'} rate behavior`,
      confidence: 0.75
    })
  }

  return conclusions
}

// ============ Public API ============

/**
 * Phase 8-H2: generate scientific conclusions from an analysis report.
 * Deterministic — rule-based interpretation, no hallucinated values.
 */
export function interpretAnalysis(report: AnalysisReport): ScientificConclusion[] {
  return [
    ...interpretQuality(report),
    ...interpretStatistics(report),
    ...interpretModels(report)
  ]
}

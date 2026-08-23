// Visualization Planner (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: deterministic recommendation of figures based on dataset
// structure and variable types. No LLM.

import type {
  ScientificDataset,
  FigureRecommendation,
  ModelFitResult
} from '../../../shared/science/scientific-data-schema'

// ============ Figure selection logic ============

function selectTimeSeriesFigures(dataset: ScientificDataset): FigureRecommendation[] {
  const figures: FigureRecommendation[] = []
  const dateVars = dataset.variables.filter((v: { type: string }) => v.type === 'date')
  const numVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  if (dateVars.length > 0 && numVars.length > 0) {
    for (const nv of numVars.slice(0, 3)) {
      figures.push({
        type: 'line',
        title: `${nv.name} over time`,
        xVariable: dateVars[0].name,
        yVariable: nv.name,
        reason: `Time-series line chart for ${nv.name} evolution`
      })
    }
  }
  return figures
}

function selectDistributionFigures(dataset: ScientificDataset): FigureRecommendation[] {
  const figures: FigureRecommendation[] = []
  const numVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  for (const v of numVars.slice(0, 2)) {
    figures.push({
      type: 'histogram',
      title: `Distribution of ${v.name}`,
      xVariable: v.name,
      yVariable: 'frequency',
      reason: `Histogram showing ${v.name} distribution shape`
    })
  }
  return figures
}

function selectComparisonFigures(dataset: ScientificDataset): FigureRecommendation[] {
  const figures: FigureRecommendation[] = []
  const stringVars = dataset.variables.filter((v: { type: string }) => v.type === 'string')
  const numVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  if (stringVars.length > 0 && numVars.length > 0) {
    for (const nv of numVars.slice(0, 2)) {
      figures.push({
        type: 'bar',
        title: `${nv.name} by ${stringVars[0].name}`,
        xVariable: stringVars[0].name,
        yVariable: nv.name,
        reason: `Bar chart comparing ${nv.name} across ${stringVars[0].name} categories`
      })
    }
  }
  return figures
}

function selectCorrelationFigures(dataset: ScientificDataset): FigureRecommendation[] {
  const figures: FigureRecommendation[] = []
  const numVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  if (numVars.length >= 2) {
    figures.push({
      type: 'scatter',
      title: `${numVars[0].name} vs ${numVars[1].name}`,
      xVariable: numVars[0].name,
      yVariable: numVars[1].name,
      reason: `Scatter plot showing relationship between ${numVars[0].name} and ${numVars[1].name}`
    })
  }
  return figures
}

function selectModelFigures(
  dataset: ScientificDataset,
  models: ModelFitResult[]
): FigureRecommendation[] {
  const figures: FigureRecommendation[] = []
  const numVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  if (numVars.length >= 2 && models.length > 0) {
    const best = models[0]
    figures.push({
      type: 'scatter+fit',
      title: `Data with ${best.model} fit (R²=${best.rSquared.toFixed(3)})`,
      xVariable: numVars[0].name,
      yVariable: numVars[1].name,
      reason: `Scatter with ${best.model} model fitting curve`
    })
  }
  return figures
}

// ============ Public API ============

/**
 * Phase 8-H2: recommend visualizations for a dataset based on variable types.
 * Deterministic — no LLM.
 */
export function planVisualizations(
  dataset: ScientificDataset,
  models: ModelFitResult[] = []
): FigureRecommendation[] {
  const figures: FigureRecommendation[] = [
    ...selectTimeSeriesFigures(dataset),
    ...selectDistributionFigures(dataset),
    ...selectComparisonFigures(dataset),
    ...selectCorrelationFigures(dataset),
    ...selectModelFigures(dataset, models)
  ]

  // Deduplicate by type + xVariable + yVariable
  const seen = new Set<string>()
  return figures.filter(f => {
    const key = `${f.type}:${f.xVariable}:${f.yVariable}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

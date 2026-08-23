// Figure Caption Generator (Phase 8-H3: Scientific Paper Generation Agent).
//
// Phase 8-H3: deterministic generation of figure captions from visualization
// recommendations and analysis reports. No invented values — captions describe
// what the figure shows. No LLM.

import type { FigureCaption } from '../../../shared/science/manuscript-schema'
import type { FigureRecommendation } from '../../../shared/science/scientific-data-schema'
import type { AnalysisReport } from '../../../shared/science/scientific-data-schema'

// ============ Caption templates ============

function generateCaption(
  fig: FigureRecommendation,
  report: AnalysisReport,
  index: number
): FigureCaption {
  const figId = `fig-${index + 1}`
  let caption = ''

  switch (fig.type) {
    case 'line':
      caption = `${fig.title}. Temporal evolution of ${fig.yVariable} as a function of ${fig.xVariable}.`
      break
    case 'histogram':
      caption = `Distribution of ${fig.xVariable}. Frequency histogram showing the spread of measured values.`
      break
    case 'bar':
      caption = `${fig.title}. Comparison of ${fig.yVariable} across different ${fig.xVariable} categories.`
      break
    case 'scatter':
      caption = `Relationship between ${fig.xVariable} and ${fig.yVariable}. Scatter plot showing the correlation between variables.`
      break
    case 'scatter+fit': {
      const bestModel = report.models[0]
      if (bestModel) {
        caption = `${fig.title}. Scatter plot of ${fig.xVariable} versus ${fig.yVariable} with ${bestModel.model} model fit (R²=${bestModel.rSquared.toFixed(3)}).`
      } else {
        caption = `${fig.title}. Scatter plot of ${fig.xVariable} versus ${fig.yVariable} with model fitting curve.`
      }
      break
    }
    default:
      caption = `${fig.title}. Visualization of ${fig.xVariable} versus ${fig.yVariable}.`
  }

  const description = `${fig.type} chart showing ${fig.reason}`

  return { figureId: figId, caption, description }
}

// ============ Public API ============

/**
 * Phase 8-H3: generate figure captions from recommendations and analysis.
 * Deterministic — template-based, no invented values.
 */
export function generateFigureCaptions(
  figures: FigureRecommendation[],
  report: AnalysisReport
): FigureCaption[] {
  return figures.map((fig, i) => generateCaption(fig, report, i))
}

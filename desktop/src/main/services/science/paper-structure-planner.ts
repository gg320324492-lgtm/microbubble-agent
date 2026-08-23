// Paper Structure Planner (Phase 8-H3: Scientific Paper Generation Agent).
//
// Phase 8-H3: deterministic generation of a ManuscriptOutline from research
// design results and analysis reports. No writing — just structure. No LLM.

import type { SectionType, ManuscriptOutline } from '../../../shared/science/manuscript-schema'
import type { ResearchDesignResult } from '../../../shared/science/research-design-schema'
import type { AnalysisReport } from '../../../shared/science/scientific-data-schema'

// ============ Section templates ============

function buildIntroductionKeyPoints(design: ResearchDesignResult): string[] {
  const points: string[] = []
  points.push(`Research problem: ${design.problemAnalysis.keyScientificQuestion}`)
  if (design.problemAnalysis.possibleMechanisms.length > 0) {
    points.push(`Known mechanisms: ${design.problemAnalysis.possibleMechanisms.join(', ')}`)
  }
  if (design.problemAnalysis.requiredEvidence.length > 0) {
    points.push(`Required evidence: ${design.problemAnalysis.requiredEvidence.join(', ')}`)
  }
  points.push(`Objective: ${design.problemAnalysis.recommendedApproach}`)
  return points
}

function buildMethodsKeyPoints(design: ResearchDesignResult): string[] {
  const points: string[] = []
  const vars = design.experimentPlan.variables
  const independent = vars.filter((v: { type: string; name: string; range: string; unit: string }) => v.type === 'independent')
  const dependent = vars.filter((v: { type: string }) => v.type === 'dependent')

  if (independent.length > 0) {
    points.push(`Independent variables: ${independent.map((v: { name: string; range: string; unit: string }) => `${v.name} (${v.range} ${v.unit})`).join(', ')}`)
  }
  if (dependent.length > 0) {
    points.push(`Dependent variables: ${dependent.map((v: { name: string }) => v.name).join(', ')}`)
  }
  points.push(`Experimental groups: ${design.experimentPlan.groups.length}`)
  points.push(`Measurements: ${design.experimentPlan.measurements.map((m: { name: string }) => m.name).join(', ')}`)
  if (design.modelSelection.model) {
    points.push(`Analysis model: ${design.modelSelection.model}`)
  }
  return points
}

function buildResultsKeyPoints(report: AnalysisReport): string[] {
  const points: string[] = []
  if (report.statistics.length > 0) {
    const keyStats = report.statistics.filter((s: { metric: string }) => s.metric.includes('_mean') || s.metric.startsWith('correlation_'))
    points.push(`Key statistics: ${keyStats.length} metrics computed`)
  }
  if (report.models.length > 0) {
    const best = report.models[0]
    points.push(`Best model: ${best.model} (R²=${best.rSquared.toFixed(3)})`)
  }
  if (report.conclusions.length > 0) {
    points.push(`Key findings: ${report.conclusions.length} conclusions drawn`)
  }
  return points
}

function buildDiscussionKeyPoints(report: AnalysisReport): string[] {
  const points: string[] = []
  if (report.models.length > 0) {
    points.push(`Model interpretation: ${report.models[0].model} with R²=${report.models[0].rSquared.toFixed(3)}`)
  }
  const strongCorrs = report.statistics.filter((s: { metric: string; value: number }) => s.metric.startsWith('correlation_') && Math.abs(s.value) > 0.7)
  if (strongCorrs.length > 0) {
    points.push(`Strong correlations identified: ${strongCorrs.length}`)
  }
  points.push('Compare with existing literature')
  points.push('Discuss limitations and future directions')
  return points
}

function buildConclusionKeyPoints(design: ResearchDesignResult, report: AnalysisReport): string[] {
  const points: string[] = []
  points.push(`Research question addressed: ${design.problemAnalysis.keyScientificQuestion}`)
  if (report.models.length > 0) {
    points.push(`Best model: ${report.models[0].model} (R²=${report.models[0].rSquared.toFixed(3)})`)
  }
  if (report.conclusions.length > 0) {
    points.push(`Key finding: ${report.conclusions[0].observation}`)
  }
  points.push(`Implications: ${design.problemAnalysis.recommendedApproach}`)
  return points
}

// ============ Public API ============

/**
 * Phase 8-H3: generate a manuscript outline from research data.
 * Deterministic — template-based structure, no LLM.
 */
export function planStructure(
  design: ResearchDesignResult,
  report: AnalysisReport
): ManuscriptOutline {
  const sections: ManuscriptOutline['sections'] = [
    { sectionType: 'introduction' as SectionType, title: 'Introduction', keyPoints: buildIntroductionKeyPoints(design) },
    { sectionType: 'methods' as SectionType, title: 'Materials and Methods', keyPoints: buildMethodsKeyPoints(design) },
    { sectionType: 'results' as SectionType, title: 'Results and Discussion', keyPoints: buildResultsKeyPoints(report) },
    { sectionType: 'discussion' as SectionType, title: 'Discussion', keyPoints: buildDiscussionKeyPoints(report) },
    { sectionType: 'conclusion' as SectionType, title: 'Conclusions', keyPoints: buildConclusionKeyPoints(design, report) }
  ]

  return {
    title: design.problemAnalysis.keyScientificQuestion,
    sections,
    figureCount: report.figures.length,
    referenceCount: report.statistics.length + report.models.length
  }
}

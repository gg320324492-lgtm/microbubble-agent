// Optimization Advisor (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: deterministic generation of optimization suggestions from
// detected issues and variable importance. Uses rule-based reasoning — no LLM.

import type {
  OptimizationIssue,
  VariableImportance,
  OptimizationSuggestion
} from '../../../shared/science/experiment-optimization-schema'

// ============ Suggestion rules ============

interface SuggestionRule {
  issueType: string
  keywords: readonly string[]
  suggestion: string
  reason: string
  expectedEffect: string
  confidence: number
}

const SUGGESTION_RULES: readonly SuggestionRule[] = [
  // Outlier rules
  { issueType: 'outlier', keywords: ['removal', 'efficiency'],
    suggestion: 'Repeat measurement at the outlier condition to verify reproducibility',
    reason: 'Outliers may indicate measurement error or genuine process variability',
    expectedEffect: 'Improved data reliability and confidence in trend analysis',
    confidence: 0.75 },
  { issueType: 'outlier', keywords: ['concentration', 'dosage'],
    suggestion: 'Check calibration of analytical instruments and sampling procedure',
    reason: 'Concentration measurements are sensitive to instrument calibration drift',
    expectedEffect: 'Reduced measurement uncertainty',
    confidence: 0.70 },

  // Contradiction rules
  { issueType: 'contradiction', keywords: ['ozone', 'o3', 'dosage'],
    suggestion: 'Investigate ozone mass transfer limitation at higher dosages',
    reason: 'Higher gas dosage may not translate to higher dissolved ozone if mass transfer is saturated',
    expectedEffect: 'Identify mass transfer bottleneck and optimize gas-liquid contact',
    confidence: 0.80 },
  { issueType: 'contradiction', keywords: ['pressure', 'bubble'],
    suggestion: 'Optimize pressure to balance bubble size reduction with gas throughput',
    reason: 'Higher pressure produces smaller bubbles but may reduce gas flow rate',
    expectedEffect: 'Optimal bubble size distribution for maximum interfacial area',
    confidence: 0.75 },
  { issueType: 'contradiction', keywords: ['temperature', 'rate'],
    suggestion: 'Consider competing effects of temperature on reaction rate and gas solubility',
    reason: 'Temperature increases reaction kinetics but decreases gas溶解度 (Henry constant)',
    expectedEffect: 'Optimal temperature balancing kinetics and solubility',
    confidence: 0.70 },

  // Missing data rules
  { issueType: 'missing-data', keywords: [],
    suggestion: 'Complete all planned measurements in subsequent experiments',
    reason: 'Missing data reduces statistical power and may mask important trends',
    expectedEffect: 'Improved analysis completeness and trend detection',
    confidence: 0.85 },

  // Unexpected trend rules
  { issueType: 'unexpected-trend', keywords: ['variability', 'cv'],
    suggestion: 'Increase number of replicates at key conditions to reduce noise',
    reason: 'High coefficient of variation indicates process variability or measurement noise',
    expectedEffect: 'Improved signal-to-noise ratio and trend reliability',
    confidence: 0.72 },
  { issueType: 'unexpected-trend', keywords: ['size', 'diameter'],
    suggestion: 'Tighten control of bubble generation parameters (pressure, orifice size)',
    reason: 'Bubble size variability directly impacts mass transfer consistency',
    expectedEffect: 'More uniform bubble population and consistent mass transfer',
    confidence: 0.68 },

  // Weak signal rules
  { issueType: 'weak-signal', keywords: [],
    suggestion: 'Expand the variable range to amplify the signal-to-noise ratio',
    reason: 'Weak signals may indicate the variable range is too narrow to detect meaningful effects',
    expectedEffect: 'Stronger, more detectable trends in subsequent experiments',
    confidence: 0.65 }
]

// ============ Logic ============

function matchRules(issue: OptimizationIssue): SuggestionRule[] {
  const text = (issue.description + ' ' + issue.evidence).toLowerCase()
  return SUGGESTION_RULES.filter(rule => {
    if (rule.issueType !== issue.type) return false
    if (rule.keywords.length === 0) return true // default rule for this type
    return rule.keywords.some(kw => text.includes(kw))
  })
}

function generateFromImportance(
  importantVars: VariableImportance[]
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = []
  const topVars = importantVars.filter(v => v.importance > 0.3).slice(0, 2)

  for (const v of topVars) {
    suggestions.push({
      suggestion: `Focus optimization efforts on ${v.variable} — highest impact variable`,
      reason: v.contribution,
      expectedEffect: `Optimizing ${v.variable} should produce the largest improvement in performance`,
      confidence: v.confidence
    })
  }
  return suggestions
}

// ============ Public API ============

/**
 * Phase 8-H1: generate optimization suggestions from issues and variable importance.
 * Deterministic — rule-based, no LLM.
 */
export function generateSuggestions(
  issues: OptimizationIssue[],
  importantVariables: VariableImportance[]
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = []

  // Generate from issues
  for (const issue of issues) {
    const rules = matchRules(issue)
    for (const rule of rules) {
      suggestions.push({
        suggestion: rule.suggestion,
        reason: rule.reason,
        expectedEffect: rule.expectedEffect,
        confidence: rule.confidence
      })
    }
  }

  // Generate from variable importance
  suggestions.push(...generateFromImportance(importantVariables))

  // Deduplicate by suggestion text
  const seen = new Set<string>()
  return suggestions.filter(s => {
    if (seen.has(s.suggestion)) return false
    seen.add(s.suggestion)
    return true
  })
}

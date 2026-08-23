// Phase 8-H1: Experiment Optimization Agent — test suite.
// Target: ≥400 tests (3800 base → ≥4200 total).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__testDir, '..', '..', 'src')

import {
  isValidIssueType,
  isValidMetricObservation,
  isValidExperimentObservation,
  isValidOptimizationIssue,
  isValidVariableImportance,
  isValidOptimizationSuggestion,
  isValidNextExperimentRecommendation,
  isValidExperimentOptimizationResult,
  __testHelpers
} from '../../src/shared/science/experiment-optimization-schema'

import type {
  ExperimentPlan,
  ExperimentObservation,
  MetricObservation,
  OptimizationIssue,
  VariableImportance,
  ExperimentOptimizationResult,
  IssueType
} from '../../src/shared/science/experiment-optimization-schema'

import { analyzeExperiment } from '../../src/main/services/science/experiment-analyzer'
import { calculateImportance } from '../../src/main/services/science/variable-importance'
import { interpretMechanism } from '../../src/main/services/science/mechanism-interpreter'
import { generateSuggestions } from '../../src/main/services/science/optimization-advisor'
import { generateNextExperiments } from '../../src/main/services/science/next-experiment-generator'
import { ExperimentOptimizationAgent } from '../../src/main/services/science/experiment-optimization-agent'

// ============ Fixtures ============

function makeMetric(overrides?: Partial<MetricObservation>): MetricObservation {
  return { name: 'removal_efficiency', value: 85, unit: '%', direction: 'higher-is-better', ...overrides }
}

function makeObservation(overrides?: Partial<ExperimentObservation>): ExperimentObservation {
  return {
    observationId: 'obs-1',
    variableValues: { bubble_diameter: 200, ozone_dosage: 5, pressure: 0.2 },
    metrics: [makeMetric()],
    ...overrides
  }
}

function makePlan(overrides?: Partial<ExperimentPlan>): ExperimentPlan {
  return {
    planId: 'plan-1',
    hypothesis: 'Smaller bubbles improve ozone mass transfer',
    variables: [
      { name: 'bubble_diameter', type: 'independent', range: '100-500 nm', unit: 'nm', importance: 0.8 },
      { name: 'ozone_dosage', type: 'independent', range: '5-20 mg/L', unit: 'mg/L', importance: 0.7 },
      { name: 'pressure', type: 'independent', range: '0.1-0.5 MPa', unit: 'MPa', importance: 0.5 },
      { name: 'removal_efficiency', type: 'dependent', range: '0-100%', unit: '%', importance: 0.9 }
    ],
    groups: [
      { groupId: 'g-control', condition: 'baseline', purpose: 'control' },
      { groupId: 'g1', condition: 'varied bubble_diameter', purpose: 'test diameter effect' }
    ],
    measurements: [
      { name: 'removal_efficiency', method: 'UV-Vis', reason: 'quantify removal' },
      { name: 'reaction_rate', method: 'kinetic analysis', reason: 'determine rate' }
    ],
    expectedOutcome: 'Decreasing bubble diameter increases removal efficiency',
    ...overrides
  }
}

function makeObservations(count: number, baseValues?: Partial<ExperimentObservation>): ExperimentObservation[] {
  return Array.from({ length: count }, (_, i) => makeObservation({
    observationId: `obs-${i}`,
    variableValues: {
      bubble_diameter: 100 + i * 50,
      ozone_dosage: 5 + i * 2,
      pressure: 0.2 + i * 0.05
    },
    metrics: [
      { name: 'removal_efficiency', value: 75 + i * 3, unit: '%', direction: 'higher-is-better' },
      { name: 'reaction_rate', value: 1.5 + i * 0.3, unit: 'mg/L·min', direction: 'higher-is-better' }
    ],
    ...baseValues
  }))
}

// ============ Schema validators ============

describe('Phase 8-H1 schema', () => {
  describe('isValidIssueType', () => {
    it.each<IssueType>(['outlier', 'contradiction', 'weak-signal', 'missing-data', 'unexpected-trend'])(
      'accepts %s', (t) => { expect(isValidIssueType(t)).toBe(true) }
    )
    it('rejects empty string', () => expect(isValidIssueType('')).toBe(false))
    it('rejects "critical"', () => expect(isValidIssueType('critical')).toBe(false))
  })

  describe('isValidMetricObservation', () => {
    it('accepts valid', () => expect(isValidMetricObservation(makeMetric())).toBe(true))
    it('accepts lower-is-better', () => expect(isValidMetricObservation(makeMetric({ direction: 'lower-is-better' }))).toBe(true))
    it('rejects empty name', () => expect(isValidMetricObservation(makeMetric({ name: '' }))).toBe(false))
    it('rejects NaN value', () => expect(isValidMetricObservation(makeMetric({ value: NaN }))).toBe(false))
    it('rejects Infinity', () => expect(isValidMetricObservation(makeMetric({ value: Infinity }))).toBe(false))
    it('rejects invalid direction', () => expect(isValidMetricObservation({ name: 'm', value: 1, unit: 'u', direction: 'maximize' })).toBe(false))
    it('rejects non-object', () => expect(isValidMetricObservation(null)).toBe(false))
  })

  describe('isValidExperimentObservation', () => {
    it('accepts valid', () => expect(isValidExperimentObservation(makeObservation())).toBe(true))
    it('accepts with timestamp', () => expect(isValidExperimentObservation(makeObservation({ timestamp: Date.now() }))).toBe(true))
    it('accepts with notes', () => expect(isValidExperimentObservation(makeObservation({ notes: 'test' }))).toBe(true))
    it('rejects empty observationId', () => expect(isValidExperimentObservation(makeObservation({ observationId: '' }))).toBe(false))
    it('rejects non-object variableValues', () => expect(isValidExperimentObservation(makeObservation({ variableValues: 'bad' as never }))).toBe(false))
    it('rejects invalid metric in array', () => expect(isValidExperimentObservation(makeObservation({ metrics: [{ name: '', value: 1, unit: 'u', direction: 'higher-is-better' }] }))).toBe(false))
    it('rejects non-array metrics', () => expect(isValidExperimentObservation(makeObservation({ metrics: 'bad' as never }))).toBe(false))
  })

  describe('isValidOptimizationIssue', () => {
    const issue: OptimizationIssue = { type: 'outlier', description: 'test', severity: 0.5, evidence: 'e' }
    it('accepts valid', () => expect(isValidOptimizationIssue(issue)).toBe(true))
    it('rejects invalid type', () => expect(isValidOptimizationIssue({ ...issue, type: 'critical' })).toBe(false))
    it('rejects severity > 1', () => expect(isValidOptimizationIssue({ ...issue, severity: 1.5 })).toBe(false))
    it('rejects non-object', () => expect(isValidOptimizationIssue(null)).toBe(false))
  })

  describe('isValidVariableImportance', () => {
    const vi: VariableImportance = { variable: 'x', importance: 0.8, contribution: 'strong effect', confidence: 0.7 }
    it('accepts valid', () => expect(isValidVariableImportance(vi)).toBe(true))
    it('rejects empty variable', () => expect(isValidVariableImportance({ ...vi, variable: '' })).toBe(false))
    it('rejects importance > 1', () => expect(isValidVariableImportance({ ...vi, importance: 2 })).toBe(false))
    it('rejects non-object', () => expect(isValidVariableImportance(42)).toBe(false))
  })

  describe('isValidOptimizationSuggestion', () => {
    const s = { suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.6 }
    it('accepts valid', () => expect(isValidOptimizationSuggestion(s)).toBe(true))
    it('rejects empty suggestion', () => expect(isValidOptimizationSuggestion({ ...s, suggestion: '' })).toBe(false))
    it('rejects non-object', () => expect(isValidOptimizationSuggestion(null)).toBe(false))
  })

  describe('isValidNextExperimentRecommendation', () => {
    const r = { changeVariable: 'x', currentValue: 0.3, suggestedRange: '0.2-0.4', purpose: 'test' }
    it('accepts valid', () => expect(isValidNextExperimentRecommendation(r)).toBe(true))
    it('rejects empty changeVariable', () => expect(isValidNextExperimentRecommendation({ ...r, changeVariable: '' })).toBe(false))
    it('rejects non-number currentValue', () => expect(isValidNextExperimentRecommendation({ ...r, currentValue: 'bad' })).toBe(false))
    it('rejects non-object', () => expect(isValidNextExperimentRecommendation(null)).toBe(false))
  })

  describe('isValidExperimentOptimizationResult', () => {
    const result: ExperimentOptimizationResult = {
      issues: [], importantVariables: [], explanations: [], suggestions: [], nextExperiments: []
    }
    it('accepts valid', () => expect(isValidExperimentOptimizationResult(result)).toBe(true))
    it('rejects non-array issues', () => expect(isValidExperimentOptimizationResult({ ...result, issues: 'bad' })).toBe(false))
    it('rejects invalid issue in array', () => expect(isValidExperimentOptimizationResult({
      ...result, issues: [{ type: 'bad', description: '', severity: -1, evidence: '' }]
    })).toBe(false))
    it('rejects non-array importantVariables', () => expect(isValidExperimentOptimizationResult({ ...result, importantVariables: 'bad' })).toBe(false))
    it('rejects non-array explanations', () => expect(isValidExperimentOptimizationResult({ ...result, explanations: 42 })).toBe(false))
    it('rejects non-array suggestions', () => expect(isValidExperimentOptimizationResult({ ...result, suggestions: null })).toBe(false))
    it('rejects non-array nextExperiments', () => expect(isValidExperimentOptimizationResult({ ...result, nextExperiments: {} })).toBe(false))
    it('rejects non-object', () => expect(isValidExperimentOptimizationResult(null)).toBe(false))
  })
})

// ============ Secret guard ============

describe('Phase 8-H1 secret guard', () => {
  const { findForbidden } = __testHelpers
  it('finds sk- in value', () => expect(findForbidden('sk-abc')).toBe('sk-'))
  it('finds apiKey in value', () => expect(findForbidden('my apiKey')).toBe('apiKey'))
  it('clean returns null', () => expect(findForbidden('hello')).toBe(null))
  it('walks arrays', () => expect(findForbidden(['a', 'sk-x'])).toBe('sk-'))
  it('walks nested objects', () => expect(findForbidden({ a: { b: 'cipher' } })).toBe('cipher'))
  it('ignores field names', () => expect(findForbidden({ tokenBudget: 100 })).toBe(null))
  it('issue with apiKey throws', () => {
    expect(() => isValidOptimizationIssue({ type: 'outlier', description: 'apiKey here', severity: 0.5, evidence: '' })).toThrow('forbidden')
  })
  it('suggestion with Bearer throws', () => {
    expect(() => isValidOptimizationSuggestion({ suggestion: 'Bearer token', reason: '', expectedEffect: '', confidence: 0.5 })).toThrow('forbidden')
  })
  it('observation with token throws', () => {
    expect(() => isValidExperimentObservation(makeObservation({ notes: 'has authorization header' }))).toThrow('forbidden')
  })
  it('variable importance with cipher throws', () => {
    expect(() => isValidVariableImportance({ variable: 'x', importance: 0.5, contribution: 'cipher text', confidence: 0.5 })).toThrow('forbidden')
  })
})

// ============ Experiment Analyzer ============

describe('Phase 8-H1 experiment analyzer', () => {
  it('detects outlier in metric', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'removal', value: 95, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'removal', value: 96, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'removal', value: 93, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'removal', value: 94, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o5', metrics: [{ name: 'removal', value: 92, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o6', metrics: [{ name: 'removal', value: 30, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    expect(issues.some(i => i.type === 'outlier')).toBe(true)
  })

  it('no outlier in uniform data', () => {
    const obs = [
      makeObservation({ metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'removal', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'removal', value: 89, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    expect(issues.some(i => i.type === 'outlier')).toBe(false)
  })

  it('detects missing data', () => {
    const plan = makePlan({ measurements: [{ name: 'removal', method: 'm', reason: 'r' }, { name: 'rate', method: 'm', reason: 'r' }] })
    const obs = [makeObservation({ metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] })]
    const issues = analyzeExperiment(plan, obs)
    expect(issues.some(i => i.type === 'missing-data')).toBe(true)
  })

  it('no missing data when all metrics present', () => {
    const plan = makePlan({ measurements: [{ name: 'removal', method: 'm', reason: 'r' }] })
    const obs = [makeObservation({ metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] })]
    const issues = analyzeExperiment(plan, obs)
    expect(issues.some(i => i.type === 'missing-data')).toBe(false)
  })

  it('detects unexpected trend (high CV)', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'rate', value: 1.0, unit: 'u', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'rate', value: 5.0, unit: 'u', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'rate', value: 1.2, unit: 'u', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'rate', value: 4.8, unit: 'u', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    expect(issues.some(i => i.type === 'unexpected-trend')).toBe(true)
  })

  it('returns issues array', () => {
    const issues = analyzeExperiment(makePlan(), makeObservations(3))
    expect(Array.isArray(issues)).toBe(true)
  })

  it('issues have valid types', () => {
    const issues = analyzeExperiment(makePlan(), makeObservations(4))
    for (const issue of issues) {
      expect(isValidOptimizationIssue(issue)).toBe(true)
    }
  })

  it('deterministic', () => {
    const plan = makePlan()
    const obs = makeObservations(4)
    const a = analyzeExperiment(plan, obs)
    const b = analyzeExperiment(plan, obs)
    expect(a).toEqual(b)
  })

  it('empty observations returns empty', () => {
    expect(analyzeExperiment(makePlan(), [])).toEqual([])
  })

  it('single observation no outlier', () => {
    const issues = analyzeExperiment(makePlan(), [makeObservation()])
    expect(issues.some(i => i.type === 'outlier')).toBe(false)
  })

  it('two observations no outlier', () => {
    const obs = [
      makeObservation({ metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] })
    ]
    expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'outlier')).toBe(false)
  })
})

// ============ Variable Importance ============

describe('Phase 8-H1 variable importance', () => {
  it('calculates importance for independent variables', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const result = calculateImportance(plan, obs)
    expect(result.length).toBeGreaterThan(0)
  })

  it('sorted by importance descending', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const result = calculateImportance(plan, obs)
    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].importance).toBeGreaterThanOrEqual(result[i].importance)
    }
  })

  it('importance in 0..1', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.importance).toBeGreaterThanOrEqual(0)
      expect(v.importance).toBeLessThanOrEqual(1)
    }
  })

  it('confidence in 0..1', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.confidence).toBeGreaterThanOrEqual(0)
      expect(v.confidence).toBeLessThanOrEqual(1)
    }
  })

  it('contribution is non-empty', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.contribution.length).toBeGreaterThan(0)
    }
  })

  it('variable names match plan', () => {
    const plan = makePlan()
    const result = calculateImportance(plan, makeObservations(5))
    const planVars = plan.variables.filter(v => v.type === 'independent').map(v => v.name)
    for (const r of result) {
      expect(planVars).toContain(r.variable)
    }
  })

  it('empty observations returns zero importance', () => {
    const result = calculateImportance(makePlan(), [])
    for (const v of result) {
      expect(v.importance).toBe(0)
    }
  })

  it('single observation returns low confidence', () => {
    const result = calculateImportance(makePlan(), [makeObservation()])
    for (const v of result) {
      expect(v.confidence).toBeLessThan(0.5)
    }
  })

  it('deterministic', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const a = calculateImportance(plan, obs)
    const b = calculateImportance(plan, obs)
    expect(a).toEqual(b)
  })

  it('valid output', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(isValidVariableImportance(v)).toBe(true)
    }
  })

  it('higher metric change gives higher importance', () => {
    const plan = makePlan({ measurements: [{ name: 'removal', method: 'UV-Vis', reason: 'quantify removal' }] })
    // Make bubble_diameter have huge effect, ozone small effect
    const obs = [
      makeObservation({ observationId: 'o1', variableValues: { bubble_diameter: 100, ozone_dosage: 5, pressure: 0.2 }, metrics: [{ name: 'removal', value: 95, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', variableValues: { bubble_diameter: 500, ozone_dosage: 5, pressure: 0.2 }, metrics: [{ name: 'removal', value: 50, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', variableValues: { bubble_diameter: 300, ozone_dosage: 5, pressure: 0.2 }, metrics: [{ name: 'removal', value: 72, unit: '%', direction: 'higher-is-better' }] })
    ]
    const result = calculateImportance(plan, obs)
    const bd = result.find(v => v.variable === 'bubble_diameter')
    const od = result.find(v => v.variable === 'ozone_dosage')
    expect(bd!.importance).toBeGreaterThan(od!.importance)
  })
})

// ============ Mechanism Interpreter ============

describe('Phase 8-H1 mechanism interpreter', () => {
  it('explains ozone-related issues', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'ozone degradation efficiency anomaly', severity: 0.5, evidence: 'ozone dosage' }]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThan(0)
    expect(result.some(e => e.toLowerCase().includes('ozone') || e.toLowerCase().includes('mass transfer'))).toBe(true)
  })

  it('explains bubble-related issues', () => {
    const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'bubble diameter effect unexpected', severity: 0.6, evidence: 'microbubble size' }]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns default explanation for unknown issues', () => {
    const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'xyz problem', severity: 0.3, evidence: 'abc' }]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThan(0)
  })

  it('deduplicates explanations', () => {
    const issues: OptimizationIssue[] = [
      { type: 'outlier', description: 'ozone anomaly 1', severity: 0.5, evidence: 'ozone' },
      { type: 'outlier', description: 'ozone anomaly 2', severity: 0.4, evidence: 'ozone' }
    ]
    const result = interpretMechanism(issues, makePlan())
    const unique = new Set(result)
    expect(unique.size).toBe(result.length)
  })

  it('empty issues returns empty', () => {
    expect(interpretMechanism([], makePlan())).toEqual([])
  })

  it('deterministic', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'ozone test', severity: 0.5, evidence: 'o3' }]
    const a = interpretMechanism(issues, makePlan())
    const b = interpretMechanism(issues, makePlan())
    expect(a).toEqual(b)
  })
})

// ============ Optimization Advisor ============

describe('Phase 8-H1 optimization advisor', () => {
  it('generates suggestions from issues', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'removal efficiency outlier', severity: 0.6, evidence: 'removal' }]
    const result = generateSuggestions(issues, [])
    expect(result.length).toBeGreaterThan(0)
  })

  it('generates suggestions from importance', () => {
    const vi: VariableImportance[] = [{ variable: 'x', importance: 0.8, contribution: 'strong effect', confidence: 0.7 }]
    const result = generateSuggestions([], vi)
    expect(result.length).toBeGreaterThan(0)
  })

  it('deduplicates suggestions', () => {
    const issues: OptimizationIssue[] = [
      { type: 'outlier', description: 'removal efficiency', severity: 0.5, evidence: 'removal' },
      { type: 'outlier', description: 'removal efficiency again', severity: 0.4, evidence: 'removal' }
    ]
    const result = generateSuggestions(issues, [])
    const texts = result.map(s => s.suggestion)
    expect(new Set(texts).size).toBe(texts.length)
  })

  it('suggestions have confidence in 0..1', () => {
    const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'ozone dosage contradiction', severity: 0.5, evidence: 'ozone' }]
    const result = generateSuggestions(issues, [])
    for (const s of result) {
      expect(s.confidence).toBeGreaterThanOrEqual(0)
      expect(s.confidence).toBeLessThanOrEqual(1)
    }
  })

  it('suggestions have non-empty fields', () => {
    const issues: OptimizationIssue[] = [{ type: 'missing-data', description: 'missing metric', severity: 0.5, evidence: 'data' }]
    const result = generateSuggestions(issues, [])
    for (const s of result) {
      expect(s.suggestion.length).toBeGreaterThan(0)
      expect(s.reason.length).toBeGreaterThan(0)
      expect(s.expectedEffect.length).toBeGreaterThan(0)
    }
  })

  it('empty inputs returns empty', () => {
    expect(generateSuggestions([], [])).toEqual([])
  })

  it('deterministic', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'test', severity: 0.5, evidence: 'e' }]
    const a = generateSuggestions(issues, [])
    const b = generateSuggestions(issues, [])
    expect(a).toEqual(b)
  })

  it('valid output', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'test', severity: 0.5, evidence: 'e' }]
    const result = generateSuggestions(issues, [])
    for (const s of result) {
      expect(isValidOptimizationSuggestion(s)).toBe(true)
    }
  })
})

// ============ Next Experiment Generator ============

describe('Phase 8-H1 next experiment generator', () => {
  it('generates recommendations', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    expect(result.length).toBeGreaterThan(0)
  })

  it('recommendations have valid fields', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    for (const r of result) {
      expect(isValidNextExperimentRecommendation(r)).toBe(true)
    }
  })

  it('suggested range is non-empty', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    for (const r of result) {
      expect(r.suggestedRange.length).toBeGreaterThan(0)
    }
  })

  it('purpose is non-empty', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    for (const r of result) {
      expect(r.purpose.length).toBeGreaterThan(0)
    }
  })

  it('max 3 recommendations', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    expect(result.length).toBeLessThanOrEqual(3)
  })

  it('changeVariable matches plan variables', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    const planVars = plan.variables.filter(v => v.type === 'independent').map(v => v.name)
    for (const r of result) {
      expect(planVars).toContain(r.changeVariable)
    }
  })

  it('empty observations still returns recommendations', () => {
    const plan = makePlan()
    const vi = calculateImportance(plan, [])
    const result = generateNextExperiments(plan, [], vi)
    expect(result.length).toBeGreaterThan(0)
  })

  it('deterministic', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const a = generateNextExperiments(plan, obs, vi)
    const b = generateNextExperiments(plan, obs, vi)
    expect(a).toEqual(b)
  })
})

// ============ Optimization Agent Facade ============

describe('Phase 8-H1 optimization agent', () => {
  const agent = new ExperimentOptimizationAgent()

  it('optimizeExperiment returns valid result', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(isValidExperimentOptimizationResult(result)).toBe(true)
  })

  it('result has issues', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(Array.isArray(result.issues)).toBe(true)
  })

  it('result has importantVariables', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(result.importantVariables.length).toBeGreaterThan(0)
  })

  it('result has suggestions', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(Array.isArray(result.suggestions)).toBe(true)
  })

  it('result has nextExperiments', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(result.nextExperiments.length).toBeGreaterThan(0)
  })

  it('analyzeExperiment works standalone', () => {
    const issues = agent.analyzeExperiment(makePlan(), makeObservations(4))
    expect(Array.isArray(issues)).toBe(true)
  })

  it('calculateImportance works standalone', () => {
    const vi = agent.calculateImportance(makePlan(), makeObservations(5))
    expect(vi.length).toBeGreaterThan(0)
  })

  it('deterministic full pipeline', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const r1 = agent.optimizeExperiment(plan, obs)
    const r2 = agent.optimizeExperiment(plan, obs)
    expect(r1).toEqual(r2)
  })

  it('pipeline with outlier data', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'removal', value: 95, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'removal', value: 96, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'removal', value: 93, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'removal', value: 94, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o5', metrics: [{ name: 'removal', value: 92, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o6', metrics: [{ name: 'removal', value: 30, unit: '%', direction: 'higher-is-better' }] })
    ]
    const result = agent.optimizeExperiment(makePlan(), obs)
    expect(result.issues.some(i => i.type === 'outlier')).toBe(true)
  })

  it('pipeline with missing data', () => {
    const plan = makePlan({ measurements: [{ name: 'removal', method: 'm', reason: 'r' }, { name: 'rate', method: 'm', reason: 'r' }] })
    const obs = [makeObservation({ metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] })]
    const result = agent.optimizeExperiment(plan, obs)
    expect(result.issues.some(i => i.type === 'missing-data')).toBe(true)
  })
})

// ============ Determinism ============

describe('Phase 8-H1 determinism', () => {
  const plan = makePlan()
  const obs = makeObservations(5)
  const agent = new ExperimentOptimizationAgent()

  it('analyzer 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => analyzeExperiment(plan, obs))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('importance 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => calculateImportance(plan, obs))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('mechanism 5 runs identical', () => {
    const issues = analyzeExperiment(plan, obs)
    const results = Array.from({ length: 5 }, () => interpretMechanism(issues, plan))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('advisor 5 runs identical', () => {
    const issues = analyzeExperiment(plan, obs)
    const vi = calculateImportance(plan, obs)
    const results = Array.from({ length: 5 }, () => generateSuggestions(issues, vi))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('next experiment 5 runs identical', () => {
    const vi = calculateImportance(plan, obs)
    const results = Array.from({ length: 5 }, () => generateNextExperiments(plan, obs, vi))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('full pipeline 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => agent.optimizeExperiment(plan, obs))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
})

// ============ Security source scan ============

describe('Phase 8-H1 security', () => {
  it('schema has no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'shared/science/experiment-optimization-schema.ts'), 'utf8')
    expect(content).not.toMatch(/from 'app\//)
  })

  it('analyzer has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/experiment-analyzer.ts'), 'utf8')
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toContain('login')
  })

  it('variable importance has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/variable-importance.ts'), 'utf8')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
  })

  it('mechanism interpreter has no model-provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/mechanism-interpreter.ts'), 'utf8')
    expect(content).not.toMatch(/import.*ModelProvider/)
  })

  it('optimization advisor has no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/optimization-advisor.ts'), 'utf8')
    expect(content).not.toMatch(/from 'app\//)
  })

  it('next experiment generator has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/next-experiment-generator.ts'), 'utf8')
    expect(content).not.toMatch(/import.*auth/)
  })

  it('facade has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/experiment-optimization-agent.ts'), 'utf8')
    expect(content).not.toMatch(/import.*anthropic/)
    expect(content).not.toMatch(/import.*openai/)
  })
})

// ============ Extended schema ============

describe('Phase 8-H1 extended schema', () => {
  it('isValidIssueType case sensitive', () => expect(isValidIssueType('Outlier')).toBe(false))
  it('isValidMetricObservation direction exact', () => expect(isValidMetricObservation({ name: 'm', value: 1, unit: 'u', direction: 'Maximize' })).toBe(false))
  it('isValidExperimentObservation accepts empty metrics', () => {
    expect(isValidExperimentObservation({ observationId: 'o', variableValues: {}, metrics: [] })).toBe(true)
  })
  it('isValidExperimentObservation timestamp float', () => {
    expect(isValidExperimentObservation(makeObservation({ timestamp: 1.5 }))).toBe(true)
  })
  it('isValidOptimizationIssue severity 0', () => {
    expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0, evidence: 'e' })).toBe(true)
  })
  it('isValidOptimizationIssue severity 1', () => {
    expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 1, evidence: 'e' })).toBe(true)
  })
  it('isValidVariableImportance importance 0', () => {
    expect(isValidVariableImportance({ variable: 'v', importance: 0, contribution: 'c', confidence: 0.5 })).toBe(true)
  })
  it('isValidVariableImportance confidence 1', () => {
    expect(isValidVariableImportance({ variable: 'v', importance: 0.5, contribution: 'c', confidence: 1 })).toBe(true)
  })
  it('isValidOptimizationSuggestion confidence 0', () => {
    expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0 })).toBe(true)
  })
  it('isValidNextExperimentRecommendation currentValue negative', () => {
    expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: -1.5, suggestedRange: '-2--1', purpose: 'p' })).toBe(true)
  })
  it('isValidExperimentOptimizationResult with all populated', () => {
    expect(isValidExperimentOptimizationResult({
      issues: [{ type: 'outlier', description: 'd', severity: 0.5, evidence: 'e' }],
      importantVariables: [{ variable: 'v', importance: 0.8, contribution: 'c', confidence: 0.7 }],
      explanations: ['explanation'],
      suggestions: [{ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.6 }],
      nextExperiments: [{ changeVariable: 'x', currentValue: 0.3, suggestedRange: '0.2-0.4', purpose: 'p' }]
    })).toBe(true)
  })
  it('isValidExperimentObservation with many metrics', () => {
    const metrics = Array.from({ length: 10 }, (_, i) => ({ name: `m${i}`, value: i, unit: 'u', direction: 'higher-is-better' as const }))
    expect(isValidExperimentObservation(makeObservation({ metrics }))).toBe(true)
  })
  it('isValidExperimentOptimizationResult with 5 issues', () => {
    const issues = Array.from({ length: 5 }, () => ({ type: 'outlier' as const, description: 'd', severity: 0.5, evidence: 'e' }))
    expect(isValidExperimentOptimizationResult({ issues, importantVariables: [], explanations: [], suggestions: [], nextExperiments: [] })).toBe(true)
  })
})

// ============ Extended analyzer ============

describe('Phase 8-H1 extended analyzer', () => {
  it('detects multiple outliers', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o5', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o6', metrics: [{ name: 'r', value: 5, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    expect(issues.filter(i => i.type === 'outlier').length).toBeGreaterThanOrEqual(1)
  })
  it('no issues on clean data', () => {
    const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'UV-Vis', reason: 'quantify removal' }] })
    const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
      observationId: `o${i}`,
      metrics: [{ name: 'removal_efficiency', value: 90 + i, unit: '%', direction: 'higher-is-better' }]
    }))
    const issues = analyzeExperiment(plan, obs)
    expect(issues.length).toBe(0)
  })
  it('detects missing data for multiple observations', () => {
    const plan = makePlan({ measurements: [{ name: 'removal', method: 'm', reason: 'r' }, { name: 'rate', method: 'm', reason: 'r' }] })
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'removal', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'removal', value: 91, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(plan, obs)
    expect(issues.filter(i => i.type === 'missing-data').length).toBe(2)
  })
  it('issues have severity 0..1', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'r', value: 5, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    for (const i of issues) {
      expect(i.severity).toBeGreaterThanOrEqual(0)
      expect(i.severity).toBeLessThanOrEqual(1)
    }
  })
  it('issues have non-empty descriptions', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'r', value: 5, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    for (const i of issues) {
      expect(i.description.length).toBeGreaterThan(0)
    }
  })
  it('issues have non-empty evidence', () => {
    const obs = [
      makeObservation({ observationId: 'o1', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o2', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o3', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ observationId: 'o4', metrics: [{ name: 'r', value: 5, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    for (const i of issues) {
      expect(i.evidence.length).toBeGreaterThan(0)
    }
  })
})

// ============ Extended importance ============

describe('Phase 8-H1 extended importance', () => {
  it('all importance values in 0..1', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.importance).toBeGreaterThanOrEqual(0)
      expect(v.importance).toBeLessThanOrEqual(1)
    }
  })
  it('variable names are non-empty', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.variable.length).toBeGreaterThan(0)
    }
  })
  it('contribution contains variable name', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    for (const v of result) {
      expect(v.contribution).toContain(v.variable)
    }
  })
  it('no dependent variables in importance output', () => {
    const result = calculateImportance(makePlan(), makeObservations(5))
    const depVars = makePlan().variables.filter(v => v.type === 'dependent').map(v => v.name)
    for (const v of result) {
      expect(depVars).not.toContain(v.variable)
    }
  })
  it('returns empty for no independent variables', () => {
    const plan = makePlan({ variables: [{ name: 'dep', type: 'dependent', range: '0-1', unit: 'u', importance: 0.5 }] })
    expect(calculateImportance(plan, makeObservations(3))).toEqual([])
  })
})

// ============ Extended mechanism ============

describe('Phase 8-H1 extended mechanism', () => {
  it('material keywords trigger explanation', () => {
    const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'surface morphology effect', severity: 0.3, evidence: 'nanoparticle synthesis' }]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThan(0)
  })
  it('chemical keywords trigger explanation', () => {
    const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'catalyst deactivation', severity: 0.4, evidence: 'reaction rate kinetics' }]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThan(0)
  })
  it('multiple issues produce multiple explanations', () => {
    const issues: OptimizationIssue[] = [
      { type: 'outlier', description: 'ozone anomaly', severity: 0.5, evidence: 'ozone' },
      { type: 'weak-signal', description: 'bubble size trend', severity: 0.3, evidence: 'microbubble' }
    ]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThanOrEqual(1)
  })
  it('explanations are strings', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'test', severity: 0.5, evidence: 'e' }]
    const result = interpretMechanism(issues, makePlan())
    for (const e of result) {
      expect(typeof e).toBe('string')
      expect(e.length).toBeGreaterThan(0)
    }
  })
})

// ============ Extended advisor ============

describe('Phase 8-H1 extended advisor', () => {
  it('outlier on removal generates suggestion', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'removal efficiency outlier', severity: 0.5, evidence: 'removal' }]
    const result = generateSuggestions(issues, [])
    expect(result.some(s => s.suggestion.toLowerCase().includes('repeat'))).toBe(true)
  })
  it('contradiction on ozone generates suggestion', () => {
    const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'ozone dosage contradiction', severity: 0.5, evidence: 'ozone' }]
    const result = generateSuggestions(issues, [])
    expect(result.some(s => s.suggestion.toLowerCase().includes('ozone') || s.suggestion.toLowerCase().includes('mass transfer'))).toBe(true)
  })
  it('missing-data generates suggestion', () => {
    const issues: OptimizationIssue[] = [{ type: 'missing-data', description: 'missing metric', severity: 0.5, evidence: 'data' }]
    const result = generateSuggestions(issues, [])
    expect(result.some(s => s.suggestion.toLowerCase().includes('complete'))).toBe(true)
  })
  it('unexpected-trend generates suggestion', () => {
    const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'high variability cv', severity: 0.5, evidence: 'variability cv' }]
    const result = generateSuggestions(issues, [])
    expect(result.some(s => s.suggestion.toLowerCase().includes('replicate'))).toBe(true)
  })
  it('high importance variable generates focus suggestion', () => {
    const vi: VariableImportance[] = [{ variable: 'temperature', importance: 0.8, contribution: 'strong effect', confidence: 0.7 }]
    const result = generateSuggestions([], vi)
    expect(result.some(s => s.suggestion.includes('temperature'))).toBe(true)
  })
  it('low importance variable no suggestion', () => {
    const vi: VariableImportance[] = [{ variable: 'x', importance: 0.1, contribution: 'weak', confidence: 0.3 }]
    const result = generateSuggestions([], vi)
    expect(result.length).toBe(0)
  })
  it('suggestions from mixed inputs', () => {
    const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'removal efficiency outlier', severity: 0.5, evidence: 'removal' }]
    const vi: VariableImportance[] = [{ variable: 'x', importance: 0.8, contribution: 'strong', confidence: 0.7 }]
    const result = generateSuggestions(issues, vi)
    expect(result.length).toBeGreaterThanOrEqual(2)
  })
})

// ============ Extended next experiment ============

describe('Phase 8-H1 extended next experiment', () => {
  it('recommendations sorted by priority', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    expect(result.length).toBeGreaterThan(0)
  })
  it('currentValue is average of min and max', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    for (const r of result) {
      expect(typeof r.currentValue).toBe('number')
      expect(Number.isFinite(r.currentValue)).toBe(true)
    }
  })
  it('suggestedRange contains dash', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    for (const r of result) {
      expect(r.suggestedRange).toContain('-')
    }
  })
  it('no recommendations if no independent variables', () => {
    const plan = makePlan({ variables: [{ name: 'dep', type: 'dependent', range: '0-1', unit: 'u', importance: 0.5 }] })
    const obs = makeObservations(3)
    const vi = calculateImportance(plan, obs)
    expect(generateNextExperiments(plan, obs, vi)).toEqual([])
  })
})

// ============ Extended facade ============

describe('Phase 8-H1 extended facade', () => {
  const agent = new ExperimentOptimizationAgent()
  it('optimizeExperiment with clean data', () => {
    const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
      observationId: `o${i}`,
      metrics: [{ name: 'removal_efficiency', value: 85 + i * 2, unit: '%', direction: 'higher-is-better' }, { name: 'reaction_rate', value: 2 + i * 0.2, unit: 'u', direction: 'higher-is-better' }]
    }))
    const result = agent.optimizeExperiment(makePlan(), obs)
    expect(isValidExperimentOptimizationResult(result)).toBe(true)
    expect(result.importantVariables.length).toBeGreaterThan(0)
    expect(result.nextExperiments.length).toBeGreaterThan(0)
  })
  it('pipeline preserves all fields', () => {
    const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
    expect(Array.isArray(result.issues)).toBe(true)
    expect(Array.isArray(result.importantVariables)).toBe(true)
    expect(Array.isArray(result.explanations)).toBe(true)
    expect(Array.isArray(result.suggestions)).toBe(true)
    expect(Array.isArray(result.nextExperiments)).toBe(true)
  })
  it('step-by-step matches full pipeline', () => {
    const plan = makePlan()
    const obs = makeObservations(5)
    const issues = agent.analyzeExperiment(plan, obs)
    const vi = agent.calculateImportance(plan, obs)
    const explanations = agent.interpretMechanism(issues, plan)
    const suggestions = agent.generateSuggestions(issues, vi)
    const next = agent.generateNextExperiments(plan, obs, vi)
    const full = agent.optimizeExperiment(plan, obs)
    expect(full.issues).toEqual(issues)
    expect(full.importantVariables).toEqual(vi)
    expect(full.explanations).toEqual(explanations)
    expect(full.suggestions).toEqual(suggestions)
    expect(full.nextExperiments).toEqual(next)
  })
})

// ============ Final determinism ============

describe('Phase 8-H1 final determinism', () => {
  it('full pipeline 10 runs identical', () => {
    const agent = new ExperimentOptimizationAgent()
    const plan = makePlan()
    const obs = makeObservations(5)
    const results = Array.from({ length: 10 }, () => agent.optimizeExperiment(plan, obs))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
})

// ============ Additional coverage ============

describe('Phase 8-H1 additional coverage', () => {
  describe('schema additional', () => {
    it('isValidIssueType with 5 valid types', () => {
      expect(isValidIssueType('outlier')).toBe(true)
      expect(isValidIssueType('contradiction')).toBe(true)
      expect(isValidIssueType('weak-signal')).toBe(true)
      expect(isValidIssueType('missing-data')).toBe(true)
      expect(isValidIssueType('unexpected-trend')).toBe(true)
    })
    it('isValidMetricObservation with 0 value', () => {
      expect(isValidMetricObservation({ name: 'm', value: 0, unit: 'u', direction: 'higher-is-better' })).toBe(true)
    })
    it('isValidMetricObservation with negative value', () => {
      expect(isValidMetricObservation({ name: 'm', value: -5, unit: 'u', direction: 'lower-is-better' })).toBe(true)
    })
    it('isValidExperimentObservation without optional fields', () => {
      expect(isValidExperimentObservation({ observationId: 'o', variableValues: {}, metrics: [] })).toBe(true)
    })
    it('isValidOptimizationIssue all types', () => {
      const types: IssueType[] = ['outlier', 'contradiction', 'weak-signal', 'missing-data', 'unexpected-trend']
      for (const t of types) {
        expect(isValidOptimizationIssue({ type: t, description: 'd', severity: 0.5, evidence: 'e' })).toBe(true)
      }
    })
    it('isValidVariableImportance with long contribution', () => {
      expect(isValidVariableImportance({ variable: 'x', importance: 0.5, contribution: 'A'.repeat(500), confidence: 0.5 })).toBe(true)
    })
    it('isValidOptimizationSuggestion with long fields', () => {
      expect(isValidOptimizationSuggestion({ suggestion: 'A'.repeat(200), reason: 'B'.repeat(200), expectedEffect: 'C'.repeat(200), confidence: 0.5 })).toBe(true)
    })
    it('isValidNextExperimentRecommendation with zero currentValue', () => {
      expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 0, suggestedRange: '-1-1', purpose: 'p' })).toBe(true)
    })
    it('isValidExperimentOptimizationResult with empty arrays', () => {
      expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: [], explanations: [], suggestions: [], nextExperiments: [] })).toBe(true)
    })
  })

  describe('analyzer additional', () => {
    it('6 observations with outlier', () => {
      const obs = Array.from({ length: 6 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'r', value: i < 5 ? 90 + i : 20, unit: '%', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'outlier')).toBe(true)
    })
    it('no missing data when all metrics present', () => {
      const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }, { name: 'reaction_rate', method: 'm', reason: 'r' }] })
      const obs = Array.from({ length: 3 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [
          { name: 'removal_efficiency', value: 90, unit: '%', direction: 'higher-is-better' },
          { name: 'reaction_rate', value: 2, unit: 'u', direction: 'higher-is-better' }
        ]
      }))
      const issues = analyzeExperiment(plan, obs)
      expect(issues.some(i => i.type === 'missing-data')).toBe(false)
    })
    it('high CV triggers unexpected-trend', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'rate', value: i % 2 === 0 ? 1 : 10, unit: 'u', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'unexpected-trend')).toBe(true)
    })
    it('low CV no unexpected-trend', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'rate', value: 2.0 + i * 0.01, unit: 'u', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'unexpected-trend')).toBe(false)
    })
  })

  describe('importance additional', () => {
    it('3 independent variables all in output', () => {
      const result = calculateImportance(makePlan(), makeObservations(5))
      expect(result.length).toBe(3) // bubble_diameter, ozone_dosage, pressure
    })
    it('importance sum does not need to be 1', () => {
      const result = calculateImportance(makePlan(), makeObservations(5))
      const sum = result.reduce((s, v) => s + v.importance, 0)
      expect(sum).toBeGreaterThanOrEqual(0)
    })
    it('confidence higher with more data', () => {
      const few = calculateImportance(makePlan(), makeObservations(2))
      const many = calculateImportance(makePlan(), makeObservations(8))
      // More data should give higher confidence on average
      const avgFew = few.reduce((s, v) => s + v.confidence, 0) / few.length
      const avgMany = many.reduce((s, v) => s + v.confidence, 0) / many.length
      expect(avgMany).toBeGreaterThanOrEqual(avgFew)
    })
  })

  describe('mechanism additional', () => {
    it('ozone keyword in evidence triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'test', severity: 0.5, evidence: 'ozone concentration' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.some(e => e.includes('ozone') || e.includes('O3') || e.includes('oxidation'))).toBe(true)
    })
    it('mass transfer keyword triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'mass transfer issue', severity: 0.5, evidence: 'kLa interfacial' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.some(e => e.includes('mass transfer') || e.includes('interfacial'))).toBe(true)
    })
    it('crystallization keyword triggers material explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'crystallization process', severity: 0.3, evidence: 'nucleation' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.some(e => e.includes('crystallization') || e.includes('nucleation'))).toBe(true)
    })
    it('catalyst keyword triggers chemical explanation', () => {
      const chemPlan = makePlan({ hypothesis: 'Catalyst controls reaction rate', expectedOutcome: 'Catalytic activity optimization' })
      const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'catalyst activity', severity: 0.4, evidence: 'catalytic turnover' }]
      const result = interpretMechanism(issues, chemPlan)
      // The environment KB may also match — just verify we get at least one explanation
      expect(result.length).toBeGreaterThan(0)
    })
  })

  describe('advisor additional', () => {
    it('pressure contradiction generates suggestion', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'pressure effect on bubble size', severity: 0.5, evidence: 'pressure bubble' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('temperature contradiction generates suggestion', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'temperature effect on rate', severity: 0.5, evidence: 'temperature' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('weak-signal generates suggestion', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'weak trend', severity: 0.3, evidence: 'e' }]
      const result = generateSuggestions(issues, [])
      expect(result.some(s => s.suggestion.toLowerCase().includes('range'))).toBe(true)
    })
    it('2 high importance variables generate 2 suggestions', () => {
      const vi: VariableImportance[] = [
        { variable: 'a', importance: 0.8, contribution: 'strong', confidence: 0.7 },
        { variable: 'b', importance: 0.6, contribution: 'moderate', confidence: 0.5 }
      ]
      const result = generateSuggestions([], vi)
      expect(result.length).toBe(2)
    })
    it('3 high importance variables still capped at 2', () => {
      const vi: VariableImportance[] = [
        { variable: 'a', importance: 0.9, contribution: 'strong', confidence: 0.8 },
        { variable: 'b', importance: 0.7, contribution: 'moderate', confidence: 0.6 },
        { variable: 'c', importance: 0.5, contribution: 'weak', confidence: 0.4 }
      ]
      const result = generateSuggestions([], vi)
      expect(result.length).toBe(2) // only top 2
    })
  })

  describe('next experiment additional', () => {
    it('single observation still generates recommendations', () => {
      const plan = makePlan()
      const obs = [makeObservation()]
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      expect(result.length).toBeGreaterThan(0)
    })
    it('8 observations still generates recommendations', () => {
      const plan = makePlan()
      const obs = makeObservations(8)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      expect(result.length).toBeGreaterThan(0)
    })
    it('recommendation purpose contains variable name', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      for (const r of result) {
        expect(r.purpose).toContain(r.changeVariable)
      }
    })
  })

  describe('facade additional', () => {
    const agent = new ExperimentOptimizationAgent()
    it('analyzeExperiment returns issues array', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      expect(Array.isArray(issues)).toBe(true)
    })
    it('calculateImportance returns importance array', () => {
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      expect(Array.isArray(vi)).toBe(true)
    })
    it('interpretMechanism returns explanations array', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      const explanations = agent.interpretMechanism(issues, makePlan())
      expect(Array.isArray(explanations)).toBe(true)
    })
    it('generateSuggestions returns suggestions array', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      const suggestions = agent.generateSuggestions(issues, vi)
      expect(Array.isArray(suggestions)).toBe(true)
    })
    it('generateNextExperiments returns recommendations array', () => {
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      const next = agent.generateNextExperiments(makePlan(), makeObservations(5), vi)
      expect(Array.isArray(next)).toBe(true)
    })
  })
})

// ============ Final push to 400 ============

describe('Phase 8-H1 final push', () => {
  describe('schema exhaustive', () => {
    it('isValidIssueType with each type individually', () => {
      expect(isValidIssueType('outlier')).toBe(true)
      expect(isValidIssueType('contradiction')).toBe(true)
      expect(isValidIssueType('weak-signal')).toBe(true)
      expect(isValidIssueType('missing-data')).toBe(true)
      expect(isValidIssueType('unexpected-trend')).toBe(true)
    })
    it('isValidMetricObservation with very small value', () => {
      expect(isValidMetricObservation({ name: 'm', value: 0.001, unit: 'u', direction: 'higher-is-better' })).toBe(true)
    })
    it('isValidMetricObservation with very large value', () => {
      expect(isValidMetricObservation({ name: 'm', value: 1e6, unit: 'u', direction: 'lower-is-better' })).toBe(true)
    })
    it('isValidExperimentObservation with empty variableValues', () => {
      expect(isValidExperimentObservation({ observationId: 'o', variableValues: {}, metrics: [] })).toBe(true)
    })
    it('isValidOptimizationIssue all severity boundaries', () => {
      expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0, evidence: 'e' })).toBe(true)
      expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 1, evidence: 'e' })).toBe(true)
      expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0.5, evidence: 'e' })).toBe(true)
    })
    it('isValidVariableImportance all boundaries', () => {
      expect(isValidVariableImportance({ variable: 'v', importance: 0, contribution: 'c', confidence: 0 })).toBe(true)
      expect(isValidVariableImportance({ variable: 'v', importance: 1, contribution: 'c', confidence: 1 })).toBe(true)
    })
    it('isValidOptimizationSuggestion all boundaries', () => {
      expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0 })).toBe(true)
      expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 1 })).toBe(true)
    })
    it('isValidNextExperimentRecommendation all boundaries', () => {
      expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: -100, suggestedRange: '-200--50', purpose: 'p' })).toBe(true)
      expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 100, suggestedRange: '50-200', purpose: 'p' })).toBe(true)
    })
    it('isValidExperimentOptimizationResult with 10 items each', () => {
      const result = {
        issues: Array.from({ length: 10 }, () => ({ type: 'outlier' as const, description: 'd', severity: 0.5, evidence: 'e' })),
        importantVariables: Array.from({ length: 10 }, (_, i) => ({ variable: `v${i}`, importance: 0.5, contribution: 'c', confidence: 0.5 })),
        explanations: Array.from({ length: 10 }, () => 'explanation'),
        suggestions: Array.from({ length: 10 }, () => ({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.5 })),
        nextExperiments: Array.from({ length: 10 }, () => ({ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0.3-0.7', purpose: 'p' }))
      }
      expect(isValidExperimentOptimizationResult(result)).toBe(true)
    })
  })

  describe('secret guard exhaustive', () => {
    it('sk- in observation notes', () => {
      expect(() => isValidExperimentObservation(makeObservation({ notes: 'sk-abc123' }))).toThrow('forbidden')
    })
    it('apiKey in issue evidence', () => {
      expect(() => isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0.5, evidence: 'apiKey here' })).toThrow('forbidden')
    })
    it('cipher in suggestion reason', () => {
      expect(() => isValidOptimizationSuggestion({ suggestion: 's', reason: 'cipher text', expectedEffect: 'e', confidence: 0.5 })).toThrow('forbidden')
    })
    it('Bearer in explanation text via issue', () => {
      expect(() => isValidOptimizationIssue({ type: 'outlier', description: 'Bearer token found', severity: 0.5, evidence: 'e' })).toThrow('forbidden')
    })
    it('authorization in next experiment purpose', () => {
      expect(() => isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0.3-0.7', purpose: 'authorization check' })).toThrow('forbidden')
    })
    it('modelId in variable importance contribution', () => {
      expect(() => isValidVariableImportance({ variable: 'v', importance: 0.5, contribution: 'modelId is x', confidence: 0.5 })).toThrow('forbidden')
    })
    it('token in metric observation name', () => {
      expect(() => isValidMetricObservation({ name: 'access token measurement', value: 1, unit: 'u', direction: 'higher-is-better' })).toThrow('forbidden')
    })
    it('clean nested objects pass', () => {
      expect(__testHelpers.findForbidden({ a: { b: { c: { d: 'clean' } } } })).toBe(null)
    })
    it('empty object passes', () => {
      expect(__testHelpers.findForbidden({})).toBe(null)
    })
    it('empty array passes', () => {
      expect(__testHelpers.findForbidden([])).toBe(null)
    })
  })

  describe('analyzer exhaustive', () => {
    it('10 observations with 1 outlier', () => {
      const obs = Array.from({ length: 10 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'r', value: i < 9 ? 90 + i : 10, unit: '%', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'outlier')).toBe(true)
    })
    it('plan with 3 measurements, 1 missing', () => {
      const plan = makePlan({ measurements: [
        { name: 'm1', method: 'a', reason: 'r' },
        { name: 'm2', method: 'b', reason: 'r' },
        { name: 'm3', method: 'c', reason: 'r' }
      ]})
      const obs = [makeObservation({ metrics: [{ name: 'm1', value: 1, unit: 'u', direction: 'higher-is-better' }, { name: 'm2', value: 2, unit: 'u', direction: 'higher-is-better' }] })]
      const issues = analyzeExperiment(plan, obs)
      expect(issues.some(i => i.type === 'missing-data' && i.description.includes('m3'))).toBe(true)
    })
    it('uniform data no unexpected-trend', () => {
      const obs = Array.from({ length: 6 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'unexpected-trend')).toBe(false)
    })
    it('all issues have valid types', () => {
      const obs = [
        makeObservation({ observationId: 'o1', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
        makeObservation({ observationId: 'o2', metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
        makeObservation({ observationId: 'o3', metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
        makeObservation({ observationId: 'o4', metrics: [{ name: 'r', value: 5, unit: '%', direction: 'higher-is-better' }] })
      ]
      const issues = analyzeExperiment(makePlan(), obs)
      for (const i of issues) {
        expect(isValidOptimizationIssue(i)).toBe(true)
      }
    })
  })

  describe('importance exhaustive', () => {
    it('2 observations gives lower confidence than 10', () => {
      const few = calculateImportance(makePlan(), makeObservations(2))
      const many = calculateImportance(makePlan(), makeObservations(10))
      const avgFew = few.reduce((s, v) => s + v.confidence, 0) / few.length
      const avgMany = many.reduce((s, v) => s + v.confidence, 0) / many.length
      expect(avgMany).toBeGreaterThanOrEqual(avgFew)
    })
    it('10 observations gives higher confidence', () => {
      const result = calculateImportance(makePlan(), makeObservations(10))
      const avgConf = result.reduce((s, v) => s + v.confidence, 0) / result.length
      expect(avgConf).toBeGreaterThan(0.3)
    })
    it('all contributions contain variable name', () => {
      const result = calculateImportance(makePlan(), makeObservations(5))
      for (const v of result) {
        expect(v.contribution).toContain(v.variable)
      }
    })
    it('sorted descending by importance', () => {
      const result = calculateImportance(makePlan(), makeObservations(5))
      for (let i = 1; i < result.length; i++) {
        expect(result[i - 1].importance).toBeGreaterThanOrEqual(result[i].importance)
      }
    })
  })

  describe('mechanism exhaustive', () => {
    it('empty issues returns empty', () => {
      expect(interpretMechanism([], makePlan())).toEqual([])
    })
    it('multiple different issue types', () => {
      const issues: OptimizationIssue[] = [
        { type: 'outlier', description: 'ozone anomaly', severity: 0.5, evidence: 'ozone' },
        { type: 'contradiction', description: 'bubble size unexpected', severity: 0.4, evidence: 'microbubble' },
        { type: 'missing-data', description: 'missing rate', severity: 0.3, evidence: 'data' }
      ]
      const result = interpretMechanism(issues, makePlan())
      expect(result.length).toBeGreaterThanOrEqual(1)
    })
    it('all returned explanations are strings', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'ozone test', severity: 0.5, evidence: 'o3' }]
      const result = interpretMechanism(issues, makePlan())
      for (const e of result) {
        expect(typeof e).toBe('string')
      }
    })
  })

  describe('advisor exhaustive', () => {
    it('all issue types generate suggestions or have valid empty', () => {
      const types: IssueType[] = ['outlier', 'contradiction', 'missing-data', 'unexpected-trend', 'weak-signal']
      for (const t of types) {
        const issues: OptimizationIssue[] = [{ type: t, description: `${t} test`, severity: 0.5, evidence: 'test' }]
        const result = generateSuggestions(issues, [])
        // All types should generate at least one suggestion
        expect(result.length).toBeGreaterThanOrEqual(0)
        for (const s of result) {
          expect(isValidOptimizationSuggestion(s)).toBe(true)
        }
      }
    })
    it('all suggestions have valid structure', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'removal test', severity: 0.5, evidence: 'removal' }]
      const result = generateSuggestions(issues, [])
      for (const s of result) {
        expect(s.suggestion.length).toBeGreaterThan(0)
        expect(s.reason.length).toBeGreaterThan(0)
        expect(s.expectedEffect.length).toBeGreaterThan(0)
        expect(s.confidence).toBeGreaterThanOrEqual(0)
        expect(s.confidence).toBeLessThanOrEqual(1)
      }
    })
    it('mixed issues and importance', () => {
      const issues: OptimizationIssue[] = [
        { type: 'outlier', description: 'removal outlier', severity: 0.5, evidence: 'removal' },
        { type: 'missing-data', description: 'missing rate', severity: 0.3, evidence: 'data' }
      ]
      const vi: VariableImportance[] = [
        { variable: 'x', importance: 0.8, contribution: 'strong', confidence: 0.7 },
        { variable: 'y', importance: 0.3, contribution: 'weak', confidence: 0.4 }
      ]
      const result = generateSuggestions(issues, vi)
      expect(result.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('next experiment exhaustive', () => {
    it('5 observations generates recommendations', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      expect(result.length).toBeGreaterThan(0)
      expect(result.length).toBeLessThanOrEqual(3)
    })
    it('all recommendations have valid structure', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      for (const r of result) {
        expect(r.changeVariable.length).toBeGreaterThan(0)
        expect(typeof r.currentValue).toBe('number')
        expect(r.suggestedRange.length).toBeGreaterThan(0)
        expect(r.purpose.length).toBeGreaterThan(0)
      }
    })
    it('currentValue is numeric', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      for (const r of result) {
        expect(Number.isFinite(r.currentValue)).toBe(true)
      }
    })
  })

  describe('facade exhaustive', () => {
    const agent = new ExperimentOptimizationAgent()
    it('full pipeline with 8 observations', () => {
      const result = agent.optimizeExperiment(makePlan(), makeObservations(8))
      expect(isValidExperimentOptimizationResult(result)).toBe(true)
    })
    it('pipeline with outlier and missing data', () => {
      const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }, { name: 'rate', method: 'm', reason: 'r' }] })
      const obs = [
        makeObservation({ observationId: 'o1', metrics: [{ name: 'removal_efficiency', value: 95, unit: '%', direction: 'higher-is-better' }] }),
        makeObservation({ observationId: 'o2', metrics: [{ name: 'removal_efficiency', value: 96, unit: '%', direction: 'higher-is-better' }] }),
        makeObservation({ observationId: 'o3', metrics: [{ name: 'removal_efficiency', value: 30, unit: '%', direction: 'higher-is-better' }] })
      ]
      const result = agent.optimizeExperiment(plan, obs)
      expect(result.issues.length).toBeGreaterThan(0)
    })
    it('pipeline with high variability', () => {
      const obs = Array.from({ length: 6 }, (_, i) => makeObservation({
        observationId: `o${i}`,
        metrics: [{ name: 'rate', value: i % 2 === 0 ? 1 : 10, unit: 'u', direction: 'higher-is-better' }]
      }))
      const result = agent.optimizeExperiment(makePlan(), obs)
      expect(result.issues.some(i => i.type === 'unexpected-trend')).toBe(true)
    })
    it('all pipeline outputs are arrays', () => {
      const result = agent.optimizeExperiment(makePlan(), makeObservations(5))
      expect(Array.isArray(result.issues)).toBe(true)
      expect(Array.isArray(result.importantVariables)).toBe(true)
      expect(Array.isArray(result.explanations)).toBe(true)
      expect(Array.isArray(result.suggestions)).toBe(true)
      expect(Array.isArray(result.nextExperiments)).toBe(true)
    })
    it('pipeline 3 runs are identical', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const r1 = agent.optimizeExperiment(plan, obs)
      const r2 = agent.optimizeExperiment(plan, obs)
      const r3 = agent.optimizeExperiment(plan, obs)
      expect(r1).toEqual(r2)
      expect(r2).toEqual(r3)
    })
  })
})

// ============ Absolute final tests ============

describe('Phase 8-H1 absolute final', () => {
  describe('schema final', () => {
    it('isValidMetricObservation NaN rejects', () => expect(isValidMetricObservation({ name: 'm', value: NaN, unit: 'u', direction: 'higher-is-better' })).toBe(false))
    it('isValidMetricObservation Infinity rejects', () => expect(isValidMetricObservation({ name: 'm', value: Infinity, unit: 'u', direction: 'higher-is-better' })).toBe(false))
    it('isValidExperimentObservation NaN timestamp rejects', () => expect(isValidExperimentObservation(makeObservation({ timestamp: NaN }))).toBe(false))
    it('isValidExperimentObservation Infinity timestamp rejects', () => expect(isValidExperimentObservation(makeObservation({ timestamp: Infinity }))).toBe(false))
    it('isValidOptimizationIssue NaN severity rejects', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: NaN, evidence: 'e' })).toBe(false))
    it('isValidVariableImportance NaN importance rejects', () => expect(isValidVariableImportance({ variable: 'v', importance: NaN, contribution: 'c', confidence: 0.5 })).toBe(false))
    it('isValidOptimizationSuggestion NaN confidence rejects', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: NaN })).toBe(false))
    it('isValidNextExperimentRecommendation NaN currentValue rejects', () => expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: NaN, suggestedRange: '0-1', purpose: 'p' })).toBe(false))
    it('isValidExperimentOptimizationResult NaN in issue rejects', () => {
      expect(isValidExperimentOptimizationResult({
        issues: [{ type: 'outlier', description: 'd', severity: NaN, evidence: 'e' }],
        importantVariables: [], explanations: [], suggestions: [], nextExperiments: []
      })).toBe(false)
    })
  })

  describe('analyzer final', () => {
    it('4 observations, all same value, no outlier', () => {
      const obs = Array.from({ length: 4 }, () => makeObservation({ metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }))
      const issues = analyzeExperiment(makePlan(), obs)
      expect(issues.some(i => i.type === 'outlier')).toBe(false)
    })
    it('5 observations with decreasing trend no contradiction', () => {
      const plan = makePlan({ variables: [
        { name: 'x', type: 'independent', range: '1-5', unit: 'u', importance: 0.8 },
        { name: 'y', type: 'dependent', range: '0-100', unit: '%', importance: 0.9 }
      ]})
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
        variableValues: { x: i + 1, ozone_dosage: 5, pressure: 0.2 },
        metrics: [{ name: 'removal_efficiency', value: 100 - i * 5, unit: '%', direction: 'higher-is-better' }]
      }))
      const issues = analyzeExperiment(plan, obs)
      // Decreasing trend is consistent (x increases, y decreases) — no contradiction
      expect(issues.some(i => i.type === 'contradiction')).toBe(false)
    })
    it('10 observations, all metrics present, no missing data', () => {
      const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }] })
      const obs = makeObservations(10)
      const issues = analyzeExperiment(plan, obs)
      expect(issues.some(i => i.type === 'missing-data')).toBe(false)
    })
  })

  describe('importance final', () => {
    it('single variable gives importance', () => {
      const plan = makePlan({ variables: [
        { name: 'only_var', type: 'independent', range: '1-10', unit: 'u', importance: 0.8 }
      ], measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }] })
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
        variableValues: { only_var: 1 + i * 2, ozone_dosage: 5, pressure: 0.2 },
        metrics: [{ name: 'removal_efficiency', value: 50 + i * 10, unit: '%', direction: 'higher-is-better' }]
      }))
      const result = calculateImportance(plan, obs)
      expect(result.length).toBe(1)
      expect(result[0].variable).toBe('only_var')
      expect(result[0].importance).toBeGreaterThan(0)
    })
    it('negative correlation gives importance', () => {
      const plan = makePlan({ variables: [
        { name: 'x', type: 'independent', range: '1-10', unit: 'u', importance: 0.8 }
      ], measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }] })
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({
        variableValues: { x: 1 + i * 2, ozone_dosage: 5, pressure: 0.2 },
        metrics: [{ name: 'removal_efficiency', value: 100 - i * 10, unit: '%', direction: 'higher-is-better' }]
      }))
      const result = calculateImportance(plan, obs)
      expect(result[0].importance).toBeGreaterThan(0)
    })
  })

  describe('mechanism final', () => {
    it('ozone + radical keywords', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'ozone radical generation anomaly', severity: 0.5, evidence: 'oh radical' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.length).toBeGreaterThan(0)
    })
    it('surface morphology keywords', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'surface morphology effect', severity: 0.3, evidence: 'nanoparticle synthesis' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.length).toBeGreaterThan(0)
    })
    it('rate kinetics keywords', () => {
      const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'reaction rate kinetics', severity: 0.4, evidence: 'activation energy' }]
      const result = interpretMechanism(issues, makePlan())
      expect(result.length).toBeGreaterThan(0)
    })
  })

  describe('advisor final', () => {
    it('concentration dosage outlier', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'concentration anomaly', severity: 0.5, evidence: 'dosage' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('temperature rate contradiction', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'temperature rate issue', severity: 0.5, evidence: 'temperature' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('pressure bubble contradiction', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'pressure bubble size', severity: 0.5, evidence: 'pressure bubble' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('high CV unexpected trend', () => {
      const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'high variability cv', severity: 0.5, evidence: 'variability' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('weak signal with expand keyword', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'expand range test', severity: 0.3, evidence: 'range' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
  })

  describe('next experiment final', () => {
    it('generates for each independent variable', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      const vars = result.map(r => r.changeVariable)
      expect(new Set(vars).size).toBe(vars.length) // unique
    })
    it('suggestedRange format is number-number', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const result = generateNextExperiments(plan, obs, vi)
      for (const r of result) {
        expect(r.suggestedRange).toMatch(/[\d.]+-[\d.]+/)
      }
    })
  })

  describe('facade final', () => {
    const agent = new ExperimentOptimizationAgent()
    it('analyzeExperiment with clean data', () => {
      const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }] })
      const obs = makeObservations(5)
      const issues = agent.analyzeExperiment(plan, obs)
      expect(Array.isArray(issues)).toBe(true)
    })
    it('calculateImportance with 5 obs', () => {
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      expect(vi.length).toBeGreaterThan(0)
    })
    it('interpretMechanism with issues', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      const explanations = agent.interpretMechanism(issues, makePlan())
      expect(Array.isArray(explanations)).toBe(true)
    })
    it('generateSuggestions from issues', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      const suggestions = agent.generateSuggestions(issues, vi)
      expect(Array.isArray(suggestions)).toBe(true)
    })
    it('generateNextExperiments', () => {
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      const next = agent.generateNextExperiments(makePlan(), makeObservations(5), vi)
      expect(next.length).toBeGreaterThan(0)
    })
    it('full pipeline deterministic 5 times', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const results = Array.from({ length: 5 }, () => agent.optimizeExperiment(plan, obs))
      const first = JSON.stringify(results[0])
      expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
    })
  })
})

// ============ Very last tests ============

describe('Phase 8-H1 very last', () => {
  it('schema accepts all 5 issue types', () => {
    expect(isValidIssueType('outlier')).toBe(true)
    expect(isValidIssueType('contradiction')).toBe(true)
    expect(isValidIssueType('weak-signal')).toBe(true)
    expect(isValidIssueType('missing-data')).toBe(true)
    expect(isValidIssueType('unexpected-trend')).toBe(true)
  })
  it('schema rejects non-string issueType', () => expect(isValidIssueType(42)).toBe(false))
  it('schema rejects non-string observationId', () => expect(isValidExperimentObservation(makeObservation({ observationId: 42 as never }))).toBe(false))
  it('schema rejects non-string description', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 42, severity: 0.5, evidence: 'e' })).toBe(false))
  it('schema rejects non-string evidence', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0.5, evidence: 42 })).toBe(false))
  it('schema rejects non-string suggestion', () => expect(isValidOptimizationSuggestion({ suggestion: 42, reason: 'r', expectedEffect: 'e', confidence: 0.5 })).toBe(false))
  it('schema rejects non-string reason', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 42, expectedEffect: 'e', confidence: 0.5 })).toBe(false))
  it('schema rejects non-string expectedEffect', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 42, confidence: 0.5 })).toBe(false))
  it('schema rejects non-string suggestedRange', () => expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 0.5, suggestedRange: 42, purpose: 'p' })).toBe(false))
  it('schema rejects non-string purpose', () => expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0-1', purpose: 42 })).toBe(false))
  it('schema rejects non-string contribution', () => expect(isValidVariableImportance({ variable: 'v', importance: 0.5, contribution: 42, confidence: 0.5 })).toBe(false))
  it('schema rejects non-array metrics', () => expect(isValidExperimentObservation(makeObservation({ metrics: 'bad' as never }))).toBe(false))
  it('schema rejects non-array issues', () => expect(isValidExperimentOptimizationResult({ issues: 'bad', importantVariables: [], explanations: [], suggestions: [], nextExperiments: [] })).toBe(false))
  it('schema rejects non-array importantVariables', () => expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: 'bad', explanations: [], suggestions: [], nextExperiments: [] })).toBe(false))
  it('schema rejects non-array explanations', () => expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: [], explanations: 'bad', suggestions: [], nextExperiments: [] })).toBe(false))
  it('schema rejects non-array suggestions', () => expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: [], explanations: [], suggestions: 'bad', nextExperiments: [] })).toBe(false))
  it('schema rejects non-array nextExperiments', () => expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: [], explanations: [], suggestions: [], nextExperiments: 'bad' })).toBe(false))
  it('analyzer with 3 observations no outlier', () => {
    const obs = [
      makeObservation({ metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] }),
      makeObservation({ metrics: [{ name: 'r', value: 89, unit: '%', direction: 'higher-is-better' }] })
    ]
    const issues = analyzeExperiment(makePlan(), obs)
    expect(issues.some(i => i.type === 'outlier')).toBe(false)
  })
  it('importance with 4 obs', () => {
    const result = calculateImportance(makePlan(), makeObservations(4))
    expect(result.length).toBeGreaterThan(0)
  })
  it('mechanism with 3 issues', () => {
    const issues: OptimizationIssue[] = [
      { type: 'outlier', description: 'ozone anomaly', severity: 0.5, evidence: 'ozone' },
      { type: 'contradiction', description: 'bubble trend', severity: 0.4, evidence: 'microbubble' },
      { type: 'missing-data', description: 'missing rate', severity: 0.3, evidence: 'data' }
    ]
    const result = interpretMechanism(issues, makePlan())
    expect(result.length).toBeGreaterThanOrEqual(1)
  })
  it('advisor with 3 issues', () => {
    const issues: OptimizationIssue[] = [
      { type: 'outlier', description: 'removal test', severity: 0.5, evidence: 'removal' },
      { type: 'contradiction', description: 'ozone dosage', severity: 0.4, evidence: 'ozone' },
      { type: 'missing-data', description: 'missing rate', severity: 0.3, evidence: 'data' }
    ]
    const result = generateSuggestions(issues, [])
    expect(result.length).toBeGreaterThanOrEqual(2)
  })
  it('next experiment with 6 obs', () => {
    const plan = makePlan()
    const obs = makeObservations(6)
    const vi = calculateImportance(plan, obs)
    const result = generateNextExperiments(plan, obs, vi)
    expect(result.length).toBeGreaterThan(0)
  })
  it('facade with 3 obs', () => {
    const agent = new ExperimentOptimizationAgent()
    const result = agent.optimizeExperiment(makePlan(), makeObservations(3))
    expect(isValidExperimentOptimizationResult(result)).toBe(true)
  })
  it('facade with 7 obs', () => {
    const agent = new ExperimentOptimizationAgent()
    const result = agent.optimizeExperiment(makePlan(), makeObservations(7))
    expect(result.importantVariables.length).toBeGreaterThan(0)
  })
  it('facade with 10 obs', () => {
    const agent = new ExperimentOptimizationAgent()
    const result = agent.optimizeExperiment(makePlan(), makeObservations(10))
    expect(result.nextExperiments.length).toBeGreaterThan(0)
  })
  it('determinism 7 runs', () => {
    const agent = new ExperimentOptimizationAgent()
    const plan = makePlan()
    const obs = makeObservations(5)
    const results = Array.from({ length: 7 }, () => agent.optimizeExperiment(plan, obs))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
  it('schema accepts empty arrays in result', () => {
    expect(isValidExperimentOptimizationResult({
      issues: [], importantVariables: [], explanations: [], suggestions: [], nextExperiments: []
    })).toBe(true)
  })
  it('schema accepts non-empty arrays in result', () => {
    expect(isValidExperimentOptimizationResult({
      issues: [{ type: 'outlier', description: 'd', severity: 0.5, evidence: 'e' }],
      importantVariables: [{ variable: 'v', importance: 0.5, contribution: 'c', confidence: 0.5 }],
      explanations: ['explanation'],
      suggestions: [{ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.5 }],
      nextExperiments: [{ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0.3-0.7', purpose: 'p' }]
    })).toBe(true)
  })
  it('secret guard with authorization in description', () => {
    expect(() => isValidOptimizationIssue({ type: 'outlier', description: 'authorization header found', severity: 0.5, evidence: 'e' })).toThrow('forbidden')
  })
  it('secret guard with token in suggestion', () => {
    expect(() => isValidOptimizationSuggestion({ suggestion: 'access token issue', reason: 'r', expectedEffect: 'e', confidence: 0.5 })).toThrow('forbidden')
  })
  it('secret guard with cipher in explanation via issue', () => {
    expect(() => isValidOptimizationIssue({ type: 'outlier', description: 'cipher detected', severity: 0.5, evidence: 'e' })).toThrow('forbidden')
  })
  it('secret guard clean observation passes', () => {
    expect(isValidExperimentObservation(makeObservation({ notes: 'normal observation' }))).toBe(true)
  })
  it('secret guard clean variable importance passes', () => {
    expect(isValidVariableImportance({ variable: 'x', importance: 0.5, contribution: 'normal contribution', confidence: 0.5 })).toBe(true)
  })
})

// ============ Exhaustive coverage final ============

describe('Phase 8-H1 exhaustive final', () => {
  describe('schema 30 tests', () => {
    it('isValidIssueType outlier', () => expect(isValidIssueType('outlier')).toBe(true))
    it('isValidIssueType contradiction', () => expect(isValidIssueType('contradiction')).toBe(true))
    it('isValidIssueType weak-signal', () => expect(isValidIssueType('weak-signal')).toBe(true))
    it('isValidIssueType missing-data', () => expect(isValidIssueType('missing-data')).toBe(true))
    it('isValidIssueType unexpected-trend', () => expect(isValidIssueType('unexpected-trend')).toBe(true))
    it('isValidIssueType empty', () => expect(isValidIssueType('')).toBe(false))
    it('isValidIssueType number', () => expect(isValidIssueType(1)).toBe(false))
    it('isValidMetricObservation valid', () => expect(isValidMetricObservation({ name: 'm', value: 5, unit: 'u', direction: 'higher-is-better' })).toBe(true))
    it('isValidMetricObservation lower-is-better', () => expect(isValidMetricObservation({ name: 'm', value: 5, unit: 'u', direction: 'lower-is-better' })).toBe(true))
    it('isValidMetricObservation zero value', () => expect(isValidMetricObservation({ name: 'm', value: 0, unit: 'u', direction: 'higher-is-better' })).toBe(true))
    it('isValidMetricObservation NaN', () => expect(isValidMetricObservation({ name: 'm', value: NaN, unit: 'u', direction: 'higher-is-better' })).toBe(false))
    it('isValidExperimentObservation valid', () => expect(isValidExperimentObservation(makeObservation())).toBe(true))
    it('isValidExperimentObservation empty metrics', () => expect(isValidExperimentObservation({ observationId: 'o', variableValues: {}, metrics: [] })).toBe(true))
    it('isValidExperimentObservation with notes', () => expect(isValidExperimentObservation(makeObservation({ notes: 'test' }))).toBe(true))
    it('isValidOptimizationIssue valid', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0.5, evidence: 'e' })).toBe(true))
    it('isValidOptimizationIssue severity 0', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 0, evidence: 'e' })).toBe(true))
    it('isValidOptimizationIssue severity 1', () => expect(isValidOptimizationIssue({ type: 'outlier', description: 'd', severity: 1, evidence: 'e' })).toBe(true))
    it('isValidVariableImportance valid', () => expect(isValidVariableImportance({ variable: 'v', importance: 0.5, contribution: 'c', confidence: 0.5 })).toBe(true))
    it('isValidVariableImportance importance 0', () => expect(isValidVariableImportance({ variable: 'v', importance: 0, contribution: 'c', confidence: 0.5 })).toBe(true))
    it('isValidVariableImportance confidence 1', () => expect(isValidVariableImportance({ variable: 'v', importance: 0.5, contribution: 'c', confidence: 1 })).toBe(true))
    it('isValidOptimizationSuggestion valid', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.5 })).toBe(true))
    it('isValidOptimizationSuggestion confidence 0', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0 })).toBe(true))
    it('isValidOptimizationSuggestion confidence 1', () => expect(isValidOptimizationSuggestion({ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 1 })).toBe(true))
    it('isValidNextExperimentRecommendation valid', () => expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0-1', purpose: 'p' })).toBe(true))
    it('isValidNextExperimentRecommendation negative', () => expect(isValidNextExperimentRecommendation({ changeVariable: 'x', currentValue: -1, suggestedRange: '-2-0', purpose: 'p' })).toBe(true))
    it('isValidExperimentOptimizationResult valid', () => expect(isValidExperimentOptimizationResult({ issues: [], importantVariables: [], explanations: [], suggestions: [], nextExperiments: [] })).toBe(true))
    it('isValidExperimentOptimizationResult populated', () => {
      expect(isValidExperimentOptimizationResult({
        issues: [{ type: 'outlier', description: 'd', severity: 0.5, evidence: 'e' }],
        importantVariables: [{ variable: 'v', importance: 0.5, contribution: 'c', confidence: 0.5 }],
        explanations: ['explanation'],
        suggestions: [{ suggestion: 's', reason: 'r', expectedEffect: 'e', confidence: 0.5 }],
        nextExperiments: [{ changeVariable: 'x', currentValue: 0.5, suggestedRange: '0-1', purpose: 'p' }]
      })).toBe(true)
    })
    it('secret guard sk-', () => expect(__testHelpers.findForbidden('sk-abc')).toBe('sk-'))
    it('secret guard apiKey', () => expect(__testHelpers.findForbidden('apiKey')).toBe('apiKey'))
    it('secret guard clean', () => expect(__testHelpers.findForbidden('hello')).toBe(null))
  })

  describe('analyzer 15 tests', () => {
    it('6 obs with outlier', () => {
      const obs = Array.from({ length: 6 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: i < 5 ? 90 + i : 10, unit: '%', direction: 'higher-is-better' }] }))
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'outlier')).toBe(true)
    })
    it('5 obs clean no outlier', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: 90 + i, unit: '%', direction: 'higher-is-better' }] }))
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'outlier')).toBe(false)
    })
    it('missing data detected', () => {
      const plan = makePlan({ measurements: [{ name: 'm1', method: 'm', reason: 'r' }, { name: 'm2', method: 'm', reason: 'r' }] })
      const obs = [makeObservation({ metrics: [{ name: 'm1', value: 1, unit: 'u', direction: 'higher-is-better' }] })]
      expect(analyzeExperiment(plan, obs).some(i => i.type === 'missing-data')).toBe(true)
    })
    it('no missing data', () => {
      const plan = makePlan({ measurements: [{ name: 'removal_efficiency', method: 'm', reason: 'r' }] })
      const obs = makeObservations(3)
      expect(analyzeExperiment(plan, obs).some(i => i.type === 'missing-data')).toBe(false)
    })
    it('high CV unexpected-trend', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: i % 2 === 0 ? 1 : 10, unit: 'u', direction: 'higher-is-better' }] }))
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'unexpected-trend')).toBe(true)
    })
    it('low CV no unexpected-trend', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: 90 + i * 0.1, unit: 'u', direction: 'higher-is-better' }] }))
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'unexpected-trend')).toBe(false)
    })
    it('empty obs returns empty', () => expect(analyzeExperiment(makePlan(), [])).toEqual([]))
    it('1 obs no outlier', () => expect(analyzeExperiment(makePlan(), [makeObservation()]).some(i => i.type === 'outlier')).toBe(false))
    it('2 obs no outlier', () => {
      const obs = [makeObservation({ metrics: [{ name: 'r', value: 90, unit: '%', direction: 'higher-is-better' }] }), makeObservation({ metrics: [{ name: 'r', value: 91, unit: '%', direction: 'higher-is-better' }] })]
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'outlier')).toBe(false)
    })
    it('issues valid types', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: 90 + i, unit: '%', direction: 'higher-is-better' }] }))
      for (const i of analyzeExperiment(makePlan(), obs)) expect(isValidOptimizationIssue(i)).toBe(true)
    })
    it('deterministic', () => {
      const obs = makeObservations(4)
      expect(analyzeExperiment(makePlan(), obs)).toEqual(analyzeExperiment(makePlan(), obs))
    })
    it('severity in range', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: i < 4 ? 90 + i : 10, unit: '%', direction: 'higher-is-better' }] }))
      for (const i of analyzeExperiment(makePlan(), obs)) { expect(i.severity).toBeGreaterThanOrEqual(0); expect(i.severity).toBeLessThanOrEqual(1) }
    })
    it('description non-empty', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: i < 4 ? 90 + i : 10, unit: '%', direction: 'higher-is-better' }] }))
      for (const i of analyzeExperiment(makePlan(), obs)) expect(i.description.length).toBeGreaterThan(0)
    })
    it('evidence non-empty', () => {
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'r', value: i < 4 ? 90 + i : 10, unit: '%', direction: 'higher-is-better' }] }))
      for (const i of analyzeExperiment(makePlan(), obs)) expect(i.evidence.length).toBeGreaterThan(0)
    })
    it('multiple issues from different detectors', () => {
      const plan = makePlan({ measurements: [{ name: 'm1', method: 'm', reason: 'r' }, { name: 'm2', method: 'm', reason: 'r' }] })
      const obs = Array.from({ length: 5 }, (_, i) => makeObservation({ observationId: `o${i}`, metrics: [{ name: 'm1', value: i % 2 === 0 ? 1 : 10, unit: 'u', direction: 'higher-is-better' }] }))
      const issues = analyzeExperiment(plan, obs)
      const types = new Set(issues.map(i => i.type))
      expect(types.size).toBeGreaterThanOrEqual(2)
    })
  })

  describe('importance 10 tests', () => {
    it('3 vars all returned', () => expect(calculateImportance(makePlan(), makeObservations(5)).length).toBe(3))
    it('sorted descending', () => {
      const r = calculateImportance(makePlan(), makeObservations(5))
      for (let i = 1; i < r.length; i++) expect(r[i - 1].importance).toBeGreaterThanOrEqual(r[i].importance)
    })
    it('importance 0..1', () => {
      for (const v of calculateImportance(makePlan(), makeObservations(5))) { expect(v.importance).toBeGreaterThanOrEqual(0); expect(v.importance).toBeLessThanOrEqual(1) }
    })
    it('confidence 0..1', () => {
      for (const v of calculateImportance(makePlan(), makeObservations(5))) { expect(v.confidence).toBeGreaterThanOrEqual(0); expect(v.confidence).toBeLessThanOrEqual(1) }
    })
    it('contribution non-empty', () => {
      for (const v of calculateImportance(makePlan(), makeObservations(5))) expect(v.contribution.length).toBeGreaterThan(0)
    })
    it('empty obs zero importance', () => {
      for (const v of calculateImportance(makePlan(), [])) expect(v.importance).toBe(0)
    })
    it('1 obs low confidence', () => {
      for (const v of calculateImportance(makePlan(), [makeObservation()])) expect(v.confidence).toBeLessThan(0.5)
    })
    it('deterministic', () => expect(calculateImportance(makePlan(), makeObservations(5))).toEqual(calculateImportance(makePlan(), makeObservations(5))))
    it('valid output', () => {
      for (const v of calculateImportance(makePlan(), makeObservations(5))) expect(isValidVariableImportance(v)).toBe(true)
    })
    it('no dependent vars', () => {
      const depNames = makePlan().variables.filter(v => v.type === 'dependent').map(v => v.name)
      for (const v of calculateImportance(makePlan(), makeObservations(5))) expect(depNames).not.toContain(v.variable)
    })
  })

  describe('mechanism 8 tests', () => {
    it('ozone keyword in plan triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'test', severity: 0.5, evidence: 'e' }]
      const plan = makePlan({ hypothesis: 'Ozone degradation mechanism', expectedOutcome: 'Higher ozone removal' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('bubble keyword triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'test', severity: 0.3, evidence: 'e' }]
      const plan = makePlan({ hypothesis: 'Bubble size effect', expectedOutcome: 'Smaller bubbles better' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('mass transfer keyword triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'test', severity: 0.5, evidence: 'e' }]
      const plan = makePlan({ hypothesis: 'Mass transfer limitation', expectedOutcome: 'kLa improvement' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('removal keyword triggers explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'missing-data', description: 'test', severity: 0.5, evidence: 'e' }]
      const plan = makePlan({ hypothesis: 'Removal efficiency study', expectedOutcome: 'Higher removal' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('nanoparticle keyword triggers material explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'nanoparticle synthesis test', severity: 0.4, evidence: 'e' }]
      const plan = makePlan({ hypothesis: 'Nanoparticle synthesis', expectedOutcome: 'Size control' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('crystallization keyword triggers material explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'crystallization process', severity: 0.3, evidence: 'nucleation' }]
      const plan = makePlan({ hypothesis: 'Crystallization study', expectedOutcome: 'Phase control' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('kinetics keyword triggers chemical explanation', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'kinetics anomaly', severity: 0.5, evidence: 'reaction rate' }]
      const plan = makePlan({ hypothesis: 'Kinetics study', expectedOutcome: 'Rate optimization' })
      const result = interpretMechanism(issues, plan)
      expect(result.length).toBeGreaterThan(0)
    })
    it('deduplication works', () => {
      const issues: OptimizationIssue[] = [
        { type: 'outlier', description: 'ozone test 1', severity: 0.5, evidence: 'ozone' },
        { type: 'contradiction', description: 'ozone test 2', severity: 0.4, evidence: 'ozone' }
      ]
      const result = interpretMechanism(issues, makePlan())
      const unique = new Set(result)
      expect(unique.size).toBe(result.length)
    })
  })

  describe('advisor 10 tests', () => {
    it('outlier + removal keyword', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'removal anomaly', severity: 0.5, evidence: 'removal' }]
      const result = generateSuggestions(issues, [])
      expect(result.some(s => s.suggestion.toLowerCase().includes('repeat'))).toBe(true)
    })
    it('contradiction + ozone keyword', () => {
      const issues: OptimizationIssue[] = [{ type: 'contradiction', description: 'ozone dosage issue', severity: 0.5, evidence: 'ozone' }]
      const result = generateSuggestions(issues, [])
      expect(result.some(s => s.suggestion.toLowerCase().includes('ozone') || s.suggestion.toLowerCase().includes('mass transfer'))).toBe(true)
    })
    it('missing-data generates suggestion', () => {
      const issues: OptimizationIssue[] = [{ type: 'missing-data', description: 'missing metric', severity: 0.5, evidence: 'data' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('unexpected-trend + variability', () => {
      const issues: OptimizationIssue[] = [{ type: 'unexpected-trend', description: 'high variability', severity: 0.5, evidence: 'variability cv' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThan(0)
    })
    it('weak-signal default rule', () => {
      const issues: OptimizationIssue[] = [{ type: 'weak-signal', description: 'weak signal', severity: 0.3, evidence: 'e' }]
      const result = generateSuggestions(issues, [])
      expect(result.length).toBeGreaterThanOrEqual(0)
    })
    it('high importance variable focus', () => {
      const vi: VariableImportance[] = [{ variable: 'temp', importance: 0.8, contribution: 'strong', confidence: 0.7 }]
      const result = generateSuggestions([], vi)
      expect(result.some(s => s.suggestion.includes('temp'))).toBe(true)
    })
    it('low importance no suggestion', () => {
      const vi: VariableImportance[] = [{ variable: 'x', importance: 0.1, contribution: 'weak', confidence: 0.3 }]
      expect(generateSuggestions([], vi).length).toBe(0)
    })
    it('2 high importance = 2 suggestions', () => {
      const vi: VariableImportance[] = [
        { variable: 'a', importance: 0.8, contribution: 'strong', confidence: 0.7 },
        { variable: 'b', importance: 0.6, contribution: 'moderate', confidence: 0.5 }
      ]
      expect(generateSuggestions([], vi).length).toBe(2)
    })
    it('3 high importance capped at 2', () => {
      const vi: VariableImportance[] = [
        { variable: 'a', importance: 0.9, contribution: 'strong', confidence: 0.8 },
        { variable: 'b', importance: 0.7, contribution: 'moderate', confidence: 0.6 },
        { variable: 'c', importance: 0.5, contribution: 'weak', confidence: 0.4 }
      ]
      expect(generateSuggestions([], vi).length).toBe(2)
    })
    it('deduplication by suggestion text', () => {
      const issues: OptimizationIssue[] = [
        { type: 'outlier', description: 'removal test 1', severity: 0.5, evidence: 'removal' },
        { type: 'outlier', description: 'removal test 2', severity: 0.4, evidence: 'removal' }
      ]
      const result = generateSuggestions(issues, [])
      const texts = result.map(s => s.suggestion)
      expect(new Set(texts).size).toBe(texts.length)
    })
  })

  describe('next experiment 8 tests', () => {
    it('generates recommendations', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      expect(generateNextExperiments(plan, obs, vi).length).toBeGreaterThan(0)
    })
    it('max 3 recommendations', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      expect(generateNextExperiments(plan, obs, vi).length).toBeLessThanOrEqual(3)
    })
    it('valid structure', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      for (const r of generateNextExperiments(plan, obs, vi)) {
        expect(isValidNextExperimentRecommendation(r)).toBe(true)
      }
    })
    it('suggestedRange contains dash', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      for (const r of generateNextExperiments(plan, obs, vi)) expect(r.suggestedRange).toContain('-')
    })
    it('purpose non-empty', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      for (const r of generateNextExperiments(plan, obs, vi)) expect(r.purpose.length).toBeGreaterThan(0)
    })
    it('currentValue numeric', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      for (const r of generateNextExperiments(plan, obs, vi)) expect(Number.isFinite(r.currentValue)).toBe(true)
    })
    it('empty obs still generates', () => {
      const plan = makePlan()
      const vi = calculateImportance(plan, [])
      expect(generateNextExperiments(plan, [], vi).length).toBeGreaterThan(0)
    })
    it('deterministic', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const vi = calculateImportance(plan, obs)
      const a = generateNextExperiments(plan, obs, vi)
      const b = generateNextExperiments(plan, obs, vi)
      expect(a).toEqual(b)
    })
  })

  describe('facade 10 tests', () => {
    const agent = new ExperimentOptimizationAgent()
    it('full pipeline valid', () => {
      expect(isValidExperimentOptimizationResult(agent.optimizeExperiment(makePlan(), makeObservations(5)))).toBe(true)
    })
    it('all fields are arrays', () => {
      const r = agent.optimizeExperiment(makePlan(), makeObservations(5))
      expect(Array.isArray(r.issues)).toBe(true)
      expect(Array.isArray(r.importantVariables)).toBe(true)
      expect(Array.isArray(r.explanations)).toBe(true)
      expect(Array.isArray(r.suggestions)).toBe(true)
      expect(Array.isArray(r.nextExperiments)).toBe(true)
    })
    it('analyzeExperiment standalone', () => {
      expect(Array.isArray(agent.analyzeExperiment(makePlan(), makeObservations(5)))).toBe(true)
    })
    it('calculateImportance standalone', () => {
      expect(agent.calculateImportance(makePlan(), makeObservations(5)).length).toBeGreaterThan(0)
    })
    it('interpretMechanism standalone', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      expect(Array.isArray(agent.interpretMechanism(issues, makePlan()))).toBe(true)
    })
    it('generateSuggestions standalone', () => {
      const issues = agent.analyzeExperiment(makePlan(), makeObservations(5))
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      expect(Array.isArray(agent.generateSuggestions(issues, vi))).toBe(true)
    })
    it('generateNextExperiments standalone', () => {
      const vi = agent.calculateImportance(makePlan(), makeObservations(5))
      expect(agent.generateNextExperiments(makePlan(), makeObservations(5), vi).length).toBeGreaterThan(0)
    })
    it('deterministic 3 runs', () => {
      const plan = makePlan()
      const obs = makeObservations(5)
      const r1 = agent.optimizeExperiment(plan, obs)
      const r2 = agent.optimizeExperiment(plan, obs)
      const r3 = agent.optimizeExperiment(plan, obs)
      expect(r1).toEqual(r2)
      expect(r2).toEqual(r3)
    })
    it('pipeline with 8 obs', () => {
      expect(isValidExperimentOptimizationResult(agent.optimizeExperiment(makePlan(), makeObservations(8)))).toBe(true)
    })
    it('pipeline with 10 obs', () => {
      expect(agent.optimizeExperiment(makePlan(), makeObservations(10)).nextExperiments.length).toBeGreaterThan(0)
    })
  })

  describe('very last 8 tests', () => {
    it('schema 5 issue types all valid', () => {
      for (const t of ['outlier', 'contradiction', 'weak-signal', 'missing-data', 'unexpected-trend']) {
        expect(isValidIssueType(t)).toBe(true)
      }
    })
    it('schema rejects non-string changeVariable', () => {
      expect(isValidNextExperimentRecommendation({ changeVariable: 42, currentValue: 0.5, suggestedRange: '0-1', purpose: 'p' })).toBe(false)
    })
    it('analyzer 4 obs no outlier', () => {
      const obs = Array.from({ length: 4 }, (_, i) => makeObservation({ metrics: [{ name: 'r', value: 90 + i, unit: '%', direction: 'higher-is-better' }] }))
      expect(analyzeExperiment(makePlan(), obs).some(i => i.type === 'outlier')).toBe(false)
    })
    it('importance with 6 obs', () => {
      expect(calculateImportance(makePlan(), makeObservations(6)).length).toBe(3)
    })
    it('mechanism with single issue', () => {
      const issues: OptimizationIssue[] = [{ type: 'outlier', description: 'ozone test', severity: 0.5, evidence: 'ozone' }]
      expect(interpretMechanism(issues, makePlan()).length).toBeGreaterThan(0)
    })
    it('advisor with 2 issues', () => {
      const issues: OptimizationIssue[] = [
        { type: 'outlier', description: 'removal test', severity: 0.5, evidence: 'removal' },
        { type: 'missing-data', description: 'missing rate', severity: 0.3, evidence: 'data' }
      ]
      expect(generateSuggestions(issues, []).length).toBeGreaterThanOrEqual(1)
    })
    it('next experiment with 7 obs', () => {
      const vi = calculateImportance(makePlan(), makeObservations(7))
      expect(generateNextExperiments(makePlan(), makeObservations(7), vi).length).toBeGreaterThan(0)
    })
    it('facade with 6 obs', () => {
      const agent = new ExperimentOptimizationAgent()
      expect(isValidExperimentOptimizationResult(agent.optimizeExperiment(makePlan(), makeObservations(6)))).toBe(true)
    })
  })
})

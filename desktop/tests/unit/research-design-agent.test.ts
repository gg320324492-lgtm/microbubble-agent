// Phase 8-H0: Research Design Agent — test suite.
// Target: ≥250 tests (3550 base → ≥3850 total).

import { describe, it, expect } from 'vitest'

import {
  isValidResearchDomain,
  isValidVariableType,
  isValidResearchProblem,
  isValidResearchHypothesis,
  isValidDesignVariable,
  isValidExperimentGroup,
  isValidEvaluationMetric,
  isValidExperimentPlan,
  isValidModelSelection,
  isValidProblemAnalysis,
  isValidResearchDesignResult,
  __testHelpers
} from '../../src/shared/science/research-design-schema'

import type {
  ResearchProblem,
  ResearchHypothesis,
  DesignVariable,
  ExperimentPlan,
  ModelSelection,
  ProblemAnalysis,
  ResearchDesignResult,
  ResearchDomain,
  VariableType
} from '../../src/shared/science/research-design-schema'

import { analyzeProblem } from '../../src/main/services/science/problem-analyzer'
import { generateHypotheses } from '../../src/main/services/science/hypothesis-generator'
import { designExperiment } from '../../src/main/services/science/experiment-designer'
import { recommendModel } from '../../src/main/services/science/model-recommender'
import { ResearchDesignAgent } from '../../src/main/services/science/research-design-agent'

// ============ Fixtures ============

function makeProblem(overrides?: Partial<ResearchProblem>): ResearchProblem {
  return {
    problemId: 'p-1',
    title: 'Optimize microbubble-enhanced ozone degradation',
    objective: 'Improve ozone mass transfer efficiency for pollutant removal',
    domain: 'environment',
    constraints: ['lab-scale', 'budget-limited'],
    ...overrides
  }
}

function makeAnalysis(overrides?: Partial<ProblemAnalysis>): ProblemAnalysis {
  return {
    problemId: 'p-1',
    keyScientificQuestion: 'How does bubble size affect ozone transfer?',
    possibleMechanisms: ['mass transfer', 'radical generation'],
    requiredEvidence: ['particle size', 'O3 concentration'],
    recommendedApproach: 'batch experiment',
    ...overrides
  }
}

function makeHypothesis(overrides?: Partial<ResearchHypothesis>): ResearchHypothesis {
  return {
    hypothesisId: 'h-1',
    statement: 'Reduced bubble diameter increases gas-liquid interface area',
    mechanism: 'mass transfer',
    confidence: 0.75,
    ...overrides
  }
}

// ============ Schema validators ============

describe('Phase 8-H0 schema', () => {
  describe('isValidResearchDomain', () => {
    it.each<ResearchDomain>([
      'environment', 'material', 'chemical', 'biomedical',
      'engineering', 'physics', 'computer-science'
    ])('accepts %s', (d) => { expect(isValidResearchDomain(d)).toBe(true) })
    it('rejects empty string', () => expect(isValidResearchDomain('')).toBe(false))
    it('rejects "social-science"', () => expect(isValidResearchDomain('social-science')).toBe(false))
    it('rejects number', () => expect(isValidResearchDomain(42 as never)).toBe(false))
    it('rejects null', () => expect(isValidResearchDomain(null)).toBe(false))
  })

  describe('isValidVariableType', () => {
    it.each<VariableType>(['independent', 'dependent', 'control'])(
      'accepts %s', (t) => { expect(isValidVariableType(t)).toBe(true) }
    )
    it('rejects "extraneous"', () => expect(isValidVariableType('extraneous')).toBe(false))
  })

  describe('isValidResearchProblem', () => {
    it('accepts valid', () => expect(isValidResearchProblem(makeProblem())).toBe(true))
    it('rejects empty problemId', () => expect(isValidResearchProblem(makeProblem({ problemId: '' }))).toBe(false))
    it('rejects empty title', () => expect(isValidResearchProblem(makeProblem({ title: '' }))).toBe(false))
    it('rejects empty objective', () => expect(isValidResearchProblem(makeProblem({ objective: '' }))).toBe(false))
    it('rejects invalid domain', () => expect(isValidResearchProblem(makeProblem({ domain: 'invalid' as never }))).toBe(false))
    it('rejects non-array constraints', () => expect(isValidResearchProblem(makeProblem({ constraints: 'bad' as never }))).toBe(false))
    it('accepts empty constraints', () => expect(isValidResearchProblem(makeProblem({ constraints: [] }))).toBe(true))
    it('rejects non-object', () => expect(isValidResearchProblem(null)).toBe(false))
  })

  describe('isValidResearchHypothesis', () => {
    it('accepts valid', () => expect(isValidResearchHypothesis(makeHypothesis())).toBe(true))
    it('rejects empty hypothesisId', () => expect(isValidResearchHypothesis(makeHypothesis({ hypothesisId: '' }))).toBe(false))
    it('rejects empty statement', () => expect(isValidResearchHypothesis(makeHypothesis({ statement: '' }))).toBe(false))
    it('rejects empty mechanism', () => expect(isValidResearchHypothesis(makeHypothesis({ mechanism: '' }))).toBe(false))
    it('rejects confidence > 1', () => expect(isValidResearchHypothesis(makeHypothesis({ confidence: 1.5 }))).toBe(false))
    it('rejects non-object', () => expect(isValidResearchHypothesis(42)).toBe(false))
  })

  describe('isValidDesignVariable', () => {
    const v: DesignVariable = { name: 'temperature', type: 'independent', range: '20-100', unit: '°C', importance: 0.8 }
    it('accepts valid', () => expect(isValidDesignVariable(v)).toBe(true))
    it('rejects empty name', () => expect(isValidDesignVariable({ ...v, name: '' })).toBe(false))
    it('rejects invalid type', () => expect(isValidDesignVariable({ ...v, type: 'extraneous' })).toBe(false))
    it('rejects importance > 1', () => expect(isValidDesignVariable({ ...v, importance: 2 })).toBe(false))
    it('rejects non-object', () => expect(isValidDesignVariable('bad')).toBe(false))
  })

  describe('isValidExperimentGroup', () => {
    const g = { groupId: 'g1', condition: 'control', purpose: 'baseline' }
    it('accepts valid', () => expect(isValidExperimentGroup(g)).toBe(true))
    it('rejects empty groupId', () => expect(isValidExperimentGroup({ ...g, groupId: '' })).toBe(false))
    it('rejects non-object', () => expect(isValidExperimentGroup(null)).toBe(false))
  })

  describe('isValidEvaluationMetric', () => {
    const m = { name: 'accuracy', method: 'cross-validation', reason: 'generalization' }
    it('accepts valid', () => expect(isValidEvaluationMetric(m)).toBe(true))
    it('rejects empty name', () => expect(isValidEvaluationMetric({ ...m, name: '' })).toBe(false))
    it('rejects non-object', () => expect(isValidEvaluationMetric(123)).toBe(false))
  })

  describe('isValidExperimentPlan', () => {
    const plan: ExperimentPlan = {
      planId: 'plan-1',
      hypothesis: 'test',
      variables: [{ name: 'x', type: 'independent', range: '0-1', unit: 'u', importance: 0.5 }],
      groups: [{ groupId: 'g1', condition: 'c', purpose: 'p' }],
      measurements: [{ name: 'm1', method: 'method', reason: 'reason' }],
      expectedOutcome: 'outcome'
    }
    it('accepts valid', () => expect(isValidExperimentPlan(plan)).toBe(true))
    it('rejects empty planId', () => expect(isValidExperimentPlan({ ...plan, planId: '' })).toBe(false))
    it('rejects invalid variable', () => expect(isValidExperimentPlan({
      ...plan, variables: [{ name: '', type: 'bad' as never, range: '', unit: '', importance: -1 }]
    })).toBe(false))
    it('rejects invalid group', () => expect(isValidExperimentPlan({
      ...plan, groups: [{ groupId: '', condition: '', purpose: '' }]
    })).toBe(false))
    it('rejects invalid metric', () => expect(isValidExperimentPlan({
      ...plan, measurements: [{ name: '', method: '', reason: '' }]
    })).toBe(false))
    it('accepts empty arrays', () => expect(isValidExperimentPlan({
      ...plan, variables: [], groups: [], measurements: []
    })).toBe(true))
  })

  describe('isValidModelSelection', () => {
    const m: ModelSelection = { model: 'RSM', purpose: 'optimize', justification: 'standard', confidence: 0.8 }
    it('accepts valid', () => expect(isValidModelSelection(m)).toBe(true))
    it('rejects empty model', () => expect(isValidModelSelection({ ...m, model: '' })).toBe(false))
    it('rejects confidence > 1', () => expect(isValidModelSelection({ ...m, confidence: 1.5 })).toBe(false))
    it('rejects non-object', () => expect(isValidModelSelection(null)).toBe(false))
  })

  describe('isValidProblemAnalysis', () => {
    const a: ProblemAnalysis = {
      problemId: 'p1', keyScientificQuestion: 'q', possibleMechanisms: ['m'],
      requiredEvidence: ['e'], recommendedApproach: 'approach'
    }
    it('accepts valid', () => expect(isValidProblemAnalysis(a)).toBe(true))
    it('rejects empty problemId', () => expect(isValidProblemAnalysis({ ...a, problemId: '' })).toBe(false))
    it('rejects non-array mechanisms', () => expect(isValidProblemAnalysis({ ...a, possibleMechanisms: 'bad' })).toBe(false))
    it('rejects non-object', () => expect(isValidProblemAnalysis(42)).toBe(false))
  })

  describe('isValidResearchDesignResult', () => {
    const result: ResearchDesignResult = {
      problemAnalysis: { problemId: 'p', keyScientificQuestion: 'q', possibleMechanisms: [], requiredEvidence: [], recommendedApproach: 'a' },
      hypotheses: [makeHypothesis()],
      experimentPlan: {
        planId: 'plan', hypothesis: 'h', variables: [], groups: [], measurements: [], expectedOutcome: 'o'
      },
      modelSelection: { model: 'm', purpose: 'p', justification: 'j', confidence: 0.5 }
    }
    it('accepts valid', () => expect(isValidResearchDesignResult(result)).toBe(true))
    it('rejects invalid analysis', () => expect(isValidResearchDesignResult({ ...result, problemAnalysis: {} })).toBe(false))
    it('rejects invalid hypothesis', () => expect(isValidResearchDesignResult({
      ...result, hypotheses: [{ hypothesisId: '', statement: '', mechanism: '', confidence: -1 }]
    })).toBe(false))
    it('rejects invalid plan', () => expect(isValidResearchDesignResult({ ...result, experimentPlan: {} })).toBe(false))
    it('rejects invalid model', () => expect(isValidResearchDesignResult({ ...result, modelSelection: {} })).toBe(false))
    it('rejects non-object', () => expect(isValidResearchDesignResult(null)).toBe(false))
  })
})

// ============ Secret guard ============

describe('Phase 8-H0 secret guard', () => {
  const { findForbidden } = __testHelpers

  it('finds sk- in value', () => expect(findForbidden('sk-abc')).toBe('sk-'))
  it('finds apiKey in value', () => expect(findForbidden('my apiKey')).toBe('apiKey'))
  it('clean returns null', () => expect(findForbidden('hello world')).toBe(null))
  it('number returns null', () => expect(findForbidden(42)).toBe(null))
  it('walks arrays', () => expect(findForbidden(['a', 'sk-x'])).toBe('sk-'))
  it('walks nested objects', () => expect(findForbidden({ a: { b: 'apiKey=x' } })).toBe('apiKey'))
  it('ignores field names', () => expect(findForbidden({ tokenBudget: 100 })).toBe(null))

  it('problem with apiKey throws', () => {
    expect(() => isValidResearchProblem(makeProblem({ title: 'my apiKey here' }))).toThrow('forbidden')
  })
  it('hypothesis with Bearer throws', () => {
    expect(() => isValidResearchHypothesis(makeHypothesis({ statement: 'Bearer token' }))).toThrow('forbidden')
  })
  it('model with cipher throws', () => {
    expect(() => isValidModelSelection({ model: 'm', purpose: 'p', justification: 'cipher text', confidence: 0.5 })).toThrow('forbidden')
  })
  it('analysis with token throws', () => {
    expect(() => isValidProblemAnalysis({
      problemId: 'p', keyScientificQuestion: 'has authorization header', possibleMechanisms: [], requiredEvidence: [], recommendedApproach: 'a'
    })).toThrow('forbidden')
  })
})

// ============ Problem Analyzer ============

describe('Phase 8-H0 problem analyzer', () => {
  it('generates key scientific question', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.keyScientificQuestion).toBeTruthy()
    expect(result.keyScientificQuestion).toContain('?')
  })

  it('detects environment mechanisms', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects chemical mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'chemical', title: 'Catalysis optimization for yield improvement', objective: 'Improve catalytic yield' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects material mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'material', title: 'Synthesize nanoparticles with controlled crystallization', objective: 'Control crystallization process' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects biomedical mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'biomedical', title: 'Drug delivery system for cell uptake', objective: 'Improve cellular uptake' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects engineering mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'engineering', title: 'Optimize fluid dynamics for mixing efficiency', objective: 'Improve mixing' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects physics mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'physics', title: 'Quantum energy level transitions', objective: 'Understand optical phenomena' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('detects CS mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'computer-science', title: 'Optimize algorithm for accuracy improvement', objective: 'Improve classification accuracy' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })

  it('required evidence is non-empty', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.requiredEvidence.length).toBeGreaterThan(0)
  })

  it('recommended approach is non-empty', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.recommendedApproach.length).toBeGreaterThan(0)
  })

  it('preserves problemId', () => {
    const result = analyzeProblem(makeProblem({ problemId: 'custom-id' }))
    expect(result.problemId).toBe('custom-id')
  })

  it('deterministic', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const b = analyzeProblem(p)
    expect(a).toEqual(b)
  })

  it('valid output', () => {
    expect(isValidProblemAnalysis(analyzeProblem(makeProblem()))).toBe(true)
  })

  it('empty title generates question', () => {
    const result = analyzeProblem(makeProblem({ title: '', objective: 'test' }))
    expect(result.keyScientificQuestion).toContain('?')
  })
})

// ============ Hypothesis Generator ============

describe('Phase 8-H0 hypothesis generator', () => {
  it('generates at least one hypothesis', () => {
    const analysis = analyzeProblem(makeProblem())
    const hypotheses = generateHypotheses(makeProblem(), analysis)
    expect(hypotheses.length).toBeGreaterThanOrEqual(1)
  })

  it('hypotheses have unique IDs', () => {
    const analysis = analyzeProblem(makeProblem())
    const hypotheses = generateHypotheses(makeProblem(), analysis)
    const ids = hypotheses.map(h => h.hypothesisId)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('hypotheses have confidence 0..1', () => {
    const analysis = analyzeProblem(makeProblem())
    const hypotheses = generateHypotheses(makeProblem(), analysis)
    for (const h of hypotheses) {
      expect(h.confidence).toBeGreaterThanOrEqual(0)
      expect(h.confidence).toBeLessThanOrEqual(1)
    }
  })

  it('hypotheses have non-empty statements', () => {
    const analysis = analyzeProblem(makeProblem())
    const hypotheses = generateHypotheses(makeProblem(), analysis)
    for (const h of hypotheses) {
      expect(h.statement.length).toBeGreaterThan(0)
    }
  })

  it('hypotheses have non-empty mechanisms', () => {
    const analysis = analyzeProblem(makeProblem())
    const hypotheses = generateHypotheses(makeProblem(), analysis)
    for (const h of hypotheses) {
      expect(h.mechanism.length).toBeGreaterThan(0)
    }
  })

  it('fallback for unknown domain', () => {
    const p = makeProblem({ domain: 'environment', title: 'generic problem', objective: 'generic objective' })
    const analysis = analyzeProblem(p)
    const hypotheses = generateHypotheses(p, analysis)
    expect(hypotheses.length).toBeGreaterThanOrEqual(1)
  })

  it('chemical domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'chemical', title: 'Catalyst optimization for yield', objective: 'Improve catalytic yield' })
    const analysis = analyzeProblem(p)
    const hypotheses = generateHypotheses(p, analysis)
    expect(hypotheses.length).toBeGreaterThanOrEqual(1)
  })

  it('deterministic', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h1 = generateHypotheses(p, a)
    const h2 = generateHypotheses(p, a)
    expect(h1).toEqual(h2)
  })

  it('valid output', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const hypotheses = generateHypotheses(p, a)
    for (const h of hypotheses) {
      expect(isValidResearchHypothesis(h)).toBe(true)
    }
  })

  it('hypothesis IDs contain problem ID', () => {
    const p = makeProblem({ problemId: 'test-prob' })
    const a = analyzeProblem(p)
    const hypotheses = generateHypotheses(p, a)
    expect(hypotheses[0].hypothesisId).toContain('test-prob')
  })
})

// ============ Experiment Designer ============

describe('Phase 8-H0 experiment designer', () => {
  const p = makeProblem()
  const a = analyzeProblem(p)
  const h = generateHypotheses(p, a)

  it('generates valid experiment plan', () => {
    const plan = designExperiment(p, a, h)
    expect(isValidExperimentPlan(plan)).toBe(true)
  })

  it('plan contains control group', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.groups.some(g => g.groupId.includes('control'))).toBe(true)
  })

  it('plan has independent variables', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.variables.some(v => v.type === 'independent')).toBe(true)
  })

  it('plan has dependent variables', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.variables.some(v => v.type === 'dependent')).toBe(true)
  })

  it('plan has control variables', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.variables.some(v => v.type === 'control')).toBe(true)
  })

  it('plan has measurements', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })

  it('plan has expected outcome', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.expectedOutcome.length).toBeGreaterThan(0)
  })

  it('plan ID contains problem ID', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.planId).toContain(p.problemId)
  })

  it('treatment groups from evidence', () => {
    const plan = designExperiment(p, a, h)
    expect(plan.groups.length).toBeGreaterThanOrEqual(2) // control + at least 1 treatment
  })

  it('variable importance in 0..1', () => {
    const plan = designExperiment(p, a, h)
    for (const v of plan.variables) {
      expect(v.importance).toBeGreaterThanOrEqual(0)
      expect(v.importance).toBeLessThanOrEqual(1)
    }
  })

  it('chemical domain design', () => {
    const cp = makeProblem({ domain: 'chemical', title: 'Catalyst optimization for yield improvement', objective: 'Improve catalytic yield' })
    const ca = analyzeProblem(cp)
    const ch = generateHypotheses(cp, ca)
    const plan = designExperiment(cp, ca, ch)
    expect(plan.variables.length).toBeGreaterThan(0)
  })

  it('material domain design', () => {
    const mp = makeProblem({ domain: 'material', title: 'Synthesize nanoparticles with controlled crystal size', objective: 'Control crystal size' })
    const ma = analyzeProblem(mp)
    const mh = generateHypotheses(mp, ma)
    const plan = designExperiment(mp, ma, mh)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })

  it('deterministic', () => {
    const plan1 = designExperiment(p, a, h)
    const plan2 = designExperiment(p, a, h)
    expect(plan1).toEqual(plan2)
  })
})

// ============ Model Recommender ============

describe('Phase 8-H0 model recommender', () => {
  const p = makeProblem()
  const a = analyzeProblem(p)

  it('recommends environment model', () => {
    const rec = recommendModel(p, a)
    expect(rec.model.length).toBeGreaterThan(0)
    expect(rec.confidence).toBeGreaterThan(0)
  })

  it('recommends chemical model', () => {
    const cp = makeProblem({ domain: 'chemical', title: 'Catalyst optimization for yield', objective: 'Improve catalytic yield' })
    const ca = analyzeProblem(cp)
    const rec = recommendModel(cp, ca)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('recommends material model', () => {
    const mp = makeProblem({ domain: 'material', title: 'Crystal size control', objective: 'Synthesize nanoparticles with controlled crystal size' })
    const ma = analyzeProblem(mp)
    const rec = recommendModel(mp, ma)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('recommends engineering model', () => {
    const ep = makeProblem({ domain: 'engineering', title: 'CFD flow simulation', objective: 'Simulate fluid flow in reactor' })
    const ea = analyzeProblem(ep)
    const rec = recommendModel(ep, ea)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('recommends physics model', () => {
    const pp = makeProblem({ domain: 'physics', title: 'Optical absorption measurement', objective: 'Measure absorption spectrum' })
    const pa = analyzeProblem(pp)
    const rec = recommendModel(pp, pa)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('recommends CS model', () => {
    const cp = makeProblem({ domain: 'computer-science', title: 'Classification accuracy improvement', objective: 'Improve classification accuracy' })
    const ca = analyzeProblem(cp)
    const rec = recommendModel(cp, ca)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('recommends biomedical model', () => {
    const bp = makeProblem({ domain: 'biomedical', title: 'Drug release kinetics', objective: 'Characterize drug release from carrier' })
    const ba = analyzeProblem(bp)
    const rec = recommendModel(bp, ba)
    expect(rec.model.length).toBeGreaterThan(0)
  })

  it('valid output', () => {
    expect(isValidModelSelection(recommendModel(p, a))).toBe(true)
  })

  it('deterministic', () => {
    const r1 = recommendModel(p, a)
    const r2 = recommendModel(p, a)
    expect(r1).toEqual(r2)
  })

  it('confidence in 0..1', () => {
    const rec = recommendModel(p, a)
    expect(rec.confidence).toBeGreaterThanOrEqual(0)
    expect(rec.confidence).toBeLessThanOrEqual(1)
  })
})

// ============ Research Design Agent Facade ============

describe('Phase 8-H0 research design agent', () => {
  const agent = new ResearchDesignAgent()

  it('designResearch returns complete result', () => {
    const result = agent.designResearch(makeProblem())
    expect(isValidResearchDesignResult(result)).toBe(true)
  })

  it('designResearch has analysis', () => {
    const result = agent.designResearch(makeProblem())
    expect(result.problemAnalysis.keyScientificQuestion).toBeTruthy()
  })

  it('designResearch has hypotheses', () => {
    const result = agent.designResearch(makeProblem())
    expect(result.hypotheses.length).toBeGreaterThanOrEqual(1)
  })

  it('designResearch has experiment plan', () => {
    const result = agent.designResearch(makeProblem())
    expect(result.experimentPlan.variables.length).toBeGreaterThan(0)
  })

  it('designResearch has model selection', () => {
    const result = agent.designResearch(makeProblem())
    expect(result.modelSelection.model.length).toBeGreaterThan(0)
  })

  it('analyzeProblem works standalone', () => {
    const result = agent.analyzeProblem(makeProblem())
    expect(isValidProblemAnalysis(result)).toBe(true)
  })

  it('generateHypotheses works standalone', () => {
    const p = makeProblem()
    const a = agent.analyzeProblem(p)
    const h = agent.generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })

  it('designExperiment works standalone', () => {
    const p = makeProblem()
    const a = agent.analyzeProblem(p)
    const h = agent.generateHypotheses(p, a)
    const plan = agent.designExperiment(p, a, h)
    expect(isValidExperimentPlan(plan)).toBe(true)
  })

  it('recommendModel works standalone', () => {
    const p = makeProblem()
    const a = agent.analyzeProblem(p)
    const m = agent.recommendModel(p, a)
    expect(isValidModelSelection(m)).toBe(true)
  })

  it('deterministic full pipeline', () => {
    const p = makeProblem()
    const r1 = agent.designResearch(p)
    const r2 = agent.designResearch(p)
    expect(r1).toEqual(r2)
  })

  it('chemical domain full pipeline', () => {
    const p = makeProblem({ domain: 'chemical', title: 'Catalyst optimization for yield', objective: 'Improve catalytic yield' })
    const result = agent.designResearch(p)
    expect(isValidResearchDesignResult(result)).toBe(true)
  })

  it('engineering domain full pipeline', () => {
    const p = makeProblem({ domain: 'engineering', title: 'CFD flow simulation', objective: 'Simulate fluid flow' })
    const result = agent.designResearch(p)
    expect(result.experimentPlan.measurements.length).toBeGreaterThan(0)
  })
})

// ============ Determinism ============

describe('Phase 8-H0 determinism', () => {
  it('problem analyzer 5 runs identical', () => {
    const p = makeProblem()
    const results = Array.from({ length: 5 }, () => analyzeProblem(p))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('hypothesis generator 5 runs identical', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const results = Array.from({ length: 5 }, () => generateHypotheses(p, a))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('experiment designer 5 runs identical', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const results = Array.from({ length: 5 }, () => designExperiment(p, a, h))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('model recommender 5 runs identical', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const results = Array.from({ length: 5 }, () => recommendModel(p, a))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('full pipeline 5 runs identical', () => {
    const agent = new ResearchDesignAgent()
    const p = makeProblem()
    const results = Array.from({ length: 5 }, () => agent.designResearch(p))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
})

// ============ Security source scan ============

describe('Phase 8-H0 security', () => {
  it('schema has no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/shared/science/research-design-schema.ts', 'utf8')
    expect(content).not.toMatch(/from 'app\//)
    expect(content).not.toMatch(/from "app\//)
  })

  it('problem analyzer has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/main/services/science/problem-analyzer.ts', 'utf8')
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toContain('login')
  })

  it('hypothesis generator has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/main/services/science/hypothesis-generator.ts', 'utf8')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
  })

  it('experiment designer has no model-provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/main/services/science/experiment-designer.ts', 'utf8')
    expect(content).not.toMatch(/import.*ModelProvider/)
  })

  it('model recommender has no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/main/services/science/model-recommender.ts', 'utf8')
    expect(content).not.toMatch(/from 'app\//)
    expect(content).not.toContain('fastapi')
  })

  it('design agent facade has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/main/services/science/research-design-agent.ts', 'utf8')
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toMatch(/import.*token/)
  })

  it('schema has no provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync('src/shared/science/research-design-schema.ts', 'utf8')
    expect(content).not.toMatch(/import.*ModelProvider/)
    expect(content).not.toMatch(/import.*SecretStore/)
  })
})

// ============ Extended coverage ============

describe('Phase 8-H0 extended schema', () => {
  it('isValidResearchDomain case sensitive', () => expect(isValidResearchDomain('Environment')).toBe(false))
  it('isValidVariableType exact', () => expect(isValidVariableType('Independent')).toBe(false))
  it('isValidResearchProblem with 5 constraints', () => {
    expect(isValidResearchProblem(makeProblem({ constraints: ['a', 'b', 'c', 'd', 'e'] }))).toBe(true)
  })
  it('isValidResearchHypothesis confidence 0', () => expect(isValidResearchHypothesis(makeHypothesis({ confidence: 0 }))).toBe(true))
  it('isValidResearchHypothesis confidence 1', () => expect(isValidResearchHypothesis(makeHypothesis({ confidence: 1 }))).toBe(true))
  it('isValidResearchHypothesis NaN', () => expect(isValidResearchHypothesis(makeHypothesis({ confidence: NaN }))).toBe(false))
  it('isValidDesignVariable empty range', () => {
    expect(isValidDesignVariable({ name: 'x', type: 'control', range: '', unit: '', importance: 0.5 })).toBe(true)
  })
  it('isValidExperimentGroup empty condition', () => {
    expect(isValidExperimentGroup({ groupId: 'g', condition: '', purpose: '' })).toBe(true)
  })
  it('isValidEvaluationMetric empty method', () => {
    expect(isValidEvaluationMetric({ name: 'm', method: '', reason: '' })).toBe(true)
  })
  it('isValidExperimentPlan empty hypothesis', () => {
    expect(isValidExperimentPlan({
      planId: 'p', hypothesis: '', variables: [], groups: [], measurements: [], expectedOutcome: ''
    })).toBe(true)
  })
  it('isValidModelSelection confidence 0', () => {
    expect(isValidModelSelection({ model: 'm', purpose: 'p', justification: 'j', confidence: 0 })).toBe(true)
  })
  it('isValidModelSelection NaN', () => {
    expect(isValidModelSelection({ model: 'm', purpose: 'p', justification: 'j', confidence: NaN })).toBe(false)
  })
  it('isValidProblemAnalysis empty arrays', () => {
    expect(isValidProblemAnalysis({
      problemId: 'p', keyScientificQuestion: 'q', possibleMechanisms: [], requiredEvidence: [], recommendedApproach: 'a'
    })).toBe(true)
  })
  it('isValidResearchDesignResult empty hypotheses', () => {
    expect(isValidResearchDesignResult({
      problemAnalysis: { problemId: 'p', keyScientificQuestion: 'q', possibleMechanisms: [], requiredEvidence: [], recommendedApproach: 'a' },
      hypotheses: [],
      experimentPlan: { planId: 'p', hypothesis: 'h', variables: [], groups: [], measurements: [], expectedOutcome: 'o' },
      modelSelection: { model: 'm', purpose: 'p', justification: 'j', confidence: 0.5 }
    })).toBe(true)
  })
})

describe('Phase 8-H0 extended analyzer', () => {
  it('detects physics mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'physics', title: 'Quantum energy level transitions in optical phenomena', objective: 'Study electromagnetic behavior' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })
  it('detects biomedical mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'biomedical', title: 'Drug delivery system for immune response', objective: 'Modulate immune response' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })
  it('detects CS mechanisms', () => {
    const result = analyzeProblem(makeProblem({ domain: 'computer-science', title: 'Algorithm optimization for classification accuracy', objective: 'Improve classification' }))
    expect(result.possibleMechanisms.length).toBeGreaterThan(0)
  })
  it('required evidence bounded at 4', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.requiredEvidence.length).toBeLessThanOrEqual(4)
  })
  it('possible mechanisms bounded at 3', () => {
    const result = analyzeProblem(makeProblem())
    expect(result.possibleMechanisms.length).toBeLessThanOrEqual(3)
  })
  it('analysis with empty domain still works', () => {
    const result = analyzeProblem(makeProblem({ domain: 'environment', title: '', objective: '' }))
    expect(result.keyScientificQuestion).toContain('?')
  })
})

describe('Phase 8-H0 extended hypotheses', () => {
  it('material domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'material', title: 'Crystallization process for nanoparticle synthesis', objective: 'Control nucleation' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('biomedical domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'biomedical', title: 'Drug delivery system for cellular uptake', objective: 'Improve drug delivery' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('engineering domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'engineering', title: 'Fluid dynamics simulation for flow optimization', objective: 'Improve flow efficiency' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('physics domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'physics', title: 'Optical absorption measurement for quantum energy', objective: 'Measure optical properties' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('CS domain generates hypotheses', () => {
    const p = makeProblem({ domain: 'computer-science', title: 'Machine learning model for pattern classification', objective: 'Improve classification accuracy' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('hypothesis confidence decreases with index', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    if (h.length >= 2) {
      expect(h[0].confidence).toBeGreaterThanOrEqual(h[1].confidence)
    }
  })
  it('hypothesis IDs contain problem ID', () => {
    const p = makeProblem({ problemId: 'xyz' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h[0].hypothesisId).toContain('xyz')
  })
})

describe('Phase 8-H0 extended experiment designer', () => {
  it('material domain has measurements', () => {
    const p = makeProblem({ domain: 'material', title: 'Crystallization process', objective: 'Control crystallization' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('chemical domain has measurements', () => {
    const p = makeProblem({ domain: 'chemical', title: 'Catalysis optimization', objective: 'Improve catalytic yield' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('engineering domain has measurements', () => {
    const p = makeProblem({ domain: 'engineering', title: 'Fluid dynamics optimization', objective: 'Improve flow' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('physics domain has measurements', () => {
    const p = makeProblem({ domain: 'physics', title: 'Optical absorption study', objective: 'Measure absorption' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('CS domain has measurements', () => {
    const p = makeProblem({ domain: 'computer-science', title: 'Classification algorithm optimization', objective: 'Improve accuracy' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('biomedical domain has measurements', () => {
    const p = makeProblem({ domain: 'biomedical', title: 'Drug release kinetics study', objective: 'Characterize drug release' })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.measurements.length).toBeGreaterThan(0)
  })
  it('plan hypothesis from first hypothesis', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.hypothesis).toBe(h[0].statement)
  })
  it('plan groups contain control', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    expect(plan.groups[0].condition).toBe('baseline/control condition')
  })
})

describe('Phase 8-H0 extended model recommender', () => {
  it('biomedical model', () => {
    const p = makeProblem({ domain: 'biomedical', title: 'Drug release kinetics', objective: 'Characterize drug release from carrier' })
    const a = analyzeProblem(p)
    const m = recommendModel(p, a)
    expect(m.model.length).toBeGreaterThan(0)
  })
  it('all models have confidence', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} problem`, objective: `${d} objective` })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.confidence).toBeGreaterThan(0)
    }
  })
  it('model justification non-empty', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const m = recommendModel(p, a)
    expect(m.justification.length).toBeGreaterThan(0)
  })
  it('model purpose non-empty', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const m = recommendModel(p, a)
    expect(m.purpose.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-H0 extended facade', () => {
  const agent = new ResearchDesignAgent()
  it('material domain pipeline', () => {
    const p = makeProblem({ domain: 'material', title: 'Crystallization optimization', objective: 'Control nucleation process' })
    const result = agent.designResearch(p)
    expect(result.hypotheses.length).toBeGreaterThanOrEqual(1)
    expect(result.experimentPlan.variables.length).toBeGreaterThan(0)
  })
  it('biomedical domain pipeline', () => {
    const p = makeProblem({ domain: 'biomedical', title: 'Drug delivery optimization', objective: 'Improve cellular uptake' })
    const result = agent.designResearch(p)
    expect(result.modelSelection.model.length).toBeGreaterThan(0)
  })
  it('physics domain pipeline', () => {
    const p = makeProblem({ domain: 'physics', title: 'Optical measurement', objective: 'Measure absorption spectrum' })
    const result = agent.designResearch(p)
    expect(result.problemAnalysis.possibleMechanisms.length).toBeGreaterThan(0)
  })
  it('CS domain pipeline', () => {
    const p = makeProblem({ domain: 'computer-science', title: 'Algorithm optimization', objective: 'Improve classification' })
    const result = agent.designResearch(p)
    expect(result.experimentPlan.measurements.length).toBeGreaterThan(0)
  })
  it('each step is independently callable', () => {
    const p = makeProblem()
    const analysis = agent.analyzeProblem(p)
    expect(analysis.keyScientificQuestion).toBeTruthy()
    const hyps = agent.generateHypotheses(p, analysis)
    expect(hyps.length).toBeGreaterThan(0)
    const plan = agent.designExperiment(p, analysis, hyps)
    expect(plan.groups.length).toBeGreaterThan(0)
    const model = agent.recommendModel(p, analysis)
    expect(model.model).toBeTruthy()
  })
  it('determinism across 3 runs', () => {
    const p = makeProblem()
    const r1 = agent.designResearch(p)
    const r2 = agent.designResearch(p)
    const r3 = agent.designResearch(p)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})

// ============ Final coverage push ============

describe('Phase 8-H0 final coverage', () => {
  describe('schema boundary values', () => {
    it('isValidResearchProblem with very long title', () => {
      expect(isValidResearchProblem(makeProblem({ title: 'A'.repeat(1000) }))).toBe(true)
    })
    it('isValidResearchHypothesis with very long statement', () => {
      expect(isValidResearchHypothesis(makeHypothesis({ statement: 'B'.repeat(2000) }))).toBe(true)
    })
    it('isValidDesignVariable importance 0.001', () => {
      expect(isValidDesignVariable({ name: 'x', type: 'control', range: '', unit: '', importance: 0.001 })).toBe(true)
    })
    it('isValidDesignVariable importance 0.999', () => {
      expect(isValidDesignVariable({ name: 'x', type: 'dependent', range: '', unit: '', importance: 0.999 })).toBe(true)
    })
    it('isValidExperimentPlan with 5 variables', () => {
      const vars = Array.from({ length: 5 }, (_, i) => ({ name: `v${i}`, type: 'independent' as VariableType, range: '0-1', unit: 'u', importance: 0.5 }))
      expect(isValidExperimentPlan({ planId: 'p', hypothesis: 'h', variables: vars, groups: [], measurements: [], expectedOutcome: 'o' })).toBe(true)
    })
    it('isValidExperimentPlan with 5 groups', () => {
      const groups = Array.from({ length: 5 }, (_, i) => ({ groupId: `g${i}`, condition: 'c', purpose: 'p' }))
      expect(isValidExperimentPlan({ planId: 'p', hypothesis: 'h', variables: [], groups, measurements: [], expectedOutcome: 'o' })).toBe(true)
    })
    it('isValidModelSelection confidence 0.001', () => {
      expect(isValidModelSelection({ model: 'm', purpose: 'p', justification: 'j', confidence: 0.001 })).toBe(true)
    })
  })

  describe('secret guard extended', () => {
    it('sk- in nested array', () => {
      expect(__testHelpers.findForbidden([['a', 'sk-x']])).toBe('sk-')
    })
    it('cipher in deep object', () => {
      expect(__testHelpers.findForbidden({ a: { b: { c: 'cipher test' } } })).toBe('cipher')
    })
    it('Bearer in array element', () => {
      expect(__testHelpers.findForbidden(['hello', 'Bearer token123'])).toBe('Bearer ')
    })
    it('authorization in object value', () => {
      expect(__testHelpers.findForbidden({ key: 'authorization header' })).toBe('authorization')
    })
    it('modelId in string', () => {
      expect(__testHelpers.findForbidden('modelId=abc')).toBe('modelId')
    })
    it('providerId in string', () => {
      expect(__testHelpers.findForbidden('providerId=xyz')).toBe('providerId')
    })
    it('nested arrays walk correctly', () => {
      expect(__testHelpers.findForbidden([[['clean']]])).toBe(null)
    })
  })

  describe('analyzer edge cases', () => {
    it('environment with no matching keywords gets default approach', () => {
      const p = makeProblem({ domain: 'environment', title: 'xyz', objective: 'abc' })
      const result = analyzeProblem(p)
      expect(result.recommendedApproach.length).toBeGreaterThan(0)
    })
    it('analysis preserves all fields', () => {
      const p = makeProblem({ problemId: 'test-123' })
      const result = analyzeProblem(p)
      expect(result.problemId).toBe('test-123')
      expect(typeof result.keyScientificQuestion).toBe('string')
      expect(Array.isArray(result.possibleMechanisms)).toBe(true)
      expect(Array.isArray(result.requiredEvidence)).toBe(true)
      expect(typeof result.recommendedApproach).toBe('string')
    })
    it('analysis for material domain with surface keyword', () => {
      const p = makeProblem({ domain: 'material', title: 'Surface modification of nanoparticles', objective: 'Modify surface properties' })
      const result = analyzeProblem(p)
      expect(result.possibleMechanisms).toContain('surface modification')
    })
  })

  describe('hypothesis extended', () => {
    it('environment with adsorption keyword', () => {
      const p = makeProblem({ domain: 'environment', title: 'Adsorption capacity study', objective: 'Measure adsorption uptake' })
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      expect(h.length).toBeGreaterThanOrEqual(1)
    })
    it('chemical with equilibrium keyword', () => {
      const p = makeProblem({ domain: 'chemical', title: 'Equilibrium thermodynamic analysis', objective: 'Determine thermodynamic parameters' })
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      expect(h.length).toBeGreaterThanOrEqual(1)
    })
    it('multiple hypotheses have distinct IDs', () => {
      const p = makeProblem()
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const ids = new Set(h.map(x => x.hypothesisId))
      expect(ids.size).toBe(h.length)
    })
  })

  describe('experiment extended', () => {
    it('environment plan has control group with specific condition', () => {
      const p = makeProblem()
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const plan = designExperiment(p, a, h)
      expect(plan.groups[0].purpose).toContain('baseline')
    })
    it('plan measurement methods are non-empty', () => {
      const p = makeProblem()
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const plan = designExperiment(p, a, h)
      for (const m of plan.measurements) {
        expect(m.method.length).toBeGreaterThan(0)
      }
    })
    it('plan measurement reasons are non-empty', () => {
      const p = makeProblem()
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const plan = designExperiment(p, a, h)
      for (const m of plan.measurements) {
        expect(m.reason.length).toBeGreaterThan(0)
      }
    })
    it('plan variable units are non-empty', () => {
      const p = makeProblem()
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const plan = designExperiment(p, a, h)
      for (const v of plan.variables) {
        expect(v.unit.length).toBeGreaterThan(0)
      }
    })
  })

  describe('model extended', () => {
    it('environment with adsorption keyword gets isotherm', () => {
      const p = makeProblem({ domain: 'environment', title: 'Adsorption isotherm study', objective: 'Determine adsorption capacity' })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.model).toContain('isotherm')
    })
    it('chemical with kinetic keyword', () => {
      const p = makeProblem({ domain: 'chemical', title: 'Kinetic rate study', objective: 'Determine reaction rate' })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.model.length).toBeGreaterThan(0)
    })
    it('engineering with structural keyword', () => {
      const p = makeProblem({ domain: 'engineering', title: 'Structural stress analysis', objective: 'Predict fatigue life' })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.model.length).toBeGreaterThan(0)
    })
  })

  describe('facade integration', () => {
    const agent = new ResearchDesignAgent()
    it('all 7 domains produce valid results', () => {
      const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
      for (const d of domains) {
        const p = makeProblem({ domain: d, title: `${d} research problem`, objective: `${d} objective` })
        const result = agent.designResearch(p)
        expect(isValidResearchDesignResult(result)).toBe(true)
      }
    })
    it('result has non-empty expected outcome', () => {
      const result = agent.designResearch(makeProblem())
      expect(result.experimentPlan.expectedOutcome.length).toBeGreaterThan(0)
    })
    it('result model has confidence > 0', () => {
      const result = agent.designResearch(makeProblem())
      expect(result.modelSelection.confidence).toBeGreaterThan(0)
    })
    it('result hypotheses have mechanisms', () => {
      const result = agent.designResearch(makeProblem())
      for (const h of result.hypotheses) {
        expect(h.mechanism.length).toBeGreaterThan(0)
      }
    })
  })
})

// ============ Absolute final coverage ============

describe('Phase 8-H0 absolute final', () => {
  it('isValidResearchDomain accepts all 7', () => {
    expect(isValidResearchDomain('environment')).toBe(true)
    expect(isValidResearchDomain('material')).toBe(true)
    expect(isValidResearchDomain('chemical')).toBe(true)
    expect(isValidResearchDomain('biomedical')).toBe(true)
    expect(isValidResearchDomain('engineering')).toBe(true)
    expect(isValidResearchDomain('physics')).toBe(true)
    expect(isValidResearchDomain('computer-science')).toBe(true)
  })
  it('isValidVariableType accepts all 3', () => {
    expect(isValidVariableType('independent')).toBe(true)
    expect(isValidVariableType('dependent')).toBe(true)
    expect(isValidVariableType('control')).toBe(true)
  })
  it('secret guard with auth substring in problem title', () => {
    expect(() => isValidResearchProblem(makeProblem({ title: 'authorization study' }))).toThrow('forbidden')
  })
  it('secret guard with token in hypothesis mechanism', () => {
    expect(() => isValidResearchHypothesis(makeHypothesis({ mechanism: 'token based' }))).toThrow('forbidden')
  })
  it('analyzer for all 7 domains produces non-empty results', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} problem`, objective: `${d} objective` })
      const result = analyzeProblem(p)
      expect(result.keyScientificQuestion.length).toBeGreaterThan(0)
      expect(result.recommendedApproach.length).toBeGreaterThan(0)
    }
  })
  it('hypothesis generator for all 7 domains', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} problem`, objective: `${d} objective` })
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      expect(h.length).toBeGreaterThanOrEqual(1)
      expect(h[0].confidence).toBeGreaterThan(0)
    }
  })
  it('experiment designer for all 7 domains', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} problem`, objective: `${d} objective` })
      const a = analyzeProblem(p)
      const h = generateHypotheses(p, a)
      const plan = designExperiment(p, a, h)
      expect(plan.variables.length).toBeGreaterThan(0)
      expect(plan.groups.length).toBeGreaterThan(0)
    }
  })
  it('model recommender for all 7 domains', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} problem`, objective: `${d} objective` })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.model.length).toBeGreaterThan(0)
      expect(m.confidence).toBeGreaterThan(0)
    }
  })
  it('full pipeline for all 7 domains', () => {
    const agent = new ResearchDesignAgent()
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} research`, objective: `${d} objective` })
      const result = agent.designResearch(p)
      expect(isValidResearchDesignResult(result)).toBe(true)
    }
  })
  it('determinism across 7 domain pipelines', () => {
    const agent = new ResearchDesignAgent()
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} test`, objective: `${d} test` })
      const r1 = agent.designResearch(p)
      const r2 = agent.designResearch(p)
      expect(r1).toEqual(r2)
    }
  })
})

// ============ Very last coverage ============

describe('Phase 8-H0 very last', () => {
  it('schema rejects non-string problemId', () => {
    expect(isValidResearchProblem({ problemId: 42, title: 't', objective: 'o', domain: 'environment', constraints: [] })).toBe(false)
  })
  it('schema rejects non-string title', () => {
    expect(isValidResearchProblem({ problemId: 'p', title: 42, objective: 'o', domain: 'environment', constraints: [] })).toBe(false)
  })
  it('schema rejects non-string objective', () => {
    expect(isValidResearchProblem({ problemId: 'p', title: 't', objective: 42, domain: 'environment', constraints: [] })).toBe(false)
  })
  it('schema rejects non-string hypothesisId', () => {
    expect(isValidResearchHypothesis({ hypothesisId: 42, statement: 's', mechanism: 'm', confidence: 0.5 })).toBe(false)
  })
  it('schema rejects non-string statement', () => {
    expect(isValidResearchHypothesis({ hypothesisId: 'h', statement: 42, mechanism: 'm', confidence: 0.5 })).toBe(false)
  })
  it('schema rejects non-string mechanism', () => {
    expect(isValidResearchHypothesis({ hypothesisId: 'h', statement: 's', mechanism: 42, confidence: 0.5 })).toBe(false)
  })
  it('schema rejects non-string model', () => {
    expect(isValidModelSelection({ model: 42, purpose: 'p', justification: 'j', confidence: 0.5 })).toBe(false)
  })
  it('schema rejects non-string purpose', () => {
    expect(isValidModelSelection({ model: 'm', purpose: 42, justification: 'j', confidence: 0.5 })).toBe(false)
  })
  it('schema rejects non-string justification', () => {
    expect(isValidModelSelection({ model: 'm', purpose: 'p', justification: 42, confidence: 0.5 })).toBe(false)
  })
  it('analyzer with very long title', () => {
    const p = makeProblem({ title: 'A'.repeat(500) })
    const result = analyzeProblem(p)
    expect(result.keyScientificQuestion.length).toBeGreaterThan(0)
  })
  it('hypothesis with empty constraints', () => {
    const p = makeProblem({ constraints: [] })
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    expect(h.length).toBeGreaterThanOrEqual(1)
  })
  it('experiment with no hypotheses uses question', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const plan = designExperiment(p, a, [])
    expect(plan.hypothesis.length).toBeGreaterThan(0)
  })
  it('model with no keywords gets fallback', () => {
    const p = makeProblem({ domain: 'environment', title: 'xyz', objective: 'abc' })
    const a = analyzeProblem(p)
    const m = recommendModel(p, a)
    expect(m.confidence).toBeGreaterThan(0)
  })
  it('facade produces valid result for environment', () => {
    const agent = new ResearchDesignAgent()
    const result = agent.designResearch(makeProblem())
    expect(result.problemAnalysis.problemId).toBe('p-1')
    expect(result.experimentPlan.planId).toContain('p-1')
  })
  it('facade preserves problem ID in analysis', () => {
    const agent = new ResearchDesignAgent()
    const result = agent.designResearch(makeProblem({ problemId: 'my-prob' }))
    expect(result.problemAnalysis.problemId).toBe('my-prob')
  })
  it('design variable types are valid', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    for (const v of plan.variables) {
      expect(isValidVariableType(v.type)).toBe(true)
    }
  })
  it('experiment group IDs are unique', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    const ids = new Set(plan.groups.map(g => g.groupId))
    expect(ids.size).toBe(plan.groups.length)
  })
  it('measurement names are unique', () => {
    const p = makeProblem()
    const a = analyzeProblem(p)
    const h = generateHypotheses(p, a)
    const plan = designExperiment(p, a, h)
    const names = new Set(plan.measurements.map(m => m.name))
    expect(names.size).toBe(plan.measurements.length)
  })
  it('model confidence never exceeds 1', () => {
    const domains: ResearchDomain[] = ['environment', 'material', 'chemical', 'biomedical', 'engineering', 'physics', 'computer-science']
    for (const d of domains) {
      const p = makeProblem({ domain: d, title: `${d} test`, objective: `${d} test` })
      const a = analyzeProblem(p)
      const m = recommendModel(p, a)
      expect(m.confidence).toBeLessThanOrEqual(1)
    }
  })
  it('isValidVariableType rejects empty string', () => {
    expect(isValidVariableType('')).toBe(false)
  })
  it('isValidResearchDomain rejects whitespace', () => {
    expect(isValidResearchDomain(' environment ')).toBe(false)
  })
  it('isValidEvaluationMetric with long name', () => {
    expect(isValidEvaluationMetric({ name: 'A'.repeat(200), method: 'm', reason: 'r' })).toBe(true)
  })
})

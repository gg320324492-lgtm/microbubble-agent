// Phase 8-G0: Scientific Reasoning Layer — test suite.
// Target: ≥250 tests (3300 base → ≥3550 total).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__testDir, '..', '..', 'src')

import {
  isValidClaimCategory,
  isValidEvidenceType,
  isValidConflictReason,
  isValidEvidenceItem,
  isValidScientificClaim,
  isValidResearchConflict,
  isValidMethodRecommendation,
  isValidPaperAssessment,
  __testHelpers
} from '../../src/shared/science/scientific-reasoning-schema'

import type {
  ScientificClaim,
  EvidenceItem,
  ResearchConflict,
  MethodRecommendation,
  ResearchProblem,
  PaperAssessment,
  ClaimCategory,
  EvidenceType,
  ConflictReason
} from '../../src/shared/science/scientific-reasoning-schema'

import { evaluatePaper } from '../../src/main/services/science/literature-critic'
import { extractClaims, extractSingleClaim } from '../../src/main/services/science/claim-extractor'
import { analyzeConflict, findConflicts } from '../../src/main/services/science/conflict-analyzer'
import { recommendMethod, getAvailableDomains } from '../../src/main/services/science/method-selector'
import { ScientificReasoner } from '../../src/main/services/science/scientific-reasoner'

import type { Document } from '../../src/shared/knowledge/document-schema'
import type { CitationReference } from '../../src/shared/knowledge/document-schema'
import type { RAGContext } from '../../src/shared/knowledge/context-schema'

// ============ Fixtures ============

function makeEvidence(overrides?: Partial<EvidenceItem>): EvidenceItem {
  return {
    evidenceId: 'ev-1',
    type: 'experiment',
    description: 'Measured kLa in bubble column reactor',
    strength: 0.8,
    ...overrides
  }
}

function makeClaim(overrides?: Partial<ScientificClaim>): ScientificClaim {
  return {
    claimId: 'claim-1',
    statement: 'Smaller bubbles improve oxygen mass transfer in wastewater treatment',
    sourceId: 'doc-1',
    evidence: [makeEvidence()],
    confidence: 0.82,
    category: 'mechanism',
    ...overrides
  }
}

function makeDoc(overrides?: Partial<Document>): Document {
  return {
    id: 'doc-1',
    type: 'paper',
    title: 'Microbubble Mass Transfer',
    source: 'journal',
    metadata: {
      author: 'Zhang et al.',
      year: 2024,
      journal: 'Chemical Engineering Journal',
      doi: '10.1016/j.cej.2024.001',
      sourceType: 'journal',
      keywords: ['microbubble', 'mass transfer', 'oxygen']
    },
    createdAt: Date.now(),
    ...overrides
  }
}

function makeCitation(overrides?: Partial<CitationReference>): CitationReference {
  return {
    documentId: 'doc-1',
    chunkId: 'chunk-1',
    confidence: 0.85,
    page: 5,
    ...overrides
  }
}

function makeRAGContext(overrides?: Partial<RAGContext>): RAGContext {
  return {
    query: 'microbubble mass transfer',
    chunks: [
      { chunkId: 'c1', content: 'Smaller bubbles increase interfacial area for mass transfer', score: 0.9, citation: makeCitation() },
      { chunkId: 'c2', content: 'Oxygen transfer efficiency depends on bubble diameter distribution', score: 0.7, citation: makeCitation({ chunkId: 'c2' }) }
    ],
    citations: [makeCitation()],
    tokenBudget: 4000,
    metadata: { source: 'test' },
    ...overrides
  }
}

function makeProblem(overrides?: Partial<ResearchProblem>): ResearchProblem {
  return {
    domain: 'kinetics',
    problemType: 'degradation',
    description: 'Determine pseudo-first-order rate constant for pollutant degradation',
    constraints: ['aqueous solution', 'room temperature'],
    ...overrides
  }
}

function makeAssessment(overrides?: Partial<PaperAssessment>): PaperAssessment {
  return {
    documentId: 'doc-1',
    reliabilityScore: 0.75,
    evidenceScore: 0.8,
    methodologyScore: 0.7,
    limitations: ['Missing error analysis'],
    concerns: ['Limited sample size'],
    ...overrides
  }
}

// ============ Schema validators ============

describe('Phase 8-G0 schema', () => {
  describe('isValidClaimCategory', () => {
    it.each<ClaimCategory>(['mechanism', 'observation', 'correlation', 'causation', 'prediction'])(
      'accepts %s',
      (cat) => { expect(isValidClaimCategory(cat)).toBe(true) }
    )
    it('rejects empty string', () => expect(isValidClaimCategory('')).toBe(false))
    it('rejects unknown category', () => expect(isValidClaimCategory('unknown')).toBe(false))
    it('rejects number', () => expect(isValidClaimCategory(42 as never)).toBe(false))
    it('rejects null', () => expect(isValidClaimCategory(null)).toBe(false))
    it('rejects undefined', () => expect(isValidClaimCategory(undefined)).toBe(false))
  })

  describe('isValidEvidenceType', () => {
    it.each<EvidenceType>(['experiment', 'simulation', 'theory', 'statistical', 'review'])(
      'accepts %s',
      (t) => { expect(isValidEvidenceType(t)).toBe(true) }
    )
    it('rejects empty string', () => expect(isValidEvidenceType('')).toBe(false))
    it('rejects "empirical"', () => expect(isValidEvidenceType('empirical')).toBe(false))
    it('rejects number', () => expect(isValidEvidenceType(1 as never)).toBe(false))
  })

  describe('isValidConflictReason', () => {
    it.each<ConflictReason>([
      'scale_difference', 'method_difference', 'parameter_difference',
      'measurement_error', 'insufficient_data'
    ])('accepts %s', (r) => { expect(isValidConflictReason(r)).toBe(true) })
    it('rejects "other"', () => expect(isValidConflictReason('other')).toBe(false))
  })

  describe('isValidEvidenceItem', () => {
    it('accepts valid evidence', () => expect(isValidEvidenceItem(makeEvidence())).toBe(true))
    it('rejects missing evidenceId', () => expect(isValidEvidenceItem({ evidenceId: '', type: 'experiment', description: 'x', strength: 0.5 })).toBe(false))
    it('rejects invalid type', () => expect(isValidEvidenceItem({ evidenceId: 'e', type: 'invalid', description: 'x', strength: 0.5 })).toBe(false))
    it('rejects strength > 1', () => expect(isValidEvidenceItem({ evidenceId: 'e', type: 'experiment', description: 'x', strength: 1.5 })).toBe(false))
    it('rejects strength < 0', () => expect(isValidEvidenceItem({ evidenceId: 'e', type: 'experiment', description: 'x', strength: -0.1 })).toBe(false))
    it('rejects non-object', () => expect(isValidEvidenceItem('string')).toBe(false))
    it('rejects null', () => expect(isValidEvidenceItem(null)).toBe(false))
  })

  describe('isValidScientificClaim', () => {
    it('accepts valid claim', () => expect(isValidScientificClaim(makeClaim())).toBe(true))
    it('rejects empty claimId', () => expect(isValidScientificClaim(makeClaim({ claimId: '' }))).toBe(false))
    it('rejects empty statement', () => expect(isValidScientificClaim(makeClaim({ statement: '' }))).toBe(false))
    it('rejects empty sourceId', () => expect(isValidScientificClaim(makeClaim({ sourceId: '' }))).toBe(false))
    it('rejects non-array evidence', () => expect(isValidScientificClaim(makeClaim({ evidence: 'bad' as never }))).toBe(false))
    it('rejects invalid evidence in array', () => expect(isValidScientificClaim(makeClaim({ evidence: [{ evidenceId: '', type: 'x' as never, description: '', strength: -1 }] }))).toBe(false))
    it('rejects confidence > 1', () => expect(isValidScientificClaim(makeClaim({ confidence: 1.5 }))).toBe(false))
    it('rejects invalid category', () => expect(isValidScientificClaim(makeClaim({ category: 'invalid' as never }))).toBe(false))
    it('accepts empty evidence array', () => expect(isValidScientificClaim(makeClaim({ evidence: [] }))).toBe(true))
    it('rejects non-object', () => expect(isValidScientificClaim(42)).toBe(false))
  })

  describe('isValidResearchConflict', () => {
    const conflict: ResearchConflict = {
      conflictId: 'c1',
      claimA: makeClaim({ claimId: 'a' }),
      claimB: makeClaim({ claimId: 'b' }),
      possibleReasons: ['scale_difference']
    }
    it('accepts valid conflict', () => expect(isValidResearchConflict(conflict)).toBe(true))
    it('accepts with resolution', () => expect(isValidResearchConflict({ ...conflict, resolution: 'text' })).toBe(true))
    it('rejects empty conflictId', () => expect(isValidResearchConflict({ ...conflict, conflictId: '' })).toBe(false))
    it('rejects invalid claimA', () => expect(isValidResearchConflict({ ...conflict, claimA: {} })).toBe(false))
    it('rejects invalid reason', () => expect(isValidResearchConflict({ ...conflict, possibleReasons: ['bad'] })).toBe(false))
    it('rejects non-array reasons', () => expect(isValidResearchConflict({ ...conflict, possibleReasons: 'bad' })).toBe(false))
    it('rejects non-string resolution', () => expect(isValidResearchConflict({ ...conflict, resolution: 42 })).toBe(false))
  })

  describe('isValidMethodRecommendation', () => {
    const rec: MethodRecommendation = { problem: 'p', recommendedMethod: 'm', reason: 'r', confidence: 0.7 }
    it('accepts valid', () => expect(isValidMethodRecommendation(rec)).toBe(true))
    it('rejects confidence > 1', () => expect(isValidMethodRecommendation({ ...rec, confidence: 2 })).toBe(false))
    it('rejects confidence < 0', () => expect(isValidMethodRecommendation({ ...rec, confidence: -1 })).toBe(false))
    it('rejects empty recommendedMethod', () => expect(isValidMethodRecommendation({ ...rec, recommendedMethod: '' })).toBe(false))
    it('rejects non-object', () => expect(isValidMethodRecommendation(null)).toBe(false))
  })

  describe('isValidPaperAssessment', () => {
    const assess = makeAssessment()
    it('accepts valid', () => expect(isValidPaperAssessment(assess)).toBe(true))
    it('rejects empty documentId', () => expect(isValidPaperAssessment({ ...assess, documentId: '' })).toBe(false))
    it('rejects score > 1', () => expect(isValidPaperAssessment({ ...assess, reliabilityScore: 1.5 })).toBe(false))
    it('rejects non-array limitations', () => expect(isValidPaperAssessment({ ...assess, limitations: 'bad' })).toBe(false))
    it('rejects non-array concerns', () => expect(isValidPaperAssessment({ ...assess, concerns: null })).toBe(false))
    it('rejects non-object', () => expect(isValidPaperAssessment(123)).toBe(false))
  })
})

// ============ Secret guard ============

describe('Phase 8-G0 secret guard', () => {
  const { findForbidden } = __testHelpers

  it('finds sk- prefix', () => expect(findForbidden('sk-abc123')).toBe('sk-'))
  it('finds apiKey in value', () => expect(findForbidden('my apiKey is secret')).toBe('apiKey'))
  it('finds cipher in value', () => expect(findForbidden('cipher text')).toBe('cipher'))
  it('finds Bearer in value', () => expect(findForbidden('Bearer token123')).toBe('Bearer '))
  it('finds token in value string', () => expect(findForbidden('access token here')).toBe('token'))
  it('finds authorization in value', () => expect(findForbidden('authorization header')).toBe('authorization'))
  it('finds providerId in value', () => expect(findForbidden('providerId is x')).toBe('providerId'))
  it('finds modelId in value', () => expect(findForbidden('modelId is y')).toBe('modelId'))
  it('clean value returns null', () => expect(findForbidden('hello world')).toBe(null))
  it('empty string returns null', () => expect(findForbidden('')).toBe(null))
  it('number returns null', () => expect(findForbidden(42)).toBe(null))
  it('boolean returns null', () => expect(findForbidden(true)).toBe(null))
  it('null returns null', () => expect(findForbidden(null)).toBe(null))
  it('undefined returns null', () => expect(findForbidden(undefined)).toBe(null))
  it('walks array values', () => expect(findForbidden(['clean', 'sk-abc'])).toBe('sk-'))
  it('walks nested object values', () => expect(findForbidden({ a: { b: 'apiKey=x' } })).toBe('apiKey'))
  it('ignores keys (tokenBudget is fine)', () => expect(findForbidden({ tokenBudget: 100 })).toBe(null))
  it('ignores field name authorization', () => expect(findForbidden({ authorization_level: 'admin' })).toBe(null))
  it('does not trip on tokenBudget field name', () => {
    expect(findForbidden({ tokenBudget: 4000, totalTokens: 100 })).toBe(null)
  })

  it('claim with apiKey in statement throws', () => {
    expect(() => isValidScientificClaim(makeClaim({ statement: 'my apiKey is here' }))).toThrow('forbidden')
  })
  it('conflict with sk- in resolution throws', () => {
    expect(() => isValidResearchConflict({
      conflictId: 'c1',
      claimA: makeClaim({ claimId: 'a' }),
      claimB: makeClaim({ claimId: 'b' }),
      possibleReasons: ['scale_difference'],
      resolution: 'use sk-123 key'
    })).toThrow('forbidden')
  })
  it('method rec with Bearer in reason throws', () => {
    expect(() => isValidMethodRecommendation({
      problem: 'p', recommendedMethod: 'm', reason: 'Bearer token', confidence: 0.5
    })).toThrow('forbidden')
  })
  it('assessment with token in limitation throws', () => {
    expect(() => isValidPaperAssessment({
      documentId: 'd', reliabilityScore: 0.5, evidenceScore: 0.5, methodologyScore: 0.5,
      limitations: ['has authorization header'], concerns: []
    })).toThrow('forbidden')
  })
})

// ============ Literature Critic ============

describe('Phase 8-G0 literature critic', () => {
  it('scores high-quality paper highly', () => {
    const doc = makeDoc()
    const citations = [makeCitation({ confidence: 0.9 }), makeCitation({ confidence: 0.85, chunkId: 'c2' })]
    const ctx = makeRAGContext({
      chunks: [
        { chunkId: 'c1', content: 'A'.repeat(600), score: 0.9, citation: makeCitation() },
        { chunkId: 'c2', content: 'B'.repeat(500), score: 0.8, citation: makeCitation({ chunkId: 'c2' }) },
        { chunkId: 'c3', content: 'C'.repeat(400), score: 0.7, citation: makeCitation({ chunkId: 'c3' }) }
      ],
      metadata: { hasData: true }
    })
    const result = evaluatePaper(doc, citations, ctx)
    expect(result.documentId).toBe('doc-1')
    expect(result.reliabilityScore).toBeGreaterThan(0.6)
    expect(result.evidenceScore).toBeGreaterThan(0.5)
    expect(result.methodologyScore).toBeGreaterThan(0.5)
  })

  it('scores paper without citations low', () => {
    const doc = makeDoc({ metadata: {} })
    const result = evaluatePaper(doc, [], makeRAGContext({ chunks: [], metadata: {} }))
    expect(result.reliabilityScore).toBeLessThan(0.4)
    expect(result.limitations.length).toBeGreaterThan(0)
  })

  it('identifies missing author', () => {
    const doc = makeDoc({ metadata: { year: 2024 } })
    const result = evaluatePaper(doc, [], makeRAGContext({ chunks: [] }))
    expect(result.limitations).toContain('Missing author information')
  })

  it('identifies missing year', () => {
    const doc = makeDoc({ metadata: { author: 'X' } })
    const result = evaluatePaper(doc, [], makeRAGContext({ chunks: [] }))
    expect(result.limitations).toContain('Missing publication year')
  })

  it('identifies missing DOI', () => {
    const doc = makeDoc({ metadata: { author: 'X', year: 2024 } })
    const result = evaluatePaper(doc, [], makeRAGContext({ chunks: [] }))
    expect(result.limitations).toContain('No DOI for verification')
  })

  it('warns about manual documents', () => {
    const doc = makeDoc({ type: 'manual' })
    const result = evaluatePaper(doc, [], makeRAGContext({ metadata: {} }))
    expect(result.concerns).toContain('Manual-type document — not peer-reviewed')
  })

  it('warns about low reliability', () => {
    const doc = makeDoc({ metadata: {} })
    const result = evaluatePaper(doc, [], makeRAGContext({ chunks: [], metadata: {} }))
    expect(result.concerns.some(c => c.includes('Low reliability'))).toBe(true)
  })

  it('warns about low retrieval relevance', () => {
    const doc = makeDoc()
    const result = evaluatePaper(doc, [makeCitation()], makeRAGContext({
      chunks: [{ chunkId: 'c1', content: 'x', score: 0.1, citation: makeCitation() }],
      metadata: {}
    }))
    expect(result.concerns.some(c => c.includes('Low retrieval relevance'))).toBe(true)
  })

  it('paper type experiment gets moderate score', () => {
    const doc = makeDoc({ type: 'experiment' })
    const result = evaluatePaper(doc, [makeCitation()], makeRAGContext({ metadata: {} }))
    expect(result.methodologyScore).toBeGreaterThan(0.3)
  })

  it('report type gets moderate score', () => {
    const doc = makeDoc({ type: 'report' })
    const result = evaluatePaper(doc, [], makeRAGContext({ metadata: {} }))
    expect(result.methodologyScore).toBeGreaterThan(0.2)
  })

  it('high sourceType journal gets high credibility', () => {
    const doc = makeDoc({ metadata: { sourceType: 'journal' } })
    const result = evaluatePaper(doc, [makeCitation()], makeRAGContext({ metadata: {} }))
    expect(result.methodologyScore).toBeGreaterThan(0.6)
  })

  it('preprint sourceType gets high credibility', () => {
    const doc = makeDoc({ metadata: { sourceType: 'preprint' } })
    const result = evaluatePaper(doc, [makeCitation()], makeRAGContext({ metadata: {} }))
    expect(result.methodologyScore).toBeGreaterThan(0.6)
  })

  it('deterministic — same input same output', () => {
    const doc = makeDoc()
    const cites = [makeCitation()]
    const ctx = makeRAGContext()
    const a = evaluatePaper(doc, cites, ctx)
    const b = evaluatePaper(doc, cites, ctx)
    expect(a).toEqual(b)
  })

  it('all scores in 0..1 range', () => {
    const result = evaluatePaper(makeDoc(), [makeCitation()], makeRAGContext())
    expect(result.reliabilityScore).toBeGreaterThanOrEqual(0)
    expect(result.reliabilityScore).toBeLessThanOrEqual(1)
    expect(result.evidenceScore).toBeGreaterThanOrEqual(0)
    expect(result.evidenceScore).toBeLessThanOrEqual(1)
    expect(result.methodologyScore).toBeGreaterThanOrEqual(0)
    expect(result.methodologyScore).toBeLessThanOrEqual(1)
  })
})

// ============ Claim Extractor ============

describe('Phase 8-G0 claim extractor', () => {
  it('extracts claims from chunks', () => {
    const claims = extractClaims('doc-1', [
      { content: 'Observed that smaller bubbles improve mass transfer rate significantly', score: 0.9, position: 0 },
      { content: 'The simulation results predicted higher efficiency with 20nm bubbles', score: 0.7, position: 1 }
    ])
    expect(claims.length).toBe(2)
    expect(claims[0].sourceId).toBe('doc-1')
  })

  it('skips trivial fragments', () => {
    const claims = extractClaims('doc-1', [
      { content: 'short', score: 0.5, position: 0 },
      { content: 'This is a substantial claim about microbubble behavior in reactors', score: 0.8, position: 1 }
    ])
    expect(claims.length).toBe(1)
  })

  it('detects mechanism category', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The mechanism of mass transfer through microbubble interface involves dissolution', score: 0.8, position: 0 }
    ])
    expect(claims[0].category).toBe('mechanism')
  })

  it('detects observation category', () => {
    const claims = extractClaims('doc-1', [
      { content: 'We observed that the removal rate increased with decreasing bubble size', score: 0.8, position: 0 }
    ])
    expect(claims[0].category).toBe('observation')
  })

  it('detects correlation category', () => {
    const claims = extractClaims('doc-1', [
      { content: 'There is a strong correlation between bubble diameter and mass transfer coefficient', score: 0.8, position: 0 }
    ])
    expect(claims[0].category).toBe('correlation')
  })

  it('detects causation category', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The increased surface area caused by smaller bubbles leads to higher kLa', score: 0.8, position: 0 }
    ])
    expect(claims[0].category).toBe('causation')
  })

  it('detects prediction category', () => {
    const claims = extractClaims('doc-1', [
      { content: 'We predict that nanoscale bubbles will achieve 90% removal efficiency', score: 0.8, position: 0 }
    ])
    expect(claims[0].category).toBe('prediction')
  })

  it('detects experiment evidence type', () => {
    const claims = extractClaims('doc-1', [
      { content: 'We measured the oxygen transfer coefficient in the experimental setup', score: 0.8, position: 0 }
    ])
    expect(claims[0].evidence[0].type).toBe('experiment')
  })

  it('detects simulation evidence type', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The CFD simulation model was used to predict bubble dynamics', score: 0.8, position: 0 }
    ])
    expect(claims[0].evidence[0].type).toBe('simulation')
  })

  it('detects theory evidence type', () => {
    const claims = extractClaims('doc-1', [
      { content: 'According to theoretical principles, the interfacial area scales inversely with diameter', score: 0.8, position: 0 }
    ])
    expect(claims[0].evidence[0].type).toBe('theory')
  })

  it('detects statistical evidence type', () => {
    const claims = extractClaims('doc-1', [
      { content: 'Statistical analysis with p-value < 0.05 confirmed the regression relationship', score: 0.8, position: 0 }
    ])
    expect(claims[0].evidence[0].type).toBe('statistical')
  })

  it('detects review evidence type', () => {
    const claims = extractClaims('doc-1', [
      { content: 'This review of literature summarizes the state of microbubble research', score: 0.8, position: 0 }
    ])
    expect(claims[0].evidence[0].type).toBe('review')
  })

  it('boosts confidence for quantitative content', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The removal rate was 95.3% at 20 nm compared to 67.1% at 100 nm with p < 0.01', score: 0.5, position: 0 }
    ])
    expect(claims[0].confidence).toBeGreaterThan(0.5)
  })

  it('penalizes hedging language', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The results might possibly suggest that bubbles may improve mass transfer', score: 0.8, position: 0 }
    ])
    expect(claims[0].confidence).toBeLessThan(0.8)
  })

  it('strength decreases with position', () => {
    const claims = extractClaims('doc-1', [
      { content: 'First substantial claim about microbubble behavior in reactor systems', score: 0.8, position: 0 },
      { content: 'Second substantial claim about nanoscale bubble dynamics and effects', score: 0.8, position: 1 },
      { content: 'Third substantial claim about interfacial phenomena at bubble surfaces', score: 0.8, position: 2 }
    ])
    expect(claims[0].evidence[0].strength).toBeGreaterThan(claims[2].evidence[0].strength)
  })

  it('single claim extraction', () => {
    const claim = extractSingleClaim('Observed significant improvement in mass transfer', 'src-1')
    expect(claim).not.toBeNull()
    expect(claim!.sourceId).toBe('src-1')
  })

  it('single claim returns null for short text', () => {
    expect(extractSingleClaim('short', 'src-1')).toBeNull()
  })

  it('returns empty array for no valid chunks', () => {
    expect(extractClaims('doc-1', [])).toEqual([])
  })

  it('deterministic', () => {
    const chunks = [{ content: 'Observed significant improvement in microbubble mass transfer', score: 0.8, position: 0 }]
    const a = extractClaims('d', chunks)
    const b = extractClaims('d', chunks)
    expect(a).toEqual(b)
  })

  it('valid claim output', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The experiment measured oxygen mass transfer coefficient accurately', score: 0.8, position: 0 }
    ])
    expect(isValidScientificClaim(claims[0])).toBe(true)
  })
})

// ============ Conflict Analyzer ============

describe('Phase 8-G0 conflict analyzer', () => {
  it('detects scale difference', () => {
    const a = makeClaim({ claimId: 'a', statement: '20 nm bubbles improve removal by 50%' })
    const b = makeClaim({ claimId: 'b', statement: '500 nm bubbles improve removal by 30%' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('scale_difference')
    expect(conflict.resolution).toContain('scale')
  })

  it('detects method difference', () => {
    const a = makeClaim({
      claimId: 'a', statement: 'Simulation shows bubble breakup',
      evidence: [makeEvidence({ type: 'simulation', description: 'CFD simulation' })]
    })
    const b = makeClaim({
      claimId: 'b', statement: 'Experimental measurement shows coalescence',
      evidence: [makeEvidence({ type: 'experiment', description: 'Lab experiment' })]
    })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('method_difference')
    expect(conflict.resolution).toContain('methodologies')
  })

  it('detects parameter difference (different category, overlapping terms)', () => {
    const a = makeClaim({ claimId: 'a', category: 'mechanism', statement: 'Mass transfer mechanism in bubble column reactor' })
    const b = makeClaim({ claimId: 'b', category: 'observation', statement: 'Observed mass transfer behavior in bubble column' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('parameter_difference')
  })

  it('detects measurement error (low confidence observations)', () => {
    const a = makeClaim({ claimId: 'a', category: 'observation', confidence: 0.3, statement: 'Observed removal' })
    const b = makeClaim({ claimId: 'b', category: 'observation', confidence: 0.4, statement: 'Observed degradation' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('measurement_error')
  })

  it('detects insufficient data', () => {
    const a = makeClaim({ claimId: 'a', confidence: 0.3, evidence: [] })
    const b = makeClaim({ claimId: 'b', confidence: 0.2, evidence: [] })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('insufficient_data')
    expect(conflict.resolution).toContain('Insufficient evidence')
  })

  it('defaults to insufficient_data when no specific reason found', () => {
    const a = makeClaim({ claimId: 'a', category: 'mechanism', confidence: 0.8 })
    const b = makeClaim({ claimId: 'b', category: 'mechanism', confidence: 0.8 })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('insufficient_data')
  })

  it('multiple reasons can coexist', () => {
    const a = makeClaim({
      claimId: 'a', category: 'observation', confidence: 0.2,
      statement: '20 nm bubbles observed improvement',
      evidence: [makeEvidence({ description: 'simulation CFD' })]
    })
    const b = makeClaim({
      claimId: 'b', category: 'correlation', confidence: 0.3,
      statement: '500 nm bubbles correlated with efficiency',
      evidence: [makeEvidence({ description: 'experimental test' })]
    })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons.length).toBeGreaterThanOrEqual(2)
  })

  it('findConflicts filters out trivial conflicts', () => {
    const claims = [
      makeClaim({ claimId: 'a', category: 'mechanism', confidence: 0.9 }),
      makeClaim({ claimId: 'b', category: 'mechanism', confidence: 0.9 })
    ]
    const conflicts = findConflicts(claims)
    // Two high-confidence mechanism claims — only insufficient_data, should be filtered
    expect(conflicts.length).toBe(0)
  })

  it('findConflicts returns meaningful conflicts', () => {
    const claims = [
      makeClaim({ claimId: 'a', statement: '20 nm bubbles improve mass transfer', category: 'observation', confidence: 0.3, evidence: [] }),
      makeClaim({ claimId: 'b', statement: '500 nm bubbles improve mass transfer', category: 'correlation', confidence: 0.2, evidence: [] })
    ]
    const conflicts = findConflicts(claims)
    expect(conflicts.length).toBeGreaterThan(0)
  })

  it('returns conflictId with both claim ids', () => {
    const a = makeClaim({ claimId: 'x' })
    const b = makeClaim({ claimId: 'y' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.conflictId).toContain('x')
    expect(conflict.conflictId).toContain('y')
  })

  it('valid conflict output', () => {
    const conflict = analyzeConflict(makeClaim({ claimId: 'a' }), makeClaim({ claimId: 'b' }))
    expect(isValidResearchConflict(conflict)).toBe(true)
  })

  it('deterministic', () => {
    const a = makeClaim({ claimId: 'a', statement: '20 nm bubbles' })
    const b = makeClaim({ claimId: 'b', statement: '500 nm bubbles' })
    const x = analyzeConflict(a, b)
    const y = analyzeConflict(a, b)
    expect(x).toEqual(y)
  })
})

// ============ Method Selector ============

describe('Phase 8-G0 method selector', () => {
  it('recommends pseudo-first-order for kinetics', () => {
    const rec = recommendMethod(makeProblem({ domain: 'kinetics', problemType: 'degradation', description: 'determine rate constant for pollutant degradation' }))
    expect(rec.recommendedMethod).toBe('pseudo-first-order')
    expect(rec.confidence).toBeGreaterThan(0.5)
  })

  it('recommends isotherm for adsorption', () => {
    const rec = recommendMethod(makeProblem({ domain: 'kinetics', problemType: 'adsorption', description: 'determine adsorption isotherm capacity' }))
    expect(rec.recommendedMethod).toContain('isotherm')
  })

  it('recommends Euler-Euler for multiphase CFD', () => {
    const rec = recommendMethod(makeProblem({ domain: 'cfd', problemType: 'simulation', description: 'simulate bubble multiphase flow' }))
    expect(rec.recommendedMethod).toBe('Euler-Euler')
  })

  it('recommends VOF for free surface', () => {
    const rec = recommendMethod(makeProblem({ domain: 'cfd', problemType: 'simulation', description: 'simulate free surface droplet breakup' }))
    expect(rec.recommendedMethod).toBe('VOF (Volume of Fluid)')
  })

  it('recommends DPM for particle tracking', () => {
    const rec = recommendMethod(makeProblem({ domain: 'cfd', problemType: 'simulation', description: 'track particle trajectory in flow' }))
    expect(rec.recommendedMethod).toBe('DPM (Discrete Phase Model)')
  })

  it('recommends RSM for optimization', () => {
    const rec = recommendMethod(makeProblem({ domain: 'optimization', problemType: 'process', description: 'find optimal conditions for maximum efficiency' }))
    expect(rec.recommendedMethod).toBe('RSM (Response Surface Methodology)')
  })

  it('recommends DOE for factorial design', () => {
    const rec = recommendMethod(makeProblem({ domain: 'optimization', problemType: 'screening', description: 'factorial design for parameter screening' }))
    expect(rec.recommendedMethod).toBe('DOE (Design of Experiments)')
  })

  it('recommends ANOVA for group comparison', () => {
    const rec = recommendMethod(makeProblem({ domain: 'statistics', problemType: 'analysis', description: 'compare treatment groups for significant difference' }))
    expect(rec.recommendedMethod).toBe('ANOVA')
  })

  it('recommends regression for correlation', () => {
    const rec = recommendMethod(makeProblem({ domain: 'statistics', problemType: 'modeling', description: 'predict correlation between variables using regression' }))
    expect(rec.recommendedMethod).toBe('multiple regression')
  })

  it('recommends DLS for particle size', () => {
    const rec = recommendMethod(makeProblem({ domain: 'characterization', problemType: 'measurement', description: 'measure particle size distribution using DLS' }))
    expect(rec.recommendedMethod).toBe('dynamic light scattering')
  })

  it('recommends SEM for morphology', () => {
    const rec = recommendMethod(makeProblem({ domain: 'characterization', problemType: 'imaging', description: 'SEM microscopy for surface morphology' }))
    expect(rec.recommendedMethod).toBe('electron microscopy')
  })

  it('recommends zeta potential for surface charge', () => {
    const rec = recommendMethod(makeProblem({ domain: 'characterization', problemType: 'measurement', description: 'measure zeta potential surface charge stability' }))
    expect(rec.recommendedMethod).toBe('electrophoretic measurement')
  })

  it('fallback for unknown domain', () => {
    const rec = recommendMethod(makeProblem({ domain: 'philosophy', problemType: 'ethics', description: 'moral implications of AI' }))
    expect(rec.recommendedMethod).toBe('literature review + pilot experiment')
    expect(rec.confidence).toBe(0.3)
  })

  it('fallback for empty problem', () => {
    const rec = recommendMethod({ domain: '', problemType: '', description: '', constraints: [] })
    expect(rec.confidence).toBe(0.3)
  })

  it('getAvailableDomains returns list', () => {
    const domains = getAvailableDomains()
    expect(domains).toContain('kinetics')
    expect(domains).toContain('cfd')
    expect(domains).toContain('optimization')
    expect(domains).toContain('statistics')
    expect(domains).toContain('characterization')
  })

  it('picks highest confidence when multiple domains match', () => {
    const rec = recommendMethod(makeProblem({
      domain: 'kinetics',
      problemType: 'degradation',
      description: 'kinetic rate constant for pollutant degradation in bubble column'
    }))
    expect(rec.confidence).toBeGreaterThanOrEqual(0.7)
  })

  it('valid output', () => {
    const rec = recommendMethod(makeProblem())
    expect(isValidMethodRecommendation(rec)).toBe(true)
  })

  it('deterministic', () => {
    const p = makeProblem()
    const a = recommendMethod(p)
    const b = recommendMethod(p)
    expect(a).toEqual(b)
  })
})

// ============ Scientific Reasoner Facade ============

describe('Phase 8-G0 scientific reasoner', () => {
  const reasoner = new ScientificReasoner()

  it('analyzePaper returns assessment and claims', () => {
    const result = reasoner.analyzePaper(makeDoc(), [makeCitation()], makeRAGContext())
    expect(result.assessment.documentId).toBe('doc-1')
    expect(result.assessment.reliabilityScore).toBeGreaterThanOrEqual(0)
    expect(Array.isArray(result.claims)).toBe(true)
  })

  it('analyzePaper produces valid assessment', () => {
    const result = reasoner.analyzePaper(makeDoc(), [makeCitation()], makeRAGContext())
    expect(isValidPaperAssessment(result.assessment)).toBe(true)
  })

  it('analyzePaper produces valid claims', () => {
    const result = reasoner.analyzePaper(makeDoc(), [makeCitation()], makeRAGContext())
    for (const claim of result.claims) {
      expect(isValidScientificClaim(claim)).toBe(true)
    }
  })

  it('compareStudies returns conflicts', () => {
    const claimsA = [makeClaim({ claimId: 'a1', statement: '20 nm bubbles improve mass transfer' })]
    const claimsB = [makeClaim({ claimId: 'b1', statement: '500 nm bubbles improve mass transfer' })]
    const conflicts = reasoner.compareStudies(claimsA, claimsB)
    expect(Array.isArray(conflicts)).toBe(true)
  })

  it('compareStudies with identical claims returns no conflicts', () => {
    const c = makeClaim({ claimId: 'same', category: 'mechanism', confidence: 0.9 })
    const conflicts = reasoner.compareStudies([c], [{ ...c, claimId: 'same2' }])
    expect(conflicts.length).toBe(0)
  })

  it('recommendMethod works', () => {
    const rec = reasoner.recommendMethod(makeProblem({ domain: 'kinetics', problemType: 'degradation', description: 'rate constant determination' }))
    expect(rec.recommendedMethod).toBeTruthy()
    expect(rec.confidence).toBeGreaterThan(0)
  })

  it('extractClaims works', () => {
    const claims = reasoner.extractClaims('doc-1', [
      { content: 'Observed that mass transfer improves with smaller bubbles in reactor', score: 0.8, position: 0 }
    ])
    expect(claims.length).toBe(1)
  })

  it('deterministic facade', () => {
    const doc = makeDoc()
    const cites = [makeCitation()]
    const ctx = makeRAGContext()
    const a = reasoner.analyzePaper(doc, cites, ctx)
    const b = reasoner.analyzePaper(doc, cites, ctx)
    expect(a).toEqual(b)
  })
})

// ============ Determinism ============

describe('Phase 8-G0 determinism', () => {
  it('literature critic is deterministic', () => {
    const doc = makeDoc()
    const cites = [makeCitation()]
    const ctx = makeRAGContext()
    const results = Array.from({ length: 5 }, () => evaluatePaper(doc, cites, ctx))
    expect(results.every(r => JSON.stringify(r) === JSON.stringify(results[0]))).toBe(true)
  })

  it('claim extractor is deterministic', () => {
    const chunks = [
      { content: 'Observed significant microbubble mass transfer improvement', score: 0.8, position: 0 },
      { content: 'The simulation predicted higher efficiency with nanoscale bubbles', score: 0.7, position: 1 }
    ]
    const results = Array.from({ length: 5 }, () => extractClaims('doc', chunks))
    expect(results.every(r => JSON.stringify(r) === JSON.stringify(results[0]))).toBe(true)
  })

  it('conflict analyzer is deterministic', () => {
    const a = makeClaim({ claimId: 'a', statement: '20 nm' })
    const b = makeClaim({ claimId: 'b', statement: '500 nm' })
    const results = Array.from({ length: 5 }, () => analyzeConflict(a, b))
    expect(results.every(r => JSON.stringify(r) === JSON.stringify(results[0]))).toBe(true)
  })

  it('method selector is deterministic', () => {
    const p = makeProblem()
    const results = Array.from({ length: 5 }, () => recommendMethod(p))
    expect(results.every(r => JSON.stringify(r) === JSON.stringify(results[0]))).toBe(true)
  })
})

// ============ Security source scan ============

describe('Phase 8-G0 security', () => {
  it('schema file contains no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'shared/science/scientific-reasoning-schema.ts'), 'utf8')
    expect(content).not.toContain("from 'app/")
    expect(content).not.toContain('from "app/')
  })

  it('literature critic has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/literature-critic.ts'), 'utf8')
    // Check for actual import statements, not substring matches in comments
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toMatch(/require.*auth/)
    expect(content).not.toContain('login')
  })

  it('claim extractor has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/claim-extractor.ts'), 'utf8')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
    expect(content).not.toContain('ollama')
  })

  it('conflict analyzer has no model-provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/conflict-analyzer.ts'), 'utf8')
    expect(content).not.toContain('ModelProvider')
    expect(content).not.toContain('model-provider')
  })

  it('method selector has no backend imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/method-selector.ts'), 'utf8')
    expect(content).not.toContain("from 'app/")
    expect(content).not.toContain('fastapi')
  })

  it('reasoner facade has no auth imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/scientific-reasoner.ts'), 'utf8')
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toMatch(/require.*auth/)
    expect(content).not.toMatch(/import.*token/)
    expect(content).not.toContain('login')
  })
})

// ============ Extended schema edge cases ============

describe('Phase 8-G0 schema edge cases', () => {
  it('isValidClaimCategory with whitespace', () => expect(isValidClaimCategory(' mechanism ')).toBe(false))
  it('isValidEvidenceType case sensitive', () => expect(isValidEvidenceType('Experiment')).toBe(false))
  it('isValidConflictReason exact match', () => expect(isValidConflictReason('scale_difference')).toBe(true))
  it('isValidConflictReason partial', () => expect(isValidConflictReason('scale')).toBe(false))
  it('isValidEvidenceItem strength exactly 0', () => expect(isValidEvidenceItem({ evidenceId: 'e', type: 'experiment', description: '', strength: 0 })).toBe(true))
  it('isValidEvidenceItem strength exactly 1', () => expect(isValidEvidenceItem({ evidenceId: 'e', type: 'experiment', description: '', strength: 1 })).toBe(true))
  it('isValidScientificClaim confidence exactly 0', () => expect(isValidScientificClaim(makeClaim({ confidence: 0 }))).toBe(true))
  it('isValidScientificClaim confidence exactly 1', () => expect(isValidScientificClaim(makeClaim({ confidence: 1 }))).toBe(true))
  it('isValidScientificClaim NaN confidence', () => expect(isValidScientificClaim(makeClaim({ confidence: NaN }))).toBe(false))
  it('isValidScientificClaim Infinity confidence', () => expect(isValidScientificClaim(makeClaim({ confidence: Infinity }))).toBe(false))
  it('isValidResearchConflict empty reasons array', () => {
    expect(isValidResearchConflict({
      conflictId: 'c', claimA: makeClaim({ claimId: 'a' }), claimB: makeClaim({ claimId: 'b' }), possibleReasons: []
    })).toBe(true)
  })
  it('isValidMethodRecommendation confidence 0', () => expect(isValidMethodRecommendation({ problem: 'p', recommendedMethod: 'm', reason: 'r', confidence: 0 })).toBe(true))
  it('isValidMethodRecommendation NaN confidence', () => expect(isValidMethodRecommendation({ problem: 'p', recommendedMethod: 'm', reason: 'r', confidence: NaN })).toBe(false))
  it('isValidPaperAssessment empty limitations', () => {
    expect(isValidPaperAssessment({ documentId: 'd', reliabilityScore: 0.5, evidenceScore: 0.5, methodologyScore: 0.5, limitations: [], concerns: [] })).toBe(true)
  })
  it('isValidPaperAssessment NaN score', () => {
    expect(isValidPaperAssessment({ documentId: 'd', reliabilityScore: NaN, evidenceScore: 0.5, methodologyScore: 0.5, limitations: [], concerns: [] })).toBe(false)
  })
})

// ============ Extended literature critic ============

describe('Phase 8-G0 literature critic extended', () => {
  it('multiple citations boost score', () => {
    const manyCites = Array.from({ length: 15 }, (_, i) => makeCitation({ chunkId: `c${i}`, confidence: 0.8 }))
    const result = evaluatePaper(makeDoc(), manyCites, makeRAGContext({ metadata: {} }))
    expect(result.evidenceScore).toBeGreaterThan(0.5)
  })

  it('high confidence citations boost reliability', () => {
    const highCites = [makeCitation({ confidence: 0.95 }), makeCitation({ confidence: 0.92, chunkId: 'c2' })]
    const lowCites = [makeCitation({ confidence: 0.2 })]
    const high = evaluatePaper(makeDoc(), highCites, makeRAGContext({ metadata: {} }))
    const low = evaluatePaper(makeDoc(), lowCites, makeRAGContext({ metadata: {} }))
    expect(high.reliabilityScore).toBeGreaterThan(low.reliabilityScore)
  })

  it('longer content boosts completeness', () => {
    const longChunks = [{ chunkId: 'c1', content: 'A'.repeat(1000), score: 0.8, citation: makeCitation() }]
    const shortChunks = [{ chunkId: 'c1', content: 'A'.repeat(50), score: 0.8, citation: makeCitation() }]
    const long = evaluatePaper(makeDoc(), [makeCitation()], makeRAGContext({ chunks: longChunks, metadata: {} }))
    const short = evaluatePaper(makeDoc(), [makeCitation()], makeRAGContext({ chunks: shortChunks, metadata: {} }))
    expect(long.evidenceScore).toBeGreaterThanOrEqual(short.evidenceScore)
  })

  it('diverse chunks improve content score', () => {
    const diverse = Array.from({ length: 8 }, (_, i) => ({
      chunkId: `c${i}`, content: `Chunk ${i} with distinct content about microbubbles`, score: 0.7, citation: makeCitation({ chunkId: `c${i}` })
    }))
    const single = [{ chunkId: 'c1', content: 'Single chunk', score: 0.7, citation: makeCitation() }]
    const d = evaluatePaper(makeDoc(), [makeCitation()], makeRAGContext({ chunks: diverse, metadata: {} }))
    const s = evaluatePaper(makeDoc(), [makeCitation()], makeRAGContext({ chunks: single, metadata: {} }))
    expect(d.evidenceScore).toBeGreaterThanOrEqual(s.evidenceScore)
  })

  it('metadata fields improve richness score', () => {
    const rich = makeDoc({ metadata: { author: 'X', year: 2024, journal: 'J', doi: '10.x', keywords: ['a'] } })
    const poor = makeDoc({ metadata: {} })
    const r = evaluatePaper(rich, [], makeRAGContext({ metadata: {} }))
    const p = evaluatePaper(poor, [], makeRAGContext({ metadata: {} }))
    expect(r.reliabilityScore).toBeGreaterThan(p.reliabilityScore)
  })

  it('no DOI adds limitation', () => {
    const result = evaluatePaper(makeDoc({ metadata: { author: 'X', year: 2024 } }), [], makeRAGContext({ chunks: [], metadata: {} }))
    expect(result.limitations).toContain('No DOI for verification')
  })

  it('no citation references adds limitation', () => {
    const result = evaluatePaper(makeDoc(), [], makeRAGContext({ citations: [], metadata: {} }))
    expect(result.limitations).toContain('No citation references found')
  })

  it('non-peer-reviewed paper gets concern', () => {
    const doc = makeDoc({ metadata: { author: 'X', year: 2024 } })
    const result = evaluatePaper(doc, [], makeRAGContext({ metadata: {} }))
    expect(result.concerns.some(c => c.includes('missing journal'))).toBe(true)
  })
})

// ============ Extended claim extractor ============

describe('Phase 8-G0 claim extractor extended', () => {
  it('extracts multiple evidence types from different chunks', () => {
    const claims = extractClaims('doc-1', [
      { content: 'The experiment measured oxygen transfer rate in bubble column', score: 0.8, position: 0 },
      { content: 'CFD simulation predicted bubble trajectory and coalescence', score: 0.7, position: 1 },
      { content: 'Statistical analysis showed p-value < 0.05 for regression model', score: 0.6, position: 2 }
    ])
    expect(claims).toHaveLength(3)
    const types = claims.map(c => c.evidence[0].type)
    expect(types).toContain('experiment')
    expect(types).toContain('simulation')
  })

  it('confidence bounded at 0', () => {
    const claims = extractClaims('doc-1', [
      { content: 'might possibly may suggest uncertain unclear', score: 0.1, position: 0 }
    ])
    expect(claims[0].confidence).toBeGreaterThanOrEqual(0)
  })

  it('confidence bounded at 1', () => {
    const claims = extractClaims('doc-1', [
      { content: 'Measured 95.3% removal with p < 0.01 significance confirmed', score: 1.0, position: 0 }
    ])
    expect(claims[0].confidence).toBeLessThanOrEqual(1)
  })

  it('claim IDs are unique per document', () => {
    const claims = extractClaims('doc-X', [
      { content: 'First claim about microbubble reactor performance metrics', score: 0.8, position: 0 },
      { content: 'Second claim about nanoscale bubble dynamics in liquid', score: 0.7, position: 1 }
    ])
    expect(claims[0].claimId).not.toBe(claims[1].claimId)
  })

  it('evidence IDs are unique', () => {
    const claims = extractClaims('doc-X', [
      { content: 'Claim about bubble size distribution measurement accuracy', score: 0.8, position: 0 },
      { content: 'Claim about mass transfer coefficient determination method', score: 0.7, position: 1 }
    ])
    expect(claims[0].evidence[0].evidenceId).not.toBe(claims[1].evidence[0].evidenceId)
  })

  it('single claim with hedging has lower confidence', () => {
    const hedging = extractSingleClaim('This might possibly suggest that bubbles may improve transfer', 's1')
    const direct = extractSingleClaim('Bubbles significantly improve mass transfer coefficient', 's2')
    expect(hedging!.confidence).toBeLessThan(direct!.confidence)
  })

  it('single claim statement truncated at 300 chars', () => {
    const longText = 'A'.repeat(500)
    const claim = extractSingleClaim(longText, 's1')
    expect(claim!.statement.length).toBeLessThanOrEqual(300)
  })

  it('description truncated at 200 chars', () => {
    const longText = 'A'.repeat(500)
    const claims = extractClaims('doc-1', [{ content: longText, score: 0.8, position: 0 }])
    expect(claims[0].evidence[0].description.length).toBeLessThanOrEqual(200)
  })
})

// ============ Extended conflict analyzer ============

describe('Phase 8-G0 conflict analyzer extended', () => {
  it('no conflict between same-category high-confidence claims without scale difference', () => {
    const a = makeClaim({ claimId: 'a', category: 'mechanism', confidence: 0.9, statement: 'Mass transfer improves with aeration' })
    const b = makeClaim({ claimId: 'b', category: 'mechanism', confidence: 0.9, statement: 'Aeration enhances mass transfer coefficient' })
    const conflict = analyzeConflict(a, b)
    // Same category, high confidence, no scale difference → only insufficient_data default
    expect(conflict.possibleReasons).toContain('insufficient_data')
  })

  it('scale difference with numeric claims', () => {
    const a = makeClaim({ statement: '10 nm bubbles show improvement' })
    const b = makeClaim({ statement: '10000 nm bubbles show improvement' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('scale_difference')
  })

  it('method difference between simulation and experiment', () => {
    const a = makeClaim({
      statement: 'The simulation model predicts bubble behavior',
      evidence: [makeEvidence({ description: 'Computational simulation CFD' })]
    })
    const b = makeClaim({
      statement: 'Experimental measurements confirm the trend',
      evidence: [makeEvidence({ description: 'Laboratory experiment measurement' })]
    })
    const conflict = analyzeConflict(a, b)
    expect(conflict.possibleReasons).toContain('method_difference')
  })

  it('findConflicts with 3 claims finds pairwise', () => {
    const claims = [
      makeClaim({ claimId: 'a', statement: '20 nm bubbles', category: 'observation', confidence: 0.3, evidence: [] }),
      makeClaim({ claimId: 'b', statement: '500 nm bubbles', category: 'correlation', confidence: 0.2, evidence: [] }),
      makeClaim({ claimId: 'c', statement: '10000 nm bubbles', category: 'observation', confidence: 0.3, evidence: [] })
    ]
    const conflicts = findConflicts(claims)
    expect(conflicts.length).toBeGreaterThanOrEqual(1)
  })

  it('findConflicts with empty array returns empty', () => {
    expect(findConflicts([])).toEqual([])
  })

  it('findConflicts with single claim returns empty', () => {
    expect(findConflicts([makeClaim()])).toEqual([])
  })

  it('conflict resolution mentions scale for scale differences', () => {
    const a = makeClaim({ statement: '10 nm' })
    const b = makeClaim({ statement: '10000 nm' })
    const conflict = analyzeConflict(a, b)
    expect(conflict.resolution).toBeDefined()
    expect(conflict.resolution!.toLowerCase()).toContain('scale')
  })

  it('conflict resolution mentions methodologies for method differences', () => {
    const a = makeClaim({
      statement: 'CFD simulation shows breakup',
      evidence: [makeEvidence({ description: 'simulation numerical' })]
    })
    const b = makeClaim({
      statement: 'Lab experiment shows coalescence',
      evidence: [makeEvidence({ description: 'experimental measurement' })]
    })
    const conflict = analyzeConflict(a, b)
    expect(conflict.resolution).toBeDefined()
    expect(conflict.resolution!.toLowerCase()).toContain('methodolog')
  })
})

// ============ Extended method selector ============

describe('Phase 8-G0 method selector extended', () => {
  it('two-film theory for mass transfer', () => {
    const rec = recommendMethod(makeProblem({ domain: 'kinetics', problemType: 'mass transfer', description: 'determine kLa interfacial area diffusion' }))
    expect(rec.recommendedMethod).toContain('two-film')
  })

  it('NSGA-II for multi-objective', () => {
    const rec = recommendMethod(makeProblem({ domain: 'optimization', problemType: 'multi-objective', description: 'Pareto trade-off between cost and efficiency' }))
    expect(rec.recommendedMethod).toBe('NSGA-II')
  })

  it('Mann-Whitney for non-parametric', () => {
    const rec = recommendMethod(makeProblem({ domain: 'statistics', problemType: 'non-parametric', description: 'distribution normality test non-parametric comparison' }))
    expect(rec.recommendedMethod).toContain('Mann-Whitney')
  })

  it('k-epsilon for turbulence', () => {
    const rec = recommendMethod(makeProblem({ domain: 'cfd', problemType: 'turbulence', description: 'Reynolds turbulence RANS simulation' }))
    expect(rec.recommendedMethod).toContain('k-epsilon')
  })

  it('returns confidence > 0 for matched domains', () => {
    const domains = ['kinetics', 'cfd', 'optimization', 'statistics', 'characterization']
    for (const d of domains) {
      const rec = recommendMethod(makeProblem({ domain: d, problemType: 'test', description: `${d} analysis` }))
      expect(rec.confidence).toBeGreaterThan(0)
    }
  })

  it('getAvailableDomains returns at least 5', () => {
    expect(getAvailableDomains().length).toBeGreaterThanOrEqual(5)
  })

  it('fallback for philosophy domain', () => {
    const rec = recommendMethod(makeProblem({ domain: 'philosophy', problemType: 'ethics', description: 'moral implications' }))
    expect(rec.confidence).toBeLessThanOrEqual(0.3)
  })

  it('fallback for empty domain', () => {
    const rec = recommendMethod({ domain: '', problemType: '', description: '', constraints: [] })
    expect(rec.recommendedMethod).toBeTruthy()
  })

  it('multiple keywords boost match score', () => {
    const rec = recommendMethod(makeProblem({
      domain: 'kinetics',
      problemType: 'adsorption',
      description: 'determine adsorption isotherm capacity uptake equilibrium'
    }))
    expect(rec.confidence).toBeGreaterThanOrEqual(0.7)
  })
})

// ============ Extended determinism ============

describe('Phase 8-G0 extended determinism', () => {
  it('extractClaims 10 runs identical', () => {
    const chunks = [
      { content: 'Observed significant microbubble mass transfer improvement in reactor', score: 0.8, position: 0 }
    ]
    const results = Array.from({ length: 10 }, () => extractClaims('d', chunks))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('recommendMethod 10 runs identical', () => {
    const p = makeProblem()
    const results = Array.from({ length: 10 }, () => recommendMethod(p))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('analyzeConflict 10 runs identical', () => {
    const a = makeClaim({ claimId: 'a', statement: '20 nm' })
    const b = makeClaim({ claimId: 'b', statement: '500 nm' })
    const results = Array.from({ length: 10 }, () => analyzeConflict(a, b))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
})

// ============ Extended security ============

describe('Phase 8-G0 extended security', () => {
  it('claim extractor has no model-provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/claim-extractor.ts'), 'utf8')
    expect(content).not.toMatch(/import.*ModelProvider/)
    expect(content).not.toMatch(/import.*model-provider/)
  })

  it('method selector has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/method-selector.ts'), 'utf8')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
  })

  it('scientific reasoner has no SDK imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'main/services/science/scientific-reasoner.ts'), 'utf8')
    expect(content).not.toMatch(/import.*anthropic/)
    expect(content).not.toMatch(/import.*openai/)
    expect(content).not.toMatch(/import.*ollama/)
  })

  it('schema file has no provider imports', async () => {
    const fs = await import('fs')
    const content = fs.readFileSync(resolve(srcRoot, 'shared/science/scientific-reasoning-schema.ts'), 'utf8')
    expect(content).not.toMatch(/import.*ModelProvider/)
    expect(content).not.toMatch(/import.*SecretStore/)
  })
})

// ============ Additional coverage tests ============

describe('Phase 8-G0 additional coverage', () => {
  describe('schema type guards additional', () => {
    it('isValidEvidenceItem with strength 0.5', () => {
      expect(isValidEvidenceItem({ evidenceId: 'e', type: 'theory', description: 'test', strength: 0.5 })).toBe(true)
    })
    it('isValidScientificClaim with empty evidence array', () => {
      expect(isValidScientificClaim(makeClaim({ evidence: [] }))).toBe(true)
    })
    it('isValidScientificClaim with 3 evidence items', () => {
      expect(isValidScientificClaim(makeClaim({
        evidence: [makeEvidence({ evidenceId: 'e1' }), makeEvidence({ evidenceId: 'e2' }), makeEvidence({ evidenceId: 'e3' })]
      }))).toBe(true)
    })
    it('isValidResearchConflict with resolution undefined', () => {
      expect(isValidResearchConflict({
        conflictId: 'c', claimA: makeClaim({ claimId: 'a' }), claimB: makeClaim({ claimId: 'b' }), possibleReasons: ['scale_difference']
      })).toBe(true)
    })
    it('isValidPaperAssessment with 3 limitations', () => {
      expect(isValidPaperAssessment({
        documentId: 'd', reliabilityScore: 0.5, evidenceScore: 0.5, methodologyScore: 0.5,
        limitations: ['a', 'b', 'c'], concerns: []
      })).toBe(true)
    })
    it('isValidClaimCategory rejects number', () => expect(isValidClaimCategory(0 as never)).toBe(false))
    it('isValidEvidenceType rejects boolean', () => expect(isValidEvidenceType(true as never)).toBe(false))
    it('isValidConflictReason rejects array', () => expect(isValidConflictReason([] as never)).toBe(false))
  })

  describe('literature critic scoring edge cases', () => {
    it('single citation with moderate confidence', () => {
      const result = evaluatePaper(makeDoc(), [makeCitation({ confidence: 0.5 })], makeRAGContext({ metadata: {} }))
      expect(result.reliabilityScore).toBeGreaterThan(0.3)
      expect(result.reliabilityScore).toBeLessThan(0.9)
    })
    it('empty metadata reduces richness', () => {
      const r = evaluatePaper(makeDoc({ metadata: {} }), [], makeRAGContext({ metadata: {} }))
      expect(r.reliabilityScore).toBeLessThan(0.5)
    })
    it('equipment type gets low score', () => {
      const doc = makeDoc({ type: 'equipment', metadata: {} })
      const result = evaluatePaper(doc, [], makeRAGContext({ metadata: {} }))
      expect(result.methodologyScore).toBeLessThan(0.5)
    })
    it('dataset type gets low score', () => {
      const doc = makeDoc({ type: 'dataset', metadata: {} })
      const result = evaluatePaper(doc, [], makeRAGContext({ metadata: {} }))
      expect(result.methodologyScore).toBeLessThan(0.5)
    })
    it('confidence score boundary 0', () => {
      const result = evaluatePaper(makeDoc(), [makeCitation({ confidence: 0 })], makeRAGContext({ metadata: {} }))
      expect(result.evidenceScore).toBeGreaterThanOrEqual(0)
    })
    it('confidence score boundary 1', () => {
      const result = evaluatePaper(makeDoc(), [makeCitation({ confidence: 1 })], makeRAGContext({
        chunks: [{ chunkId: 'c1', content: 'A'.repeat(1000), score: 1, citation: makeCitation() }],
        metadata: { hasData: true }
      }))
      expect(result.evidenceScore).toBeLessThanOrEqual(1)
    })
  })

  describe('claim extractor additional', () => {
    it('all chunks skipped if all trivial', () => {
      expect(extractClaims('doc', [
        { content: 'ab', score: 0.5, position: 0 },
        { content: 'cd', score: 0.5, position: 1 }
      ])).toHaveLength(0)
    })
    it('claim preserves sourceId', () => {
      const claims = extractClaims('my-doc', [
        { content: 'Observed that smaller bubbles improve mass transfer significantly', score: 0.8, position: 0 }
      ])
      expect(claims[0].sourceId).toBe('my-doc')
    })
    it('claim category defaults to observation for ambiguous text', () => {
      const claims = extractClaims('doc', [
        { content: 'The water was blue and cold with no specific signals', score: 0.5, position: 0 }
      ])
      expect(claims[0].category).toBe('observation')
    })
    it('extractSingleClaim returns claim with correct sourceId', () => {
      const claim = extractSingleClaim('Observed significant improvement in reactor performance', 'src-X')
      expect(claim!.sourceId).toBe('src-X')
    })
    it('extractSingleClaim evidence has correct sourceId', () => {
      const claim = extractSingleClaim('Measured bubble size distribution accurately', 'src-Y')
      expect(claim!.evidence[0].evidenceId).toContain('src-Y')
    })
  })

  describe('conflict analyzer additional', () => {
    it('analyzeConflict returns valid output', () => {
      const conflict = analyzeConflict(makeClaim({ claimId: 'x' }), makeClaim({ claimId: 'y' }))
      expect(conflict.conflictId).toBeTruthy()
      expect(Array.isArray(conflict.possibleReasons)).toBe(true)
    })
    it('findConflicts with 4 claims finds multiple', () => {
      const claims = [
        makeClaim({ claimId: 'a', statement: '5 nm bubbles', category: 'observation', confidence: 0.2, evidence: [] }),
        makeClaim({ claimId: 'b', statement: '5000 nm bubbles', category: 'correlation', confidence: 0.3, evidence: [] }),
        makeClaim({ claimId: 'c', statement: '10 nm bubbles', category: 'observation', confidence: 0.25, evidence: [] }),
        makeClaim({ claimId: 'd', statement: '8000 nm bubbles', category: 'correlation', confidence: 0.35, evidence: [] })
      ]
      const conflicts = findConflicts(claims)
      expect(conflicts.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('method selector additional', () => {
    it('returns method for characterization with zeta', () => {
      const rec = recommendMethod(makeProblem({ domain: 'characterization', problemType: 'charge', description: 'zeta potential surface charge stability colloidal' }))
      expect(rec.recommendedMethod).toBe('electrophoretic measurement')
    })
    it('returns method for characterization with SEM', () => {
      const rec = recommendMethod(makeProblem({ domain: 'characterization', problemType: 'imaging', description: 'SEM TEM microscopy surface morphology' }))
      expect(rec.recommendedMethod).toBe('electron microscopy')
    })
    it('returns method for kinetics with adsorption', () => {
      const rec = recommendMethod(makeProblem({ domain: 'kinetics', problemType: 'uptake', description: 'adsorption capacity equilibrium isotherm' }))
      expect(rec.recommendedMethod).toContain('isotherm')
    })
    it('fallback for random domain', () => {
      const rec = recommendMethod(makeProblem({ domain: 'music', problemType: 'rhythm', description: 'tempo analysis' }))
      expect(rec.recommendedMethod).toBe('literature review + pilot experiment')
    })
    it('getAvailableDomains includes all 5', () => {
      const domains = getAvailableDomains()
      expect(domains).toContain('kinetics')
      expect(domains).toContain('cfd')
      expect(domains).toContain('optimization')
      expect(domains).toContain('statistics')
      expect(domains).toContain('characterization')
    })
  })

  describe('reasoner facade additional', () => {
    const reasoner = new ScientificReasoner()

    it('analyzePaper with empty chunks', () => {
      const result = reasoner.analyzePaper(makeDoc(), [], makeRAGContext({ chunks: [], citations: [], metadata: {} }))
      expect(result.assessment.documentId).toBe('doc-1')
      expect(result.claims).toHaveLength(0)
    })

    it('compareStudies with 3 vs 3 claims', () => {
      const a = [
        makeClaim({ claimId: 'a1', statement: '10 nm', category: 'observation', confidence: 0.3, evidence: [] }),
        makeClaim({ claimId: 'a2', statement: '20 nm', category: 'observation', confidence: 0.3, evidence: [] }),
        makeClaim({ claimId: 'a3', statement: '30 nm', category: 'observation', confidence: 0.3, evidence: [] })
      ]
      const b = [
        makeClaim({ claimId: 'b1', statement: '5000 nm', category: 'correlation', confidence: 0.2, evidence: [] }),
        makeClaim({ claimId: 'b2', statement: '6000 nm', category: 'correlation', confidence: 0.2, evidence: [] }),
        makeClaim({ claimId: 'b3', statement: '7000 nm', category: 'correlation', confidence: 0.2, evidence: [] })
      ]
      const conflicts = reasoner.compareStudies(a, b)
      expect(conflicts.length).toBeGreaterThanOrEqual(1)
    })

    it('recommendMethod returns valid', () => {
      const rec = reasoner.recommendMethod(makeProblem({ domain: 'cfd', problemType: 'flow', description: 'bubble multiphase simulation' }))
      expect(isValidMethodRecommendation(rec)).toBe(true)
    })

    it('extractClaims with multiple chunks', () => {
      const claims = reasoner.extractClaims('doc', [
        { content: 'Observed bubble breakup in turbulent flow regime', score: 0.8, position: 0 },
        { content: 'Simulation predicted coalescence at high void fraction', score: 0.7, position: 1 }
      ])
      expect(claims.length).toBe(2)
    })

    it('analyzePaper with multiple citations', () => {
      const cites = [makeCitation({ confidence: 0.9 }), makeCitation({ confidence: 0.8, chunkId: 'c2' })]
      const result = reasoner.analyzePaper(makeDoc(), cites, makeRAGContext())
      expect(result.assessment.reliabilityScore).toBeGreaterThan(0.5)
    })
  })
})

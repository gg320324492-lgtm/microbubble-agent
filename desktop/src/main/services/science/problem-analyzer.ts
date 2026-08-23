// Research Problem Analyzer (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: deterministic analysis of a ResearchProblem into scientific
// questions, mechanisms, evidence requirements, and approach recommendations.
// Uses keyword matching against domain knowledge — no LLM.

import type {
  ResearchProblem,
  ProblemAnalysis,
  ResearchDomain
} from '../../../shared/science/research-design-schema'

// ============ Domain-specific knowledge ============

interface DomainKnowledge {
  mechanisms: readonly string[]
  evidence: readonly string[]
  approaches: readonly string[]
  questionPatterns: readonly string[]
}

const DOMAIN_KB: ReadonlyMap<ResearchDomain, DomainKnowledge> = new Map([
  ['environment', {
    mechanisms: ['mass transfer', 'radical generation', 'adsorption', 'biodegradation', 'oxidation'],
    evidence: ['pollutant concentration', 'removal efficiency', 'reaction kinetics', 'byproduct formation'],
    approaches: ['batch experiment', 'column study', 'field pilot', 'life cycle assessment'],
    questionPatterns: ['How does', 'affect', 'removal', 'degradation', 'treatment']
  }],
  ['material', {
    mechanisms: ['crystallization', 'nucleation', 'phase transformation', 'surface modification', 'self-assembly'],
    evidence: ['microstructure', 'mechanical properties', 'thermal stability', 'surface morphology'],
    approaches: ['synthesis optimization', 'characterization', 'structure-property correlation', 'computational modeling'],
    questionPatterns: ['How to synthesize', 'improve', 'properties', 'structure', 'performance']
  }],
  ['chemical', {
    mechanisms: ['reaction pathway', 'catalysis', 'equilibrium', 'kinetics', 'selectivity'],
    evidence: ['yield', 'selectivity', 'reaction rate', 'activation energy', 'product distribution'],
    approaches: ['kinetic study', 'thermodynamic analysis', 'catalyst screening', 'process optimization'],
    questionPatterns: ['How to improve', 'yield', 'selectivity', 'catalyst', 'reaction']
  }],
  ['biomedical', {
    mechanisms: ['cell signaling', 'immune response', 'drug delivery', 'tissue regeneration', 'biocompatibility'],
    evidence: ['cell viability', 'gene expression', 'protein levels', 'clinical outcomes', 'biomarkers'],
    approaches: ['in vitro study', 'in vivo model', 'clinical trial', 'biocompatibility test'],
    questionPatterns: ['How does', 'affect', 'cell', 'tissue', 'efficacy', 'safety']
  }],
  ['engineering', {
    mechanisms: ['fluid dynamics', 'heat transfer', 'mass transfer', 'structural mechanics', 'control theory'],
    evidence: ['pressure drop', 'heat flux', 'mass flux', 'stress distribution', 'system response'],
    approaches: ['CFD simulation', 'experimental validation', 'scale-up study', 'process control'],
    questionPatterns: ['How to optimize', 'design', 'improve', 'performance', 'efficiency']
  }],
  ['physics', {
    mechanisms: ['quantum effects', 'electromagnetic interaction', 'thermodynamic processes', 'optical phenomena', 'particle dynamics'],
    evidence: ['spectral data', 'field measurements', 'energy spectra', 'scattering patterns'],
    approaches: ['analytical derivation', 'numerical simulation', 'precision measurement', 'theoretical prediction'],
    questionPatterns: ['What is the', 'mechanism', 'behavior', 'property', 'phenomenon']
  }],
  ['computer-science', {
    mechanisms: ['algorithm complexity', 'data structures', 'optimization', 'learning patterns', 'system architecture'],
    evidence: ['accuracy', 'latency', 'throughput', 'scalability', 'convergence'],
    approaches: ['algorithm design', 'benchmark testing', 'ablation study', 'theoretical analysis'],
    questionPatterns: ['How to improve', 'accuracy', 'efficiency', 'performance', 'scalability']
  }]
])

// ============ Analysis logic ============

function detectQuestion(problem: ResearchProblem): string {
  const kb = DOMAIN_KB.get(problem.domain)
  const patterns = kb?.questionPatterns ?? ['How does', 'What is the']
  const title = problem.title.toLowerCase()
  const objective = problem.objective.toLowerCase()
  const combined = title + ' ' + objective

  // Find best matching pattern
  let bestPattern = patterns[0]
  let bestScore = 0
  for (const p of patterns) {
    if (combined.includes(p.toLowerCase())) {
      bestScore += p.split(' ').length
      bestPattern = p
    }
  }

  return `${bestPattern} ${problem.title.toLowerCase()} in ${problem.domain} context?`
}

function detectMechanisms(problem: ResearchProblem): string[] {
  const kb = DOMAIN_KB.get(problem.domain)
  if (!kb) return ['general mechanism']
  const combined = (problem.title + ' ' + problem.objective).toLowerCase()
  return kb.mechanisms.filter(m => {
    const words = m.split(' ')
    return words.some(w => combined.includes(w)) || combined.includes(m)
  }).slice(0, 3)
}

function detectEvidence(problem: ResearchProblem): string[] {
  const kb = DOMAIN_KB.get(problem.domain)
  if (!kb) return ['experimental data']
  const combined = (problem.title + ' ' + problem.objective).toLowerCase()
  return kb.evidence.filter(e => {
    const words = e.split(' ')
    return words.some(w => combined.includes(w)) || combined.includes(e)
  }).slice(0, 4)
}

function detectApproach(problem: ResearchProblem): string {
  const kb = DOMAIN_KB.get(problem.domain)
  if (!kb) return 'literature review + pilot experiment'
  const combined = (problem.title + ' ' + problem.objective).toLowerCase()
  const matched = kb.approaches.filter(a => {
    const words = a.split(' ')
    return words.some(w => combined.includes(w))
  })
  return matched[0] ?? kb.approaches[0]
}

// ============ Public API ============

/**
 * Phase 8-H0: analyze a research problem into scientific questions,
 * mechanisms, evidence requirements, and recommended approach.
 * Deterministic — keyword matching against domain knowledge.
 */
export function analyzeProblem(problem: ResearchProblem): ProblemAnalysis {
  return {
    problemId: problem.problemId,
    keyScientificQuestion: detectQuestion(problem),
    possibleMechanisms: detectMechanisms(problem),
    requiredEvidence: detectEvidence(problem),
    recommendedApproach: detectApproach(problem)
  }
}

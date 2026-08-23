// Hypothesis Generator (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: deterministic generation of ResearchHypothesis objects from
// a ResearchProblem and its analysis. Mechanism-based hypothesis creation
// using domain knowledge — no LLM, no hallucinated numerical claims.

import type {
  ResearchProblem,
  ProblemAnalysis,
  ResearchHypothesis,
  ResearchDomain
} from '../../../shared/science/research-design-schema'

// ============ Mechanism-hypothesis templates ============

interface HypothesisTemplate {
  mechanismKeywords: readonly string[]
  statementTemplate: string
  baseConfidence: number
}

const DOMAIN_TEMPLATES: ReadonlyMap<ResearchDomain, readonly HypothesisTemplate[]> = new Map([
  ['environment', [
    { mechanismKeywords: ['mass transfer', 'dissolution', 'interfacial'],
      statementTemplate: 'Enhanced mass transfer through increased interfacial area improves pollutant removal efficiency',
      baseConfidence: 0.75 },
    { mechanismKeywords: ['radical', 'oxidation', 'degradation'],
      statementTemplate: 'Reactive radical generation during bubble collapse accelerates chemical oxidation of target compounds',
      baseConfidence: 0.70 },
    { mechanismKeywords: ['adsorption', 'surface', 'uptake'],
      statementTemplate: 'Surface adsorption capacity correlates with specific surface area and functional group density',
      baseConfidence: 0.72 },
    { mechanismKeywords: ['biodegradation', 'microbial', 'biological'],
      statementTemplate: 'Microbial activity enhancement through improved oxygen supply increases biodegradation rate',
      baseConfidence: 0.68 }
  ]],
  ['material', [
    { mechanismKeywords: ['crystallization', 'nucleation', 'grain'],
      statementTemplate: 'Controlled nucleation conditions determine crystal size distribution and phase purity',
      baseConfidence: 0.73 },
    { mechanismKeywords: ['surface', 'modification', 'coating'],
      statementTemplate: 'Surface modification alters interfacial energy and wettability characteristics',
      baseConfidence: 0.70 },
    { mechanismKeywords: ['composite', 'reinforcement', 'strength'],
      statementTemplate: 'Reinforcement phase distribution governs mechanical property enhancement',
      baseConfidence: 0.72 }
  ]],
  ['chemical', [
    { mechanismKeywords: ['catalyst', 'catalytic', 'active site'],
      statementTemplate: 'Active site density and accessibility determine catalytic turnover frequency',
      baseConfidence: 0.74 },
    { mechanismKeywords: ['kinetic', 'rate', 'reaction'],
      statementTemplate: 'Reaction rate follows Arrhenius behavior with activation energy as controlling parameter',
      baseConfidence: 0.76 },
    { mechanismKeywords: ['selectivity', 'pathway', 'product'],
      statementTemplate: 'Reaction pathway selectivity depends on thermodynamic vs kinetic control conditions',
      baseConfidence: 0.71 }
  ]],
  ['biomedical', [
    { mechanismKeywords: ['delivery', 'transport', 'uptake'],
      statementTemplate: 'Carrier system design controls drug release kinetics and cellular uptake efficiency',
      baseConfidence: 0.69 },
    { mechanismKeywords: ['immune', 'response', 'inflammation'],
      statementTemplate: 'Immune modulation through surface chemistry affects inflammatory response magnitude',
      baseConfidence: 0.65 },
    { mechanismKeywords: ['regeneration', 'repair', 'growth'],
      statementTemplate: 'Scaffold architecture and growth factor delivery synergistically promote tissue regeneration',
      baseConfidence: 0.67 }
  ]],
  ['engineering', [
    { mechanismKeywords: ['flow', 'turbulence', 'mixing'],
      statementTemplate: 'Flow regime and turbulence intensity govern mixing efficiency and heat transfer coefficient',
      baseConfidence: 0.75 },
    { mechanismKeywords: ['pressure', 'stress', 'structural'],
      statementTemplate: 'Structural load distribution determines failure mode and safety factor',
      baseConfidence: 0.73 },
    { mechanismKeywords: ['control', 'feedback', 'stability'],
      statementTemplate: 'Control system design and feedback gain determine system response time and stability',
      baseConfidence: 0.72 }
  ]],
  ['physics', [
    { mechanismKeywords: ['quantum', 'energy', 'level'],
      statementTemplate: 'Energy level quantization determines spectral properties and transition probabilities',
      baseConfidence: 0.78 },
    { mechanismKeywords: ['field', 'electromagnetic', 'wave'],
      statementTemplate: 'Field interaction geometry governs wave propagation and interference patterns',
      baseConfidence: 0.76 }
  ]],
  ['computer-science', [
    { mechanismKeywords: ['algorithm', 'complexity', 'optimization'],
      statementTemplate: 'Algorithmic complexity and data structure choice determine computational scalability',
      baseConfidence: 0.77 },
    { mechanismKeywords: ['learning', 'training', 'model'],
      statementTemplate: 'Model architecture and training data quality jointly determine generalization performance',
      baseConfidence: 0.74 }
  ]]
])

// ============ Hypothesis generation ============

function matchTemplates(domain: ResearchDomain, problemText: string): HypothesisTemplate[] {
  const templates = DOMAIN_TEMPLATES.get(domain)
  if (!templates) return []
  return templates.filter(t =>
    t.mechanismKeywords.some(kw => problemText.includes(kw))
  )
}

function adjustConfidence(base: number, analysis: ProblemAnalysis, idx: number): number {
  let conf = base
  // Boost if mechanism matches evidence
  if (analysis.possibleMechanisms.length > 0) conf += 0.05
  // Slight penalty for each additional hypothesis (diminishing confidence)
  conf -= idx * 0.03
  return Math.max(0.1, Math.min(0.95, Math.round(conf * 100) / 100))
}

// ============ Public API ============

/**
 * Phase 8-H0: generate research hypotheses from a problem and its analysis.
 * Deterministic — template matching, no LLM, no hallucinated numbers.
 */
export function generateHypotheses(
  problem: ResearchProblem,
  analysis: ProblemAnalysis
): ResearchHypothesis[] {
  const combined = (problem.title + ' ' + problem.objective).toLowerCase()
  const matched = matchTemplates(problem.domain, combined)

  if (matched.length === 0) {
    // Fallback: generic hypothesis from analysis mechanisms
    const mechanism = analysis.possibleMechanisms[0] ?? 'underlying physical process'
    return [{
      hypothesisId: `${problem.problemId}-h1`,
      statement: `The ${mechanism} is the primary factor controlling ${problem.title.toLowerCase()}`,
      mechanism,
      confidence: 0.5
    }]
  }

  return matched.map((template, idx) => ({
    hypothesisId: `${problem.problemId}-h${idx + 1}`,
    statement: template.statementTemplate,
    mechanism: analysis.possibleMechanisms[idx] ?? template.mechanismKeywords[0],
    confidence: adjustConfidence(template.baseConfidence, analysis, idx)
  }))
}

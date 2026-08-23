// Scientific Method Selector (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: deterministic recommendation of analysis methods based on
// research problem characteristics. Maps problem domain + type to known
// scientific methods using keyword matching — no LLM.

import type {
  ResearchProblem,
  MethodRecommendation
} from '../../../shared/science/scientific-reasoning-schema'

// ============ Method knowledge base ============

interface MethodEntry {
  keywords: readonly string[]
  method: string
  reason: string
  confidence: number
}

const METHOD_KB: ReadonlyMap<string, readonly MethodEntry[]> = new Map([
  ['kinetics', [
    { keywords: ['rate', 'kinetic', 'degradation', 'removal rate', 'reaction rate'],
      method: 'pseudo-first-order',
      reason: 'Standard kinetic model for dilute system degradation processes',
      confidence: 0.85 },
    { keywords: ['adsorption', 'isotherm', 'capacity', 'uptake'],
      method: 'Langmuir/Freundlich isotherm',
      reason: 'Equilibrium adsorption models for surface interaction quantification',
      confidence: 0.80 },
    { keywords: ['mass transfer', 'diffusion', 'klA', 'interfacial'],
      method: 'two-film theory',
      reason: 'Classical mass transfer model for gas-liquid interfaces',
      confidence: 0.75 }
  ]],
  ['cfd', [
    { keywords: ['bubble', 'multiphase', 'two-phase', 'gas-liquid', 'void fraction'],
      method: 'Euler-Euler',
      reason: 'Suitable for dispersed bubbly flow with high bubble population',
      confidence: 0.85 },
    { keywords: ['free surface', 'breakup', 'coalescence', 'droplet'],
      method: 'VOF (Volume of Fluid)',
      reason: 'Captures interface topology for large deformations',
      confidence: 0.80 },
    { keywords: ['particle', 'tracking', 'trajectory', 'Lagrangian'],
      method: 'DPM (Discrete Phase Model)',
      reason: 'Tracks individual particle/bubble paths in continuous phase',
      confidence: 0.75 },
    { keywords: ['turbulence', 'Reynolds', 'LES', 'RANS'],
      method: 'k-epsilon / SST k-omega',
      reason: 'Standard turbulence models for industrial flow simulations',
      confidence: 0.70 }
  ]],
  ['optimization', [
    { keywords: ['optimal', 'maximum', 'minimum', 'efficiency', 'improve'],
      method: 'RSM (Response Surface Methodology)',
      reason: 'Statistical design for process parameter optimization',
      confidence: 0.80 },
    { keywords: ['factor', 'screening', 'factorial', 'Taguchi'],
      method: 'DOE (Design of Experiments)',
      reason: 'Systematic factor screening before detailed optimization',
      confidence: 0.85 },
    { keywords: ['multi-objective', 'Pareto', 'trade-off'],
      method: 'NSGA-II',
      reason: 'Multi-objective evolutionary algorithm for Pareto-optimal solutions',
      confidence: 0.70 }
  ]],
  ['statistics', [
    { keywords: ['compare', 'difference', 'group', 'treatment'],
      method: 'ANOVA',
      reason: 'Standard method for comparing means across multiple groups',
      confidence: 0.85 },
    { keywords: ['correlation', 'relationship', 'regression', 'predict'],
      method: 'multiple regression',
      reason: 'Models relationships between dependent and independent variables',
      confidence: 0.80 },
    { keywords: ['distribution', 'normality', 'non-parametric'],
      method: 'Mann-Whitney / Kruskal-Wallis',
      reason: 'Non-parametric alternatives when normality assumptions fail',
      confidence: 0.75 }
  ]],
  ['characterization', [
    { keywords: ['size', 'distribution', 'DLS', 'particle size'],
      method: 'dynamic light scattering',
      reason: 'Standard technique for nanoparticle/bubble size distribution',
      confidence: 0.85 },
    { keywords: ['morphology', 'SEM', 'TEM', 'microscopy'],
      method: 'electron microscopy',
      reason: 'Direct visualization of surface structure and morphology',
      confidence: 0.80 },
    { keywords: ['zeta potential', 'surface charge', 'stability'],
      method: 'electrophoretic measurement',
      reason: 'Quantifies surface charge for colloidal stability assessment',
      confidence: 0.80 }
  ]]
])

// ============ Domain matching ============

function matchDomainKeywords(problem: ResearchProblem): string[] {
  const text = (
    problem.domain + ' ' + problem.problemType + ' ' + problem.description
  ).toLowerCase()
  const matchedDomains: string[] = []
  for (const [domain, _entries] of METHOD_KB) {
    if (text.includes(domain)) matchedDomains.push(domain)
  }
  return matchedDomains
}

function findBestMethod(
  domain: string,
  problem: ResearchProblem
): MethodRecommendation | null {
  const entries = METHOD_KB.get(domain)
  if (!entries) return null

  const problemText = (problem.problemType + ' ' + problem.description).toLowerCase()
  let bestEntry: MethodEntry | null = null
  let bestScore = 0

  for (const entry of entries) {
    let score = 0
    for (const kw of entry.keywords) {
      if (problemText.includes(kw)) score++
    }
    if (score > bestScore) {
      bestScore = score
      bestEntry = entry
    }
  }

  if (!bestEntry || bestScore === 0) return null

  return {
    problem: problem.description,
    recommendedMethod: bestEntry.method,
    reason: bestEntry.reason,
    confidence: bestEntry.confidence
  }
}

// ============ Public API ============

/**
 * Phase 8-G0: recommend scientific methods for a research problem.
 * Deterministic — keyword matching against method knowledge base.
 */
export function recommendMethod(problem: ResearchProblem): MethodRecommendation {
  const domains = matchDomainKeywords(problem)

  // Try each matched domain, pick highest confidence
  let bestRec: MethodRecommendation | null = null
  for (const domain of domains) {
    const rec = findBestMethod(domain, problem)
    if (rec && (!bestRec || rec.confidence > bestRec.confidence)) {
      bestRec = rec
    }
  }

  if (bestRec) return bestRec

  // Fallback: generic recommendation
  return {
    problem: problem.description,
    recommendedMethod: 'literature review + pilot experiment',
    reason: 'No specific method matched — start with systematic review and small-scale validation',
    confidence: 0.3
  }
}

/**
 * Phase 8-G0: get all available method domains.
 */
export function getAvailableDomains(): string[] {
  return Array.from(METHOD_KB.keys())
}

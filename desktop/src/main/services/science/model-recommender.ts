// Model Recommendation Engine (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: deterministic recommendation of analysis models for research
// problems. Reuses Phase 8-G0 MethodRecommendation concept and extends it
// with domain-specific model-to-purpose mapping — no LLM.

import type {
  ResearchProblem,
  ProblemAnalysis,
  ModelSelection,
  ResearchDomain
} from '../../../shared/science/research-design-schema'

// ============ Model knowledge base ============

interface ModelEntry {
  keywords: readonly string[]
  model: string
  purpose: string
  justification: string
  confidence: number
}

const MODEL_KB: ReadonlyMap<ResearchDomain, readonly ModelEntry[]> = new Map([
  ['environment', [
    { keywords: ['degradation', 'removal', 'kinetic', 'rate'],
      model: 'pseudo-first-order kinetic model',
      purpose: 'Quantify degradation kinetics and rate constants',
      justification: 'Standard model for dilute pollutant removal processes',
      confidence: 0.82 },
    { keywords: ['mass transfer', 'oxygen', 'transfer', 'kLa'],
      model: 'two-film theory model',
      purpose: 'Calculate mass transfer coefficients at gas-liquid interface',
      justification: 'Classical model for interfacial mass transfer quantification',
      confidence: 0.78 },
    { keywords: ['optimization', 'optimal', 'efficiency', 'improve'],
      model: 'response surface methodology (RSM)',
      purpose: 'Optimize multiple process parameters simultaneously',
      justification: 'Statistical method for empirical process optimization',
      confidence: 0.80 },
    { keywords: ['adsorption', 'isotherm', 'capacity'],
      model: 'Langmuir/Freundlich isotherm',
      purpose: 'Model adsorption equilibrium and capacity',
      justification: 'Standard equilibrium models for surface interactions',
      confidence: 0.79 }
  ]],
  ['material', [
    { keywords: ['crystal', 'size', 'growth', 'nucleation'],
      model: 'Johnson-Mehl-Avrami-Kolmogorov (JMAK)',
      purpose: 'Model crystallization kinetics and phase transformation',
      justification: 'Established model for solid-state transformation kinetics',
      confidence: 0.76 },
    { keywords: ['mechanical', 'stress', 'strain', 'strength'],
      model: 'finite element analysis (FEA)',
      purpose: 'Predict mechanical behavior under loading conditions',
      justification: 'Standard numerical method for structural analysis',
      confidence: 0.80 },
    { keywords: ['thermal', 'heat', 'conductivity'],
      model: 'Fourier heat conduction model',
      purpose: 'Predict thermal behavior and heat distribution',
      justification: 'Classical model for heat transfer in materials',
      confidence: 0.77 }
  ]],
  ['chemical', [
    { keywords: ['catalyst', 'catalytic', 'turnover'],
      model: 'Michaelis-Menten / Langmuir-Hinshelwood',
      purpose: 'Model catalytic reaction kinetics',
      justification: 'Standard kinetic models for catalytic processes',
      confidence: 0.81 },
    { keywords: ['equilibrium', 'thermodynamic', 'Gibbs'],
      model: 'van\'t Hoff equation',
      purpose: 'Determine thermodynamic parameters from temperature dependence',
      justification: 'Fundamental thermodynamic relationship for equilibrium analysis',
      confidence: 0.83 },
    { keywords: ['reactor', 'CSTR', 'PFR', 'reactor design'],
      model: 'reactor design equation',
      purpose: 'Size and optimize reactor configuration',
      justification: 'Standard chemical engineering reactor design approach',
      confidence: 0.79 }
  ]],
  ['biomedical', [
    { keywords: ['drug', 'release', 'delivery', 'kinetic'],
      model: 'Higuchi / Korsmeyer-Peppas model',
      purpose: 'Characterize drug release kinetics from carrier systems',
      justification: 'Standard models for pharmaceutical release profiling',
      confidence: 0.77 },
    { keywords: ['dose', 'response', 'efficacy', 'toxicity'],
      model: 'dose-response curve (Hill equation)',
      purpose: 'Quantify therapeutic window and potency',
      justification: 'Standard pharmacological dose-response modeling',
      confidence: 0.79 },
    { keywords: ['survival', 'mortality', 'time-to-event'],
      model: 'Kaplan-Meier / Cox regression',
      purpose: 'Analyze time-to-event data and survival probability',
      justification: 'Standard biostatistical methods for clinical outcomes',
      confidence: 0.75 }
  ]],
  ['engineering', [
    { keywords: ['CFD', 'flow', 'fluid', 'simulation'],
      model: 'Navier-Stokes / k-epsilon turbulence',
      purpose: 'Simulate fluid flow behavior and transport phenomena',
      justification: 'Industry-standard CFD approach for turbulent flow',
      confidence: 0.82 },
    { keywords: ['optimization', 'design', 'parametric'],
      model: 'taguchi / DOE optimization',
      purpose: 'Systematic parameter optimization with minimal experiments',
      justification: 'Efficient experimental design for engineering optimization',
      confidence: 0.80 },
    { keywords: ['structural', 'fatigue', 'load', 'stress'],
      model: 'S-N curve / fatigue analysis',
      purpose: 'Predict structural fatigue life under cyclic loading',
      justification: 'Standard approach for structural durability assessment',
      confidence: 0.76 }
  ]],
  ['physics', [
    { keywords: ['optical', 'absorption', 'emission', 'spectrum'],
      model: 'Beer-Lambert law',
      purpose: 'Relate optical absorption to concentration and path length',
      justification: 'Fundamental optical relationship for quantitative spectroscopy',
      confidence: 0.85 },
    { keywords: ['quantum', 'energy', 'transition'],
      model: 'Schrödinger equation (perturbation theory)',
      purpose: 'Predict energy levels and transition probabilities',
      justification: 'Fundamental quantum mechanical framework',
      confidence: 0.80 }
  ]],
  ['computer-science', [
    { keywords: ['classification', 'prediction', 'pattern'],
      model: 'supervised learning (SVM/Random Forest/neural network)',
      purpose: 'Classify or predict from labeled training data',
      justification: 'Standard machine learning approaches for predictive tasks',
      confidence: 0.78 },
    { keywords: ['clustering', 'grouping', 'unsupervised'],
      model: 'k-means / DBSCAN clustering',
      purpose: 'Discover natural groupings in unlabeled data',
      justification: 'Standard unsupervised learning for pattern discovery',
      confidence: 0.75 },
    { keywords: ['optimization', 'search', 'schedule'],
      model: 'genetic algorithm / simulated annealing',
      purpose: 'Find near-optimal solutions in large search spaces',
      justification: 'Metaheuristic approaches for combinatorial optimization',
      confidence: 0.74 }
  ]]
])

// ============ Model matching ============

function findBestModel(
  domain: ResearchDomain,
  problemText: string
): ModelSelection | null {
  const entries = MODEL_KB.get(domain)
  if (!entries) return null

  let bestEntry: ModelEntry | null = null
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
    model: bestEntry.model,
    purpose: bestEntry.purpose,
    justification: bestEntry.justification,
    confidence: bestEntry.confidence
  }
}

// ============ Public API ============

/**
 * Phase 8-H0: recommend analysis models for a research problem.
 * Deterministic — keyword matching against model knowledge base.
 */
export function recommendModel(
  problem: ResearchProblem,
  _analysis: ProblemAnalysis
): ModelSelection {
  const problemText = (problem.title + ' ' + problem.objective).toLowerCase()
  const result = findBestModel(problem.domain, problemText)

  if (result) return result

  // Fallback: generic recommendation
  return {
    model: 'literature-based empirical correlation',
    purpose: 'Establish baseline relationship from existing data',
    justification: 'No specific model matched — start with empirical analysis of available data',
    confidence: 0.35
  }
}

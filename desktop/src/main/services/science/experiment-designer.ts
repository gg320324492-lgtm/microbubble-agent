// Experiment Designer (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: deterministic generation of ExperimentPlan objects from a
// ResearchProblem, ProblemAnalysis, and hypotheses. Uses domain-specific
// variable/measurement templates — no LLM.

import type {
  ResearchProblem,
  ProblemAnalysis,
  ResearchHypothesis,
  ExperimentPlan,
  DesignVariable,
  ExperimentGroup,
  EvaluationMetric,
  ResearchDomain
} from '../../../shared/science/research-design-schema'

// ============ Domain experiment templates ============

interface ExperimentTemplate {
  variables: readonly Omit<DesignVariable, 'importance'>[]
  measurements: readonly EvaluationMetric[]
  controlCondition: string
  expectedTrend: string
}

const DOMAIN_TEMPLATES: ReadonlyMap<ResearchDomain, ExperimentTemplate> = new Map([
  ['environment', {
    variables: [
      { name: 'bubble_diameter', type: 'independent', range: '50-500 nm', unit: 'nm' },
      { name: 'removal_efficiency', type: 'dependent', range: '0-100%', unit: '%' },
      { name: 'temperature', type: 'control', range: '20-25', unit: '°C' },
      { name: 'initial_concentration', type: 'independent', range: '10-100 mg/L', unit: 'mg/L' }
    ],
    measurements: [
      { name: 'particle_size_distribution', method: 'dynamic light scattering', reason: 'Characterize bubble size distribution' },
      { name: 'pollutant_concentration', method: 'UV-Vis spectroscopy', reason: 'Quantify removal efficiency over time' },
      { name: 'dissolved_oxygen', method: 'DO meter', reason: 'Measure oxygen mass transfer performance' }
    ],
    controlCondition: 'conventional aeration (no microbubbles)',
    expectedTrend: 'Decreasing bubble diameter increases removal efficiency up to an optimal size'
  }],
  ['material', {
    variables: [
      { name: 'synthesis_temperature', type: 'independent', range: '100-600', unit: '°C' },
      { name: 'crystal_size', type: 'dependent', range: '1-100 nm', unit: 'nm' },
      { name: 'precursor_concentration', type: 'independent', range: '0.1-2.0 M', unit: 'M' },
      { name: 'reaction_time', type: 'control', range: '1-24', unit: 'h' }
    ],
    measurements: [
      { name: 'xrd_pattern', method: 'X-ray diffraction', reason: 'Identify crystal phase and size' },
      { name: 'sem_image', method: 'scanning electron microscopy', reason: 'Observe morphology and particle size' },
      { name: 'bet_surface_area', method: 'BET analysis', reason: 'Quantify specific surface area' }
    ],
    controlCondition: 'standard synthesis conditions from literature',
    expectedTrend: 'Higher synthesis temperature increases crystal size but improves phase purity'
  }],
  ['chemical', {
    variables: [
      { name: 'catalyst_loading', type: 'independent', range: '0.1-5.0 wt%', unit: 'wt%' },
      { name: 'conversion_rate', type: 'dependent', range: '0-100%', unit: '%' },
      { name: 'reaction_temperature', type: 'independent', range: '25-150', unit: '°C' },
      { name: 'solvent', type: 'control', range: 'water', unit: '-' }
    ],
    measurements: [
      { name: 'gc_analysis', method: 'gas chromatography', reason: 'Quantify product distribution and yield' },
      { name: 'kinetic_profile', method: 'time-course sampling', reason: 'Determine reaction rate constants' },
      { name: 'catalyst_recycling', method: 'reusability test', reason: 'Assess catalyst stability over cycles' }
    ],
    controlCondition: 'uncatalyzed reaction under same conditions',
    expectedTrend: 'Conversion rate increases with catalyst loading up to saturation point'
  }],
  ['biomedical', {
    variables: [
      { name: 'drug_concentration', type: 'independent', range: '0.1-100 μM', unit: 'μM' },
      { name: 'cell_viability', type: 'dependent', range: '0-100%', unit: '%' },
      { name: 'incubation_time', type: 'independent', range: '24-72', unit: 'h' },
      { name: 'cell_line', type: 'control', range: 'standard line', unit: '-' }
    ],
    measurements: [
      { name: 'mtt_assay', method: 'MTT viability assay', reason: 'Quantify cell metabolic activity' },
      { name: 'flow_cytometry', method: 'flow cytometry', reason: 'Analyze cell population distribution' },
      { name: 'microscopy', method: 'fluorescence microscopy', reason: 'Visualize cellular morphology changes' }
    ],
    controlCondition: 'untreated cells under same culture conditions',
    expectedTrend: 'Cell viability decreases with drug concentration above therapeutic threshold'
  }],
  ['engineering', {
    variables: [
      { name: 'flow_rate', type: 'independent', range: '0.1-10 L/min', unit: 'L/min' },
      { name: 'pressure_drop', type: 'dependent', range: '0-500 kPa', unit: 'kPa' },
      { name: 'geometry', type: 'independent', range: '3 configurations', unit: '-' },
      { name: 'fluid', type: 'control', range: 'water', unit: '-' }
    ],
    measurements: [
      { name: 'pressure_profile', method: 'pressure transducer array', reason: 'Map pressure distribution along flow path' },
      { name: 'velocity_field', method: 'PIV or CFD', reason: 'Characterize flow patterns and velocity distribution' },
      { name: 'energy_consumption', method: 'power measurement', reason: 'Quantify energy efficiency' }
    ],
    controlCondition: 'baseline geometry at standard flow rate',
    expectedTrend: 'Pressure drop increases with flow rate; optimal geometry minimizes energy consumption'
  }],
  ['physics', {
    variables: [
      { name: 'wavelength', type: 'independent', range: '200-800 nm', unit: 'nm' },
      { name: 'intensity', type: 'dependent', range: '0-100%', unit: '%' },
      { name: 'sample_thickness', type: 'control', range: '1 mm', unit: 'mm' },
      { name: 'temperature', type: 'control', range: '293 K', unit: 'K' }
    ],
    measurements: [
      { name: 'absorption_spectrum', method: 'UV-Vis-NIR spectrophotometry', reason: 'Measure optical absorption characteristics' },
      { name: 'emission_spectrum', method: 'fluorescence spectroscopy', reason: 'Characterize emission properties' },
      { name: 'scattering_pattern', method: 'light scattering', reason: 'Analyze scattering behavior' }
    ],
    controlCondition: 'reference material under same conditions',
    expectedTrend: 'Optical properties vary with wavelength following material-specific absorption profile'
  }],
  ['computer-science', {
    variables: [
      { name: 'algorithm_variant', type: 'independent', range: '3-5 variants', unit: '-' },
      { name: 'accuracy', type: 'dependent', range: '0-100%', unit: '%' },
      { name: 'dataset_size', type: 'independent', range: '1K-1M samples', unit: 'samples' },
      { name: 'hardware', type: 'control', range: 'standard GPU', unit: '-' }
    ],
    measurements: [
      { name: 'accuracy_metric', method: 'cross-validation', reason: 'Quantify generalization performance' },
      { name: 'inference_latency', method: 'benchmark timing', reason: 'Measure computational efficiency' },
      { name: 'memory_usage', method: 'profiling', reason: 'Assess resource requirements' }
    ],
    controlCondition: 'baseline algorithm on same dataset',
    expectedTrend: 'Accuracy improves with dataset size; trade-off between accuracy and latency'
  }]
])

// ============ Design logic ============

function buildVariables(template: ExperimentTemplate, _problem: ResearchProblem): DesignVariable[] {
  return template.variables.map((v, idx) => ({
    ...v,
    importance: Math.round((0.9 - idx * 0.15) * 100) / 100
  }))
}

function buildGroups(problem: ResearchProblem, analysis: ProblemAnalysis): ExperimentGroup[] {
  const groups: ExperimentGroup[] = [
    {
      groupId: `${problem.problemId}-g-control`,
      condition: 'baseline/control condition',
      purpose: 'Establish baseline performance for comparison'
    }
  ]

  // Generate treatment groups from evidence requirements
  const evidenceGroups = analysis.requiredEvidence.slice(0, 3).map((evidence, idx) => ({
    groupId: `${problem.problemId}-g${idx + 1}`,
    condition: `varied ${evidence}`,
    purpose: `Investigate effect of ${evidence} on outcome`
  }))

  return [...groups, ...evidenceGroups]
}

// ============ Public API ============

/**
 * Phase 8-H0: design an experiment from a problem, analysis, and hypotheses.
 * Deterministic — template-based design with domain-specific variables.
 */
export function designExperiment(
  problem: ResearchProblem,
  analysis: ProblemAnalysis,
  hypotheses: ResearchHypothesis[]
): ExperimentPlan {
  const template = DOMAIN_TEMPLATES.get(problem.domain) ?? DOMAIN_TEMPLATES.get('environment')!

  const variables = buildVariables(template, problem)
  const groups = buildGroups(problem, analysis)
  const hypothesis = hypotheses[0]?.statement ?? analysis.keyScientificQuestion

  return {
    planId: `${problem.problemId}-plan`,
    hypothesis,
    variables,
    groups,
    measurements: [...template.measurements],
    expectedOutcome: template.expectedTrend
  }
}

// Experiment Optimization Agent Facade (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: dependency-injection facade that composes experiment analysis,
// variable importance, mechanism interpretation, optimization suggestions,
// and next experiment generation into a single coherent API. All components
// are deterministic — no LLM, no backend, no SDK, no auth.

import type {
  ExperimentObservation,
  ExperimentOptimizationResult
} from '../../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../../shared/science/research-design-schema'

import { analyzeExperiment } from './experiment-analyzer'
import { calculateImportance } from './variable-importance'
import { interpretMechanism } from './mechanism-interpreter'
import { generateSuggestions } from './optimization-advisor'
import { generateNextExperiments } from './next-experiment-generator'

// ============ Facade ============

/**
 * Phase 8-H1: the Experiment Optimization Agent composes all optimization
 * components. Input: ExperimentPlan + observations. Output: complete
 * ExperimentOptimizationResult with issues, importance, explanations,
 * suggestions, and next experiments.
 */
export class ExperimentOptimizationAgent {
  constructor() {}

  /**
   * Full optimization pipeline: analyze → importance → mechanism → suggest → next.
   */
  optimizeExperiment(
    plan: ExperimentPlan,
    observations: ExperimentObservation[]
  ): ExperimentOptimizationResult {
    const issues = analyzeExperiment(plan, observations)
    const importantVariables = calculateImportance(plan, observations)
    const explanations = interpretMechanism(issues, plan)
    const suggestions = generateSuggestions(issues, importantVariables)
    const nextExperiments = generateNextExperiments(plan, observations, importantVariables)

    return {
      issues,
      importantVariables,
      explanations,
      suggestions,
      nextExperiments
    }
  }

  /**
   * Analyze only (step 1).
   */
  analyzeExperiment(plan: ExperimentPlan, observations: ExperimentObservation[]) {
    return analyzeExperiment(plan, observations)
  }

  /**
   * Calculate importance only (step 2).
   */
  calculateImportance(plan: ExperimentPlan, observations: ExperimentObservation[]) {
    return calculateImportance(plan, observations)
  }

  /**
   * Interpret mechanisms only (step 3).
   */
  interpretMechanism(issues: Parameters<typeof interpretMechanism>[0], plan: ExperimentPlan) {
    return interpretMechanism(issues, plan)
  }

  /**
   * Generate suggestions only (step 4).
   */
  generateSuggestions(issues: Parameters<typeof generateSuggestions>[0], importantVariables: Parameters<typeof generateSuggestions>[1]) {
    return generateSuggestions(issues, importantVariables)
  }

  /**
   * Generate next experiments only (step 5).
   */
  generateNextExperiments(plan: ExperimentPlan, observations: ExperimentObservation[], importantVariables: Parameters<typeof generateNextExperiments>[2]) {
    return generateNextExperiments(plan, observations, importantVariables)
  }
}

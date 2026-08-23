// Research Design Agent Facade (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: dependency-injection facade that composes problem analysis,
// hypothesis generation, experiment design, and model recommendation into
// a single coherent API. All components are deterministic — no LLM, no
// backend, no SDK, no auth.

import type {
  ResearchProblem,
  ProblemAnalysis,
  ResearchHypothesis,
  ExperimentPlan,
  ModelSelection,
  ResearchDesignResult
} from '../../../shared/science/research-design-schema'

import { analyzeProblem } from './problem-analyzer'
import { generateHypotheses } from './hypothesis-generator'
import { designExperiment } from './experiment-designer'
import { recommendModel } from './model-recommender'

// ============ Facade ============

/**
 * Phase 8-H0: the Research Design Agent composes all design components.
 * Input: a ResearchProblem. Output: a complete ResearchDesignResult with
 * analysis, hypotheses, experiment plan, and model selection.
 */
export class ResearchDesignAgent {
  constructor() {}

  /**
   * Full research design pipeline: analyze → hypothesize → design → model.
   */
  designResearch(problem: ResearchProblem): ResearchDesignResult {
    const problemAnalysis = analyzeProblem(problem)
    const hypotheses = generateHypotheses(problem, problemAnalysis)
    const experimentPlan = designExperiment(problem, problemAnalysis, hypotheses)
    const modelSelection = recommendModel(problem, problemAnalysis)

    return {
      problemAnalysis,
      hypotheses,
      experimentPlan,
      modelSelection
    }
  }

  /**
   * Analyze only (step 1 of pipeline).
   */
  analyzeProblem(problem: ResearchProblem): ProblemAnalysis {
    return analyzeProblem(problem)
  }

  /**
   * Generate hypotheses only (step 2 of pipeline).
   */
  generateHypotheses(
    problem: ResearchProblem,
    analysis: ProblemAnalysis
  ): ResearchHypothesis[] {
    return generateHypotheses(problem, analysis)
  }

  /**
   * Design experiment only (step 3 of pipeline).
   */
  designExperiment(
    problem: ResearchProblem,
    analysis: ProblemAnalysis,
    hypotheses: ResearchHypothesis[]
  ): ExperimentPlan {
    return designExperiment(problem, analysis, hypotheses)
  }

  /**
   * Recommend model only (step 4 of pipeline).
   */
  recommendModel(
    problem: ResearchProblem,
    analysis: ProblemAnalysis
  ): ModelSelection {
    return recommendModel(problem, analysis)
  }
}

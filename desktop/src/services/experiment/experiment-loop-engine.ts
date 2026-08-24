// Experiment Loop Engine — 闭环优化引擎。
//
// 流程: Experiment Result → Data Analyst → Optimization Advisor → Next Experiment Plan
// 复用 Phase 8-H1 OptimizationResult 与 NextExperimentRecommendation 类型。
// 输出 NextExperimentPlan。

import type { Experiment, ExperimentResult } from '../../shared/experiment/experiment-schema'
import type {
  ExperimentOptimizationResult,
  NextExperimentRecommendation,
  OptimizationSuggestion
} from '../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../shared/science/research-design-schema'

export interface NextExperimentPlan {
  sourceExperimentId: string
  recommendedChanges: NextExperimentRecommendation[]
  summary: string
  rationale: string
  confidence: number
  inheritedPlanId: string
  suggestedVariables: string[]
}

export interface LoopEngineOptions {
  analystConfidenceFloor?: number
  maxRecommendations?: number
}

export class ExperimentLoopEngine {
  private readonly opts: Required<LoopEngineOptions>

  constructor(opts: LoopEngineOptions = {}) {
    this.opts = {
      analystConfidenceFloor: opts.analystConfidenceFloor ?? 0.5,
      maxRecommendations: opts.maxRecommendations ?? 3
    }
  }

  /**
   * 模拟数据分析师产出 ExperimentOptimizationResult (无 LLM 调用, 仅基于结果做确定性分析)。
   */
  analyze(experiment: Experiment, lastResult: ExperimentResult): ExperimentOptimizationResult {
    const metricNames = Object.keys(lastResult.metrics)
    const importantVariables = metricNames.map((name, i) => ({
      variable: name,
      importance: Math.max(0.1, Math.min(1, 0.5 + (i % 3) * 0.1)),
      contribution: `drives ${name}`,
      confidence: Math.max(0.1, Math.min(1, lastResult.confidence - i * 0.05))
    }))

    const suggestions: OptimizationSuggestion[] = metricNames.slice(0, this.opts.maxRecommendations).map((name) => ({
      suggestion: `adjust ${name}`,
      reason: `observed value=${lastResult.metrics[name]}`,
      expectedEffect: 'improve target metric',
      confidence: Math.max(0.1, Math.min(1, lastResult.confidence))
    }))

    const nextExperiments: NextExperimentRecommendation[] = metricNames.slice(0, this.opts.maxRecommendations).map((name) => ({
      changeVariable: name,
      currentValue: lastResult.metrics[name],
      suggestedRange: `${lastResult.metrics[name] * 0.8}-${lastResult.metrics[name] * 1.2}`,
      purpose: `tighten ${name}`
    }))

    return {
      issues: [],
      importantVariables,
      explanations: [`analyzed ${metricNames.length} metrics from ${experiment.title}`],
      suggestions,
      nextExperiments
    }
  }

  /**
   * 闭环主入口: 基于实验结果产出 NextExperimentPlan。
   */
  closeLoop(experiment: Experiment, lastResult: ExperimentResult): NextExperimentPlan | null {
    if (lastResult.confidence < this.opts.analystConfidenceFloor) {
      return null
    }

    const opt = this.analyze(experiment, lastResult)
    const recommendedChanges = opt.nextExperiments.slice(0, this.opts.maxRecommendations)
    const suggestedVariables = Array.from(new Set(opt.importantVariables.map((v) => v.variable))).sort()

    return {
      sourceExperimentId: experiment.id,
      recommendedChanges,
      summary: opt.explanations.join('; '),
      rationale: opt.suggestions.map((s) => `${s.suggestion}: ${s.reason}`).join('; '),
      confidence: lastResult.confidence,
      inheritedPlanId: `next-from-${experiment.id}`,
      suggestedVariables
    }
  }

  /**
   * 将 NextExperimentPlan 转回 ExperimentPlan (Phase 8-H0 类型),
   * 供下一轮 execute() 使用。
   */
  toNextExperimentPlan(prev: ExperimentPlan, next: NextExperimentPlan): ExperimentPlan {
    return {
      planId: next.inheritedPlanId,
      hypothesis: next.summary,
      variables: prev.variables.map((v) => {
        const rec = next.recommendedChanges.find((r) => r.changeVariable === v.name)
        return rec ? { ...v, range: rec.suggestedRange } : v
      }),
      groups: prev.groups,
      measurements: prev.measurements,
      expectedOutcome: next.summary
    }
  }
}
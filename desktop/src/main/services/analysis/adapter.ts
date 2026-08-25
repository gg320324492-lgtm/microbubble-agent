// Analysis Adapter — Phase 8-M1-D
// AnalysisEngineAdapter 接口 + LocalAnalysisEngine (默认实现).
// 未来可替换为 RemoteAnalysisEngine (Python service) — 渲染端 / 业务层无感.

import type { AnalysisEngine } from './analysis-engine'
import type { StatisticsResult } from './types'

export interface AnalysisResultRecord {
  id: string
  runType: string
  status: string | null
  model: string | null
  startedAt: number
  finishedAt: number | null
  summary: string | null
  confidence: number | null
  parameters: Array<{ name: string; value: number; unit: string | null; stdError: number | null; pValue: number | null }>
}

export interface AnalysisEngineAdapter {
  runKinetic(experimentId: string, model: 'first-order' | 'zero-order' | 'pseudo-second-order', metric: string): Promise<string>
  runRegression(experimentId: string, xMetric: string, yMetric: string, degree: 1 | 2 | 3 | 4): Promise<string>
  runCorrelation(experimentId: string, xMetric: string, yMetric: string): Promise<string>
  runCurve(experimentId: string, family: 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian', metric: string): Promise<string>
  listByExperiment(experimentId: string): Promise<AnalysisResultRecord[]>
  statistics(experimentId: string, metric: string): Promise<{ summary: StatisticsResult; n: number }>
}

class LocalAnalysisEngineAdapter implements AnalysisEngineAdapter {
  constructor(private readonly engine: AnalysisEngine) {}

  async runKinetic(experimentId: string, model: 'first-order' | 'zero-order' | 'pseudo-second-order', metric: string): Promise<string> {
    return this.engine.runKinetic(experimentId, model, metric)
  }
  async runRegression(experimentId: string, xMetric: string, yMetric: string, degree: 1 | 2 | 3 | 4): Promise<string> {
    return this.engine.runRegression(experimentId, xMetric, yMetric, degree)
  }
  async runCorrelation(experimentId: string, xMetric: string, yMetric: string): Promise<string> {
    return this.engine.runCorrelation(experimentId, xMetric, yMetric)
  }
  async runCurve(experimentId: string, family: 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian', metric: string): Promise<string> {
    return this.engine.runCurve(experimentId, family, metric)
  }
  async listByExperiment(experimentId: string): Promise<AnalysisResultRecord[]> {
    return this.engine.listByExperiment(experimentId) as AnalysisResultRecord[]
  }
  async statistics(experimentId: string, metric: string): Promise<{ summary: StatisticsResult; n: number }> {
    return this.engine.statistics(experimentId, metric) as { summary: StatisticsResult; n: number }
  }
}

export function createLocalAnalysisEngineAdapter(engine: AnalysisEngine): AnalysisEngineAdapter {
  return new LocalAnalysisEngineAdapter(engine)
}
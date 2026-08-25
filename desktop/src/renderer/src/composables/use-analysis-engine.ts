// useAnalysisEngine Composable — Phase 8-M1-D
// 渲染端调用 analysis.* IPC, 完全通过主进程分析引擎计算.
// 严禁在 composable 中复刻数值算法; 仅桥接.

import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export type KineticModelKind = 'first-order' | 'zero-order' | 'pseudo-second-order'
export type RegressionDegree = 1 | 2 | 3 | 4
export type CurveFamily = 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian'

export interface AnalysisResultRow {
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

export interface StatisticsSummary {
  metric: string
  count: number
  missingRate: number
  mean: number | null
  std: number | null
  median: number | null
  min: number | null
  max: number | null
  p25: number | null
  p75: number | null
  outliers: number
  interpretation: string
}

interface AnalysisApi {
  runKinetic?: (experimentId: string, model: KineticModelKind, metric: string) => Promise<string>
  runRegression?: (experimentId: string, xMetric: string, yMetric: string, degree: RegressionDegree) => Promise<string>
  runCorrelation?: (experimentId: string, xMetric: string, yMetric: string) => Promise<string>
  runCurve?: (experimentId: string, family: CurveFamily, metric: string) => Promise<string>
  listByExperiment?: (experimentId: string) => Promise<AnalysisResultRow[]>
  statistics?: (experimentId: string, metric: string) => Promise<{ summary: StatisticsSummary; n: number }>
}

function getAnalysisApi(): AnalysisApi | null {
  if (typeof window === 'undefined') return null
  return (window as unknown as { api?: { analysis?: AnalysisApi } }).api?.analysis ?? null
}

export interface AnalysisBus {
  results: Ref<AnalysisResultRow[]>
  statistics: Ref<{ summary: StatisticsSummary; n: number } | null>
  isRunning: Ref<boolean>
  errorMessage: Ref<string>
  hasResults: Ref<boolean>
  runKinetic(experimentId: string, model: KineticModelKind, metric: string): Promise<string | null>
  runRegression(experimentId: string, xMetric: string, yMetric: string, degree: RegressionDegree): Promise<string | null>
  runCorrelation(experimentId: string, xMetric: string, yMetric: string): Promise<string | null>
  runCurve(experimentId: string, family: CurveFamily, metric: string): Promise<string | null>
  loadResults(experimentId: string): Promise<void>
  loadStatistics(experimentId: string, metric: string): Promise<void>
  clear(): void
}

export function useAnalysisEngine(): AnalysisBus {
  const results = ref<AnalysisResultRow[]>([])
  const statistics = ref<{ summary: StatisticsSummary; n: number } | null>(null)
  const isRunning = ref(false)
  const errorMessage = ref('')

  async function run<T>(fn: () => Promise<T>): Promise<T | null> {
    isRunning.value = true; errorMessage.value = ''
    try {
      return await fn()
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '分析运行失败'
      return null
    } finally {
      isRunning.value = false
    }
  }

  async function runKinetic(experimentId: string, model: KineticModelKind, metric: string): Promise<string | null> {
    const api = getAnalysisApi()
    if (!api?.runKinetic) return null
    const id = await run(() => api.runKinetic!(experimentId, model, metric))
    if (id) await loadResults(experimentId)
    return id
  }

  async function runRegression(experimentId: string, xMetric: string, yMetric: string, degree: RegressionDegree): Promise<string | null> {
    const api = getAnalysisApi()
    if (!api?.runRegression) return null
    const id = await run(() => api.runRegression!(experimentId, xMetric, yMetric, degree))
    if (id) await loadResults(experimentId)
    return id
  }

  async function runCorrelation(experimentId: string, xMetric: string, yMetric: string): Promise<string | null> {
    const api = getAnalysisApi()
    if (!api?.runCorrelation) return null
    const id = await run(() => api.runCorrelation!(experimentId, xMetric, yMetric))
    if (id) await loadResults(experimentId)
    return id
  }

  async function runCurve(experimentId: string, family: CurveFamily, metric: string): Promise<string | null> {
    const api = getAnalysisApi()
    if (!api?.runCurve) return null
    const id = await run(() => api.runCurve!(experimentId, family, metric))
    if (id) await loadResults(experimentId)
    return id
  }

  async function loadResults(experimentId: string): Promise<void> {
    const api = getAnalysisApi()
    if (!api?.listByExperiment) { results.value = []; return }
    try {
      results.value = await api.listByExperiment(experimentId)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载分析结果失败'
    }
  }

  async function loadStatistics(experimentId: string, metric: string): Promise<void> {
    const api = getAnalysisApi()
    if (!api?.statistics) { statistics.value = null; return }
    try {
      statistics.value = await api.statistics(experimentId, metric)
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载统计失败'
    }
  }

  function clear(): void {
    results.value = []
    statistics.value = null
    errorMessage.value = ''
  }

  return {
    results, statistics, isRunning, errorMessage,
    hasResults: computed(() => results.value.length > 0),
    runKinetic, runRegression, runCorrelation, runCurve,
    loadResults, loadStatistics, clear
  }
}
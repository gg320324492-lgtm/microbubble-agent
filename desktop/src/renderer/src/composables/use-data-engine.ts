// useDataEngine Composable — Phase 8-M1-C
// 渲染端调用 dataEngine.* IPC, 完全通过 main 进程仓库操作 SQLite.
// 严禁在 composable 中 import better-sqlite3; 仅通过 window.api.dataEngine 桥接.

import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export interface DataEngineSample {
  id: string
  experimentId: string
  batch: string | null
  replicate: number | null
  conditionLabel: string | null
  sampledAt: number
  operator: string | null
  notes: string | null
  metadata: Record<string, unknown> | null
}

export interface DataEngineAnalysis {
  id: string
  experimentId: string
  runType: string
  status: string | null
  startedAt: number
  finishedAt: number | null
  model: string | null
  summary: string | null
  confidence: number | null
}

export interface DataEngineModelParam {
  id?: number
  analysisId: string
  name: string
  value: number
  unit: string | null
  stdError: number | null
  pValue: number | null
}

export interface DataEngineFigure {
  id: string
  experimentId: string
  analysisId: string | null
  figureType: string
  title: string | null
  renderedAt: number | null
}

interface DataEngineApi {
  sampleCreate?: (s: Record<string, unknown>) => Promise<Record<string, unknown>>
  sampleListByExperiment?: (id: string) => Promise<Record<string, unknown>[]>
  sampleDelete?: (id: string) => Promise<{ deleted: boolean }>
  analysisCreate?: (r: Record<string, unknown>) => Promise<Record<string, unknown>>
  analysisListByExperiment?: (id: string) => Promise<Record<string, unknown>[]>
  analysisAddModelParam?: (p: Record<string, unknown>) => Promise<Record<string, unknown>>
  analysisListModelParams?: (id: string) => Promise<Record<string, unknown>[]>
  figureCreate?: (f: Record<string, unknown>) => Promise<Record<string, unknown>>
  figureListByExperiment?: (id: string) => Promise<Record<string, unknown>[]>
  figureListByAnalysis?: (id: string) => Promise<Record<string, unknown>[]>
}

function getDataEngineApi(): DataEngineApi | null {
  if (typeof window === 'undefined') return null
  return (window as unknown as { api?: { dataEngine?: DataEngineApi } }).api?.dataEngine ?? null
}

export interface DataEngineBus {
  samples: Ref<DataEngineSample[]>
  analyses: Ref<DataEngineAnalysis[]>
  params: Ref<DataEngineModelParam[]>
  figures: Ref<DataEngineFigure[]>
  isLoading: Ref<boolean>
  errorMessage: Ref<string>
  hasData: Ref<boolean>
  loadSamples(experimentId: string): Promise<void>
  loadAnalyses(experimentId: string): Promise<void>
  loadFigures(experimentId: string): Promise<void>
  createSample(sample: Omit<DataEngineSample, 'sampledAt'> & { sampledAt?: number }): Promise<DataEngineSample | null>
  createAnalysis(result: Omit<DataEngineAnalysis, 'startedAt'> & { startedAt?: number }): Promise<DataEngineAnalysis | null>
  addModelParam(param: Omit<DataEngineModelParam, 'id'>): Promise<DataEngineModelParam | null>
  createFigure(figure: Omit<DataEngineFigure, 'renderedAt'> & { renderedAt?: number }): Promise<DataEngineFigure | null>
  clear(): void
}

export function useDataEngine(): DataEngineBus {
  const samples = ref<DataEngineSample[]>([])
  const analyses = ref<DataEngineAnalysis[]>([])
  const params = ref<DataEngineModelParam[]>([])
  const figures = ref<DataEngineFigure[]>([])
  const isLoading = ref(false)
  const errorMessage = ref('')

  async function loadSamples(experimentId: string): Promise<void> {
    const api = getDataEngineApi()
    if (!api?.sampleListByExperiment) { samples.value = []; return }
    isLoading.value = true; errorMessage.value = ''
    try {
      const rows = await api.sampleListByExperiment(experimentId)
      samples.value = rows as unknown as DataEngineSample[]
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载样本失败'
    } finally {
      isLoading.value = false
    }
  }

  async function loadAnalyses(experimentId: string): Promise<void> {
    const api = getDataEngineApi()
    if (!api?.analysisListByExperiment) { analyses.value = []; return }
    isLoading.value = true; errorMessage.value = ''
    try {
      const rows = await api.analysisListByExperiment(experimentId)
      analyses.value = rows as unknown as DataEngineAnalysis[]
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载分析失败'
    } finally {
      isLoading.value = false
    }
  }

  async function loadFigures(experimentId: string): Promise<void> {
    const api = getDataEngineApi()
    if (!api?.figureListByExperiment) { figures.value = []; return }
    isLoading.value = true; errorMessage.value = ''
    try {
      const rows = await api.figureListByExperiment(experimentId)
      figures.value = rows as unknown as DataEngineFigure[]
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '加载图表失败'
    } finally {
      isLoading.value = false
    }
  }

  async function createSample(sample: Omit<DataEngineSample, 'sampledAt'> & { sampledAt?: number }): Promise<DataEngineSample | null> {
    const api = getDataEngineApi()
    if (!api?.sampleCreate) return null
    try {
      const result = await api.sampleCreate(sample as unknown as Record<string, unknown>)
      if (result) {
        samples.value = [result as unknown as DataEngineSample, ...samples.value]
        return result as unknown as DataEngineSample
      }
      return null
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '创建样本失败'
      return null
    }
  }

  async function createAnalysis(result: Omit<DataEngineAnalysis, 'startedAt'> & { startedAt?: number }): Promise<DataEngineAnalysis | null> {
    const api = getDataEngineApi()
    if (!api?.analysisCreate) return null
    try {
      const created = await api.analysisCreate(result as unknown as Record<string, unknown>)
      if (created) {
        analyses.value = [created as unknown as DataEngineAnalysis, ...analyses.value]
        return created as unknown as DataEngineAnalysis
      }
      return null
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '创建分析失败'
      return null
    }
  }

  async function addModelParam(param: Omit<DataEngineModelParam, 'id'>): Promise<DataEngineModelParam | null> {
    const api = getDataEngineApi()
    if (!api?.analysisAddModelParam) return null
    try {
      const created = await api.analysisAddModelParam(param as unknown as Record<string, unknown>)
      if (created) {
        params.value = [...params.value, created as unknown as DataEngineModelParam]
        return created as unknown as DataEngineModelParam
      }
      return null
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '添加模型参数失败'
      return null
    }
  }

  async function createFigure(figure: Omit<DataEngineFigure, 'renderedAt'> & { renderedAt?: number }): Promise<DataEngineFigure | null> {
    const api = getDataEngineApi()
    if (!api?.figureCreate) return null
    try {
      const created = await api.figureCreate(figure as unknown as Record<string, unknown>)
      if (created) {
        figures.value = [created as unknown as DataEngineFigure, ...figures.value]
        return created as unknown as DataEngineFigure
      }
      return null
    } catch (err) {
      errorMessage.value = err instanceof Error ? err.message : '创建图表失败'
      return null
    }
  }

  function clear(): void {
    samples.value = []
    analyses.value = []
    params.value = []
    figures.value = []
    errorMessage.value = ''
  }

  return {
    samples, analyses, params, figures,
    isLoading, errorMessage,
    hasData: computed(() => samples.value.length > 0 || analyses.value.length > 0 || figures.value.length > 0),
    loadSamples, loadAnalyses, loadFigures,
    createSample, createAnalysis, addModelParam, createFigure,
    clear
  }
}
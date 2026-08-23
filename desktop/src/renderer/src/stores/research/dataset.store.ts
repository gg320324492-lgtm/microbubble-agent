// Dataset Store — 数据集/分析状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { dataAnalysisService, type AnalysisReport, type StatisticalResult, type ModelFitResult } from '../../services/research/data-analysis.service'

export const useDatasetStore = defineStore('research-dataset', () => {
  const report = ref<AnalysisReport | null>(null)
  const isLoading = ref(false)

  const statistics = computed(() => report.value?.statistics ?? [])
  const models = computed(() => report.value?.models ?? [])
  const conclusions = computed(() => report.value?.conclusions ?? [])
  const quality = computed(() => report.value?.quality ?? null)

  async function loadReport() {
    isLoading.value = true
    try { report.value = await dataAnalysisService.getAnalysisReport() }
    finally { isLoading.value = false }
  }

  return { report, isLoading, statistics, models, conclusions, quality, loadReport }
})

// Dataset Store — 数据集/分析状态管理（升级版）。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { dataAnalysisService, type AnalysisReport, type VariableImportance } from '../../services/research/data-analysis.service'

export const useDatasetStore = defineStore('research-dataset', () => {
  const report = ref<AnalysisReport | null>(null)
  const importance = ref<VariableImportance[]>([])
  const isLoading = ref(false)

  const statistics = computed(() => report.value?.statistics ?? [])
  const models = computed(() => report.value?.models ?? [])
  const conclusions = computed(() => report.value?.conclusions ?? [])
  const quality = computed(() => report.value?.quality ?? null)
  const figures = computed(() => report.value?.figures ?? [])

  async function loadReport() {
    isLoading.value = true
    try {
      report.value = await dataAnalysisService.getAnalysisReport()
      importance.value = await dataAnalysisService.getVariableImportance()
    } finally { isLoading.value = false }
  }

  return { report, importance, isLoading, statistics, models, conclusions, quality, figures, loadReport }
})

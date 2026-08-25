// Dataset Store — 数据集/分析状态管理 (Phase 8-M0-D 纯状态容器, 不直接调用 service).
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnalysisReport, VariableImportance } from '../../services/research/data-analysis.service'

export const useDatasetStore = defineStore('research-dataset', () => {
  const report = ref<AnalysisReport | null>(null)
  const importance = ref<VariableImportance[]>([])
  const isLoading = ref(false)
  const errorMessage = ref<string>('')

  const statistics = computed(() => report.value?.statistics ?? [])
  const models = computed(() => report.value?.models ?? [])
  const conclusions = computed(() => report.value?.conclusions ?? [])
  const quality = computed(() => report.value?.quality ?? null)
  const figures = computed(() => report.value?.figures ?? [])
  const isEmpty = computed(() => report.value === null)

  function setReport(next: AnalysisReport) {
    report.value = next
  }
  function setImportance(next: VariableImportance[]) {
    importance.value = [...next]
  }
  function setLoading(loading: boolean) {
    isLoading.value = loading
  }
  function setError(message: string) {
    errorMessage.value = message
  }
  async function loadReport(_loader: () => Promise<void>) {
    isLoading.value = true
    void _loader().finally(() => { isLoading.value = false })
  }
  function reset() {
    report.value = null
    importance.value = []
    isLoading.value = false
    errorMessage.value = ''
  }

  return {
    report, importance, isLoading, errorMessage,
    statistics, models, conclusions, quality, figures, isEmpty,
    setReport, setImportance, setLoading, setError, loadReport, reset
  }
})
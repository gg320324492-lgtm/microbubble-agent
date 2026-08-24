// Experiment Store — 实验设计状态管理。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { experimentService, type ExperimentDesign } from '../../services/research/experiment.service'

export const useExperimentStore = defineStore('research-experiment', () => {
  const design = ref<ExperimentDesign | null>(null)
  const isLoading = ref(false)

  async function loadDesign() {
    isLoading.value = true
    try { design.value = await experimentService.getDesign() }
    finally { isLoading.value = false }
  }

  async function updateDesign(patch: Partial<ExperimentDesign>) {
    await experimentService.updateDesign(patch)
    if (design.value) design.value = { ...design.value, ...patch }
  }

  return { design, isLoading, loadDesign, updateDesign }
})

// Manuscript Store — 论文助手状态管理 (Phase 8-M0-C 纯状态容器, 不直接调用 service).
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Manuscript, WritingIssue } from '../../../../shared/science/manuscript-schema'

export const useManuscriptStore = defineStore('research-manuscript', () => {
  const manuscript = ref<Manuscript | null>(null)
  const issues = ref<WritingIssue[]>([])
  const activeSection = ref<string>('introduction')
  const isLoading = ref(false)
  const errorMessage = ref<string>('')

  const sections = computed(() => manuscript.value?.sections ?? [])
  const highlights = computed(() => manuscript.value?.highlights ?? [])
  const wordCount = computed(() => {
    const m = manuscript.value as unknown as { wordCount?: number } | null
    return m?.wordCount ?? 0
  })
  const issueCount = computed(() => issues.value.length)
  const isEmpty = computed(() => manuscript.value !== null && sections.value.length === 0)

  function setManuscript(next: Manuscript) {
    manuscript.value = next
  }
  function setIssues(next: WritingIssue[]) {
    issues.value = [...next]
  }
  function setActiveSection(type: string) {
    activeSection.value = type
  }
  function setLoading(loading: boolean) {
    isLoading.value = loading
  }
  function setError(message: string) {
    errorMessage.value = message
  }
  function loadManuscript(_loader?: () => Promise<void>) {
    isLoading.value = true
    const safeLoader = typeof _loader === 'function' ? _loader : null
    if (safeLoader) {
      void safeLoader().finally(() => { isLoading.value = false })
    } else {
      isLoading.value = false
    }
  }
  function reset() {
    manuscript.value = null
    issues.value = []
    activeSection.value = 'introduction'
    isLoading.value = false
    errorMessage.value = ''
  }

  return {
    manuscript,
    issues,
    activeSection,
    isLoading,
    errorMessage,
    sections,
    highlights,
    wordCount,
    issueCount,
    isEmpty,
    setManuscript,
    setIssues,
    setActiveSection,
    setLoading,
    setError,
    loadManuscript,
    reset
  }
})
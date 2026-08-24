// Manuscript Store — 论文助手状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { manuscriptService, type Manuscript, type WritingIssue } from '../../services/research/manuscript.service'

export const useManuscriptStore = defineStore('research-manuscript', () => {
  const manuscript = ref<Manuscript | null>(null)
  const issues = ref<WritingIssue[]>([])
  const activeSection = ref<string>('introduction')
  const isLoading = ref(false)

  const sections = computed(() => manuscript.value?.sections ?? [])
  const highlights = computed(() => manuscript.value?.highlights ?? [])
  const wordCount = computed(() => manuscript.value?.wordCount ?? 0)
  const issueCount = computed(() => issues.value.length)

  async function loadManuscript() {
    isLoading.value = true
    try {
      manuscript.value = await manuscriptService.getManuscript()
      issues.value = await manuscriptService.getWritingIssues()
    } finally { isLoading.value = false }
  }

  function setActiveSection(type: string) { activeSection.value = type }

  return { manuscript, issues, activeSection, isLoading, sections, highlights, wordCount, issueCount, loadManuscript, setActiveSection }
})

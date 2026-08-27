// Knowledge Store — 文献/知识库状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { knowledgeService, type DocumentItem, type KnowledgeFolder } from '../../services/research/knowledge.service'
import { literatureService, type PaperAssessment } from '../../services/research/literature.service'

export const useKnowledgeStore = defineStore('research-knowledge', () => {
  const documents = ref<DocumentItem[]>([])
  const folders = ref<KnowledgeFolder[]>([])
  const selectedDocumentId = ref<string | null>(null)
  const assessments = ref<PaperAssessment[]>([])
  const searchQuery = ref('')
  const isLoading = ref(false)

  const selectedDocument = computed(() => documents.value.find(d => d.id === selectedDocumentId.value))
  const filteredDocuments = computed(() => {
    if (!searchQuery.value) return documents.value
    const q = searchQuery.value.toLowerCase()
    return documents.value.filter(d => d.title.toLowerCase().includes(q) || d.tags.some(t => t.includes(q)))
  })
  const totalDocuments = computed(() => documents.value.length)

  async function loadDocuments() {
    isLoading.value = true
    try {
      // [类 20.191] 真实数据接入. 失败时保持空数组, UI 显示空态.
      try {
        documents.value = await knowledgeService.getDocuments()
        folders.value = await knowledgeService.getFolders()
      } catch (e) {
        console.warn('[knowledge.store] loadDocuments failed:', e instanceof Error ? e.message : String(e))
        documents.value = []
        folders.value = []
      }
    } finally { isLoading.value = false }
  }

  async function loadAssessments() {
    // [类 20.191] literature service 暂未接真实 adapter, 失败时保持空数组.
    try {
      assessments.value = await literatureService.getDocumentAssessments()
    } catch (e) {
      // silently ignore - service 未 wire 抛 NotWiredError
      assessments.value = []
    }
  }

  function selectDocument(id: string) { selectedDocumentId.value = id }
  function setSearch(q: string) { searchQuery.value = q }

  return { documents, folders, selectedDocumentId, selectedDocument, filteredDocuments, totalDocuments, assessments, searchQuery, isLoading, loadDocuments, loadAssessments, selectDocument, setSearch }
})

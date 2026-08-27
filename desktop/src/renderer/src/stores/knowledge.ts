// Knowledge Pinia store —— 分类 + 文档列表 (分页) + 当前详情 + 搜索 query.
//
// [类 20.209] 2026-08-28: 切换到本地 SQLite (research/knowledge.service.ts SqliteKnowledgeAdapter).
//   之前走 web API /knowledge/categories → 只显示 web 端 97 条 (子集).
//   改用本地 desktop_knowledge 表 (535 条真实知识条目, 23 个分类).
//
// 数据流: View -> Store -> Service (SqliteAdapter) -> window.api.database -> main IPC -> SQLite.

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  knowledgeService as sqliteKnowledge,
  type DocumentItem,
  type SearchResult,
  type KnowledgeFolder
} from '../services/research/knowledge.service'

const DEFAULT_PAGE_SIZE = 20

interface DisplayCategory {
  name: string
  count: number
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  // 分类 + 选中分类
  const categories = ref<DisplayCategory[]>([])
  const selectedCategory = ref<string>('all')

  // 文档列表 + 分页 + 搜索
  const items = ref<DocumentItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const keyword = ref('')

  // 详情
  const currentDetail = ref<DocumentItem | null>(null)
  const detailLoading = ref(false)

  const lastError = ref<string | null>(null)
  const loading = ref(false)

  // ============ 派生 ============
  const totalCount = computed(() => categories.value.reduce((acc, c) => acc + c.count, 0))
  const selectedCategoryCount = computed(() => {
    if (selectedCategory.value === 'all') return totalCount.value
    const c = categories.value.find((x) => x.name === selectedCategory.value)
    return c?.count ?? 0
  })
  const pageInfo = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    total: total.value,
    totalPages: Math.max(1, Math.ceil(total.value / pageSize.value))
  }))

  // ============ Actions ============
  async function loadCategories(): Promise<boolean> {
    try {
      const folders = await sqliteKnowledge.getFolders()
      categories.value = folders
        .filter((f: KnowledgeFolder) => f.name && f.name !== '未分类')
        .map((f: KnowledgeFolder) => ({ name: f.name, count: f.count }))
      return true
    } catch (err) {
      lastError.value = err instanceof Error ? err.message : String(err)
      return false
    }
  }

  async function loadList(): Promise<boolean> {
    loading.value = true
    try {
      let docs: DocumentItem[] = []
      if (keyword.value.trim()) {
        // 搜索路径: 先拿所有匹配
        const r: SearchResult[] = await sqliteKnowledge.searchDocuments(keyword.value)
        docs = (await Promise.all(r.map((s) => sqliteKnowledge.getDocument(s.documentId))))
          .filter((d): d is DocumentItem => !!d)
      } else {
        docs = await sqliteKnowledge.getDocuments()
      }
      // 客户端按 category 过滤
      if (selectedCategory.value !== 'all') {
        docs = docs.filter((d) => {
          const cat = (d as unknown as { category?: string }).category
          // 同时尝试一些变体
          return cat === selectedCategory.value ||
                 (selectedCategory.value === '综述' && cat?.includes('综述'))
        })
      }
      // 分页
      total.value = docs.length
      const start = (page.value - 1) * pageSize.value
      items.value = docs.slice(start, start + pageSize.value)
      return true
    } catch (err) {
      lastError.value = err instanceof Error ? err.message : String(err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function selectCategory(name: string): Promise<void> {
    selectedCategory.value = name
    page.value = 1
    await loadList()
  }

  async function search(q: string): Promise<void> {
    keyword.value = q
    page.value = 1
    await loadList()
  }

  async function goToPage(p: number): Promise<void> {
    if (p < 1 || p > pageInfo.value.totalPages) return
    if (p === page.value) return
    page.value = p
    await loadList()
  }

  async function loadDetail(id: string | number): Promise<boolean> {
    detailLoading.value = true
    try {
      const d = await sqliteKnowledge.getDocument(String(id))
      if (d) {
        currentDetail.value = d
        return true
      }
      lastError.value = '未找到文档'
      return false
    } catch (err) {
      lastError.value = err instanceof Error ? err.message : String(err)
      return false
    } finally {
      detailLoading.value = false
    }
  }

  function clearDetail(): void {
    currentDetail.value = null
  }

  function clearError(): void {
    lastError.value = null
  }

  async function bootstrap(): Promise<void> {
    loading.value = true
    try {
      await Promise.all([loadCategories(), loadList()])
    } finally {
      loading.value = false
    }
  }

  return {
    // state
    categories,
    selectedCategory,
    items,
    total,
    page,
    pageSize,
    keyword,
    currentDetail,
    detailLoading,
    lastError,
    loading,
    // derived
    totalCount,
    selectedCategoryCount,
    pageInfo,
    // actions
    loadCategories,
    loadList,
    selectCategory,
    search,
    goToPage,
    loadDetail,
    clearDetail,
    clearError,
    bootstrap
  }
})

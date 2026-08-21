// Knowledge Pinia store —— 分类 + 文档列表 (分页) + 当前详情 + 搜索 query。
//
// 拉数据全部走 IPC 委托 main api.service。renderer 不持久化任何数据。
//
// Phase 4-A: store 不再直接调 api/knowledge, 走 knowledgeService (业务层).
// 架构: View -> Store -> Service -> API (IPC) -> main api.service -> FastAPI.

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { knowledgeService } from '../services/knowledge.service'
import {
  derivePageInfo,
  type DynamicCategory,
  type KnowledgeListItem,
  type KnowledgeResponse,
  type PageInfo
} from '@shared/knowledge-types'
import type { ApiError } from '@shared/preload-api'

const DEFAULT_PAGE_SIZE = 20

export const useKnowledgeStore = defineStore('knowledge', () => {
  // 分类 + 选中分类
  const categories = ref<DynamicCategory[]>([])
  const selectedCategory = ref<string>('all')

  // 文档列表 + 分页 + 搜索
  const items = ref<KnowledgeListItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const keyword = ref('')

  // 详情（Phase 2-Impl-2B Pro）
  const currentDetail = ref<KnowledgeResponse | null>(null)
  const detailLoading = ref(false)

  // 错误归一
  const lastError = ref<ApiError | null>(null)
  const loading = ref(false)

  // ============ 派生 ============
  const totalCount = computed(() => categories.value.reduce((acc, c) => acc + c.count, 0))
  const selectedCategoryCount = computed(() => {
    if (selectedCategory.value === 'all') return totalCount.value
    const c = categories.value.find((x) => x.name === selectedCategory.value)
    return c?.count ?? 0
  })
  const pageInfo = computed<PageInfo>(() => derivePageInfo(page.value, pageSize.value, total.value))

  // ============ Actions ============
  async function loadCategories(): Promise<boolean> {
    const r = await knowledgeService.getCategories()
    if (r.ok) {
      categories.value = r.data
      return true
    }
    lastError.value = r.error
    return false
  }

  async function loadList(): Promise<boolean> {
    loading.value = true
    try {
      const r = await knowledgeService.listKnowledge({
        category: selectedCategory.value === 'all' ? null : selectedCategory.value,
        keyword: keyword.value,
        page: page.value,
        pageSize: pageSize.value
      })
      if (r.ok) {
        items.value = r.data.items
        total.value = r.data.total
        return true
      }
      lastError.value = r.error
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

  async function loadDetail(id: number): Promise<boolean> {
    detailLoading.value = true
    try {
      const r = await knowledgeService.getKnowledge(id)
      if (r.ok) {
        currentDetail.value = r.data
        return true
      }
      lastError.value = r.error
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

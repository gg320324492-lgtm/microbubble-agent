// Knowledge Pinia store —— 分类 + 文档列表 + 当前详情 + 搜索 query。
//
// 拉数据全部走 IPC 委托 main api.service。renderer 不持久化任何数据。

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getCategories,
  listKnowledge,
  getKnowledge
} from '../api/knowledge'
import type {
  DynamicCategory,
  KnowledgeListItem,
  KnowledgeResponse
} from '@shared/knowledge-types'
import type { ApiError } from '@shared/preload-api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // 分类 + 选中分类
  const categories = ref<DynamicCategory[]>([])
  const selectedCategory = ref<string>('all')

  // 文档列表 + 分页 + 搜索
  const items = ref<KnowledgeListItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const keyword = ref('')

  // 详情（Phase 2-Impl-2A 路由占位）
  const currentDetail = ref<KnowledgeResponse | null>(null)
  const detailLoading = ref(false)

  // 错误归一
  const lastError = ref<ApiError | null>(null)
  const loading = ref(false)

  /**
   * 分类总数 (排除 'all' 自身)。
   */
  const totalCount = computed(() => {
    return categories.value.reduce((acc, c) => acc + c.count, 0)
  })

  /**
   * 选中分类的 count（'all' -> 所有汇总）。
   */
  const selectedCategoryCount = computed(() => {
    if (selectedCategory.value === 'all') return totalCount.value
    const c = categories.value.find((x) => x.name === selectedCategory.value)
    return c?.count ?? 0
  })

  /** 拉左侧分类。 */
  async function loadCategories(): Promise<boolean> {
    const r = await getCategories()
    if (r.ok) {
      categories.value = r.data
      return true
    }
    lastError.value = r.error
    return false
  }

  /** 拉中间文档列表（按当前 selectedCategory + keyword + page）。 */
  async function loadList(): Promise<boolean> {
    loading.value = true
    try {
      const r = await listKnowledge({
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

  /** 用户改变分类。 */
  async function selectCategory(name: string): Promise<void> {
    selectedCategory.value = name
    page.value = 1
    await loadList()
  }

  /** 用户改搜索框 (debounced in view, 这里直接调)。 */
  async function search(q: string): Promise<void> {
    keyword.value = q
    page.value = 1
    await loadList()
  }

  async function loadDetail(id: number): Promise<boolean> {
    detailLoading.value = true
    try {
      const r = await getKnowledge(id)
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

  /** 进入页面一次拉全部分类 + 列表。 */
  async function bootstrap(): Promise<void> {
    loading.value = true
    try {
      await Promise.all([loadCategories(), loadList()])
    } finally {
      loading.value = false
    }
  }

  return {
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
    totalCount,
    selectedCategoryCount,
    loadCategories,
    loadList,
    selectCategory,
    search,
    loadDetail,
    clearDetail,
    clearError,
    bootstrap
  }
})

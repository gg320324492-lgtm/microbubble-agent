// dashboard Pinia store —— 缓存 DashboardView 的拉取数据。
//
// 所有 fetch 通过 IPC 委托 main 进程 (api.service 自动注入 Bearer + 单飞 refresh)。
// 不在前端持久化任何 API 响应 —— DashboardView 进入即重拉。

import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getDashboardSummary,
  getProjectStats,
  getRecentTasks
} from '../api/dashboard'
import type {
  DashboardSummary,
  ProjectStats,
  TaskSummary
} from '@shared/dashboard-types'
import type { ApiError } from '@shared/preload-api'

export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref<DashboardSummary | null>(null)
  const projectStats = ref<ProjectStats | null>(null)
  const recentTasks = ref<TaskSummary[]>([])
  const lastError = ref<ApiError | null>(null)
  const loading = ref(false)

  async function loadSummary(): Promise<boolean> {
    const result = await getDashboardSummary()
    if (result.ok) {
      summary.value = result.data
      return true
    }
    lastError.value = result.error
    return false
  }

  async function loadProjectStats(): Promise<boolean> {
    const result = await getProjectStats()
    if (result.ok) {
      projectStats.value = result.data
      return true
    }
    lastError.value = result.error
    return false
  }

  async function loadRecentTasks(limit = 5): Promise<boolean> {
    const result = await getRecentTasks(limit)
    if (result.ok) {
      recentTasks.value = result.data
      return true
    }
    lastError.value = result.error
    return false
  }

  /**
   * 全部并行拉取。任一失败 -> 整体失败 (lastError 标错)。
   * 任一成功 -> 触发对应 UI 卡 (load 模式)。
   */
  async function loadAll(): Promise<boolean> {
    loading.value = true
    lastError.value = null
    try {
      const [a, b, c] = await Promise.all([loadSummary(), loadProjectStats(), loadRecentTasks(5)])
      return a && b && c
    } finally {
      loading.value = false
    }
  }

  function clearError(): void {
    lastError.value = null
  }

  return {
    summary,
    projectStats,
    recentTasks,
    lastError,
    loading,
    loadSummary,
    loadProjectStats,
    loadRecentTasks,
    loadAll,
    clearError
  }
})

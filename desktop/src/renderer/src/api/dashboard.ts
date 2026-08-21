// Dashboard API 入口（renderer 端封装）。
//
// 全部走 window.api.api.request（main 进程注入 Bearer + 单飞 refresh），
// 禁止 renderer axios 直接调业务 endpoint。

import type {
  DashboardSummary,
  ProjectStats,
  TaskSummary,
  PaginatedTasks
} from '@shared/dashboard-types'
import type { ApiResult } from '@shared/preload-api'

/**
 * 任务概览：3 个数字（in_progress / done / overdue）。
 * 来自 GET /api/v1/dashboard/summary
 */
export async function getDashboardSummary(): Promise<ApiResult<DashboardSummary>> {
  return window.api.api.request<DashboardSummary>({
    method: 'GET',
    path: '/dashboard/summary'
  })
}

/**
 * 工程统计：commits / files / lines / dev_days 等。
 * 来自 GET /api/v1/dashboard/project-stats
 */
export async function getProjectStats(): Promise<ApiResult<ProjectStats>> {
  return window.api.api.request<ProjectStats>({
    method: 'GET',
    path: '/dashboard/project-stats'
  })
}

/**
 * 最近 N 条任务：分页 items 取前 N 条。
 * 来自 GET /api/v1/tasks
 */
export async function getRecentTasks(limit = 5): Promise<ApiResult<TaskSummary[]>> {
  const result = await window.api.api.request<PaginatedTasks>({
    method: 'GET',
    path: '/tasks',
    query: {
      page: 1,
      page_size: limit
    }
  })
  if (!result.ok) return result
  return { ok: true, data: result.data.items }
}

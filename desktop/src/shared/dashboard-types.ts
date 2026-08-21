// Dashboard 与 Task 共享类型契约。
// 来自 app/api/v1/dashboard.py (summary) + app/api/v1/task.py。
// 任何后端字段改动必须同步 auth-api-contract.md §同类规约。

import type { UserInfo } from './user-info'

/**
 * /api/v1/dashboard/summary 响应 (来自 dashboard.py:179 get_dashboard_summary)。
 * 移动端 + web 端 dashboard 都消费此端点。
 */
export interface DashboardSummary {
  in_progress_tasks: number
  done_tasks: number
  overdue_tasks: number
}

/**
 * /api/v1/dashboard/project-stats 响应节选（git 工程统计）。
 */
export interface ProjectStats {
  total_commits: number
  total_files: number
  total_lines: number
  first_commit_date: string
  dev_days: number
  [extraKey: string]: unknown  // 后端含 lines_by_type 等扩展字段
}

/**
 * 任务基础字段（来自 app/models/task.py 部分）。
 * Phase 2-Impl-1 只用 id/title/status/priority/due_date 5 个字段。
 */
export interface TaskSummary {
  id: number
  title: string
  status: 'todo' | 'in_progress' | 'done' | 'paused' | 'cancelled' | string
  priority?: 'low' | 'medium' | 'high' | 'urgent' | string
  due_date?: string | null
  created_at?: string
  updated_at?: string
  [extraKey: string]: unknown
}

/** 分页 items 包装（多数 GET 列表端点形态）。 */
export interface PaginatedTasks {
  items: TaskSummary[]
  total?: number
  page?: number
  page_size?: number
}

/** UI 派生的 4 卡统计视图。 */
export interface DashboardStatsView {
  inProgress: number
  done: number
  overdue: number
  total: number
}

/**
 * 派生：summary → 4 卡视图（含总数 = in_progress + done；不去 overdue 防止双计）。
 */
export function deriveStatsView(s: DashboardSummary): DashboardStatsView {
  return {
    inProgress: s.in_progress_tasks,
    done: s.done_tasks,
    overdue: s.overdue_tasks,
    total: s.in_progress_tasks + s.done_tasks
  }
}

/** 重新导出 UserInfo 方便业务视图一处引用。 */
export type { UserInfo }

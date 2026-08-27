// Tasks Transformer — Phase 11 P11-1
// 单向: web PG tasks → desktop desktop_tasks.
// 字段按 desktop 命名重写 + 类型转换.

import { applyTransformers, pgTimestampToEpochMs, pgTextArrayToJsonString } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

/** web tasks enum (web backend) → desktop enum. desktop 用相同的字面量 (Web 已有完整 enum). */
const WEB_TO_DESKTOP_PRIORITY: Record<string, string> = {
  high: 'high',
  medium: 'medium',
  low: 'low'
}

const WEB_TO_DESKTOP_STATUS: Record<string, string> = {
  todo: 'todo',
  in_progress: 'in_progress',
  blocked: 'blocked',
  review: 'review',
  done: 'done',
  cancelled: 'cancelled'
}

const WHITELIST_PRIORITY = ['high', 'medium', 'low']
const WHITELIST_STATUS = ['todo', 'in_progress', 'blocked', 'review', 'done', 'cancelled']

/** 转换单行 PG task → desktop_tasks row (不含 id, 含 web_id 由 caller 注入). */
export function transformTaskRow(
  pgRow: Record<string, unknown>
): Record<string, unknown> {
  const map: TransformerMap = {
    title: (v) => (v == null ? '' : String(v)),
    description: (v) => (v == null ? null : String(v)),
    project_id: (v) => (v == null ? null : Number(v) || null),
    assignee_username: (v) => (v == null ? null : String(v)),
    creator_username: (v) => (v == null ? null : String(v)),
    status: (v) => rewriteStatus(v),
    priority: (v) => rewritePriority(v),
    progress: (v) => (v == null ? 0 : Math.max(0, Math.min(100, Number(v) || 0))),
    due_date_epoch: (v) => pgTimestampToEpochMs(v),
    started_at_epoch: (v) => pgTimestampToEpochMs(v),
    completed_at_epoch: (v) => pgTimestampToEpochMs(v),
    source: (v) => (v == null ? null : String(v)),
    meeting_web_id: (v) => (v == null ? null : Number(v) || null),
    tags_json: (v) => pgTextArrayToJsonString(v) ?? '[]',
    deleted_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function rewriteStatus(raw: unknown): string {
  if (raw == null) return 'todo'
  const s = String(raw)
  const mapped = WEB_TO_DESKTOP_STATUS[s]
  if (mapped) return mapped
  if (WHITELIST_STATUS.includes(s)) return s
  throw new Error(`Invalid task status: '${s}'`)
}

function rewritePriority(raw: unknown): string {
  if (raw == null) return 'medium'
  const s = String(raw)
  const mapped = WEB_TO_DESKTOP_PRIORITY[s]
  if (mapped) return mapped
  if (WHITELIST_PRIORITY.includes(s)) return s
  throw new Error(`Invalid task priority: '${s}'`)
}

/** SELECT 语句基类 (不含 LIMIT/OFFSET). */
export const TASKS_SELECT_SQL = `
  SELECT
    id, project_id, title, description,
    assignee_id, created_by,
    status, priority, progress,
    due_date, started_at, completed_at,
    source, meeting_id, tags, deleted_at
  FROM tasks
  WHERE deleted_at IS NULL
  ORDER BY id ASC
`
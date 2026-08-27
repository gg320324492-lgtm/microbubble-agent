// Reminders Transformer — Phase 11 P11-3
// 单向: web PG reminders → desktop_reminders.
// remind_type 扩展 (web 3 值 → desktop 4 值, 'desktop' 表示本地通知).
// status/target_type 用 desktop enum 重写.
// 时间 → epoch INTEGER.

import { applyTransformers, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_TYPE = ['wechat', 'email', 'sms', 'desktop']
const WHITELIST_STATUS = ['pending', 'sent', 'cancelled', 'acknowledged']
const WHITELIST_TARGET = ['task', 'meeting']

/** 转换单行 web reminders → desktop_reminders row.
 *  pgRow 含 task_id / meeting_id / acknowledged_by (PG 列名).
 *  Transformer 输出 desktop 列名 (task_web_id / meeting_web_id / acknowledged_by_username). */
export function transformReminderRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const taskId = pgRow['task_id']
  const meetingId = pgRow['meeting_id']
  const acknowledgedBy = pgRow['acknowledged_by']
  const map: TransformerMap = {
    task_web_id: () => (taskId == null ? null : Number(taskId) || null),
    meeting_web_id: () => (meetingId == null ? null : Number(meetingId) || null),
    remind_at_epoch: (v) => pgTimestampToEpochMs(v),
    remind_type: (v) => validateEnum(v, 'remind_type', WHITELIST_TYPE, 'desktop'),
    status: (v) => validateEnum(v, 'status', WHITELIST_STATUS, 'pending'),
    target_type: (v) => validateEnum(v, 'target_type', WHITELIST_TARGET, 'task'),
    acknowledged_at_epoch: (v) => pgTimestampToEpochMs(v),
    acknowledged_by_username: () => (acknowledgedBy == null ? null : String(acknowledgedBy)),
    ack_channel: (v) => (v == null ? null : String(v)),
    snoozed_until_epoch: (v) => pgTimestampToEpochMs(v),
    reminder_batch_date: (v) => (v == null ? null : String(v)),
    policy_version: (v) => (v == null ? 2 : Number(v) || 2),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function validateEnum(raw: unknown, name: string, whitelist: ReadonlyArray<string>, fallback: string): string {
  if (raw == null) return fallback
  const s = String(raw)
  if (whitelist.includes(s)) return s
  throw new Error(`Invalid reminder ${name}: '${s}' not in [${whitelist.join(', ')}]`)
}

export const REMINDERS_SELECT_SQL = `
  SELECT
    id, task_id, meeting_id, remind_at,
    remind_type, status, sent_at,
    target_type, acknowledged_at, acknowledged_by, ack_channel,
    snoozed_until, reminder_batch_date, policy_version
  FROM reminders
  ORDER BY id ASC
`
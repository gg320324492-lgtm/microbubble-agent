// Projects Transformer — Phase 11 P11-4
// 单向: web PG projects → desktop 已有 projects 表 (合并 web_id/description/owner_username 列).
// desktop projects.id 是 TEXT PRIMARY KEY (UUID 格式); PG projects.id 是 INTEGER → 存 web_id 关联.
// name 复用, description/owner_username 字段新增 (来自 web projects 表).
// status 直接复用 (web 与 desktop 都用 string).

import { applyTransformers, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_STATUS = ['planning', 'in_progress', 'completed', 'archived', 'paused']

/** 转换单行 web projects → desktop projects row (复用 desktop id 字段).
 *  pgRow 含 id / owner_id (PG 列名); Transformer 输出 desktop 列名 (web_id / owner_username). */
export function transformProjectRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const pgId = pgRow['id']
  const ownerId = pgRow['owner_id']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    name: (v) => (v == null ? '' : String(v)),
    field: (v) => (v == null ? null : String(v)),
    goal: (v) => (v == null ? null : String(v)),
    description: (v) => (v == null ? null : String(v)),
    status: (v) => (v == null ? 'planning' : validateStatus(v)),
    owner_username: () => (ownerUsernameLookup && ownerId != null ? (ownerUsernameLookup.get(Number(ownerId)) ?? null) : null),
    created_at: (v) => pgTimestampToEpochMs(v),
    updated_at: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function validateStatus(raw: unknown): string {
  if (raw == null) return 'planning'
  const s = String(raw)
  if (WHITELIST_STATUS.includes(s)) return s
  // 兼容: web status 不在 desktop whitelist 时,保留原值 (user 可手动改)
  return s
}

/** 生成 desktop projects.id (web 没有提供 UUID → 用 web_id 派生).
 *  Phase 8 desktop projects.id 是 TEXT UUID 格式 (e.g. "prj-123-abc"). */
export function deriveDesktopProjectId(webId: number): string {
  return `web-prj-${webId}`
}

export const PROJECTS_SELECT_SQL = `
  SELECT
    id, name, description,
    status, field, goal,
    owner_id, created_at, updated_at
  FROM projects
  ORDER BY id ASC
`
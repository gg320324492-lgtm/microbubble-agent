// AuditLog + SearchLogs Transformer — Phase 11 P11-12 + P11-13
// 1) audit_log: 脱敏 (IP hash + 删除 user_agent)
// 2) search_logs: 字段子集

import { createHash } from 'node:crypto'
import { applyTransformers, pgJsonToJsonString, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const HASH_PREFIX_LEN = 16

/** IP 地址 → SHA256 hash (前 16 chars). 不可逆, 仅用于行为模式聚类. */
export function hashIpAddress(ip: unknown): string | null {
  if (ip == null) return null
  const s = String(ip)
  if (s === '\\N' || s === '') return null
  return createHash('sha256').update(s.normalize('NFKC')).digest('hex').slice(0, HASH_PREFIX_LEN)
}

/** web audit_log → desktop_audit_log row.
 *  脱敏: ip_address → ip_hash, user_agent 删除 (不写入 desktop). */
export function transformAuditLogRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const pgId = pgRow['id']
  const ipAddress = pgRow['ip_address']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    user_id: (v) => (v == null ? null : Number(v) || null),
    ip_hash: () => hashIpAddress(ipAddress),
    method: (v) => (v == null ? null : String(v)),
    path: (v) => (v == null ? null : String(v)),
    action: (v) => (v == null ? null : String(v)),
    resource_type: (v) => (v == null ? null : String(v)),
    resource_id: (v) => (v == null ? null : String(v)),
    status_code: (v) => (v == null ? null : Number(v) || null),
    duration_ms: (v) => (v == null ? null : Number(v) || null),
    meta_json: (v) => pgJsonToJsonString(v),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web search_logs → desktop_search_logs row.
 *  注意: web search_log.search_logs 有 35 列,desktop 只取 9 字段子集. */
export function transformSearchLogRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const userId = pgRow['user_id']
  const map: TransformerMap = {
    web_id: (v) => (v == null ? null : Number(v) || null),
    user_id: () => (userId == null ? null : Number(userId) || null),
    owner_username: () => (ownerUsernameLookup && userId != null ? (ownerUsernameLookup.get(Number(userId)) ?? null) : null),
    query: (v) => (v == null ? '' : String(v)),
    result_count: (v) => (v == null ? 0 : Number(v) || 0),
    clicked_kb_id: (v) => (v == null ? null : Number(v) || null),
    search_type: (v) => (v == null ? null : String(v)),
    response_time_ms: (v) => (v == null ? null : Number(v) || null),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

export const AUDIT_LOG_SELECT_SQL = `
  SELECT
    id, user_id, ip_address, method, path, action,
    resource_type, resource_id, status_code, duration_ms,
    meta_data, created_at
  FROM audit_log
  WHERE created_at >= NOW() - INTERVAL '30 days'
  ORDER BY id ASC
`

export const SEARCH_LOGS_SELECT_SQL = `
  SELECT
    id, user_id, query, result_count, clicked_kb_id,
    search_type, response_time_ms, created_at
  FROM search_logs
  ORDER BY id ASC
`
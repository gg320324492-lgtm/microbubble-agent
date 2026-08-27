// AgentTraces + ActivityEvents Transformer — Phase 11 P11-11
// 单向: web PG agent_traces (3619) + activity_events (1086) → desktop 镜像.

import { applyTransformers, pgJsonToJsonString, pgTimestampToEpochMs } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_TRACE_TYPE = ['tool_use', 'tool_result', 'message', 'system', 'error', 'plan', 'reflection']
const WHITELIST_EVENT_TYPE = ['view', 'edit', 'login', 'logout', 'create', 'delete', 'update', 'search', 'export', 'share', 'click', 'error']

/** web agent_traces → desktop_agent_traces row.
 *  trace_type 来自 web 字段,desktop 用 7 值 enum (web 可能 tool_call/error 等 → 映射到 tool_use/system). */
export function transformAgentTraceRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const pgId = pgRow['id']
  const userId = pgRow['user_id']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    session_id: (v) => (v == null ? null : String(v)),
    agent_name: (v) => (v == null ? null : String(v)),
    trace_type: (v) => mapTraceType(v),
    role: (v) => (v == null ? null : String(v)),
    content_json: (v) => pgJsonToJsonString(v),
    tool_name: (v) => (v == null ? null : String(v)),
    tool_input_json: (v) => pgJsonToJsonString(v),
    tool_output_json: (v) => pgJsonToJsonString(v),
    duration_ms: (v) => (v == null ? null : Number(v) || null),
    user_id: () => (userId == null ? null : Number(userId) || null),
    owner_username: () => (ownerUsernameLookup && userId != null ? (ownerUsernameLookup.get(Number(userId)) ?? null) : null),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web activity_events → desktop_activity_events row.
 *  user_agent 全量保留 (Phase 11 评估后决定 — 不是密码哈希必要; 包含浏览器 fingerprint 但本地不可被 web 读回).
 *  ip_address 保留原值 (本地化存储) — 与 plan 中"脱敏"区别: P11-12 audit_log 才脱敏, activity 不在脱敏范围. */
export function transformActivityEventRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const pgId = pgRow['id']
  const userId = pgRow['user_id']
  const map: TransformerMap = {
    web_id: () => (pgId == null ? null : Number(pgId) || null),
    user_id: () => (userId == null ? null : Number(userId) || null),
    owner_username: () => (ownerUsernameLookup && userId != null ? (ownerUsernameLookup.get(Number(userId)) ?? null) : null),
    event_type: (v) => mapEventType(v),
    resource_type: (v) => (v == null ? null : String(v)),
    resource_id: (v) => (v == null ? null : String(v)),
    action: (v) => (v == null ? null : String(v)),
    metadata_json: (v) => pgJsonToJsonString(v),
    ip_address: (v) => (v == null ? null : String(v)),
    user_agent: (v) => (v == null ? null : String(v)),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function mapTraceType(raw: unknown): string {
  if (raw == null) return 'system'
  const s = String(raw).toLowerCase()
  // web → desktop trace_type 映射
  if (s === 'tool_call' || s === 'tool_use') return 'tool_use'
  if (s === 'tool_result' || s === 'tool_response') return 'tool_result'
  if (WHITELIST_TRACE_TYPE.includes(s)) return s
  // 兼容: 未知值降级到 system
  return 'system'
}

function mapEventType(raw: unknown): string {
  if (raw == null) return 'view'
  const s = String(raw).toLowerCase()
  if (WHITELIST_EVENT_TYPE.includes(s)) return s
  return 'view'
}

export const AGENT_TRACES_SELECT_SQL = `
  SELECT
    id, session_id, agent_name, trace_type, role,
    content, tool_name, tool_input, tool_output,
    duration_ms, user_id, created_at
  FROM agent_traces
  ORDER BY id ASC
`

export const ACTIVITY_EVENTS_SELECT_SQL = `
  SELECT
    id, user_id, event_type, resource_type, resource_id,
    action, metadata, ip_address, user_agent, created_at
  FROM activity_events
  ORDER BY id ASC
`
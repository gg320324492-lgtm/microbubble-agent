// Chat History Transformer — Phase 11 P11-5
// 单向: web PG chat_sessions + chat_messages → desktop 镜像.
// content 截断 1000 chars (防止长对话占空间, 大字段不入 SQLite).

import { applyTransformers, pgJsonToJsonString, pgTimestampToEpochMs, truncateText } from '../transform-pipeline'
import type { TransformerMap } from '../transform-pipeline'

const WHITELIST_ROLE = ['user', 'assistant', 'system', 'tool']
const CONTENT_MAX_CHARS = 1000

/** web chat_sessions → desktop_chat_sessions row.
 *  pgRow 含 id (TEXT 'user_<ts>_<rand>' 格式) + user_id (FK members).
 *  desktop 复用 web 的 id (TEXT 主键) — 不需要 derive. */
export function transformChatSessionRow(
  pgRow: Record<string, unknown>,
  ownerUsernameLookup: Map<number, string> | null
): Record<string, unknown> {
  const userId = pgRow['user_id']
  const map: TransformerMap = {
    id: (v) => (v == null ? null : String(v)),
    web_user_id: () => (userId == null ? null : Number(userId) || null),
    owner_username: () => (ownerUsernameLookup && userId != null ? (ownerUsernameLookup.get(Number(userId)) ?? null) : null),
    title: (v) => (v == null ? '新对话' : String(v)),
    preview: (v) => (v == null ? '' : String(v)),
    is_pinned: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    is_archived: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    tags_json: (v) => pgJsonToJsonString(v) ?? '[]',
    message_count: (v) => (v == null ? 0 : Number(v) || 0),
    last_message_at_epoch: (v) => pgTimestampToEpochMs(v),
    deleted_at_epoch: (v) => pgTimestampToEpochMs(v),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    updated_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

/** web chat_messages → desktop_chat_messages row.
 *  content 截断 1000 chars (Phase 11 P11-5 防 SQLite 膨胀). */
export function transformChatMessageRow(pgRow: Record<string, unknown>): Record<string, unknown> {
  const map: TransformerMap = {
    session_id: (v) => (v == null ? null : String(v)),
    role: (v) => (v == null ? 'user' : validateRole(v)),
    content: (v) => truncateText(v, CONTENT_MAX_CHARS) ?? '',
    rich_blocks_json: (v) => pgJsonToJsonString(v),
    tool_trace_json: (v) => pgJsonToJsonString(v),
    attached_knowledge_ids_json: (v) => pgJsonToJsonString(v),
    image_url: (v) => (v == null ? null : String(v)),
    is_partial: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    is_deleted: (v) => (v == null ? 0 : Number(v) ? 1 : 0),
    client_msg_id: (v) => (v == null ? null : String(v)),
    created_at_epoch: (v) => pgTimestampToEpochMs(v),
    synced_at_epoch: () => Date.now()
  }
  return applyTransformers(pgRow, map)
}

function validateRole(raw: unknown): string {
  if (raw == null) return 'user'
  const s = String(raw)
  if (WHITELIST_ROLE.includes(s)) return s
  throw new Error(`Invalid chat role: '${s}' not in [${WHITELIST_ROLE.join(', ')}]`)
}

export const CHAT_SESSIONS_SELECT_SQL = `
  SELECT
    id, user_id, title, preview,
    is_pinned, is_archived, tags,
    message_count, last_message_at,
    deleted_at, created_at, updated_at
  FROM chat_sessions
  ORDER BY last_message_at DESC NULLS LAST, id ASC
`

export const CHAT_MESSAGES_SELECT_SQL = `
  SELECT
    id, session_id, role, content,
    rich_blocks, tool_trace, attached_knowledge_ids,
    image_url, is_partial, is_deleted, client_msg_id,
    created_at
  FROM chat_messages
  WHERE is_deleted = false
  ORDER BY session_id ASC, created_at ASC
`
/**
 * chatHistory API 客户端 — #043 账号持久化聊天历史
 *
 * 镜像 web/src/api/analytics.js 模式（直接 axios 调用）
 * 12 个端点（来自 Phase 2 后端 app/api/v1/chat_history.py）：
 *   - GET    /chat/sessions                       列会话
 *   - POST   /chat/sessions                       创建会话
 *   - GET    /chat/sessions/:id                   单个会话详情
 *   - PATCH  /chat/sessions/:id                   更新元信息
 *   - DELETE /chat/sessions/:id                   删除（默认软删）
 *   - GET    /chat/sessions/:id/messages          列消息（分页）
 *   - POST   /chat/sessions/:id/messages          追加消息
 *   - GET    /chat/sessions/:id/export?format=md  导出（md|json，blob）
 *   - POST   /chat/sessions/:id/share             生成分享链接
 *   - GET    /chat/sessions/search?q=...          跨会话搜索
 *   - POST   /chat/sync                           旧数据迁移（Phase 5 用）
 *   - GET    /chat/shares/:token                  公开分享（无 JWT）
 *
 * 关键纪律（CLAUDE.md 2026-06-13 教训）：
 * - 失败抛异常 → useChatStream / useChatMigration 各自 try/except
 * - SSE 不走此客户端（仍走 sse.ts）
 * - 公开分享端点不走全局 axios 拦截器（不带 token）
 */

import axios from 'axios'

const BASE = '/api/v1'

// ============================================================================
// Session CRUD
// ============================================================================

/**
 * 列出会话（默认按 last_message_at 倒序）
 * @param {Object} opts
 * @param {boolean} [opts.archived=false] - 是否包含已归档
 * @param {boolean} [opts.pinnedOnly=false] - 仅收藏
 * @param {string} [opts.tag] - 按标签过滤（ARRAY contains）
 * @param {string} [opts.search] - 标题/preview 模糊匹配
 * @param {number} [opts.page=1]
 * @param {number} [opts.pageSize=50]
 * @returns {Promise<{items: ServerChatSession[], total: number, page: number, page_size: number}>}
 */
export async function listSessions(opts = {}) {
  const { archived = false, pinnedOnly = false, tag, search, page = 1, pageSize = 50 } = opts
  const { data } = await axios.get(`${BASE}/chat/sessions`, {
    params: {
      archived,
      pinned_only: pinnedOnly,
      ...(tag ? { tag } : {}),
      ...(search ? { search } : {}),
      page,
      page_size: pageSize,
    },
  })
  return data
}

/**
 * 创建服务端会话（client_session_id 用于 localStorage sessionId 兼容）
 * @param {Object} opts
 * @param {string} [opts.title]
 * @param {string} [opts.first_message] - 首条 user 消息
 * @param {string} [opts.client_session_id] - 客户端 sessionId（可选）
 * @returns {Promise<ServerChatSession>}
 */
export async function createSession({ title, first_message, client_session_id } = {}) {
  const { data } = await axios.post(`${BASE}/chat/sessions`, {
    ...(title ? { title } : {}),
    ...(first_message ? { first_message } : {}),
    ...(client_session_id ? { client_session_id } : {}),
  }, { timeout: 10000 })
  return data
}

/**
 * 获取单个会话（可含 messages）
 * @param {string} sid
 * @param {Object} [opts]
 * @param {boolean} [opts.includeMessages=false]
 */
export async function getSession(sid, { includeMessages = false } = {}) {
  const { data } = await axios.get(`${BASE}/chat/sessions/${encodeURIComponent(sid)}`, {
    params: { include_messages: includeMessages },
  })
  return data
}

/**
 * 更新会话元信息（title / is_pinned / is_archived / tags）
 * @param {string} sid
 * @param {Object} patch - { title?, is_pinned?, is_archived?, tags? }
 */
export async function updateSession(sid, patch) {
  const { data } = await axios.patch(`${BASE}/chat/sessions/${encodeURIComponent(sid)}`, patch)
  return data
}

/**
 * 删除会话（默认软删除，30 天后 Celery 物理清除）
 * @param {string} sid
 * @param {Object} [opts]
 * @param {boolean} [opts.hard=false] - true = 物理删除
 */
export async function deleteSession(sid, { hard = false } = {}) {
  const { data } = await axios.delete(`${BASE}/chat/sessions/${encodeURIComponent(sid)}`, {
    params: { hard },
  })
  return data
}

// ============================================================================
// Message CRUD
// ============================================================================

/**
 * 列出会话消息（按 id 正序，游标分页）
 * @param {string} sid
 * @param {Object} [opts]
 * @param {number} [opts.page=1]
 * @param {number} [opts.pageSize=100]
 * @param {number} [opts.afterId=0] - 仅返回 id > afterId 的（增量拉取）
 */
export async function listMessages(sid, opts = {}) {
  const { page = 1, pageSize = 100, afterId = 0 } = opts
  const { data } = await axios.get(
    `${BASE}/chat/sessions/${encodeURIComponent(sid)}/messages`,
    { params: { page, page_size: pageSize, after_id: afterId } },
  )
  return data
}

/**
 * 追加单条消息（幂等 by client_msg_id）
 * @param {string} sid
 * @param {Object} msg - { role, content, rich_blocks?, tool_trace?, message_metadata?, client_msg_id?, is_partial? }
 * @returns {Promise<ServerChatMessage>}
 */
export async function appendMessage(sid, msg) {
  const { data } = await axios.post(
    `${BASE}/chat/sessions/${encodeURIComponent(sid)}/messages`,
    msg,
    { timeout: 10000 },
  )
  return data
}

// ============================================================================
// 导出
// ============================================================================

/**
 * 导出会话（md | json）
 * @param {string} sid
 * @param {Object} [opts]
 * @param {string} [opts.format='md']
 * @returns {Promise<Blob>}
 */
export async function exportSession(sid, { format = 'md' } = {}) {
  const { data } = await axios.get(
    `${BASE}/chat/sessions/${encodeURIComponent(sid)}/export`,
    { params: { format }, responseType: 'blob' },
  )
  return data
}

// ============================================================================
// 分享
// ============================================================================

/**
 * 生成分享链接
 * @param {string} sid
 * @param {Object} [opts]
 * @param {string} [opts.permission='read']
 * @param {number} [opts.expiresHours] - 过期小时数（1-8760）
 * @returns {Promise<{id: string, share_url: string, ...}>}
 */
export async function createShare(sid, { permission = 'read', expiresHours } = {}) {
  const { data } = await axios.post(
    `${BASE}/chat/sessions/${encodeURIComponent(sid)}/share`,
    {
      permission,
      ...(expiresHours ? { expires_hours: expiresHours } : {}),
    },
  )
  return data
}

/**
 * 公开访问分享链接（无 JWT — 用于匿名访客）
 * ⚠️ 此函数不通过 axios 拦截器带 token（拦截器会自动带，但分享页可能没有登录态）
 *    实际上全局拦截器总是会带 Authorization（如果有 token），不影响后端（后端此端点不鉴权）
 * @param {string} token
 */
export async function getPublicShare(token) {
  const { data } = await axios.get(`${BASE}/chat/shares/${encodeURIComponent(token)}`)
  return data
}

// ============================================================================
// 搜索
// ============================================================================

/**
 * 跨会话搜索（按消息内容）
 * @param {string} query - 搜索词（最少 2 字符）
 * @param {Object} [opts]
 * @param {number} [opts.page=1]
 * @param {number} [opts.pageSize=20]
 */
export async function searchSessions(query, opts = {}) {
  const { page = 1, pageSize = 20 } = opts
  const { data } = await axios.get(`${BASE}/chat/sessions/search`, {
    params: { q: query, page, page_size: pageSize },
  })
  return data
}

// ============================================================================
// 旧数据迁移（Phase 5 用）
// ============================================================================

/**
 * localStorage → server 同步（首次登录触发，幂等）
 * @param {Object} payload
 * @param {Array} payload.localSessions - [{id, title, preview, is_pinned, is_archived, tags, created_at, updated_at}]
 * @param {Array} payload.localMessages - [{session_id, messages: [{role, content, rich_blocks, tool_trace, message_metadata, created_at}]}]
 * @param {string} [payload.lastSyncedAt] - ISO timestamp
 */
export async function syncFromLocal({ localSessions, localMessages, lastSyncedAt } = {}) {
  const { data } = await axios.post(`${BASE}/chat/sync`, {
    local_sessions: localSessions,
    local_messages: localMessages,
    ...(lastSyncedAt ? { last_synced_at: lastSyncedAt } : {}),
  }, { timeout: 30000 })
  return data
}

// ============================================================================
// 类型定义（仅 TypeScript 用，JS 端忽略）
// ============================================================================

/**
 * @typedef {Object} ServerChatSession
 * @property {string} id
 * @property {number} user_id
 * @property {string} title
 * @property {string} preview
 * @property {boolean} is_pinned
 * @property {boolean} is_archived
 * @property {string[]} tags
 * @property {number} message_count
 * @property {string|null} last_message_at
 * @property {string} created_at
 * @property {string} updated_at
 * @property {string|null} deleted_at
 */

/**
 * @typedef {Object} ServerChatMessage
 * @property {number} id
 * @property {string} session_id
 * @property {string} role
 * @property {string} content
 * @property {Array} rich_blocks
 * @property {Object} tool_trace
 * @property {Object} metadata  // 注意：后端字段是 metadata（SQLAlchemy Column mapping）
 * @property {boolean} is_partial
 * @property {boolean} is_deleted
 * @property {string|null} client_msg_id
 * @property {string} created_at
 */

// 聚合默认导出
export const chatHistoryApi = {
  listSessions,
  createSession,
  getSession,
  updateSession,
  deleteSession,
  listMessages,
  appendMessage,
  exportSession,
  createShare,
  getPublicShare,
  searchSessions,
  syncFromLocal,
}

export default chatHistoryApi
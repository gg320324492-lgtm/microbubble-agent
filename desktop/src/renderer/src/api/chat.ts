// Chat API 入口（renderer 端封装，Phase 2-Impl-3A 同步-only）。
//
// 全部走 window.api.api.request（主进程注入 Bearer + 单飞 refresh），
// 禁止 renderer axios 直接调 chat endpoint。
// Phase 3+ SSE streaming 走独立通道 (Phase 2-Impl-3A 不接)。

import type {
  ChatSessionListResponse,
  ChatSessionOut,
  ChatMessagesPage,
  ChatRequest,
  ChatResponse
} from '@shared/chat-types'
import type { ApiResult } from '@shared/preload-api'

/** 默认 session_id — 后端约定 */
const DEFAULT_SESSION_ID = 'default'

/**
 * Session 列表：GET /api/v1/chat/sessions?page=&page_size=
 */
export async function listSessions(opts: {
  page?: number
  pageSize?: number
  includeArchived?: boolean
} = {}): Promise<ApiResult<ChatSessionListResponse>> {
  const query: Record<string, string | number | boolean> = {
    page: opts.page ?? 1,
    page_size: opts.pageSize ?? 50
  }
  if (typeof opts.includeArchived === 'boolean') {
    query['include_archived'] = opts.includeArchived
  }
  return window.api.api.request<ChatSessionListResponse>({
    method: 'GET',
    path: '/chat/sessions',
    query
  })
}

/**
 * 单 session 详情（含 messages）：GET /api/v1/chat/sessions/{id}
 */
export async function getSession(sessionId: string): Promise<ApiResult<ChatSessionOut>> {
  return window.api.api.request<ChatSessionOut>({
    method: 'GET',
    path: `/chat/sessions/${encodeURIComponent(sessionId)}`
  })
}

/**
 * 历史消息分页：GET /api/v1/chat/sessions/{id}/messages?after_id=&limit=
 *
 * Phase 2-Impl-3A 默认拉最新 50 条; Phase 3+ 增量加载用 next_after_id。
 */
export async function listMessages(
  sessionId: string,
  opts: { afterId?: number | null; limit?: number } = {}
): Promise<ApiResult<ChatMessagesPage>> {
  const query: Record<string, string | number | boolean> = {
    limit: opts.limit ?? 50
  }
  if (typeof opts.afterId === 'number') {
    query['after_id'] = opts.afterId
  }
  return window.api.api.request<ChatMessagesPage>({
    method: 'GET',
    path: `/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
    query
  })
}

/**
 * 发消息（同步）POST /api/v1/chat
 *
 * Phase 2-Impl-3A: 完全同步, 拿到完整 ChatResponse 后返回;
 * Phase 3+: 改走 SSE streaming (`POST /chat/stream`)。
 */
export async function sendMessage(
  payload: ChatRequest
): Promise<ApiResult<ChatResponse>> {
  return window.api.api.request<ChatResponse>({
    method: 'POST',
    path: '/chat',
    body: payload
  })
}

/**
 * 创建新 session 占位（Phase 2-Impl-3A 不需要，Phase 3+ 加 UI 新建按钮）。
 * 后端 POST /chat/sessions 已存在, 当前不在 UI 暴露。
 */
export const DEFAULT_SESSION = DEFAULT_SESSION_ID

// Main Service: Chat SSE Streaming (Phase 3-A: Reliability Hardened)。
//
// 设计铁律:
// 1. main 持有 Bearer access_token (renderer 永不见 token)
// 2. fetch POST /chat/stream + 流式读取 + SSE data: 帧解析
// 3. SSE HTTP 401 → performRefresh() 一次, 重连 stream (新 token)
// 4. 解析后通过 webContents.send 携带 StreamContext 广播
// 5. abort / 取消 / cleanup 都集中在 activeStreams Map
//
// 范围 (Phase 3-A):
//   ✅ 401 一级自动 refresh + 重连
//   ✅ StreamContext (streamId + sessionId) 广播
//   ✅ AbortController + cancelChatStream
//   ❌ 流内 401 多级重试 (Phase 4+)
//   ❌ reconnect after disconnect (Phase 4+)

import { app, BrowserWindow } from 'electron'
import { APP_CONFIG } from '@shared/config'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  ChatStreamRequest,
  StreamEvent,
  StreamEndPayload,
  StreamContext
} from '@shared/chat-types'
import { authService } from '../auth.service'
import { vaultLoadRefreshToken } from '../token-vault'

interface ActiveStream {
  controller: AbortController
  context: StreamContext
  request: ChatStreamRequest
  attempt: 1 | 2
}

const activeStreams = new Map<string, ActiveStream>()

function pushToRenderers(channel: string, ...args: unknown[]): void {
  const wins = BrowserWindow.getAllWindows()
  for (const w of wins) {
    if (!w.isDestroyed()) w.webContents.send(channel, ...args)
  }
}

function pushChunk(ctx: StreamContext, event: StreamEvent): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_CHUNK, ctx, event)
}
function pushEnd(ctx: StreamContext, payload: StreamEndPayload = { ok: true }): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_END, ctx, payload)
}
function pushError(ctx: StreamContext, code: string, message: string): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_ERROR, ctx, { code, message })
}

/**
 * 启动一个 SSE 流.
 * - 立刻 resolve streamId 给 renderer
 * - 后续 chunk/end/error 通过 webContents.send 携带 StreamContext 推
 * - AbortController 支持 cancelChatStream
 */
export async function startChatStream(
  req: ChatStreamRequest
): Promise<string> {
  const streamId = `stream_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const context: StreamContext = { streamId, sessionId: req.session_id }
  const controller = new AbortController()
  activeStreams.set(streamId, { controller, context, request: req, attempt: 1 })

  void runStream(streamId, req, controller.signal, 1)

  return streamId
}

/**
 * 取消流 (Phase 3-A expose).
 */
export function cancelChatStream(streamId: string): { ok: true } | { ok: false; error: string } {
  const active = activeStreams.get(streamId)
  if (!active) return { ok: false, error: `streamId ${streamId} 不存在` }
  active.controller.abort()
  activeStreams.delete(streamId)
  return { ok: true }
}

/**
 * 内部: 实际 SSE 流循环, attempt 1 → 可重试 attempt 2 (401 refresh 后).
 */
async function runStream(
  streamId: string,
  req: ChatStreamRequest,
  signal: AbortSignal,
  attempt: 1 | 2
): Promise<void> {
  const context: StreamContext = { streamId, sessionId: req.session_id }

  // attempt 1: 走 currentAccessToken
  // attempt 2: 假定 performRefresh 已成功, 重新取 currentAccessToken
  const accessToken = authService.getCurrentAccessToken()
  if (!accessToken) {
    pushError(context, 'NO_ACTIVE_SESSION', '当前未登录, 无法发起流式请求')
    activeStreams.delete(streamId)
    return
  }

  const url = `${APP_CONFIG.backendUrl}/chat/stream`
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${accessToken}`,
        'Cache-Control': 'no-cache'
      },
      body: JSON.stringify(req),
      signal
    })
  } catch (err) {
    if ((err as { name?: string }).name === 'AbortError') {
      pushError(context, 'ABORTED', '流已取消')
    } else {
      pushError(
        context,
        'NETWORK_ERROR',
        err instanceof Error ? err.message : String(err)
      )
    }
    activeStreams.delete(streamId)
    return
  }

  // === 401 refresh 接入 (Phase 3-A) ===
  if (response.status === 401) {
    if (attempt === 1) {
      // 一次 refresh + 重连 (attempt=2)
      const refreshed = await tryRefreshToken(context)
      if (refreshed) {
        // 新 token 已注入 currentAccessToken; 递归 attempt=2 (复用 request + 新 fetch)
        const newToken = authService.getCurrentAccessToken()
        if (!newToken) {
          pushError(context, 'REFRESH_FAILED', 'refresh 后仍无可用 token')
          activeStreams.delete(streamId)
          return
        }
        await runStream(streamId, req, signal, 2)
      } else {
        pushError(context, 'AUTH_EXPIRED', 'access_token 过期且 refresh 失败, 请重新登录')
        activeStreams.delete(streamId)
      }
      return
    }
    // attempt 2 也 401 → 强制清场 + 推 NO_ACTIVE_SESSION (会让 renderer 跳 /login)
    pushError(context, 'AUTH_EXPIRED', 'refresh 后仍 401, 请重新登录')
    authService.forceClearOnRefreshFail()
    activeStreams.delete(streamId)
    return
  }

  // === 其他非 OK ===
  if (!response.ok) {
    pushError(context, mapHttpToErrorCode(response.status), `SSE 上游返回 ${response.status}`)
    activeStreams.delete(streamId)
    return
  }
  if (!response.body) {
    pushError(context, 'INVALID_RESPONSE', 'SSE 上游没有响应体')
    activeStreams.delete(streamId)
    return
  }

  // === 正常流读取 ===
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split(/\r?\n\r?\n/)
      buffer = events.pop() ?? ''
      for (const rawEvent of events) {
        const trimmed = rawEvent.trim()
        if (trimmed.length === 0) continue
        const dataLines = trimmed
          .split(/\r?\n/)
          .filter((l) => l.startsWith('data:'))
          .map((l) => l.slice('data:'.length).trim())
        const dataStr = dataLines.join('\n')
        if (dataStr.length === 0) continue
        if (dataStr === '[DONE]') {
          pushEnd(context)
          activeStreams.delete(streamId)
          return
        }
        try {
          const event = JSON.parse(dataStr) as StreamEvent
          pushChunk(context, event)
        } catch (err) {
          pushError(context, 'PARSE_ERROR', `无法解析 SSE 帧: ${err instanceof Error ? err.message : String(err)}`)
        }
      }
    }
    pushEnd(context)
    activeStreams.delete(streamId)
  } catch (err) {
    if ((err as { name?: string }).name === 'AbortError') {
      pushError(context, 'ABORTED', '流已取消')
    } else {
      pushError(context, 'NETWORK_ERROR', err instanceof Error ? err.message : String(err))
    }
    activeStreams.delete(streamId)
  }
}

/**
 * 内部: 一次 refresh attempt (Phase 3-A 单飞避免 401 race).
 *
 * 复用 auth.service.performRefresh(vault 里的 refresh_token).
 * 必须 vault 仍可用, 否则 false (上层 emit AUTH_EXPIRED).
 */
async function tryRefreshToken(context: StreamContext): Promise<boolean> {
  const refreshToken = vaultLoadRefreshToken()
  if (!refreshToken) {
    pushError(context, 'NO_REFRESH_TOKEN', 'vault 中没有可用的 refresh_token, 请重新登录')
    return false
  }
  return authService.performRefresh(refreshToken)
}

function mapHttpToErrorCode(status: number): string {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'SERVER_ERROR'
  return 'HTTP_ERROR'
}

export function listActiveStreams(): Array<{ streamId: string; sessionId: string }> {
  return [...activeStreams.entries()].map(([sid, a]) => ({ streamId: sid, sessionId: a.context.sessionId }))
}

export function cleanupChatStreams(): void {
  for (const [sid, a] of activeStreams.entries()) {
    try { a.controller.abort() } catch (_e) { /* ignore */ }
    activeStreams.delete(sid)
  }
}

cleanupChatStreams()
if (typeof app !== 'undefined' && app.on) {
  app.on('before-quit', cleanupChatStreams)
}

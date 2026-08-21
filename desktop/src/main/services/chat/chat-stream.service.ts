// Main Service: Chat SSE Streaming (Phase 2-Impl-3B)。
//
// 设计铁律:
// 1. main 持有 Bearer access_token (renderer 永不见 token)
// 2. fetch POST /chat/stream + 流式读取 + SSE data: 帧解析
// 3. 解析后通过 webContents.send('chat:stream-chunk', streamId, event) 广播
// 4. 终止时 'data: [DONE]\n\n' 检测 → 'chat:stream-end'
// 5. 异常 → 'chat:stream-error' + 清理
//
// 状态: activeStreams Map (streamId -> AbortController) 支持取消.
//
// 范围 (Phase 2-Impl-3B):
//   ✅ text_delta / thinking / done / error / message_persisted 处理
//   ✅ 其余事件透传 (Phase 3+ 由 renderer 决定是否渲染)
//   ❌ 401 单飞 refresh (Phase 3: 流式 access_token 续签)
//   ❌ reconnect / resume from cursor (#043)

import { app, BrowserWindow } from 'electron'
import { APP_CONFIG } from '@shared/config'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  ChatStreamRequest,
  StreamEvent,
  StreamEndPayload
} from '@shared/chat-types'
import { authService } from '../auth.service'

interface ActiveStream {
  controller: AbortController
  sessionId: string
  request: ChatStreamRequest
}

const activeStreams = new Map<string, ActiveStream>()

/**
 * 找出有 UI 的 windows (用于 IPC push)。
 */
function pushToRenderers(channel: string, ...args: unknown[]): void {
  const wins = BrowserWindow.getAllWindows()
  for (const w of wins) {
    if (!w.isDestroyed()) {
      w.webContents.send(channel, ...args)
    }
  }
}

/**
 * 启动一个 SSE 流。
 * - 立刻 resolve streamId 给 renderer
 * - 后续 chunk/end/error 通过 webContents.send 推给所有 renderer
 * - AbortController 支持 cancelStream
 */
export async function startChatStream(
  req: ChatStreamRequest
): Promise<string> {
  const streamId = `stream_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const controller = new AbortController()
  activeStreams.set(streamId, { controller, sessionId: req.session_id, request: req })

  // 异步推流 (不阻塞 resolve)
  void runStream(streamId, req, controller.signal)

  return streamId
}

/**
 * 取消流 (Phase 2 基础支持, renderer 不暴露, 留 IPC channel 以备 Phase 3+ 用)。
 */
export function cancelChatStream(streamId: string): { ok: true } | { ok: false; error: string } {
  const active = activeStreams.get(streamId)
  if (!active) {
    return { ok: false, error: `streamId ${streamId} 不存在` }
  }
  active.controller.abort()
  activeStreams.delete(streamId)
  return { ok: true }
}

/**
 * 内部: 实际 SSE 流循环。
 */
async function runStream(
  streamId: string,
  req: ChatStreamRequest,
  signal: AbortSignal
): Promise<void> {
  const url = `${APP_CONFIG.backendUrl}/chat/stream`
  const accessToken = authService.getCurrentAccessToken()

  // 无 access_token → 立即 error (Phase 2 简化: 不做流内 refresh)
  if (!accessToken) {
    pushError(streamId, 'NO_ACTIVE_SESSION', '当前未登录, 无法发起流式请求')
    activeStreams.delete(streamId)
    return
  }

  try {
    const response = await fetch(url, {
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

    if (!response.ok) {
      pushError(streamId, mapHttpToErrorCode(response.status), `SSE 上游返回 ${response.status}`)
      activeStreams.delete(streamId)
      return
    }
    if (!response.body) {
      pushError(streamId, 'INVALID_RESPONSE', 'SSE 上游没有响应体')
      activeStreams.delete(streamId)
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    // 主循环: 读取 chunk → 拆分 SSE 帧 → 解析 data: 行
    // SSE 帧间分隔: \n\n 或 \r\n\r\n
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // 按 \n\n 拆分 events (last incomplete 留在 buffer)
      const events = buffer.split(/\r?\n\r?\n/)
      buffer = events.pop() ?? ''

      for (const rawEvent of events) {
        const trimmed = rawEvent.trim()
        if (trimmed.length === 0) continue
        // 抓 data: 行; 多行 data: 合并 (Phase 2 简化: 单行 SSE)
        const dataLines = trimmed
          .split(/\r?\n/)
          .filter((l) => l.startsWith('data:'))
          .map((l) => l.slice('data:'.length).trim())
        const dataStr = dataLines.join('\n')
        if (dataStr.length === 0) continue

        // 终结标记 [DONE]
        if (dataStr === '[DONE]') {
          pushEnd(streamId)
          activeStreams.delete(streamId)
          return
        }

        try {
          const event = JSON.parse(dataStr) as StreamEvent
          pushChunk(streamId, event)
        } catch (err) {
          // 跳过畸形行
          pushError(streamId, 'PARSE_ERROR', `无法解析 SSE 帧: ${err instanceof Error ? err.message : String(err)}`)
        }
      }
    }

    // 流自然结束但没收到 [DONE] 标记 → 也算结束
    pushEnd(streamId)
    activeStreams.delete(streamId)
  } catch (err) {
    if ((err as { name?: string }).name === 'AbortError') {
      pushError(streamId, 'ABORTED', '流已取消')
    } else {
      pushError(
        streamId,
        'NETWORK_ERROR',
        err instanceof Error ? err.message : String(err)
      )
    }
    activeStreams.delete(streamId)
  }
}

function pushChunk(streamId: string, event: StreamEvent): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_CHUNK, streamId, event)
}

function pushEnd(streamId: string, payload: StreamEndPayload = { ok: true }): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_END, streamId, payload)
}

function pushError(streamId: string, code: string, message: string): void {
  pushToRenderers(IPC_CHANNELS.CHAT_STREAM_ERROR, streamId, { code, message })
}

function mapHttpToErrorCode(status: number): string {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'SERVER_ERROR'
  return 'HTTP_ERROR'
}

/** 调试 / 设置页可见: 当前活跃流 (测试用)。 */
export function listActiveStreams(): Array<{ streamId: string; sessionId: string }> {
  return [...activeStreams.entries()].map(([sid, a]) => ({ streamId: sid, sessionId: a.sessionId }))
}

/** App quit 时清理所有活跃流。 */
export function cleanupChatStreams(): void {
  for (const [sid, a] of activeStreams.entries()) {
    try { a.controller.abort() } catch (_e) { /* ignore */ }
    activeStreams.delete(sid)
  }
  if (typeof app !== 'undefined' && app.on) {
    app.on('before-quit', cleanupChatStreams)
  }
}

// 模块加载即注册 cleanup
cleanupChatStreams()

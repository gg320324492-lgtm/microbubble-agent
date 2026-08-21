// Chat Pinia store —— Phase 3-A: Reliability Hardened (cancel / retry / session 隔离 / id 同步).
//
// 关键改动 (Phase 3-A vs Phase 2-Impl-3B):
//   - 消息携带 clientMsgId (UUID-like) 用来在 server message_persisted 事件后同步 id
//   - 流处理校验 ctx.sessionId 匹配 currentSessionId (用户切换会话时 ignore stale chunks)
//   - sendUserMessageStream 现在记录 lastSentText 用于 retry
//   - 新增 cancelActiveStream() 与 retryLastMessage()
//   - handleStreamChunkEnd 改用 (ctx, payload) 签名

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  listSessions,
  listMessages,
  DEFAULT_SESSION
} from '../api/chat'
import type {
  ChatSessionListItem,
  ChatMessageOut,
  ChatMessageRole,
  StreamingMessage,
  StreamEvent,
  StreamContext
} from '@shared/chat-types'
import { generateClientMsgId } from '@shared/chat-types'
import type { ApiError } from '@shared/preload-api'

// 增量 ID 用于 UI (Phase 3-A 仍存在; 客户端消息通过 client_msg_id 标识)
let lastTempId = 0
function nextTempId(): number {
  if (lastTempId === 0) lastTempId = Date.now()
  return ++lastTempId
}

export const useChatStore = defineStore('chat', () => {
  // ============ Session 列表 (左栏) ============
  const sessions = ref<ChatSessionListItem[]>([])
  const sessionsLoading = ref(false)
  const sessionsError = ref<ApiError | null>(null)

  // ============ 当前激活 session ============
  const currentSessionId = ref<string>(DEFAULT_SESSION)
  const currentSessionTitle = ref<string>('默认会话')

  // ============ 消息列表 ============
  const messages = ref<ChatMessageOut[]>([])
  const messagesLoading = ref(false)
  const messagesError = ref<ApiError | null>(null)

  // ============ 发送状态 ============
  const sending = ref(false)
  const lastError = ref<ApiError | null>(null)

  // ============ 流式状态 ============
  const streamingMessage = ref<StreamingMessage | null>(null)
  const isStreaming = ref(false)
  const activeStreamId = ref<string | null>(null)
  const activeStreamSessionId = ref<string | null>(null)
  const streamingContentRender = ref<string>('')

  // ============ Phase 3-A: retry / lastSentText / client_msg_id 追踪 ============
  const lastSentText = ref<string | null>(null)
  const lastSentClientMsgId = ref<string | null>(null)

  // ============ 派生 ============
  const visibleMessages = computed<ChatMessageOut[]>(() =>
    messages.value.filter((m) => !m.is_deleted)
  )

  // ============ Actions: Session ============
  async function loadSessions(): Promise<boolean> {
    sessionsLoading.value = true
    try {
      const r = await listSessions({ pageSize: 50, includeArchived: false })
      if (r.ok) {
        sessions.value = r.data.items
        return true
      }
      sessionsError.value = r.error
      return false
    } finally {
      sessionsLoading.value = false
    }
  }

  /**
   * 切换 session: 强制 abort 活跃 stream, 清空 messages, 加载新 session.
   */
  async function selectSession(sessionId: string): Promise<boolean> {
    // 1. 取消任何旧流 (Phase 3-A: 避免 stale chunks 写入新 session 的 messages)
    if (activeStreamId.value) {
      cancelActiveStream()
    }
    // 2. 重置 messages + 流状态
    currentSessionId.value = sessionId
    const target = sessions.value.find((s) => s.id === sessionId)
    currentSessionTitle.value = target?.title ?? '会话'
    messages.value = []
    messagesError.value = null
    streamingMessage.value = null
    isStreaming.value = false
    streamingContentRender.value = ''
    return await loadMessages(sessionId)
  }

  async function loadMessages(sessionId: string): Promise<boolean> {
    messagesLoading.value = true
    try {
      const r = await listMessages(sessionId, { limit: 50 })
      if (r.ok) {
        messages.value = r.data.items
        return true
      }
      messagesError.value = r.error
      return false
    } finally {
      messagesLoading.value = false
    }
  }

  // ============ Actions: 流式发送 (Phase 3-A) ============
  /**
   * 流式发送 (SSE).
   * 1. optimistic push user with clientMsgId
   * 2. 创建 streamingMessage placeholder with clientMsgId
   * 3. startStream → streamId (main 会自动 refresh on 401)
   * 4. handleStreamChunk/End/Error 接管后续, 校验 sessionId 匹配
   */
  async function sendUserMessageStream(content: string): Promise<boolean> {
    const text = content.trim()
    if (text.length === 0 || isStreaming.value) return false

    const userClientMsgId = generateClientMsgId()
    const tempUserId = nextTempId()
    const optimisticUser: ChatMessageOut = {
      id: tempUserId,
      session_id: currentSessionId.value,
      role: 'user' as ChatMessageRole,
      content: text,
      rich_blocks: [],
      tool_trace: [],
      message_metadata: { client_msg_id: userClientMsgId, optimistic: true },
      is_partial: false,
      is_deleted: false,
      client_msg_id: userClientMsgId,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: new Date().toISOString()
    }
    messages.value = [...messages.value, optimisticUser]

    const tempAssistantId = nextTempId()
    const assistantClientMsgId = generateClientMsgId()
    streamingMessage.value = {
      id: tempAssistantId,
      session_id: currentSessionId.value,
      role: 'assistant' as ChatMessageRole,
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: assistantClientMsgId
    }
    streamingContentRender.value = ''
    isStreaming.value = true
    sending.value = true
    lastSentText.value = text
    lastSentClientMsgId.value = userClientMsgId

    try {
      const streamId = await window.api.chat.startStream({
        message: text,
        session_id: currentSessionId.value
      })
      activeStreamId.value = streamId
      activeStreamSessionId.value = currentSessionId.value
      return true
    } catch (err) {
      handleStreamError({ streamId: 'failed', sessionId: currentSessionId.value }, 'START_FAILED', err instanceof Error ? err.message : String(err))
      return false
    }
  }

  /**
   * 取消当前活跃流 (用户点 "停止生成").
   */
  async function cancelActiveStream(): Promise<void> {
    if (!activeStreamId.value) return
    const sid = activeStreamId.value
    activeStreamId.value = null
    activeStreamSessionId.value = null
    try {
      await window.api.chat.cancelStream(sid)
    } catch (err) {
      // 忽略 cancel 失败 (main 已经 streamed 到 [DONE] 或 abort)
      void err
    }
  }

  /**
   * 重试上次失败消息 (复用 lastSentText).
   */
  async function retryLastMessage(): Promise<boolean> {
    if (!lastSentText.value || isStreaming.value) return false
    return await sendUserMessageStream(lastSentText.value)
  }

  /**
   * 拷贝 assistant message 到剪贴板.
   * navigator.clipboard.writeText 在 HTTPS/file:// 均有效.
   * 失败降级 prompt user 手动复制.
   */
  async function copyAssistantMessage(msgId: number): Promise<boolean> {
    const msg = messages.value.find((m) => m.id === msgId)
    if (!msg || msg.role !== 'assistant') return false
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(msg.content)
        return true
      }
      return false
    } catch (_e) {
      return false
    }
  }

  /**
   * 处理 SSE chunk. 校验 session 匹配, 否则 ignore (用户已切会话).
   */
  function handleStreamChunk(ctx: StreamContext, event: StreamEvent): void {
    if (streamStaleCheck(ctx)) return
    if (!streamingMessage.value) return

    switch (event.type) {
      case 'text_delta':
        if (event.delta) streamingMessage.value.content += event.delta
        break
      case 'thinking':
        streamingMessage.value.thinking = event.label ?? null
        break
      case 'message_persisted':
        // 服务端 message_id 同步 (按 client_msg_id 关联)
        if (event.message_id && event.role === 'assistant') {
          if (event.client_msg_id && streamingMessage.value.client_msg_id === event.client_msg_id) {
            streamingMessage.value.persisted_message_id = event.message_id
          }
        } else if (event.message_id && event.role === 'user') {
          // 替换 optimistic user id by client_msg_id
          if (event.client_msg_id) {
            updateMessageIdByClientMsgId(event.client_msg_id, event.message_id)
          }
        }
        break
      case 'sync_required':
        handleStreamError(ctx, 'SYNC_REQUIRED', event.reason ?? 'aborted')
        break
      case 'tool_use':
      case 'tool_result':
      case 'rich_block':
      case 'intent_detected':
      case 'plan_step':
      case 'synthesis_start':
      case 'critique':
      case 'retry':
      case 'refs':
      case 'suggestions':
      case 'brief':
      case 'detail':
      case 'tool_compressed':
        if (event.type === 'rich_block' && event.block) {
          streamingMessage.value.rich_blocks.push(event.block as Record<string, unknown>)
        }
        break
      case 'done':
        // finalize 由 handleStreamEnd 处理
        break
      case 'error':
        handleStreamError(ctx, event.code ?? 'STREAM_ERROR', event.message ?? '未知流错误')
        break
      default:
        break
    }
  }

  function handleStreamEnd(ctx: StreamContext): void {
    if (streamStaleCheck(ctx)) return
    if (!streamingMessage.value) return

    const finishedAt = new Date().toISOString()
    const persistedId = streamingMessage.value.persisted_message_id
    const msg: ChatMessageOut = {
      id: persistedId ?? streamingMessage.value.id,
      session_id: streamingMessage.value.session_id,
      role: 'assistant' as ChatMessageRole,
      content: streamingMessage.value.content,
      rich_blocks: streamingMessage.value.rich_blocks,
      tool_trace: streamingMessage.value.tool_trace,
      message_metadata: {
        started_at: streamingMessage.value.started_at,
        finished_at: finishedAt,
        thinking: streamingMessage.value.thinking,
        client_msg_id: streamingMessage.value.client_msg_id,
        optimistic: false
      },
      is_partial: false,
      is_deleted: false,
      client_msg_id: streamingMessage.value.client_msg_id,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: finishedAt
    }
    messages.value = [...messages.value, msg]

    streamingMessage.value = null
    streamingContentRender.value = ''
    isStreaming.value = false
    activeStreamId.value = null
    activeStreamSessionId.value = null
    sending.value = false

    if (messages.value.length > 0 && lastSentText.value) {
      const firstUser = messages.value.find((m) => m.role === 'user')
      if (firstUser && firstUser.content.length > 0 && messages.value.filter((m) => m.role === 'user').length === 1) {
        currentSessionTitle.value = firstUser.content.slice(0, 30)
      }
    }
    void loadSessions()
  }

  function handleStreamError(_ctx: StreamContext, code: string, message: string): void {
    isStreaming.value = false
    activeStreamId.value = null
    activeStreamSessionId.value = null
    sending.value = false
    streamingMessage.value = null
    streamingContentRender.value = ''
    lastError.value = { code, message, status: undefined }
  }

  /**
   * 流 chunk/end/error 校验: 用户已切换 session (ctx.sessionId !== currentSessionId)
   * 视为 stale, ignore. activeStreamId 也比对, 防止 race.
   */
  function streamStaleCheck(ctx: StreamContext): boolean {
    if (!activeStreamId.value) return true
    if (activeStreamId.value !== ctx.streamId) return true
    if (ctx.sessionId !== currentSessionId.value) {
      // 用户切了 session; 丢弃 chunk, 不写 messages / streamingMessage
      // 但不清 streamingMessage / activeStreamId (让主进程的 stream-end 自然触发清理)
      return true
    }
    return false
  }

  /**
   * 内部: 通过 client_msg_id 同步服务端 message_id (用于 user message).
   * 找不到则 no-op (可能已被替换或重复事件).
   */
  function updateMessageIdByClientMsgId(clientMsgId: string, newId: number): void {
    const idx = messages.value.findIndex((m) => m.client_msg_id === clientMsgId)
    if (idx < 0) return
    const msg = messages.value[idx]
    if (!msg) return
    const updated: ChatMessageOut = { ...msg, id: newId }
    messages.value = [
      ...messages.value.slice(0, idx),
      updated,
      ...messages.value.slice(idx + 1)
    ]
  }

  let streamingDebounceTimer: ReturnType<typeof setTimeout> | null = null
  function scheduleStreamingContentRender(): void {
    if (streamingDebounceTimer) clearTimeout(streamingDebounceTimer)
    streamingDebounceTimer = setTimeout(() => {
      if (streamingMessage.value) {
        streamingContentRender.value = streamingMessage.value.content
      }
    }, 100)
  }

  function clearError(): void {
    lastError.value = null
  }

  return {
    // state
    sessions,
    sessionsLoading,
    sessionsError,
    currentSessionId,
    currentSessionTitle,
    messages,
    messagesLoading,
    messagesError,
    sending,
    lastError,
    streamingMessage,
    isStreaming,
    activeStreamId,
    activeStreamSessionId,
    streamingContentRender,
    lastSentText,
    lastSentClientMsgId,
    // derived
    visibleMessages,
    // actions
    loadSessions,
    selectSession,
    loadMessages,
    sendUserMessageStream,
    cancelActiveStream,
    retryLastMessage,
    copyAssistantMessage,
    handleStreamChunk,
    handleStreamEnd,
    handleStreamError,
    scheduleStreamingContentRender,
    clearError
  }
})

// Chat Pinia store —— session 列表 + 当前 session + 消息列表 + 发送状态 + 流式 chat。
//
// Phase 2-Impl-3A: 同步 sendUserMessage (保留作 Phase 2 兼容)
// Phase 2-Impl-3B: 改 sendUserMessageStream → SSE 流式 + 占位 assistant + chunk append
// 数据全部经 IPC 委托 main api.service / chat-stream.service。

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  listSessions,
  listMessages,
  sendMessage,
  DEFAULT_SESSION
} from '../api/chat'
import type {
  ChatSessionListItem,
  ChatMessageOut,
  ChatMessageRole,
  StreamingMessage,
  StreamEvent
} from '@shared/chat-types'
import type { ApiError } from '@shared/preload-api'

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

  // ============ 发送状态 (Phase 2-Impl-3A 保留) ============
  const sending = ref(false)
  const pendingUserContent = ref<string | null>(null)
  const lastError = ref<ApiError | null>(null)

  // ============ 流式状态 (Phase 2-Impl-3B) ============
  const streamingMessage = ref<StreamingMessage | null>(null)
  const isStreaming = ref(false)
  const activeStreamId = ref<string | null>(null)
  /** 当前累加的 markdown content (raw 文本), debounce 给 MarkdownViewer 用 */
  const streamingContentRender = ref<string>('')

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

  async function selectSession(sessionId: string): Promise<boolean> {
    currentSessionId.value = sessionId
    const target = sessions.value.find((s) => s.id === sessionId)
    currentSessionTitle.value = target?.title ?? '会话'
    messages.value = []
    messagesError.value = null
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

  // ============ Actions: 同步发送 (Phase 2-Impl-3A 保留) ============
  async function sendUserMessage(content: string): Promise<boolean> {
    const text = content.trim()
    if (text.length === 0) return false

    const tempId = Date.now()
    const optimisticUser: ChatMessageOut = {
      id: tempId,
      session_id: currentSessionId.value,
      role: 'user' as ChatMessageRole,
      content: text,
      rich_blocks: [],
      tool_trace: [],
      message_metadata: {},
      is_partial: false,
      is_deleted: false,
      client_msg_id: null,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: new Date().toISOString()
    }
    messages.value = [...messages.value, optimisticUser]
    pendingUserContent.value = text
    sending.value = true

    try {
      const r = await sendMessage({
        message: text,
        session_id: currentSessionId.value
      })
      if (!r.ok) {
        messages.value = messages.value.filter((m) => m.id !== tempId)
        lastError.value = r.error
        return false
      }
      const resp = r.data
      messages.value = messages.value.filter((m) => m.id !== tempId)
      const assistantMsg: ChatMessageOut = {
        id: tempId + 1,
        session_id: resp.session_id,
        role: 'assistant' as ChatMessageRole,
        content: resp.content,
        rich_blocks: resp.rich_blocks,
        tool_trace: resp.tool_trace,
        message_metadata: resp.usage ? { usage: resp.usage, duration_ms: resp.duration_ms ?? null } : {},
        is_partial: false,
        is_deleted: false,
        client_msg_id: null,
        attached_knowledge_ids: [],
        image_url: null,
        created_at: new Date().toISOString()
      }
      messages.value = [...messages.value, assistantMsg]
      if (messages.value.length === 1 && text.length > 0) {
        currentSessionTitle.value = text.slice(0, 30)
      }
      void loadSessions()
      return true
    } finally {
      sending.value = false
      pendingUserContent.value = null
    }
  }

  // ============ Actions: 流式发送 (Phase 2-Impl-3B) ============
  /**
   * 流式发送 (SSE)。
   * 1. optimistic push user
   * 2. 创建 streamingMessage placeholder
   * 3. startStream → streamId
   * 4. handleStreamChunk / handleStreamEnd / handleStreamError 接管后续
   */
  async function sendUserMessageStream(content: string): Promise<boolean> {
    const text = content.trim()
    if (text.length === 0 || isStreaming.value) return false

    const tempUserId = Date.now()
    const optimisticUser: ChatMessageOut = {
      id: tempUserId,
      session_id: currentSessionId.value,
      role: 'user' as ChatMessageRole,
      content: text,
      rich_blocks: [],
      tool_trace: [],
      message_metadata: {},
      is_partial: false,
      is_deleted: false,
      client_msg_id: null,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: new Date().toISOString()
    }
    messages.value = [...messages.value, optimisticUser]

    const tempAssistantId = tempUserId + 1
    const newStreaming: StreamingMessage = {
      id: tempAssistantId,
      session_id: currentSessionId.value,
      role: 'assistant' as ChatMessageRole,
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null
    }
    streamingMessage.value = newStreaming
    streamingContentRender.value = ''
    isStreaming.value = true
    sending.value = true
    pendingUserContent.value = text

    try {
      const streamId = await window.api.chat.startStream({
        message: text,
        session_id: currentSessionId.value
      })
      activeStreamId.value = streamId
      return true
    } catch (err) {
      // IPC 失败 rollback
      handleStreamError('START_FAILED', err instanceof Error ? err.message : String(err))
      return false
    }
  }

  /**
   * 处理 SSE chunk. 仅处理 active stream 的事件.
   * Phase 2-Impl-3B 简化:
   *   - text_delta: streamingMessage.content 累加
   *   - thinking: streamingMessage.thinking 设 label
   *   - done: finalize 推送 ChatMessageOut
   *   - error / message_persisted: 记录
   *   - 其他 type: ignore (Phase 3+ 接)
   */
  function handleStreamChunk(streamId: string, event: StreamEvent): void {
    if (streamId !== activeStreamId.value) return
    if (!streamingMessage.value) return

    switch (event.type) {
      case 'text_delta':
        if (event.delta) {
          streamingMessage.value.content += event.delta
        }
        break
      case 'thinking':
        streamingMessage.value.thinking = event.label ?? null
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
        // Phase 2-Impl-3B: acknowledge 但不渲染
        // Phase 3+ 接 agent tool / RAG citation
        if (event.type === 'rich_block' && event.block) {
          // Future: append block to streamingMessage.rich_blocks
          streamingMessage.value.rich_blocks.push(event.block as Record<string, unknown>)
        }
        break
      case 'message_persisted':
        if (event.message_id) {
          streamingMessage.value.persisted_message_id = event.message_id
        }
        break
      case 'sync_required':
        // 流中断兜底
        handleStreamError('SYNC_REQUIRED', event.reason ?? 'aborted')
        break
      case 'done':
        // finalize 由 handleStreamEnd 处理 (after [DONE] marker)
        break
      case 'error':
        handleStreamError(event.code ?? 'STREAM_ERROR', event.message ?? '未知流错误')
        break
      default:
        // 未知 type: ignore
        break
    }
  }

  /**
   * 流结束 (成功). 把 streamingMessage 转 ChatMessageOut 推入 messages.
   */
  function handleStreamEnd(streamId: string): void {
    if (streamId !== activeStreamId.value) return
    if (!streamingMessage.value) return

    const finishedAt = new Date().toISOString()
    const msg: ChatMessageOut = {
      id: streamingMessage.value.id,
      session_id: streamingMessage.value.session_id,
      role: 'assistant' as ChatMessageRole,
      content: streamingMessage.value.content,
      rich_blocks: streamingMessage.value.rich_blocks,
      tool_trace: streamingMessage.value.tool_trace,
      message_metadata: {
        started_at: streamingMessage.value.started_at,
        finished_at: finishedAt,
        thinking: streamingMessage.value.thinking
      },
      is_partial: false,
      is_deleted: false,
      client_msg_id: null,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: finishedAt
    }
    messages.value = [...messages.value, msg]

    // 清理流状态
    streamingMessage.value = null
    streamingContentRender.value = ''
    isStreaming.value = false
    activeStreamId.value = null
    sending.value = false
    pendingUserContent.value = null

    // 更新 session title + 异步刷新
    if (messages.value.length === 1) {
      const firstUser = messages.value.find((m) => m.role === 'user')
      if (firstUser && firstUser.content.length > 0) {
        currentSessionTitle.value = firstUser.content.slice(0, 30)
      }
    }
    void loadSessions()
  }

  /**
   * 流错误. 移除 streamingMessage + 设置 lastError.
   */
  function handleStreamError(code: string, message: string): void {
    isStreaming.value = false
    activeStreamId.value = null
    sending.value = false
    pendingUserContent.value = null
    streamingMessage.value = null
    streamingContentRender.value = ''
    lastError.value = {
      code,
      message,
      status: undefined
    }
  }

  /**
   * Phase 2-Impl-3B 100ms debounce: 流式 content 触发 MarkdownViewer 重新渲染。
   * 触发写 streamingContentRender, 触发 ChatView reactive 更新。
   */
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
    pendingUserContent,
    lastError,
    streamingMessage,
    isStreaming,
    activeStreamId,
    streamingContentRender,
    // derived
    visibleMessages,
    // actions
    loadSessions,
    selectSession,
    loadMessages,
    sendUserMessage,
    sendUserMessageStream,
    handleStreamChunk,
    handleStreamEnd,
    handleStreamError,
    scheduleStreamingContentRender,
    clearError
  }
})

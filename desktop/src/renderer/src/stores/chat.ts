// Chat Pinia store —— session 列表 + 当前 session + 消息列表 + 发送状态。
//
// Phase 2-Impl-3A 仅同步请求, Phase 3+ 接 SSE。
// 数据全部经 IPC 委托 main api.service, renderer 不持久化。

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
  ChatMessageRole
} from '@shared/chat-types'
import type { ApiError } from '@shared/preload-api'

export const useChatStore = defineStore('chat', () => {
  // Session 列表 (左栏)
  const sessions = ref<ChatSessionListItem[]>([])
  const sessionsLoading = ref(false)

  // 当前激活 session
  const currentSessionId = ref<string>(DEFAULT_SESSION)
  const currentSessionTitle = ref<string>('默认会话')

  // 消息列表
  const messages = ref<ChatMessageOut[]>([])
  const messagesLoading = ref(false)

  // 临时"用户刚发"占位 (optimistic, 等 send 完成替换)
  const pendingUserContent = ref<string | null>(null)

  // 发送状态
  const sending = ref(false)

  // 错误归一
  const lastError = ref<ApiError | null>(null)
  const sessionsError = ref<ApiError | null>(null)
  const messagesError = ref<ApiError | null>(null)

  // ============ 派生 ============
  const visibleMessages = computed<ChatMessageOut[]>(() =>
    messages.value.filter((m) => !m.is_deleted)
  )

  // ============ Actions ============

  /** 拉 Session 列表（左栏）。 */
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

  /** 激活 Session 并加载消息。 */
  async function selectSession(sessionId: string): Promise<boolean> {
    currentSessionId.value = sessionId
    const target = sessions.value.find((s) => s.id === sessionId)
    currentSessionTitle.value = target?.title ?? '会话'
    messages.value = []
    messagesError.value = null
    return await loadMessages(sessionId)
  }

  /** 拉指定 session 的消息列表。 */
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

  /**
   * 发消息 (同步)。
   * 流程:
   *   1. 立刻把用户消息 push 到 messages (optimistic, role='user')
   *   2. 设 sending=true
   *   3. POST /chat
   *   4. 成功: 把 assistant 回复 push 到 messages; 刷新 sessions (计数变化)
   *   5. 失败: 移除 optimistic user, 设置 lastError
   */
  async function sendUserMessage(content: string): Promise<boolean> {
    const text = content.trim()
    if (text.length === 0) return false

    // optimistic UI: 立刻显示用户消息
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
        // 失败: 撤回 optimistic user
        messages.value = messages.value.filter((m) => m.id !== tempId)
        lastError.value = r.error
        return false
      }

      const resp = r.data
      // 移除 optimistic, 替换为后端实返回 (id 替换)
      messages.value = messages.value.filter((m) => m.id !== tempId)
      // assistant 回复
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

      // 同步刷新 session title (后端可能用首条消息改 title)
      if (resp.session_id === currentSessionId.value) {
        if (messages.value.length === 1 && text.length > 0) {
          currentSessionTitle.value = text.slice(0, 30)
        }
      }
      // 后台刷新 session 列表 (可能有 title / message_count 变化)
      void loadSessions()
      return true
    } finally {
      sending.value = false
      pendingUserContent.value = null
    }
  }

  function clearError(): void {
    lastError.value = null
  }

  return {
    // state
    sessions,
    sessionsLoading,
    currentSessionId,
    currentSessionTitle,
    messages,
    messagesLoading,
    pendingUserContent,
    sending,
    lastError,
    sessionsError,
    messagesError,
    // derived
    visibleMessages,
    // actions
    loadSessions,
    selectSession,
    loadMessages,
    sendUserMessage,
    clearError
  }
})

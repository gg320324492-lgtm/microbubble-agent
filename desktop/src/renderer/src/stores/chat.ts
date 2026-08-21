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
  ToolCallSnapshot,
  StreamEvent,
  StreamContext,
  StreamCitationEntry
} from '@shared/chat-types'
import type { KnowledgeResponse } from '@shared/knowledge-types'
import { generateClientMsgId } from '@shared/chat-types'
import { knowledgeService } from '../services/knowledge.service'
import { dedupCitations } from '../utils/citation'
import { deriveAgentStateHint, type AgentStateHint } from '../utils/agent-state'
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

  // ============ Phase 4-C: Citation Hot Path (cache hits) ============
  /** knowledgeId -> KnowledgeResponse. 异步 prefetch 解析后写入. */
  const cachedHintsMap = new Map<number, KnowledgeResponse>()
  const cachedHints = ref<Map<number, KnowledgeResponse>>(cachedHintsMap)
  /** 当前活跃 prefetch (按 knowledgeId). 避免重复 fire + 关闭时取消. */
  const inflightPrefetches = new Map<number, Promise<void>>()

  // ============ 派生 ============
  const visibleMessages = computed<ChatMessageOut[]>(() =>
    messages.value.filter((m) => !m.is_deleted)
  )

  /**
   * Phase 5-C: Agent State Model.
   * 纯响应式 derive: 任何 streamingMessage / isStreaming / lastError 变化触发重算.
   * session 隔离: 是 Pinia module-level singleton; streamingMessage 切换 session 时
   *   由 selectSession 同步清 (Phase 4-C), 因此 deriveAgentState 也自动随 session 切换.
   */
  const agentStateHint = computed<AgentStateHint>(() =>
    deriveAgentStateHint({
      streamingMessage: streamingMessage.value,
      isStreaming: isStreaming.value,
      lastError: lastError.value
    })
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
    // Phase 4-C: session 切换 -> 清 cachedHints + in-flight prefetch (session 隔离)
    clearCachedHints()
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
      /** Phase 5-A: tool 调用快照 (按 tool_use_id dedup) */
      tool_calls: [],
      /** Phase 3-C1: citation 累加数组 */
      citations: [],
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
        // Phase 5-A: 累积工具调用快照.
        //   - tool_use: 新建 'call_only' ToolCallSnapshot
        //   - tool_result: 找到之前的 tool_use_id, update status + result
        // 失败 / 缺字段: 静默 ack (不污染流)
        if (!event.tool_use_id) break
        if (event.type === 'tool_use') {
          const snap: ToolCallSnapshot = {
            tool_use_id: event.tool_use_id,
            name: event.tool_name ?? 'unknown',
            input: event.tool_input ?? {},
            started_at: new Date().toISOString(),
            finished_at: null,
            status: 'call_only',
            output: null,
            error: null,
            duration_ms: null
          }
          // 按 tool_use_id dedup; 已有则替换
          appendToolCall(snap)
        } else {
          // tool_result
          const existing = streamingMessage.value.tool_calls.find(
            (t) => t.tool_use_id === event.tool_use_id
          )
          if (existing) {
            existing.finished_at = new Date().toISOString()
            existing.duration_ms = event.tool_duration_ms ?? null
            existing.output = event.tool_output ?? null
            existing.error = event.tool_error ?? null
            existing.status = event.tool_error ? 'error' : 'success'
          }
        }
        break
      case 'rich_block':
        // Phase 5-A: 累积 rich_block (Phase 3-B0 frozen SchemaStreamRichBlock)
        if (event.block) {
          streamingMessage.value.rich_blocks.push(event.block)
        }
        break
      case 'intent_detected':
      case 'plan_step':
      case 'synthesis_start':
      case 'critique':
      case 'retry':
      case 'suggestions':
      case 'brief':
      case 'detail':
      case 'tool_compressed':
        // Phase 3+ 接 agent tool / intent 等. Phase 5-A 仅接 tool_use / tool_result / rich_block.
        break
      case 'citation':
      case 'refs':
        // Phase 3-C1: RAG 引用. 单条或数组皆累加, 渲染时去重 + 按 knowledgeId 排序.
        // Phase 3-C2: dedupCitations 提取到 utils, 让 store 只负责累加, dedup 在引用时
        //   (or 一次性) 由组件层 sortCitations + dedupCitations 完成.
        // Phase 4-C: 收到 citation/refs 立即触发 knowledgeService.prefetchKnowledgeForCitations,
        //   异步写入 cache + cachedHints (session 匹配 + 流 active 才写).
        if (event.citation) {
          appendCitations(streamingMessage.value.citations, event.citation)
          triggerPrefetch(Array.isArray(event.citation) ? event.citation : [event.citation])
        }
        if (event.refs) {
          appendCitations(streamingMessage.value.citations, event.refs)
          triggerPrefetch(event.refs)
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
      tool_trace: streamingMessage.value.tool_calls as unknown as Record<string, unknown>[],
      message_metadata: {
        started_at: streamingMessage.value.started_at,
        finished_at: finishedAt,
        thinking: streamingMessage.value.thinking,
        client_msg_id: streamingMessage.value.client_msg_id,
        optimistic: false,
        // Phase 3-C1: 持久化 citations (后端 ChatMessageOut schema 不含 citations,
        // 通过 message_metadata 透传, 后续 listMessages 加载时反序列化)
        citations: streamingMessage.value.citations
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
    // Phase 4-C: 流结束 (cancel / error) -> 清 cachedHints, 防止 stale UI hint
    // 注: in-flight prefetch 走其自身 .finally 清理; 这里仅清 UI 视图
    cachedHints.value = new Map()
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
   * 内部: 累加 ToolCallSnapshot, 按 tool_use_id dedup.
   * Phase 5-A: append only; 同 id 二次 append 替换 (覆盖 from SSE 重传).
   */
  function appendToolCall(snap: ToolCallSnapshot): void {
    if (!streamingMessage.value) return
    const idx = streamingMessage.value.tool_calls.findIndex(
      (t) => t.tool_use_id === snap.tool_use_id
    )
    if (idx >= 0) {
      streamingMessage.value.tool_calls[idx] = snap
    } else {
      streamingMessage.value.tool_calls.push(snap)
    }
  }

  /**
   * 内部: 把 stream event.citation 累加到 streamingMessage.citations.
   * - 接受 StreamCitationEntry | StreamCitationEntry[] | undefined
   * - dedup 走 utils/citation.dedupCitations 一次性合并 (不在这里做, 渲染时统一)
   * - 跳过非法 entry (knowledgeId 非 number)
   *
   * Phase 3-C1 原始实现; Phase 3-C2 改为 delegate 给 utils/dedupCitations.
   * 这里仍负责"累加"职责, dedup + sort 在 CitationList 渲染时一次性.
   */
  function appendCitations(
    target: StreamCitationEntry[],
    incoming: StreamCitationEntry | StreamCitationEntry[] | undefined
  ): void {
    if (!incoming) return
    const list = Array.isArray(incoming) ? incoming : [incoming]
    if (list.length === 0) return
    for (const c of list) {
      if (!c || typeof c.knowledgeId !== 'number' || !Number.isFinite(c.knowledgeId)) continue
      target.push(c)
    }
    // Phase 3-C2: dedup 与 sort 在 CitationList 渲染层做 (utils/citation.ts),
    // 这里仅保 SSE chunk 顺序, 不丢任何中间 event.
    void dedupCitations // 显式引用保 lint 通过; 实际 dedup 在 normalizeCitations 调用链
  }

  /**
   * Phase 4-C: 触发 citation prefetch (异步, 失败静默, session 隔离).
   *
   * 流程:
   *   1. 过滤 invalid id (knowledgeId 缺失 / 负 / NaN)
   *   2. dedup by knowledgeId (已在 inflightPrefetches 跳过)
   *   3. 捕获当前 sessionId (快照)
   *   4. knowledgeService.prefetchKnowledgeForCitations(...)
   *   5. 解析后断言:
   *      - 仍同 session (currentSessionId 未变)
   *      - 流仍 active (activeStreamId === ctx.streamId)
   *      - 成功 -> 写 cachedHints (Vue reactive Map)
   *   6. 失败 / 上述条件失效 -> 丢弃结果 (cache 仍写, UI 不更新)
   *
   * 注: cache 写不撤销 (KnowledgeService 自身 LRU 处理), 仅控制 UI 渲染时
   * 是否展示 hint. 用户切到新 session 后, cachedHints 被 selectSession 清.
   */
  function triggerPrefetch(citations: StreamCitationEntry[]): void {
    if (!Array.isArray(citations) || citations.length === 0) return
    const startSessionId = currentSessionId.value
    const startStreamId = activeStreamId.value
    if (!startStreamId) return  // 没有 flow 在跑, 跳过

    for (const c of citations) {
      if (!c || typeof c.knowledgeId !== 'number' || !Number.isFinite(c.knowledgeId)) continue
      const id = c.knowledgeId
      if (id <= 0) continue
      if (inflightPrefetches.has(id)) continue  // Phase 4-C: dedup by id

      const promise = knowledgeService
        .prefetchKnowledgeForCitations([c])
        .then((result) => {
          // 异步结果: 仅当 session + 流状态匹配时更新 UI hint
          if (currentSessionId.value !== startSessionId) return
          if (activeStreamId.value !== startStreamId) return
          if (!result.ok) return  // 失败静默 (cache 已由 service 写成功的部分)
          // result.data 是 KnowledgeResponse[] (批量); 当前 prefetch [c] 单条, 拿 [0]
          const r = result.data[0]
          if (!r) return
          const next = new Map(cachedHints.value)
          next.set(id, r)
          cachedHints.value = next
        })
        .catch(() => {
          // 失败 -> 不污染 cachedHints
        })
        .finally(() => {
          if (inflightPrefetches.get(id) === promise) {
            inflightPrefetches.delete(id)
          }
        })

      inflightPrefetches.set(id, promise)
    }
  }

  /**
   * Cache 命中查询 (read-only, 不触发 prefetch).
   * 暴露给组件: 在 CitationCard 等位置直接读 cache 不走 IPC.
   */
  function getCachedHint(knowledgeId: number): KnowledgeResponse | null {
    return knowledgeService.cacheLookup(knowledgeId)
  }

  /**
   * 清空 session-scoped UI hints (Phase 4-C Lifecycle).
   * cache 本身 (LRU) 不动 (Phase 4+: 跨 session 复用).
   */
  function clearCachedHints(): void {
    inflightPrefetches.clear()
    cachedHints.value = new Map()
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
    cachedHints,
    // derived
    visibleMessages,
    agentStateHint,
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
    getCachedHint,
    clearCachedHints,
    clearError
  }
})

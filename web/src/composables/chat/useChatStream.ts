/**
 * useChatStream.ts — SSE 多会话并行核心（桌面/移动共用）
 *
 * 从 ChatViewSSE.vue 抽取（PR #1 基建，PR #3 重构 ChatViewSSE.vue 调用此 composable）。
 *
 * 修复 4 多会话并行架构（**绝不可破坏**）：
 * 1. per-session 消息隔离：messagesBySession[sessionId] 而非全局 messages[]
 * 2. per-session AbortController：多次点击同会话 abort 旧流，**切会话不 abort**
 * 3. per-session 发送锁：sendingSessions: Set<string>
 * 4. 闭包捕获 targetSessionId：sendMessage 启动时锁定，防止 SSE yield 时 outer sessionId 已切走
 * 5. activeAssistantMap[sessionId] 引用：SSE yield 时通过 targetSessionId 找到正确的 assistantMsg
 * 6. loadedSessions 防覆盖：已加载过 localStorage 的 session 不重读，保留后台 SSE 增量
 * 7. debounce 100ms 持久化：SSE yield 时调用，防后台丢数据
 * 8. onUnmounted 兜底：abort 所有 + 持久化所有 session
 *
 * UI 层（桌面 / 移动）只关心 messages / loading / sendMessage / sessions，不接触 SSE 细节。
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { sseFetch } from '@/api/agent/sse'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { useUiStore } from '@/stores/useUiStore'

// ============================================================================
// 类型定义
// ============================================================================

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  richBlocks: any[]
  toolTrace?: Array<{
    type: 'thinking' | 'tool'
    label?: string
    name?: string
    state?: 'running' | 'done'
    duration_ms?: number
    // 2026-06-14 方案 C Stage 4：附加压缩信息（tool_compressed 事件）
    compression?: {
      original_count: number
      selected_count: number
      summary: string
    }
  }>
  timestamp: string
  // 2026-06-14 方案 C Stage 4：state 加 'aborted'
  state?: 'streaming' | 'idle' | 'aborted'
  is_brief?: boolean
  error?: string | null
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
  durationMs?: number
  type?: 'text' | 'image' | 'file'
  imageUrl?: string
  // 2026-06-14 方案 C Stage 4：新增 4 个字段（对应 6 个新事件）
  intent?: { category: string; confidence: number; keywords?: string[]; reasoning?: string }
  plan?: Array<{ step: string; tool?: string; status: 'pending' | 'running' | 'done' }>
  critique?: { score: number; addresses_question?: boolean; has_synthesis?: boolean; has_citations?: boolean; suggestion?: string }
  retryCount?: number
  // ===== 2026-06-30 #009 Self-RAG 新增字段 =====
  /** Self-RAG judge 最终评估 (前端可显示 confidence/can_answer badge) */
  retrievalAssessment?: { phase?: string; confidence?: number; can_answer?: boolean; missing?: string; reretrieved?: boolean; attempt?: number; latency_ms?: number }
  /** 正在重新检索动画 (reretrieval event → tool_result 后自动 false) */
  reretrieving?: boolean
  // ===== #043 新增字段（服务端持久化追踪） =====
  /** 服务端 message id（持久化成功后填入） */
  server_id?: number
  /** 客户端消息 id（幂等键，用于重试不重复写） */
  client_msg_id?: string
  /** 是否 partial（流式中断标记） */
  is_partial?: boolean
}

export interface SendOptions {
  text?: string
  file?: File | null
  image?: File | null
}

// ============================================================================
// LocalStorage 键（与原 ChatViewSSE.vue 保持一致，便于双版本并存过渡）
// ============================================================================

const SESSION_KEY = 'chat_current_session_v3'
const LEGACY_KEY = 'chat_session_id' // v1 单会话兼容键
const LEGACY_MESSAGES_KEY = 'chat_messages_v2' // 旧单会话兼容键（仅写不读）
const MESSAGES_KEY_PREFIX = 'chat_msgs_' // per-session 消息

const PERSIST_DEBOUNCE_MS = 100
const MESSAGES_SLICE_KEEP = 200

// ============================================================================
// useChatStream Composable
// ============================================================================

export function useChatStream() {
  // --------------------------------------------------------------------------
  // 当前显示的会话 ID（UI 层可读写）
  // ★ 2026-07-01 修复 bug 1a: 初始 sessionId 优先用 sessionsStore 的 currentId
  // 旧实现: localStorage 直接读 SESSION_KEY → 跨用户污染时拿到旧 user 的 id
  // → 服务端 ensure_session_for_stream 静默创建新行 → 重复 "新对话"
  // 新实现: 让 store 在 onMounted 之后用 pickInitialSessionId 选（详见 onMounted）
  // 初始值仍读 localStorage（兼容无 store / SSR / 第一次加载场景），
  // 实际"选 sessionId" 逻辑在 store 调用 resolveInitialSessionId()。
  // --------------------------------------------------------------------------
  const initialFromStorage = (() => {
    try {
      return localStorage.getItem(SESSION_KEY) ||
             localStorage.getItem(LEGACY_KEY) ||
             ''
    } catch { return '' }
  })()
  const sessionId = ref<string>(initialFromStorage)

  // --------------------------------------------------------------------------
  // 修复 4 核心：6 个 per-session 数据结构
  // --------------------------------------------------------------------------

  /** 每个会话独立的消息数组（切会话不会丢其他会话的数据） */
  const messagesBySession = ref<Record<string, ChatMessage[]>>({})

  /** 当前会话的消息（computed 给 UI 层用） */
  const messages = computed(() => messagesBySession.value[sessionId.value] || [])

  /** 每个会话"正在生成的 assistantMsg 引用"（SSE yield 时通过 targetSessionId 找正确对象） */
  const activeAssistantMap = ref<Record<string, ChatMessage>>({})

  /** per-session abort controller（多次点击同一会话时 abort 旧流） */
  const abortControllers: Record<string, AbortController> = {}

  /** per-session 发送锁（防止同一会话快速点击叠加） */
  const sendingSessions = new Set<string>()

  /** 已加载过 localStorage 的 session 集合（防重复覆盖后台 SSE 增量） */
  const loadedSessions = new Set<string>()

  /** debounce 持久化 timer（per-session 100ms） */
  const persistTimers: Record<string, ReturnType<typeof setTimeout>> = {}

  // --------------------------------------------------------------------------
  // UI 状态
  // --------------------------------------------------------------------------

  /** 当前会话是否正在生成（UI 用：消息区"三个点"动画） */
  const isCurrentSessionSending = computed(() => sendingSessions.has(sessionId.value))

  // --------------------------------------------------------------------------
  // 会话 store 集成
  // ★ 2026-07-01 修复 bug 1a: 移除自动 createSession()
  // 旧实现: if (!currentSession()) createSession()  → 每次 mount 都 mint 新 id
  // 新实现: 解析现有候选（store 已加载的 currentId / 第一个 local session），
  // 都不存在 → sessionId 留空，UI 显示空状态 + "新对话" 按钮。
  // 服务端同步后的真实初始 sessionId 在 onMounted 阶段用 pickInitialSessionId 选。
  // --------------------------------------------------------------------------
  const sessionsStore = useChatSessionsStore()
  const chatHistoryStore = useChatHistoryStore()  // #043 服务端持久化
  const ui = useUiStore()  // 2026-06-30 #009 Self-RAG: 读 useDeepThinking toggle
  sessionsStore.migrateFromV1()

  function resolveInitialSessionId(): string {
    // 1) store 已有 currentSession → 优先用
    if (sessionsStore.currentSession()) return sessionsStore.currentId as string
    // 2) store 有 sessions 但 currentId 没匹配 → 选第一个
    const first = sessionsStore.sessions[0]
    if (first) {
      sessionsStore.switchSession(first.id)
      return first.id
    }
    // 3) store 空(首次加载) → fallback 到 localStorage 初始值
    // 这是关键: 单测 mock localStorage 但不通过 store 时,需要 fallback
    if (initialFromStorage) {
      sessionsStore.switchSession(initialFromStorage)
      return initialFromStorage
    }
    return ''  // 真的空:UI 显示空状态 + "新对话" 按钮
  }

  const initialId = resolveInitialSessionId()
  if (initialId) {
    sessionId.value = initialId
  } else {
    sessionId.value = ''  // 显式空字符串（避免 undefined 走兜底 mint）
  }

  // --------------------------------------------------------------------------
  // 持久化工具
  // --------------------------------------------------------------------------

  /**
   * 同步写入（不 debounce）— 切会话/卸载/发送完成时调用
   * @param opts.updateActivity=false 跳过 updateActivity(2026-07-01 修复:
   *   切会话/卸载只持久化消息数据,不应触发会话"上浮"副作用)
   */
  function persistSessionSync(id: string, opts: { updateActivity?: boolean } = {}) {
    const msgs = messagesBySession.value[id] || []
    const slice = msgs.slice(-MESSAGES_SLICE_KEEP)
    try {
      localStorage.setItem(`${MESSAGES_KEY_PREFIX}${id}`, JSON.stringify(slice))
    } catch (e) {
      console.warn('[useChatStream] persist failed', e)
    }
    if (id === sessionId.value) {
      try {
        localStorage.setItem(LEGACY_MESSAGES_KEY, JSON.stringify(slice))
      } catch { /* ignore */ }
    }
    // 2026-07-01 修复:只有真实对话活动(发消息)才更新 session activity
    // 切会话/卸载不触发上浮(用户澄清:点击≠对话)
    if (opts.updateActivity !== false && sessionsStore.currentSession()) {
      const lastMsg = msgs[msgs.length - 1]
      sessionsStore.updateActivity(id, msgs.length, lastMsg?.content || '')
    }
  }

  /** debounce 持久化 — SSE 流式 yield 时调用，避免 localStorage 写入风暴 */
  function persistSessionDebounced(id: string) {
    if (persistTimers[id]) clearTimeout(persistTimers[id])
    persistTimers[id] = setTimeout(() => {
      persistSessionSync(id)
    }, PERSIST_DEBOUNCE_MS)
  }

  // --------------------------------------------------------------------------
  // 会话加载（修复 4：loadedSessions 防重复覆盖后台 SSE 增量）
  // --------------------------------------------------------------------------
  function ensureSessionLoaded(id: string) {
    if (loadedSessions.has(id)) return
    loadedSessions.add(id)
    const saved = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${id}`)
    if (saved) {
      try {
        messagesBySession.value[id] = JSON.parse(saved)
      } catch {
        messagesBySession.value[id] = []
      }
    } else {
      messagesBySession.value[id] = []
    }
  }

  // --------------------------------------------------------------------------
  // 会话操作
  // --------------------------------------------------------------------------

  function onCreateSession() {
    persistSessionSync(sessionId.value, { updateActivity: false })  // 2026-07-01:新会话 createSession 自己设 updatedAt=now
    sessionsStore.createSession()
    const newId = sessionsStore.currentId || sessionId.value
    sessionId.value = newId
    messagesBySession.value[newId] = [createAssistantGreeting('新对话，有什么可以帮你的吗？')]
    loadedSessions.add(newId)
    persistSessionSync(newId, { updateActivity: false })  // 2026-07-01:同上,避免重复 bump
  }

  function onSwitchSession(id: string) {
    if (id === sessionId.value) return
    // 2026-07-01:切会话 = 纯选中,不更新活动(用户澄清:点击≠对话)
    persistSessionSync(sessionId.value, { updateActivity: false }) // 切走前快照（含正在生成的流式部分）
    ensureSessionLoaded(id)
    sessionId.value = id
  }

  function clearChat() {
    messagesBySession.value[sessionId.value] = [
      createAssistantGreeting('对话已清空，有什么可以帮你的吗？'),
    ]
    loadedSessions.add(sessionId.value)
    persistSessionSync(sessionId.value)
  }

  function createAssistantGreeting(content: string): ChatMessage {
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      content,
      richBlocks: [],
      timestamp: new Date().toISOString(),
    }
  }

  // --------------------------------------------------------------------------
  // 发送（SSE 流式）— 修复 4：per-session 闭包，targetSessionId 贯穿
  // --------------------------------------------------------------------------

  async function sendMessage(opts: SendOptions = {}) {
    const content = (opts.text ?? '').trim()
    const file = opts.file ?? null
    const img = opts.image ?? null
    if (!content && !img && !file) return
    if (sendingSessions.has(sessionId.value)) return

    // ★ 2026-07-01 修复 bug 1a: 无 session 时(用户首次发消息) → 创建一个
    // 这是用户主动发消息的入口,符合"除非用户自己创建,不然不创建"的产品决策
    if (!sessionId.value) {
      sessionsStore.createSession()
      const newId = sessionsStore.currentId
      if (!newId) return
      sessionId.value = newId
      messagesBySession.value[newId] = []
      loadedSessions.add(newId)
    }

    // ★ 关键：捕获目标 sessionId 到闭包（防止 SSE yield 时用户已切走）
    const targetSessionId = sessionId.value
    const targetMsgs =
      messagesBySession.value[targetSessionId] ||
      (messagesBySession.value[targetSessionId] = [])

    // 用户消息
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      richBlocks: [],
      timestamp: new Date().toISOString(),
      type: img ? 'image' : file ? 'file' : 'text',
      // #043: 客户端幂等键（用于重试不重复写 server）
      client_msg_id: `chat_user_${targetSessionId}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    }
    targetMsgs.push(userMsg)

    // #043: user 消息 fire-and-forget 持久化到 server
    // CLAUDE.md 2026-06-12 "持久化失败必须 best-effort" 铁律 — appendMessageAsync 内部已 try/except
    chatHistoryStore.appendMessageAsync(targetSessionId, {
      role: 'user',
      content,
      rich_blocks: [],
      tool_trace: {},
      message_metadata: { source: 'chat_stream_user' },
      client_msg_id: userMsg.client_msg_id,
    }).then((persisted) => {
      if (persisted?.id) userMsg.server_id = persisted.id
    })

    // Assistant 占位
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      richBlocks: [],
      toolTrace: [],
      timestamp: new Date().toISOString(),
      state: 'streaming',
      is_brief: true,
      error: null,
    }
    targetMsgs.push(assistantMsg)
    // ★ 关键：把 assistantMsg 引用存到 activeAssistantMap[targetSessionId]
    activeAssistantMap.value[targetSessionId] = assistantMsg

    // per-session abort controller
    abortControllers[targetSessionId]?.abort()
    const controller = new AbortController()
    abortControllers[targetSessionId] = controller
    sendingSessions.add(targetSessionId)

    try {
      if (file || img) {
        await sendNonStream(content, file, img, assistantMsg, targetSessionId)
      } else {
        await sendSSE(content, assistantMsg, targetSessionId, controller.signal)
      }
      persistSessionDebounced(targetSessionId)
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        // 静默，不弹错（abort 触发不算错）
      } else {
        console.error('[useChatStream] send error', e)
        const targetAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
        targetAssistant.error = e.message || '发送失败'
        targetAssistant.content =
          targetAssistant.content || '抱歉，我暂时无法回复，请稍后再试。'
        ElMessage.error(e.message || '发送失败')
      }
    } finally {
      sendingSessions.delete(targetSessionId)
      const finalAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
      finalAssistant.state = 'idle'
      finalAssistant.is_brief = false
      if (activeAssistantMap.value[targetSessionId] === assistantMsg) {
        delete activeAssistantMap.value[targetSessionId]
      }
      persistSessionSync(targetSessionId)
    }
  }

  // --------------------------------------------------------------------------
  // SSE 流式发送 — 修复 4：通过 activeAssistantMap[targetSessionId] 找引用
  // --------------------------------------------------------------------------
  async function sendSSE(
    content: string,
    assistantMsg: ChatMessage,
    targetSessionId: string,
    signal?: AbortSignal
  ) {
    // v31 埋点: Agent 调用 search_knowledge 时暂存 query, tool_result 时连同 top_ids 一起 POST
    let pendingAgentSearchQuery: string | null = null
    // targetSessionId 是 sendMessage 启动时捕获的闭包变量
    // 2026-06-30 #009: 读 useUiStore.useDeepThinking + useThemeStore.accent 塞 fetch body
    const useDeepThinking = ui.useDeepThinking
    for await (const evt of sseFetch(
      '/api/v1/chat/stream',
      {
        message: content,
        session_id: targetSessionId,
        use_self_rag: useDeepThinking,  // null = 不传（后端用 settings 全局）
        // model: '', // 留空走 settings.AGENT_SYNTHESIS_MODEL（生产可让深度模式 = Sonnet）
      },
      { signal }
    )) {
      const currentAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg

      // 2026-06-14 方案 C Stage 4：abort 状态机守卫
      // 用户点 ⏹ → stopGeneration 把 state 改为 'aborted'
      // 后端可能还在 yield 几个事件（race condition），忽略全部避免显示错乱
      if (currentAssistant.state === 'aborted') {
        // 跳过 switch case，但 loop 仍走 persistSessionDebounced（让中断状态持久化）
        persistSessionDebounced(targetSessionId)
        continue
      }

      switch (evt.type) {
        case 'text_delta':
          // [increment] 累加 delta 到 content
          // 防 brief 重复 bug（2026-06-12 commit cf70ff5 根因）：
          //   检测单次 delta > 100 字且不包含已有内容前 50 字 → 长度异常
          if (evt.delta && evt.delta.length > 100) {
            const prevPrefix = (currentAssistant.content || '').slice(0, 50)
            if (prevPrefix && !evt.delta.includes(prevPrefix)) {
              console.warn(
                `[useChatStream] text_delta 长度异常：${evt.delta.length} 字，不含已有内容前缀`,
              )
            }
          }
          currentAssistant.content = (currentAssistant.content || '') + (evt.delta || '')
          break
        case 'brief':
          // [snapshot, deprecated] v1 客户端兼容，v2+ 忽略
          if (!currentAssistant.content && evt.delta) {
            currentAssistant.content = evt.delta
          }
          break
        case 'detail': {
          // [snapshot, deprecated] v1 客户端兼容
          const delta = evt.delta || ''
          if (delta) {
            currentAssistant.content =
              (currentAssistant.content || '') +
              (currentAssistant.content ? '\n\n' : '') +
              delta
          }
          break
        }
        case 'thinking':
          // [snapshot] 提示
          currentAssistant.toolTrace!.push({ type: 'thinking', label: evt.label })
          break
        case 'tool_use':
          // [snapshot] 工具调用开始
          currentAssistant.toolTrace!.push({
            type: 'tool',
            name: evt.tool_name,
            state: 'running',
          })
          // v31 埋点: 暂存 query, 等待 tool_result 一起 POST
          if (evt.tool_name === 'search_knowledge' && evt.tool_input) {
            pendingAgentSearchQuery =
              (evt.tool_input.query as string) ||
              (evt.tool_input as Record<string, unknown>).q as string ||
              ''
          }
          break
        case 'tool_result': {
          // [snapshot] 工具调用结果
          const last = currentAssistant.toolTrace![currentAssistant.toolTrace!.length - 1]
          if (last && last.type === 'tool' && last.name === evt.tool_name) {
            last.state = 'done'
            last.duration_ms = evt.tool_duration_ms
          }
          // 2026-06-30 #009: Self-RAG 重检索 tool_result → 关闭 reretrieving 动画
          if (evt.tool_use_id?.startsWith('reretrieve_') && currentAssistant.reretrieving) {
            currentAssistant.reretrieving = false
          }
          // v31 埋点: 收到 search_knowledge 结果, POST 到 analytics (含 top_ids)
          if (
            evt.tool_name === 'search_knowledge' &&
            pendingAgentSearchQuery &&
            evt.tool_output &&
            Array.isArray((evt.tool_output as Record<string, unknown>).results)
          ) {
            const results = (evt.tool_output as { results: Array<{ id: number }> }).results
            const topIds = results.map((r) => r.id).filter((id): id is number => typeof id === 'number').slice(0, 20)
            if (topIds.length > 0) {
              // 动态 import 避免循环依赖
              import('@/api/analytics')
                .then(({ recordSearchEvent }) => {
                  recordSearchEvent({
                    query: pendingAgentSearchQuery as string,
                    top_ids: topIds,
                    source: 'agent_chat',
                    session_id: localStorage.getItem('mnb:search_analytics:session_id') || undefined,
                  }).catch(() => { /* 埋点失败静默 */ })
                })
                .catch(() => { /* import 失败静默 */ })
            }
            pendingAgentSearchQuery = null
          }
          break
        }
        case 'tool_compressed': {
          // [snapshot] 工具结果被 Haiku 压缩（2026-06-14 Stage 4）
          // 附加到最近一个同名的 tool 项上
          const lastTool = [...currentAssistant.toolTrace!]
            .reverse()
            .find((t) => t.type === 'tool' && t.name === evt.tool_name)
          if (lastTool) {
            lastTool.compression = evt.compression
          }
          // 同时 push 一个 thinking 块展示压缩信息
          currentAssistant.toolTrace!.push({
            type: 'thinking',
            label: evt.label || `🗜️ 压缩：${evt.compression?.summary || ''}`,
          })
          break
        }
        case 'rich_block':
          // [snapshot] 富文本块
          if (evt.block) currentAssistant.richBlocks.push(evt.block)
          break
        case 'intent_detected': {
          // [snapshot] 意图分类（2026-06-14 Stage 4）
          currentAssistant.intent = evt.intent || {
            category: evt.label || 'unknown',
            confidence: 0,
          }
          // 在 toolTrace 顶部展示意图
          currentAssistant.toolTrace!.push({
            type: 'thinking',
            label: evt.label || `🧠 意图：${evt.intent?.category || 'unknown'}`,
          })
          break
        }
        case 'plan_step': {
          // [snapshot] 工具规划单步（2026-06-14 Stage 4）
          if (!currentAssistant.plan) currentAssistant.plan = []
          currentAssistant.plan.push({
            step: evt.step || evt.label || '',
            tool: evt.tool_name,
            status: evt.plan_status || 'pending',
          })
          break
        }
        case 'synthesis_start': {
          // [snapshot] 综合阶段开始（2026-06-14 Stage 4）
          currentAssistant.toolTrace!.push({
            type: 'thinking',
            label: evt.label || '✨ 综合分析中...',
          })
          break
        }
        case 'critique': {
          // [snapshot] 自评（2026-06-14 Stage 4）
          currentAssistant.critique = evt.critique || {
            score: 0,
            suggestion: evt.label,
          }
          // 低分加 ⚠️ 徽章
          if (evt.critique && evt.critique.score < 7) {
            currentAssistant.toolTrace!.push({
              type: 'thinking',
              label: `⚠️ 自评 ${evt.critique.score}/10 — ${evt.critique.suggestion || ''}`,
            })
          } else if (evt.critique) {
            currentAssistant.toolTrace!.push({
              type: 'thinking',
              label: `📊 自评 ${evt.critique.score}/10`,
            })
          }
          break
        }
        case 'retrieval_assessment': {
          // 2026-06-30 #009 Self-RAG: judge 评估结果
          currentAssistant.retrievalAssessment = evt.retrieval || null
          // 渲染徽章 (reretrieved 状态在 UI 显示 🔍 重新检索)
          if (evt.retrieval?.reretrieved) {
            currentAssistant.toolTrace!.push({
              type: 'thinking',
              label: `🔍 Self-RAG 重新检索 (attempt #${evt.retrieval.attempt ?? 0}, confidence=${(evt.retrieval.confidence ?? 0).toFixed(2)})`,
            })
          } else if (evt.retrieval && !evt.retrieval.can_answer && (evt.retrieval.confidence ?? 1) < 0.6) {
            currentAssistant.toolTrace!.push({
              type: 'thinking',
              label: `⚠️ 知识库信息有限 (confidence=${(evt.retrieval.confidence ?? 0).toFixed(2)}, 缺: ${evt.retrieval.missing?.slice(0, 40) || '—'})`,
            })
          }
          break
        }
        case 'reretrieval': {
          // 2026-06-30 #009 Self-RAG: 正在重新检索动画
          currentAssistant.reretrieving = true
          currentAssistant.toolTrace!.push({
            type: 'thinking',
            label: `🔍 正在重新检索: "${evt.retrieval?.refined_query?.slice(0, 50) || '...'}"`,
          })
          // 配套 tool_result 后会自动关闭
          break
        }
        case 'retry': {
          // [snapshot] critique 低分触发重试（2026-06-14 Stage 4）
          // 关键：必须先清空 content，否则 retry 的 text_delta 拼接到旧内容后面
          currentAssistant.retryCount = (currentAssistant.retryCount || 0) + 1
          currentAssistant.content = ''
          currentAssistant.toolTrace!.push({
            type: 'thinking',
            label: `🔄 重试中（第 ${currentAssistant.retryCount} 次）：${evt.retry_reason || ''}`,
          })
          break
        }
        case 'error':
          // [snapshot] 错误
          currentAssistant.error = evt.message
          // abort 状态：error 事件也代表流结束
          if (currentAssistant.state === 'streaming') {
            currentAssistant.state = 'idle'
          }
          break
        case 'done':
          // [snapshot] 流结束
          currentAssistant.usage = evt.usage
          currentAssistant.durationMs = evt.duration_ms
          // 2026-06-15 修复元话语/thinking 文本泄露：done 时用后端剥除过的干净文本替换 content
          // 流式过程 text_delta 累加的 content 包含 LLM 写的"我需要..."等元话语
          // 后端 text_without_json 已剥除（JSON 段 + fake tool_call + 元话语）
          // 差异时替换（保留流式观感 + 最终干净）
          if (evt.text_without_json != null && evt.text_without_json !== currentAssistant.content) {
            currentAssistant.content = evt.text_without_json
          }
          // #043: 标记 assistant 已完成（server_id 会在 message_persisted 事件里设置）
          currentAssistant.state = 'idle'
          break

        // ===== #043 新增事件处理 =====
        case 'message_persisted': {
          // [snapshot] 后端已落库某条消息（user 流开始时 + assistant 流结束时 各 yield 一次）
          // CLAUDE.md 2026-06-29 #043 Phase 3 铁律 2："assistant 落库必须在 done 事件 yield 之后立即"
          // — 即后端 done 后才会 yield 这个事件，前端收到时 server 已持久化
          const role = evt.persisted_role
          if (role === 'assistant' && currentAssistant) {
            currentAssistant.server_id = evt.message_id
            currentAssistant.client_msg_id = evt.persisted_client_msg_id || currentAssistant.client_msg_id
            currentAssistant.is_partial = evt.persisted_is_partial ?? false
          }
          if (role === 'user' && evt.persisted_client_msg_id) {
            // 找到对应 userMsg，更新 server_id（幂等键命中所以 server 返回的 id 一致）
            const matched = messagesBySession.value[targetSessionId]
              ?.find(m => m.role === 'user' && m.client_msg_id === evt.persisted_client_msg_id)
            if (matched) matched.server_id = evt.message_id
          }
          // SSE 收到 message_persisted 不 debounce localStorage（数据已稳定在 server）
          break
        }

        case 'sync_required': {
          // [snapshot] 流式中断 / 异常，前端需重新拉历史（CLAUDE.md 2026-06-29 #043 Phase 3 已知限制兜底）
          // evt.sync_reason = 'aborted' | 'error'
          console.warn(`[useChatStream] sync_required: reason=${evt.sync_reason}`)
          // 异步 reload 当前会话消息（不阻塞 UI，让后台 SSE 走完 cleanup）
          chatHistoryStore.refreshSession(targetSessionId).then((msgs) => {
            if (msgs && Array.isArray(msgs)) {
              // 替换当前会话的 messages（server 数据为准，避免本地状态错乱）
              messagesBySession.value[targetSessionId] = msgs.map(serverToClient)
              persistSessionSync(targetSessionId)
            }
          })
          break
        }
      }
      // 流式增量持久化（防后台丢数据；debounce 100ms）
      persistSessionDebounced(targetSessionId)
    }
  }

  // --------------------------------------------------------------------------
  // --------------------------------------------------------------------------
  // 停止生成（2026-06-14 方案 C Stage 4）
  // --------------------------------------------------------------------------
  function stopGeneration(targetSessionId?: string) {
    const sid = targetSessionId || sessionId.value
    const ctrl = abortControllers[sid]
    if (ctrl) {
      ctrl.abort()
      // 标记 assistant state='aborted'（UI 显示「⏹ 已中断」）
      const assistant = activeAssistantMap.value[sid]
      if (assistant && assistant.state === 'streaming') {
        assistant.state = 'aborted'
        assistant.is_partial = true  // #043: 流式中断标记
        // 后续 SSE 事件被忽略（state !== 'streaming'，switch case 不再处理）
        // 立即关闭 loading
        sendingSessions.delete(sid)
      }
      // 立即持久化（用户可能直接关页面）
      persistSessionSync(sid)
      // #043: 通知 server 标记 partial（best-effort，不阻塞 stop UI）
      // 即使 server 没收到，前端 state='aborted' + is_partial=true 已足够本地持久化
      if (assistant?.content !== undefined) {
        const partialContent = assistant.content || ''
        chatHistoryStore.appendMessageAsync(sid, {
          role: 'assistant',
          content: partialContent,
          rich_blocks: assistant.richBlocks || [],
          tool_trace: assistant.toolTrace || [],
          message_metadata: { source: 'stream_partial_aborted' },
          client_msg_id: `stream_${sid}_assistant_partial_${Date.now()}`,
          is_partial: true,
        }).then((persisted) => {
          if (persisted?.id) assistant.server_id = persisted.id
        })
      }
    }
  }

  // --------------------------------------------------------------------------
  // 非流式发送（图片/文件）— 同样闭包 targetSessionId
  // --------------------------------------------------------------------------
  async function sendNonStream(
    text: string,
    file: File | null,
    img: File | null,
    assistantMsg: ChatMessage,
    targetSessionId: string
  ) {
    let res
    if (file) {
      const fd = new FormData()
      fd.append('message', text || '')
      fd.append('session_id', targetSessionId)
      fd.append('file', file)
      res = await axios.post('/api/v1/chat/file', fd)
    } else if (img) {
      const fd = new FormData()
      fd.append('message', text || '请描述这张图片')
      fd.append('session_id', targetSessionId)
      fd.append('image', img)
      res = await axios.post('/api/v1/chat/image', fd)
    } else {
      res = await axios.post('/api/v1/chat', {
        message: text,
        session_id: targetSessionId,
      })
    }
    const targetAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
    targetAssistant.content = res.data.content || ''
    if (Array.isArray(res.data.rich_blocks)) {
      targetAssistant.richBlocks = res.data.rich_blocks
    }
  }

  // --------------------------------------------------------------------------
  // TTS 播放（提取自原 ChatViewSSE.vue）
  // --------------------------------------------------------------------------
  let playingAudio: HTMLAudioElement | null = null

  async function playTTS(text: string) {
    if (!text) return
    if (playingAudio) {
      playingAudio.pause()
      playingAudio = null
    }
    try {
      const r = await axios.post(
        '/api/v1/voice/tts',
        { text, voice: 'zh_female' },
        { responseType: 'blob' }
      )
      const url = URL.createObjectURL(r.data)
      const audio = new Audio(url)
      playingAudio = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        playingAudio = null
      }
      audio.play()
    } catch (e: any) {
      ElMessage.error('TTS 播放失败：' + (e.response?.data?.detail || e.message))
    }
  }

  // --------------------------------------------------------------------------
  // ASR 语音转文字（提取自原 onRecordStop）
  // --------------------------------------------------------------------------
  async function asrRecognize(blob: Blob): Promise<string | null> {
    if (!blob || blob.size === 0) {
      ElMessage.warning('录音为空，请重试')
      return null
    }
    // 2026-06-18 修复：录音 < 1KB 通常是 MediaRecorder 录了几毫秒（被 swipe cancel
    // 或按住时间太短），webm header 损坏，whisper 容器 ffmpeg 转 110 字节 webm 必失败
    // 拦截在客户端避免无效请求打到后端
    const MIN_AUDIO_SIZE = 1024  // 1KB
    if (blob.size < MIN_AUDIO_SIZE) {
      ElMessage.warning('录音太短（不到 1 秒），请长按说话')
      return null
    }
    try {
      const fd = new FormData()
      fd.append('audio', blob, 'voice.webm')
      const r = await axios.post('/api/v1/voice/asr', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: { language: 'zh' },
      })
      const text = r.data?.text?.trim()
      if (text) return text
      ElMessage.warning('未能识别语音，请重试')
      return null
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || 'ASR 识别失败')
      return null
    }
  }

  // --------------------------------------------------------------------------
  // 生命周期
  // --------------------------------------------------------------------------

  // #043: Server → Client 消息映射（sync_required refreshSession 用）
  function serverToClient(serverMsg: any): ChatMessage {
    return {
      id: `server_${serverMsg.id}`,
      role: serverMsg.role === 'assistant' ? 'assistant' : serverMsg.role === 'user' ? 'user' : 'assistant',
      content: serverMsg.content || '',
      richBlocks: serverMsg.rich_blocks || [],
      toolTrace: serverMsg.tool_trace || [],
      timestamp: serverMsg.created_at || new Date().toISOString(),
      server_id: serverMsg.id,
      client_msg_id: serverMsg.client_msg_id,
      is_partial: !!serverMsg.is_partial,
      state: 'idle',
    }
  }

  onMounted(async () => {
    ensureSessionLoaded(sessionId.value)
    if ((messagesBySession.value[sessionId.value] || []).length === 0) {
      messagesBySession.value[sessionId.value] = [
        createAssistantGreeting('你好！我是"小气"，课题组智能助手。有什么可以帮你的吗？'),
      ]
    }

    // #043: 服务端数据补充（background sync，不阻塞 UI）
    // 只有登录后才有 token，否则跳过（Phase 5 迁移会等登录态再跑）
    const hasToken = !!localStorage.getItem('access_token')
    if (hasToken && chatHistoryStore.syncStatus === 'idle') {
      try {
        await chatHistoryStore.loadFromServer()
        // 把 server 会话列表同步到侧栏 store（保持 UI 一致）
        sessionsStore.mergeServerList(chatHistoryStore.serverSessions)
        // ★ 2026-07-01 修复 bug 1b: 同步完成后用纯函数重选 sessionId
        // 用户决策: 服务端有会话时自动恢复最近(ChatGPT/豆包模式)
        const picked = sessionsStore.pickInitialSessionId({
          serverSessions: chatHistoryStore.serverSessions,
          localCurrentId: sessionsStore.currentId,
          localSessionIds: sessionsStore.sessions.map(s => s.id),
        })
        if (picked && picked !== sessionsStore.currentId) {
          sessionsStore.switchSession(picked)
        }
        if (picked) {
          sessionId.value = picked
          ensureSessionLoaded(picked)
        } else {
          // 都没找到(首次登录 or 服务端 0 会话)→ 留空
          sessionId.value = ''
        }
      } catch (e: any) {
        // 服务端加载失败 → 保留 localStorage 兜底，不阻塞 UI
        console.warn('[useChatStream] 服务端加载失败，保留 localStorage:', e?.message)
      }
    }

    // #043: Phase 5 旧数据自动迁移（登录后 1 秒异步跑）
    if (hasToken) {
      setTimeout(async () => {
        try {
          const { useChatMigration } = await import('@/composables/chat/useChatMigration')
          const result = await useChatMigration().migrateLocalToServer()
          if (result?.migrated && result.migrated > 0) {
            console.info(`[useChatStream] 旧数据已迁移: ${result.migrated} 条`)
          }
        } catch (e: any) {
          console.warn('[useChatStream] 旧数据迁移失败:', e?.message)
        }
      }, 1000)
    }
  })

  onUnmounted(() => {
    // abort 所有正在跑的 SSE 流
    for (const ctrl of Object.values(abortControllers)) {
      try {
        ctrl.abort()
      } catch { /* ignore */ }
    }
    // 持久化所有 session（含后台流式生成的内容）
    // 2026-07-01:关闭页面不更新活动(避免所有 session updatedAt 重置为"刚刚"→ 顺序丢失)
    for (const id of Object.keys(messagesBySession.value)) {
      persistSessionSync(id, { updateActivity: false })
    }
  })

  // --------------------------------------------------------------------------
  // 返回 API（UI 层用）
  // --------------------------------------------------------------------------
  return {
    // 状态
    sessionId,
    messages,
    messagesBySession,
    activeAssistantMap,
    isCurrentSessionSending,

    // 会话操作
    onCreateSession,
    onSwitchSession,
    clearChat,
    ensureSessionLoaded,

    // 发送
    sendMessage,
    // 2026-06-14 方案 C Stage 4：停止生成按钮
    stopGeneration,

    // 辅助
    playTTS,
    asrRecognize,

    // 持久化（暴露给 UI 层用，如清空/重命名场景）
    persistSessionSync,
    persistSessionDebounced,
  }
}

export default useChatStream
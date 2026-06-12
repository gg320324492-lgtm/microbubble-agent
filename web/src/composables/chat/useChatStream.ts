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
  }>
  timestamp: string
  state?: 'streaming' | 'idle'
  is_brief?: boolean
  error?: string | null
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
  durationMs?: number
  type?: 'text' | 'image' | 'file'
  imageUrl?: string
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
  // --------------------------------------------------------------------------
  const sessionId = ref<string>(
    localStorage.getItem(SESSION_KEY) ||
    localStorage.getItem(LEGACY_KEY) ||
    `user_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
  )

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
  // --------------------------------------------------------------------------
  const sessionsStore = useChatSessionsStore()
  sessionsStore.migrateFromV1()
  if (!sessionsStore.currentSession()) {
    sessionsStore.createSession()
  }
  if (sessionsStore.currentId) {
    sessionId.value = sessionsStore.currentId
  }

  // --------------------------------------------------------------------------
  // 持久化工具
  // --------------------------------------------------------------------------

  /** 同步写入（不 debounce）— 切会话/卸载/发送完成时调用 */
  function persistSessionSync(id: string) {
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
    if (sessionsStore.currentSession()) {
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
    persistSessionSync(sessionId.value)
    sessionsStore.createSession()
    const newId = sessionsStore.currentId || sessionId.value
    sessionId.value = newId
    messagesBySession.value[newId] = [createAssistantGreeting('新对话，有什么可以帮你的吗？')]
    loadedSessions.add(newId)
    persistSessionSync(newId)
  }

  function onSwitchSession(id: string) {
    if (id === sessionId.value) return
    persistSessionSync(sessionId.value) // 切走前快照（含正在生成的流式部分）
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
    }
    targetMsgs.push(userMsg)

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
    // targetSessionId 是 sendMessage 启动时捕获的闭包变量
    for await (const evt of sseFetch(
      '/api/v1/chat/stream',
      { message: content, session_id: targetSessionId },
      { signal }
    )) {
      const currentAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg

      switch (evt.type) {
        case 'text_delta':
          currentAssistant.content = (currentAssistant.content || '') + (evt.delta || '')
          break
        case 'brief':
          if (!currentAssistant.content && evt.delta) {
            currentAssistant.content = evt.delta
          }
          break
        case 'detail': {
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
          currentAssistant.toolTrace!.push({ type: 'thinking', label: evt.label })
          break
        case 'tool_use':
          currentAssistant.toolTrace!.push({
            type: 'tool',
            name: evt.tool_name,
            state: 'running',
          })
          break
        case 'tool_result': {
          const last = currentAssistant.toolTrace![currentAssistant.toolTrace!.length - 1]
          if (last && last.type === 'tool' && last.name === evt.tool_name) {
            last.state = 'done'
            last.duration_ms = evt.tool_duration_ms
          }
          break
        }
        case 'rich_block':
          if (evt.block) currentAssistant.richBlocks.push(evt.block)
          break
        case 'error':
          currentAssistant.error = evt.message
          break
        case 'done':
          currentAssistant.usage = evt.usage
          currentAssistant.durationMs = evt.duration_ms
          break
      }
      // 流式增量持久化（防后台丢数据；debounce 100ms）
      persistSessionDebounced(targetSessionId)
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
  onMounted(() => {
    ensureSessionLoaded(sessionId.value)
    if ((messagesBySession.value[sessionId.value] || []).length === 0) {
      messagesBySession.value[sessionId.value] = [
        createAssistantGreeting('你好！我是"小气"，课题组智能助手。有什么可以帮你的吗？'),
      ]
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
    for (const id of Object.keys(messagesBySession.value)) {
      persistSessionSync(id)
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

    // 辅助
    playTTS,
    asrRecognize,

    // 持久化（暴露给 UI 层用，如清空/重命名场景）
    persistSessionSync,
    persistSessionDebounced,
  }
}

export default useChatStream
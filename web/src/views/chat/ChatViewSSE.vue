<script setup lang="ts">
/**
 * ChatViewSSE.vue — v2 极简版（接 SSE 流式 + Rich Block 渲染）
 *
 * 修复 4：多会话并行架构
 * - 每个 sessionId 独立 messages 数组（messagesBySession）
 * - 切会话不 abort SSE，让 A 在后台继续生成
 * - SSE yield 通过 activeAssistantMap[sessionId] 找到目标 assistantMsg 引用
 * - 流式增量 debounce 100ms 持久化到 localStorage（防后台丢）
 *
 * 替换原 564 行 ChatView.vue 90% 体积，专注核心：
 * - 真实 SSE 流式（/api/v1/chat/stream）替换 setInterval 轮询
 * - assistant 消息支持 rich_blocks 渲染
 * - 工具调用中间态展示（"🔍 正在 X..."）
 * - 保留必要的图片/文件上传、欢迎页、快捷指令
 *
 * 复用：
 * - 工具标签 TOOL_LABELS（web/src/api/agent/toolLabels.ts）
 * - Rich Block 注册表（web/src/components/chat/blocks/registry.ts）
 * - Pinia store（如有，chat.ts）
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound } from '@element-plus/icons-vue'
import axios from 'axios'
import RichContent from '@/components/chat/RichContent.vue'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import { sseFetch } from '@/api/agent/sse'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { renderMarkdown } from '@/utils/markdown'

// ============================================================================
// 状态：当前 UI 显示的会话
// ============================================================================
const sessionId = ref(localStorage.getItem('chat_current_session_v3') || localStorage.getItem('chat_session_id') || `user_${Date.now()}`)
const sessionKey = 'chat_current_session_v3'
const messagesKey = 'chat_messages_v2'  // 旧单会话兼容键（仅写不读）

// ============================================================================
// 状态：per-session 数据（修复 4 核心：多会话并行）
// ============================================================================
// 每个会话独立的消息数组，切会话不会丢其他会话的数据
const messagesBySession = ref<Record<string, any[]>>({})
// 模板用 computed 从 messagesBySession 读当前 sessionId 的消息
const messages = computed(() => messagesBySession.value[sessionId.value] || [])

// 每个会话"正在生成的 assistantMsg 引用"
// SSE 流启动时把引用存入，SSE yield 时通过 targetSessionId 找到正确对象
// 关键：用户切走 A → A 后台 SSE 继续 yield → 找到 activeAssistantMap[A] 追加内容
const activeAssistantMap = ref<Record<string, any>>({})

// per-session abort controller（多次点击同一会话时 abort 旧流）
// 不在切会话时 abort（让 A 后台继续跑）
const abortControllers: Record<string, AbortController> = {}

// per-session 发送锁（防止同一会话快速点击叠加）
const sendingSessions = new Set<string>()

// 已加载过 localStorage 的 session 集合（防重复覆盖后台 SSE 增量）
const loadedSessions = new Set<string>()

// debounce 持久化 timer（per-session 100ms）
const persistTimers: Record<string, ReturnType<typeof setTimeout>> = {}

// ============================================================================
// 其他 UI 状态
// ============================================================================
const inputText = ref('')
const loading = ref(false)  // 当前会话是否在生成（按 session 算的 UI 提示）
const isDragging = ref(false)
const textareaRef = ref(null)
const messagesRef = ref(null)
const selectedImage = ref(null)
const imagePreviewUrl = ref('')
const selectedFile = ref(null)
const voiceMode = ref(false)
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const sidebarCollapsed = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')

// 当前会话是否正在生成（UI 用：消息区"三个点"动画）
const isCurrentSessionSending = computed(() => sendingSessions.has(sessionId.value))

// --- 网络状态 ---
const { online: isOnline } = useNetworkStatus()

// --- 会话管理 store ---
const sessionsStore = useChatSessionsStore()
sessionsStore.migrateFromV1()
if (!sessionsStore.currentSession()) {
  sessionsStore.createSession()
}
sessionId.value = sessionsStore.currentId || sessionId.value

// --- Dark mode ---
const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}
if (isDark.value) {
  document.documentElement.setAttribute('data-theme', 'dark')
}

// ============================================================================
// 持久化工具（修复 4：debounce 100ms 防止后台丢）
// ============================================================================
const persistSessionSync = (id: string) => {
  // 同步写入（不 debounce）— 用于切会话/卸载等关键节点
  const msgs = messagesBySession.value[id] || []
  const slice = msgs.slice(-200)
  localStorage.setItem(`chat_msgs_${id}`, JSON.stringify(slice))
  if (id === sessionId.value) {
    localStorage.setItem(messagesKey, JSON.stringify(slice))  // 兼容旧键
  }
  // 更新 store
  if (sessionsStore.currentSession()) {
    const lastMsg = msgs[msgs.length - 1]
    sessionsStore.updateActivity(id, msgs.length, lastMsg?.content || '')
  }
}

const persistSessionDebounced = (id: string) => {
  // debounce 100ms — SSE 流式 yield 时调用，避免 localStorage 写入风暴
  if (persistTimers[id]) clearTimeout(persistTimers[id])
  persistTimers[id] = setTimeout(() => {
    persistSessionSync(id)
  }, 100)
}

// ============================================================================
// 会话加载（修复 4：loadedSessions 防重复覆盖后台 SSE 增量）
// ============================================================================
const ensureSessionLoaded = (id: string) => {
  if (loadedSessions.has(id)) return  // 已加载过（不重新读 localStorage，保留后台 SSE 增量）
  loadedSessions.add(id)
  const saved = localStorage.getItem(`chat_msgs_${id}`)
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

// ============================================================================
// 会话操作
// ============================================================================
const onCreateSession = () => {
  // 修复 1：先保存当前会话
  persistSessionSync(sessionId.value)
  // 创建新会话
  sessionsStore.createSession()
  const newId = sessionsStore.currentId
  // 关键：先在 store.currentId 更新前不要改 sessionId（避免中间态）
  sessionId.value = newId
  messagesBySession.value[newId] = [{
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '新对话，有什么可以帮你的吗？',
    richBlocks: [],
    timestamp: new Date().toISOString()
  }]
  loadedSessions.add(newId)
  persistSessionSync(newId)
  nextTick(scrollToBottom)
}

const onSwitchSession = (id: string) => {
  if (id === sessionId.value) return
  // 修复 1：先保存当前会话（切走前快照，含正在生成的流式部分）
  persistSessionSync(sessionId.value)
  // 修复 4：不 abort 任何 SSE，让 A 在后台继续生成
  // 切换目标
  ensureSessionLoaded(id)
  sessionId.value = id
  nextTick(scrollToBottom)
}

const clearChat = () => {
  // 清空当前会话（不动其他会话，不 abort 后台 SSE）
  // 注意：当前会话如果在生成中，新消息会 push 到这个空数组
  messagesBySession.value[sessionId.value] = [{
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '对话已清空，有什么可以帮你的吗？',
    richBlocks: [],
    timestamp: new Date().toISOString()
  }]
  // 不生成新 sessionId（用户期望是清空而非新开）
  // 但确保 loadedSessions 标记
  loadedSessions.add(sessionId.value)
  persistSessionSync(sessionId.value)
  // 兼容旧行为：保留 sessionId 不变
}

// ============================================================================
// 生命周期
// ============================================================================
onMounted(() => {
  // 加载当前会话历史
  ensureSessionLoaded(sessionId.value)
  // 首条消息时显示欢迎页
  if ((messagesBySession.value[sessionId.value] || []).length === 0) {
    messagesBySession.value[sessionId.value] = [{
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '你好！我是"小气"，课题组智能助手。有什么可以帮你的吗？',
      richBlocks: [],
      timestamp: new Date().toISOString()
    }]
  }
})

onUnmounted(() => {
  // abort 所有正在跑的 SSE 流
  for (const ctrl of Object.values(abortControllers)) {
    try { ctrl.abort() } catch {}
  }
  // 持久化所有 session（含后台流式生成的内容）
  for (const id of Object.keys(messagesBySession.value)) {
    persistSessionSync(id)
  }
})

// ============================================================================
// 滚动到底部（仅在当前正在显示的 session 滚动）
// ============================================================================
const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// ============================================================================
// 发送（SSE 流式）— 修复 4：per-session 闭包，targetSessionId 贯穿
// ============================================================================
const sendMessage = async (text?: string) => {
  const content = (text ?? inputText.value).trim()
  if ((!content && !selectedImage.value && !selectedFile.value)) return
  // 修复 4：按 session 锁，不阻止其他 session
  if (sendingSessions.has(sessionId.value)) return

  // ★ 关键：捕获目标 sessionId 到闭包（防止 SSE yield 时用户已切走）
  const targetSessionId = sessionId.value
  const targetMsgs = messagesBySession.value[targetSessionId] || (messagesBySession.value[targetSessionId] = [])

  // 用户消息
  const userMsg = {
    id: crypto.randomUUID(),
    role: 'user',
    content,
    richBlocks: [],
    timestamp: new Date().toISOString(),
    type: selectedImage.value ? 'image' : selectedFile.value ? 'file' : 'text'
  }
  targetMsgs.push(userMsg)
  inputText.value = ''
  const file = selectedFile.value
  const img = selectedImage.value
  selectedImage.value = null
  imagePreviewUrl.value = ''
  selectedFile.value = null
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  // Assistant 占位
  const assistantMsg = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    richBlocks: [],
    toolTrace: [],
    timestamp: new Date().toISOString(),
    state: 'streaming',
    is_brief: true,
    error: null
  }
  targetMsgs.push(assistantMsg)
  // ★ 关键：把 assistantMsg 引用存到 activeAssistantMap[SSE 所属 sessionId]
  // SSE yield 时通过这个 map 找引用（即使切到 B，A 的 SSE 仍能找到 A 的 assistantMsg）
  activeAssistantMap.value[targetSessionId] = assistantMsg

  // per-session abort controller（多次点击同会话时 abort 旧流）
  abortControllers[targetSessionId]?.abort()
  const controller = new AbortController()
  abortControllers[targetSessionId] = controller
  sendingSessions.add(targetSessionId)
  // 仅当本会话是当前显示会话时设 loading（其他 session 在后台不显示"三个点"）
  if (targetSessionId === sessionId.value) {
    loading.value = true
    await scrollToBottom()
  } else {
    // 切到 B 后从 B 触发 A 的 sendMessage 不会到这里（targetSessionId === sessionId.value）
    await scrollToBottom()
  }

  try {
    if (file || img) {
      await sendNonStream(content, file, img, assistantMsg, targetSessionId)
    } else {
      await sendSSE(content, assistantMsg, targetSessionId, controller.signal)
    }
    persistSessionDebounced(targetSessionId)
  } catch (e: any) {
    // 检查是否是 abort 触发的（用户切走导致）— 不显示错误
    if (e?.name === 'AbortError') {
      // 静默，不弹错
    } else {
      console.error('SSE error', e)
      ElMessage.error(e.message || '发送失败')
      // 把错误写到目标 session 的 assistantMsg
      const targetAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
      targetAssistant.error = e.message || '发送失败'
      targetAssistant.content = targetAssistant.content || '抱歉，我暂时无法回复，请稍后再试。'
    }
  } finally {
    sendingSessions.delete(targetSessionId)
    if (targetSessionId === sessionId.value) {
      loading.value = false
    }
    const finalAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
    finalAssistant.state = 'idle'
    finalAssistant.is_brief = false
    // SSE 完成后清理 activeAssistantMap
    if (activeAssistantMap.value[targetSessionId] === assistantMsg) {
      delete activeAssistantMap.value[targetSessionId]
    }
    if (targetSessionId === sessionId.value) {
      await scrollToBottom()
    }
    persistSessionSync(targetSessionId)
  }
}

// ============================================================================
// SSE 流式发送 — 修复 4：通过 activeAssistantMap[targetSessionId] 找引用
// ============================================================================
const sendSSE = async (
  content: string,
  assistantMsg: any,
  targetSessionId: string,
  signal?: AbortSignal
) => {
  // targetSessionId 是 sendMessage 启动时捕获的闭包变量
  // 即使后续 sessionId.value 切到其他 session，这里 targetSessionId 仍指向原 session
  for await (const evt of sseFetch('/api/v1/chat/stream', {
    message: content,
    session_id: targetSessionId  // ★ 关键：传 targetSessionId 而不是 sessionId.value
  }, { signal })) {
    // ★ 关键：通过 activeAssistantMap[targetSessionId] 找当前正在生成的引用
    // （如果用户切到 B 又切回 A，activeAssistantMap 里的引用不变；但更稳妥是每次都从 map 查）
    const currentAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
    const isCurrentView = targetSessionId === sessionId.value  // 仅当显示这个会话时才滚动

    if (evt.type === 'text_delta') {
      currentAssistant.content += evt.delta || ''
      if (isCurrentView) await scrollToBottom()
    } else if (evt.type === 'brief') {
      if (!currentAssistant.content && evt.delta) {
        currentAssistant.content = evt.delta
      }
      if (isCurrentView) await scrollToBottom()
    } else if (evt.type === 'detail') {
      const delta = evt.delta || ''
      if (delta) {
        currentAssistant.content += (currentAssistant.content ? '\n\n' : '') + delta
        if (isCurrentView) await scrollToBottom()
      }
    } else if (evt.type === 'thinking') {
      currentAssistant.toolTrace.push({ type: 'thinking', label: evt.label })
    } else if (evt.type === 'tool_use') {
      currentAssistant.toolTrace.push({
        type: 'tool',
        name: evt.tool_name,
        state: 'running'
      })
    } else if (evt.type === 'tool_result') {
      const last = currentAssistant.toolTrace[currentAssistant.toolTrace.length - 1]
      if (last && last.type === 'tool' && last.name === evt.tool_name) {
        last.state = 'done'
        last.duration_ms = evt.tool_duration_ms
      }
    } else if (evt.type === 'rich_block') {
      currentAssistant.richBlocks.push(evt.block)
    } else if (evt.type === 'error') {
      currentAssistant.error = evt.message
    } else if (evt.type === 'done') {
      currentAssistant.usage = evt.usage
      currentAssistant.durationMs = evt.duration_ms
    }
    // 流式增量持久化（防后台丢数据；debounce 100ms）
    persistSessionDebounced(targetSessionId)
  }
}

// ============================================================================
// 非流式发送（图片/文件）— 同样闭包 targetSessionId
// ============================================================================
const sendNonStream = async (
  text: string,
  file: File | null,
  img: File | null,
  assistantMsg: any,
  targetSessionId: string
) => {
  let res
  if (file) {
    const fd = new FormData(); fd.append('message', text || ''); fd.append('session_id', targetSessionId); fd.append('file', file)
    res = await axios.post('/api/v1/chat/file', fd)
  } else if (img) {
    const fd = new FormData(); fd.append('message', text || '请描述这张图片'); fd.append('session_id', targetSessionId); fd.append('image', img)
    res = await axios.post('/api/v1/chat/image', fd)
  } else {
    res = await axios.post('/api/v1/chat', { message: text, session_id: targetSessionId })
  }
  const targetAssistant = activeAssistantMap.value[targetSessionId] || assistantMsg
  targetAssistant.content = res.data.content || ''
  if (Array.isArray(res.data.rich_blocks)) {
    targetAssistant.richBlocks = res.data.rich_blocks
  }
}

// ============================================================================
// 输入栏
// ============================================================================
// 快捷指令
const quickActions = [
  { icon: '📋', label: '我的任务', text: '我最近有什么任务？' },
  { icon: '📅', label: '最近会议', text: '上周开了什么会？有什么结论？' },
  { icon: '📊', label: '项目进度', text: '项目进度如何？' },
  { icon: '📚', label: '知识问答', text: 'zeta 电位是什么？' }
]

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
}
const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
const sendQuickMessage = (t: string) => { inputText.value = t; sendMessage(t) }
const triggerImageUpload = () => imageInputRef.value?.click()
const triggerFileUpload = () => fileInputRef.value?.click()
const handleImageSelect = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  if (!f.type.startsWith('image/')) return ElMessage.error('请选择图片文件')
  if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
  selectedImage.value = f; imagePreviewUrl.value = URL.createObjectURL(f); (e.target as HTMLInputElement).value = ''
}
const handleFileSelect = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
  selectedFile.value = f; (e.target as HTMLInputElement).value = ''
}
const onDragOver = () => { isDragging.value = true }
const onDragLeave = () => { isDragging.value = false }
const onDrop = (e: DragEvent) => {
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]; if (!f) return
  if (f.type.startsWith('image/')) { if (f.size > 10*1024*1024) return ElMessage.error('图片不超过10MB'); selectedImage.value = f; imagePreviewUrl.value = URL.createObjectURL(f) }
  else { if (f.size > 50*1024*1024) return ElMessage.error('文件不超过50MB'); selectedFile.value = f }
}
const toggleVoiceMode = () => { voiceMode.value = !voiceMode.value }
const onRecordStart = () => {
  ElMessage.info('🎤 录音中...')
}
const onRecordStop = async (blob: Blob) => {
  if (!blob || blob.size === 0) {
    ElMessage.warning('录音为空，请重试')
    return
  }
  try {
    const fd = new FormData()
    fd.append('audio', blob, 'voice.webm')
    const r = await axios.post('/api/v1/voice/asr', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { language: 'zh' }
    })
    const text = r.data?.text?.trim()
    if (text) {
      inputText.value = text
      await sendMessage()
    } else {
      ElMessage.warning('未能识别语音，请重试')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'ASR 识别失败')
  }
}
const onRecordError = (err: any) => {
  ElMessage.error(err?.message || '录音错误')
}

// TTS 播放
const playingAudio = ref<HTMLAudioElement | null>(null)
const playTTS = async (text: string) => {
  if (!text) return
  if (playingAudio.value) {
    playingAudio.value.pause()
    playingAudio.value = null
  }
  try {
    const r = await axios.post('/api/v1/voice/tts',
      { text, voice: 'zh_female' },
      { responseType: 'blob' }
    )
    const url = URL.createObjectURL(r.data)
    const audio = new Audio(url)
    playingAudio.value = audio
    audio.onended = () => { URL.revokeObjectURL(url); playingAudio.value = null }
    audio.play()
  } catch (e: any) {
    ElMessage.error('TTS 播放失败：' + (e.response?.data?.detail || e.message))
  }
}
</script>

<template>
  <div class="chat-immersive" :class="{ 'is-dragging': isDragging }">
    <!-- 网络断线横幅 -->
    <div v-if="!isOnline" class="network-banner">
      <span class="nb-dot" />网络已断开，正在等待恢复...
    </div>

    <div class="chat-layout">
      <!-- 侧栏 -->
      <SessionSidebar :collapsed="sidebarCollapsed" @create="onCreateSession" @switch="onSwitchSession" />

      <div class="chat-main">
        <!-- 顶部 -->
        <header class="chat-header">
          <div class="header-left">
            <el-button text size="small" @click="sidebarCollapsed = !sidebarCollapsed" title="切换侧栏">
              <span style="font-size: 16px;">☰</span>
            </el-button>
            <el-avatar :size="36" class="bot-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </el-avatar>
            <div class="header-text">
              <div class="bot-name">小气</div>
              <div class="bot-status">
                <span class="status-dot" />
                <span v-if="isCurrentSessionSending">生成中...</span>
                <span v-else>在线</span>
              </div>
            </div>
          </div>
          <div class="header-right">
            <el-button text @click="toggleTheme" :title="isDark ? '切换浅色' : '切换深色'">
              {{ isDark ? '☀️' : '🌙' }}
            </el-button>
            <el-button text @click="clearChat">清空对话</el-button>
          </div>
        </header>

    <!-- 消息区 -->
    <div ref="messagesRef" class="messages">
      <!-- 录音面板 -->
      <VoiceRecorder
        v-if="voiceMode"
        @record-start="onRecordStart"
        @record-stop="onRecordStop"
        @record-error="onRecordError"
      />

      <TransitionGroup name="msg">
      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <div v-if="idx > 0 && new Date(msg.timestamp) - new Date(messages[idx-1].timestamp) > 5*60*1000" class="time-divider">
          {{ new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
        </div>

        <div v-if="msg.role === 'user'" class="msg-row user">
          <div class="bubble user-bubble">
            <div v-html="renderMarkdown(msg.content)" />
            <div v-if="msg.imageUrl" class="msg-image">
              <img :src="msg.imageUrl" @click="window.open(msg.imageUrl, '_blank')" />
            </div>
          </div>
        </div>

        <div v-else class="msg-row bot">
          <el-avatar :size="32" class="bot-msg-avatar">
            <el-icon><ChatDotRound /></el-icon>
          </el-avatar>
          <div class="bubble bot-bubble">
            <div v-if="msg.toolTrace && msg.toolTrace.length" class="tool-trace">
              <div v-for="(t, i) in msg.toolTrace" :key="i" class="trace-item" :class="t.state">
                <span v-if="t.type === 'thinking'">{{ t.label }}</span>
                <span v-else>🔧 {{ t.name }} {{ t.state === 'running' ? '...' : '✓' }}<span v-if="t.duration_ms" class="duration"> {{ t.duration_ms }}ms</span></span>
              </div>
            </div>

            <div v-if="msg.content" class="msg-content" v-html="renderMarkdown(msg.content)" />

            <div v-if="msg.richBlocks && msg.richBlocks.length" class="rich-blocks">
              <RichContent v-for="(rb, i) in msg.richBlocks" :key="i" :block="rb" />
            </div>

            <div v-if="msg.error" class="msg-error">⚠️ {{ msg.error }}</div>

            <div v-if="msg.state === 'streaming' && !msg.content && !msg.toolTrace?.length" class="typing-bubble">
              <span /><span /><span />
            </div>

            <div v-if="msg.state === 'idle' && (msg.usage || msg.durationMs)" class="msg-meta">
              <span v-if="msg.usage">📊 {{ msg.usage.total_tokens }} tokens</span>
              <span v-if="msg.durationMs">⏱ {{ (msg.durationMs / 1000).toFixed(1) }}s</span>
              <el-button v-if="msg.content" text size="small" @click="playTTS(msg.content)" title="播放语音">🔊</el-button>
            </div>
          </div>
        </div>
      </template>
      </TransitionGroup>

      <div v-if="messages.length === 1" class="welcome-hero">
        <el-avatar :size="80" class="hero-avatar">
          <el-icon><ChatDotRound /></el-icon>
        </el-avatar>
        <h2>你好，我是小气</h2>
        <p>课题组智能助手，可以帮你查会议、查任务、查知识、查公式</p>
        <div class="quick-actions">
          <button v-for="qa in quickActions" :key="qa.label" class="quick-btn" @click="sendQuickMessage(qa.text)">
            <span class="qa-icon">{{ qa.icon }}</span>
            <span>{{ qa.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <footer class="input-bar">
      <div class="input-core">
        <div class="input-actions-left">
          <el-button text @click="triggerImageUpload"><span class="iconfont">🖼️</span></el-button>
          <el-button text @click="triggerFileUpload"><span class="iconfont">📎</span></el-button>
          <el-button text @click="toggleVoiceMode" :type="voiceMode ? 'primary' : ''"><span class="iconfont">🎤</span></el-button>
        </div>
        <textarea
          ref="textareaRef"
          id="chat-input-textarea"
          name="chat-input-textarea"
          v-model="inputText"
          class="input-textarea"
          placeholder="问问小气…"
          rows="1"
          aria-label="聊天输入框"
          title="聊天输入框"
          @keydown="handleKeydown"
          @input="autoResize"
        />
        <el-button
          type="primary"
          class="send-btn"
          :disabled="!inputText.trim()"
          @click="sendMessage()"
        >
          <span>↑</span>
        </el-button>
      </div>
      <input
        ref="imageInputRef"
        id="chat-image-upload"
        name="chat-image-upload"
        type="file"
        accept="image/*"
        hidden
        aria-label="上传图片"
        title="上传图片"
        @change="handleImageSelect"
      />
      <input
        ref="fileInputRef"
        id="chat-file-upload"
        name="chat-file-upload"
        type="file"
        hidden
        aria-label="上传文件"
        title="上传文件"
        @change="handleFileSelect"
      />
    </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-immersive {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px);
  background: linear-gradient(180deg, #f8f9fb 0%, #fefefe 100%);
  border-radius: var(--radius-lg);
  overflow: hidden;
  position: relative;
}
.chat-layout { display: flex; flex: 1; overflow: hidden; }
.chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.network-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  background: #ffebee; color: #c62828;
  font-size: 13px; font-weight: 500;
  border-bottom: 1px solid #f5c2c7;
}
.nb-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #f56c6c;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}
.msg-enter-active { transition: all 0.25s ease; }
.msg-enter-from { opacity: 0; transform: translateY(8px); }
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #eee;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.bot-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); }
.bot-msg-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); flex-shrink: 0; }
.header-text { line-height: 1.2; }
.bot-name { font-weight: 600; font-size: 15px; }
.bot-status { font-size: 12px; color: #999; display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #67c23a; }

.messages { flex: 1; overflow-y: auto; padding: 20px; }
.time-divider { text-align: center; font-size: 12px; color: #999; margin: 16px 0; }

.msg-row { display: flex; margin-bottom: 16px; gap: 8px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot { justify-content: flex-start; }

.bubble { max-width: 80%; padding: 12px 16px; border-radius: 16px; line-height: 1.6; word-wrap: break-word; }
.user-bubble { background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: white; border-bottom-right-radius: 6px; }
.bot-bubble { background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-bottom-left-radius: 6px; }

.tool-trace { margin-bottom: 12px; padding: 8px 12px; background: #fafbfc; border-radius: 8px; border-left: 3px solid #FF7A5C; }
.trace-item { font-size: 12px; color: #666; padding: 2px 0; }
.trace-item.running { color: #FF7A5C; }
.trace-item .duration { color: #999; font-size: 11px; }

.msg-content :deep(p) { margin: 0 0 8px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul), .msg-content :deep(ol) { padding-left: 20px; }
.msg-content :deep(pre) { background: #f6f8fa; padding: 8px 12px; border-radius: 6px; overflow-x: auto; }
.msg-content :deep(code) { background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; }

.rich-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.msg-error { color: #f56c6c; font-size: 13px; margin-top: 8px; }
.msg-meta { font-size: 11px; color: #999; margin-top: 8px; display: flex; gap: 12px; }

.typing-bubble { display: inline-flex; gap: 4px; }
.typing-bubble span { width: 6px; height: 6px; border-radius: 50%; background: #FF7A5C; animation: td 1.4s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.4s; }
@keyframes td { 0%, 60%, 100% { transform: scale(1); opacity: 0.5; } 30% { transform: scale(1.4); opacity: 1; } }

.welcome-hero { text-align: center; padding: 60px 20px 20px; }
.hero-avatar { background: linear-gradient(135deg, #FF7A5C, #FFB347); margin-bottom: 16px; }
.welcome-hero h2 { font-size: 24px; margin: 0 0 8px; color: #333; }
.welcome-hero p { color: #666; margin: 0 0 24px; }
.quick-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.quick-btn { display: flex; align-items: center; gap: 6px; padding: 10px 18px; background: white; border: 1px solid #e0e0e0; border-radius: 20px; cursor: pointer; transition: all 0.2s; }
.quick-btn:hover { border-color: #FF7A5C; color: #FF7A5C; transform: translateY(-1px); }
.qa-icon { font-size: 18px; }

.input-bar { padding: 16px 20px; background: rgba(255,255,255,0.85); backdrop-filter: blur(20px); border-top: 1px solid #eee; }
.input-core { display: flex; align-items: center; gap: 8px; background: white; border: 1px solid #e0e0e0; border-radius: 20px; padding: 4px 8px; }
.input-actions-left { display: flex; gap: 4px; }
.input-textarea { flex: 1; border: none; outline: none; resize: none; font: inherit; padding: 8px; max-height: 120px; background: transparent; }
.send-btn { width: 34px; height: 34px; padding: 0; border-radius: 50%; background: linear-gradient(135deg, #FF7A5C, #FFB347); border: none; color: white; font-size: 18px; }

@media (max-width: 768px) {
  .bubble { max-width: 92%; }
  .messages { padding: 12px; }
  .chat-immersive { border-radius: 0; height: calc(100vh - 56px); }
}
</style>
<script setup lang="ts">
/**
 * ChatViewSSE.vue — 桌面端 Chat（SSE 流式 + Rich Block）
 *
 * PR #3 重构：所有 SSE 状态管理逻辑抽出到 useChatStream composable
 * 桌面/移动共用一份核心（per-session 数据隔离 + targetSessionId 闭包 + abort）。
 * 本文件只保留桌面 UI 相关状态（侧栏、拖拽、录音面板）。
 *
 * 修复 4：多会话并行架构（保留，绝不可破坏）
 * - 每个 sessionId 独立 messages 数组（messagesBySession）
 * - 切会话不 abort SSE，让 A 在后台继续生成
 * - SSE yield 通过 activeAssistantMap[sessionId] 找到目标 assistantMsg 引用
 * - 流式增量 debounce 100ms 持久化到 localStorage（防后台丢）
 *
 * 复用：
 * - useChatStream (SSE 多会话核心) - 桌面/移动共用
 * - useThemeStore (Pinia 全局主题)
 * - Rich Block 注册表 (web/src/components/chat/blocks/registry.ts)
 * - Pinia chatSessions store
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, ArrowDown, ArrowUp, Search, Fold, Expand, Plus, Picture, Paperclip, Microphone, Promotion, VideoPause, MagicStick, Cpu, Moon, Sunny } from '@element-plus/icons-vue'
import RichContent from '@/components/chat/RichContent.vue'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
// #043 Phase 6 UI 升级
import SearchPalette from '@/components/chat/SearchPalette.vue'
// v78 UI-redesign：3-zone 新组件
import ChatBreadcrumb from '@/components/chat/ChatBreadcrumb.vue'
import ThinkingModeSwitch from '@/components/chat/ThinkingModeSwitch.vue'
import ShareDialog from '@/components/chat/ShareDialog.vue'
import ExportDialog from '@/components/chat/ExportDialog.vue'
import TagsEditor from '@/components/chat/TagsEditor.vue'
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'
import { useChatStream } from '@/composables/chat/useChatStream'
import { useThemeStore } from '@/stores/useThemeStore'
import { useUiStore } from '@/stores/useUiStore'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { renderMarkdown } from '@/utils/markdown'

// ============================================================================
// SSE 核心（桌面/移动共用）
// ============================================================================
const {
  sessionId,
  messages,
  isCurrentSessionSending,
  onCreateSession,
  onSwitchSession,
  clearChat,
  sendMessage: sendMessageCore,
  stopGeneration,  // 2026-06-14 方案 C Stage 4：停止生成按钮
  playTTS,
  asrRecognize,
} = useChatStream()

// ============================================================================
// 主题（PR #1 useThemeStore）
// ============================================================================
const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark)

// v78 UI-redesign: 顶部 [+] FAB 用 store 直接创建会话
const chatSessionsStore = useChatSessionsStore()
const toggleTheme = () => themeStore.toggle()

// ============================================================================
// UI 偏好（2026-06-14 收官）：是否显示 agent 内部思考过程
// ============================================================================
const uiStore = useUiStore()
const showThinking = computed(() => uiStore.showThinking)
const toggleThinking = () => uiStore.toggleThinking()
// 2026-06-30 #009 Self-RAG 深度思考 toggle
const useDeepThinking = computed(() => uiStore.useDeepThinking)
const toggleDeepThinking = () => uiStore.toggleDeepThinking()

// ============================================================================
// UI 状态（仅桌面端）
// ============================================================================
const inputText = ref('')
const isDragging = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const selectedImage = ref<File | null>(null)
const imagePreviewUrl = ref('')
const selectedFile = ref<File | null>(null)
const voiceMode = ref(false)
const imageInputRef = ref<HTMLInputElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const sidebarCollapsed = ref(false)
const loading = ref(false)

// 网络状态
const { online: isOnline } = useNetworkStatus()

// #043 Phase 6 UI 升级：搜索 / 分享 / 导出 / 标签编辑
const showSearchPalette = ref(false)
const showShareDialog = ref(false)
const showExportDialog = ref(false)
const showTagsEditor = ref(false)
const dialogSession = ref<any>(null)

function onShareSession(session: any) {
  dialogSession.value = session
  showShareDialog.value = true
}

// v78 UI-redesign: 顶栏 [+] 新对话按钮 - 调用 store.createSession 简化版
function onNewSession() {
  chatSessionsStore.createSession()
}
function onExportSession(session: any) {
  dialogSession.value = session
  showExportDialog.value = true
}
function onEditTagsSession(session: any) {
  dialogSession.value = session
  showTagsEditor.value = true
}
function onSearchSelect(payload: { sessionId: string; messageId?: number }) {
  // 切到对应 session（messagesBySession 已加载则滚到底/高亮 messageId）
  if (payload?.sessionId) {
    onSwitchSession(payload.sessionId)
  }
}

// 全局快捷键（Cmd/Ctrl+K 弹搜索，Esc 关搜索）
useGlobalShortcuts({
  'mod+k': () => { showSearchPalette.value = true },
  'escape': () => { if (showSearchPalette.value) showSearchPalette.value = false },
})

// ============================================================================
// 滚动到底部（智能 sticky scroll）
// ============================================================================
// 行为：
// 1. 任何消息变化（流式 text_delta / rich_block / 新消息）时，若 autoStick=true 则滚到底
// 2. 用户手动往上滚（scroll 位置 < 阈值）→ 取消 autoStick，停止自动滚
//    （避免用户看历史消息时被打扰）
// 3. 显示"↓ 跳到最新"按钮：点了恢复 autoStick + 滚到底
const messagesRef = ref<HTMLElement | null>(null)
const autoStick = ref(true)  // 是否自动贴底
const showJumpToBottom = ref(false)  // 是否显示"跳到最新"按钮
const showJumpToTop = ref(false)  // P0-#2 (2026-07-12): 是否显示"跳到最早"按钮
const STICK_THRESHOLD_PX = 80  // 距底 < 80px 算"贴底"
const USER_SCROLL_UP_THRESHOLD = 120  // 距底 > 120px 视为"用户主动上滚"
const TOP_THRESHOLD_PX = 100  // P0-#2: 距顶 < 100px 算"贴顶"

const scrollToBottom = async (force = false) => {
  await nextTick()
  if (messagesRef.value) {
    if (force || autoStick.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      autoStick.value = true
      showJumpToBottom.value = false
      // P0-#2: 滚到底后, 离顶部远 → 显示"跳到最早"按钮
      showJumpToTop.value = true
    }
  }
}

// P0-#2 新增: 滚到顶部 (用于"跳到最早"按钮)
const scrollToTop = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = 0
  }
}

// 监听用户手动滚动:用户往上滚 → 取消 autoStick
const onMessagesScroll = () => {
  if (!messagesRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  const distanceFromTop = scrollTop

  if (distanceFromBottom < STICK_THRESHOLD_PX) {
    // 接近底部 → 重新启用 autoStick
    autoStick.value = true
    showJumpToBottom.value = false
    // P0-#2: 离顶部 > 100px 时仍显示"跳到最早"按钮
    showJumpToTop.value = distanceFromTop > TOP_THRESHOLD_PX
  } else if (distanceFromTop < TOP_THRESHOLD_PX) {
    // P0-#2: 接近顶部 → 关闭"跳到最早"按钮 (已在顶部无需按钮)
    autoStick.value = false
    showJumpToBottom.value = true
    showJumpToTop.value = false
  } else {
    // P0-#2: 中间区域 → 两个按钮都显示 (用户可自由跳到任一端)
    autoStick.value = false
    showJumpToBottom.value = true
    showJumpToTop.value = true
  }
}

const jumpToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
  autoStick.value = true
  showJumpToBottom.value = false
  showJumpToTop.value = true  // P0-#2: 跳到底后离顶部远 → 显示"跳到最早"
}

// P0-#2 新增: 跳到最早 (历史起点)
const jumpToTop = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = 0
  }
  showJumpToBottom.value = true  // 离底部远 → 显示"跳到最新"按钮
  showJumpToTop.value = false
}

// ============================================================================
// 智能 sticky scroll：监听 messages 变化自动滚到底（除非用户已上滚）
// ============================================================================
// 2026-06-14 方案 C 增强：之前只在 sendMessage 前后滚，流式生成中不滚，
// 用户必须手动滚轮才能看新内容。改为 watch messages 实时滚。
//
// ★ 2026-07-01 修复 bug 2.2: sessionId watcher 改 rAF,避免与 messages watcher
// 同一 tick 竞争 → 同一 .messages 容器连续两次 scrollTop 赋值 → 引起
// 父级 flex 容器 (含侧边栏) 短暂 reflow → 侧边栏 scroll 跳变。
watch(
  () => messages.value,
  () => {
    // 强制模式下永远滚；autoStick 模式下用户已上滚则不滚
    scrollToBottom(false)
  },
  { deep: true, flush: 'post' },
)

// 新 session 切换时也滚到底
watch(
  () => sessionId.value,
  (newId, oldId) => {
    if (newId === oldId) return
    // rAF 推迟一帧,避免与 messages watcher 同步触发造成的 layout thrash
    requestAnimationFrame(() => scrollToBottom(true))
  },
)

// ============================================================================
// 发送消息（包装 useChatStream.sendMessage 以处理 UI 副作用）
// ============================================================================
// 关键设计：发送消息是**用户主动行为**，意图明确，必须**强制**滚到底（force=true）
// 不受 sticky scroll 的 autoStick 守卫影响（用户上滚看历史时也要能看到自己发的内容）
// 注意：scrollToBottom(true) 内部会 autoStick.value = true（line 92），恢复贴底状态
// 后续流式 text_delta 接收时 watch(messages) 仍按 sticky 行为（用户再次上滚可中断）
async function sendMessage(text?: string) {
  const content = (text ?? inputText.value).trim()
  if (!content && !selectedImage.value && !selectedFile.value) return

  inputText.value = ''
  const file = selectedFile.value
  const img = selectedImage.value
  selectedImage.value = null
  imagePreviewUrl.value = ''
  selectedFile.value = null
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  loading.value = true
  // 2026-06-14 修复：发送前**强制**滚到底（force=true），不受 autoStick 守卫
  await scrollToBottom(true)

  try {
    await sendMessageCore({
      text: content,
      file,
      image: img,
    })
  } catch {
    // 错误已由 useChatStream 内部处理
  } finally {
    loading.value = false
    // 2026-06-14 修复：发送后**强制**滚到底（force=true），确保 assistant 占位可见
    await scrollToBottom(true)
  }
}

// ============================================================================
// 输入栏 / 文件上传 / 拖拽
// ============================================================================
const quickActions = [
  { icon: '📋', label: '我的任务', text: '我最近有什么任务？' },
  { icon: '📅', label: '最近会议', text: '上周开了什么会？有什么结论？' },
  { icon: '📊', label: '项目进度', text: '项目进度如何？' },
  { icon: '📚', label: '知识问答', text: 'zeta 电位是什么？' }
]

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function sendQuickMessage(t: string) { inputText.value = t; sendMessage(t) }
function triggerImageUpload() { imageInputRef.value?.click() }
function triggerFileUpload() { fileInputRef.value?.click() }
function openImage(url: string) { window.open(url, '_blank') }

function handleImageSelect(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  if (!f.type.startsWith('image/')) return ElMessage.error('请选择图片文件')
  if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
  selectedImage.value = f
  imagePreviewUrl.value = URL.createObjectURL(f)
  ;(e.target as HTMLInputElement).value = ''
}

function handleFileSelect(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
  selectedFile.value = f
  ;(e.target as HTMLInputElement).value = ''
}

function onDragOver() { isDragging.value = true }
function onDragLeave() { isDragging.value = false }
function onDrop(e: DragEvent) {
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]; if (!f) return
  if (f.type.startsWith('image/')) {
    if (f.size > 10 * 1024 * 1024) return ElMessage.error('图片不超过10MB')
    selectedImage.value = f
    imagePreviewUrl.value = URL.createObjectURL(f)
  } else {
    if (f.size > 50 * 1024 * 1024) return ElMessage.error('文件不超过50MB')
    selectedFile.value = f
  }
}

// ============================================================================
// 录音面板
// ============================================================================
function toggleVoiceMode() { voiceMode.value = !voiceMode.value }
function onRecordStart() {
  ElMessage.info('🎤 录音中...')
}
async function onRecordStop(blob: Blob) {
  const text = await asrRecognize(blob)
  if (text) {
    inputText.value = text
    await sendMessage()
  }
}
function onRecordError(err: any) {
  ElMessage.error(err?.message || '录音错误')
}

// ============================================================================
// TTS（包装 useChatStream.playTTS）
// ============================================================================
async function playTTSWrap(text: string) {
  await playTTS(text)
}

// ============================================================================
// 生命周期
// ============================================================================
onMounted(async () => {
  await nextTick()
  scrollToBottom()
})

onUnmounted(() => {
  // useChatStream 的 onUnmounted 已处理：abort 所有 SSE + 持久化所有 session
  // 这里无需额外逻辑
})
</script>

<template>
  <div class="chat-immersive" :class="{ 'is-dragging': isDragging }">
    <!-- 网络断线横幅 -->
    <div v-if="!isOnline" class="network-banner">
      <span class="nb-dot" />网络已断开，正在等待恢复...
    </div>

    <div class="chat-layout">
      <!-- 侧栏 -->
      <SessionSidebar
        :collapsed="sidebarCollapsed"
        @create="onCreateSession"
        @switch="onSwitchSession"
        @share="onShareSession"
        @export="onExportSession"
        @edit-tags="onEditTagsSession"
      />

      <div class="chat-main">
        <!-- v78 UI-redesign 3-zone 顶栏 -->
        <header class="chat-header glass glass-lg">
          <div class="header-left">
            <el-button
              id="chat-header-sidebar-toggle"
              name="chat-header-sidebar-toggle"
              text
              size="small"
              @click="sidebarCollapsed = !sidebarCollapsed"
              aria-label="切换侧栏"
              title="切换侧栏"
            >
              <el-icon><component :is="sidebarCollapsed ? 'Expand' : 'Fold'" /></el-icon>
            </el-button>
          </div>
          <div class="header-center">
            <ChatBreadcrumb :status="isCurrentSessionSending ? 'generating' : 'idle'" />
          </div>
          <div class="header-right">
            <el-button
              id="chat-header-new-session"
              name="chat-header-new-session"
              type="primary"
              round
              size="default"
              aria-label="新建对话"
              title="新建对话"
              @click="onNewSession"
            >
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </header>

    <!-- 消息区 -->
    <div ref="messagesRef" class="messages" @scroll="onMessagesScroll">
      <!-- 2026-06-14 智能 sticky scroll：用户上滚后显示"跳到最新"按钮 -->
      <button
        v-if="showJumpToBottom"
        class="jump-to-bottom"
        type="button"
        aria-label="跳到最新消息"
        title="跳到最新消息"
        @click="jumpToBottom"
      >
        <el-icon><ArrowDown /></el-icon>
        <span>跳到最新</span>
      </button>
      <!-- P0-#2 (2026-07-12): 加"跳到最早"按钮 - 用户报"41条仍然看不全"实际原因
           autoStick 滚到底无顶部按钮,用户被卡在底部看不到前 35 条历史. 修复: -->
      <button
        v-if="showJumpToTop"
        id="chat-jump-to-top"
        class="jump-to-top"
        type="button"
        aria-label="跳到最早消息"
        title="跳到最早消息 (历史起点)"
        @click="jumpToTop"
      >
        <el-icon><ArrowUp /></el-icon>
        <span>跳到最早</span>
      </button>
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
              <img :src="msg.imageUrl" :alt="`消息图片：${msg.imageUrl.split('/').pop() || ''}`" :title="`消息图片：${msg.imageUrl.split('/').pop() || ''}`" @click="openImage(msg.imageUrl)" />
            </div>
          </div>
        </div>

        <div v-else class="msg-row bot">
          <el-avatar :size="32" class="bot-msg-avatar" alt="小气助手头像" title="小气助手">
            <el-icon><ChatDotRound /></el-icon>
          </el-avatar>
          <div class="bubble bot-bubble">
            <div v-if="showThinking && msg.toolTrace && msg.toolTrace.length" class="tool-trace">
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
              <el-button v-if="msg.content" text size="small" @click="playTTSWrap(msg.content)" title="播放语音">🔊</el-button>
            </div>
          </div>
        </div>
      </template>
      </TransitionGroup>

      <div v-if="messages.length === 1" class="welcome-hero">
        <el-avatar :size="80" class="hero-avatar" alt="小气助手大头像" title="小气助手">
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

    <!-- v78 UI-redesign: 思考模式分段控件 (输入栏上方) -->
    <div class="thinking-switch-row">
      <ThinkingModeSwitch />
    </div>

    <footer class="input-bar glass glass-lg">
      <div class="input-core">
        <div class="input-actions-left">
          <el-button
            id="chat-image-upload-btn"
            name="chat-image-upload"
            text
            aria-label="上传图片"
            title="上传图片"
            @click="triggerImageUpload"
          >
            <el-icon :size="18"><Picture /></el-icon>
          </el-button>
          <el-button
            id="chat-file-upload-btn"
            name="chat-file-upload"
            text
            aria-label="上传文件"
            title="上传文件"
            @click="triggerFileUpload"
          >
            <el-icon :size="18"><Paperclip /></el-icon>
          </el-button>
          <el-button
            id="chat-voice-toggle-btn"
            name="chat-voice-toggle"
            text
            :type="voiceMode ? 'primary' : ''"
            aria-label="录音"
            title="录音"
            @click="toggleVoiceMode"
          >
            <el-icon :size="18"><Microphone /></el-icon>
          </el-button>
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
        <!-- 2026-07-13 #P1: mode badge — 实时显示上一次响应的 mode/model/duration/thinkingTokens -->
        <span
          v-if="uiStore.lastModeInfo.mode"
          id="chat-mode-badge"
          class="mode-badge"
          :class="`mode-${uiStore.lastModeInfo.mode}`"
          :title="`mode=${uiStore.lastModeInfo.mode}, model=${uiStore.lastModeInfo.model}, ${uiStore.lastModeInfo.durationMs}ms`"
        >
          <span class="mode-badge-label">{{ uiStore.lastModeInfo.mode }}</span>
          <span v-if="uiStore.lastModeInfo.model" class="mode-badge-model">{{ uiStore.lastModeInfo.model }}</span>
          <span class="mode-badge-duration">{{ uiStore.lastModeInfo.durationMs }}ms</span>
          <span v-if="uiStore.lastModeInfo.thinkingTokens > 0" class="mode-badge-thinking">
            思考 {{ uiStore.lastModeInfo.thinkingTokens }}tok
          </span>
        </span>
        <el-button
          v-if="!isCurrentSessionSending"
          id="chat-send-btn"
          name="chat-send"
          type="primary"
          class="send-btn"
          :disabled="!inputText.trim()"
          aria-label="发送消息"
          title="发送消息"
          @click="sendMessage()"
        >
          <el-icon :size="18"><Promotion /></el-icon>
        </el-button>
        <!-- 2026-06-14 方案 C Stage 4：停止生成按钮（流式中变 ⏹） -->
        <el-button
          v-else
          id="chat-stop-btn"
          name="chat-stop"
          type="danger"
          class="stop-btn"
          aria-label="停止生成"
          title="停止生成"
          @click="stopGeneration()"
        >
          <el-icon :size="18"><VideoPause /></el-icon>
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

    <!-- #043 Phase 6: 全局搜索 / 分享 / 导出 / 标签编辑 dialog -->
    <SearchPalette
      v-model="showSearchPalette"
      @select="onSearchSelect"
    />
    <ShareDialog
      v-if="dialogSession"
      v-model="showShareDialog"
      :session="dialogSession"
    />
    <ExportDialog
      v-if="dialogSession"
      v-model="showExportDialog"
      :session="dialogSession"
    />
    <TagsEditor
      v-if="dialogSession"
      v-model="showTagsEditor"
      :session="dialogSession"
    />
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
  background: var(--color-danger-bg); color: var(--color-danger);
  font-size: 13px; font-weight: 500;
  border-bottom: 1px solid #f5c2c7;
}
.nb-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--color-danger);
  animation: pulse 1.5s infinite;
}
.msg-enter-active { transition: var(--transition-all-slow) ease; }
.msg-enter-from { opacity: 0; transform: translateY(8px); }
.chat-header {
  display: grid;
  grid-template-columns: auto 1fr auto;  /* v78 3-zone: 左 / 中 / 右 */
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border-light);
  min-height: 56px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-center { display: flex; align-items: center; justify-content: center; min-width: 0; }
.header-right { display: flex; align-items: center; gap: 4px; }
.bot-avatar { background: var(--gradient-welcome-hero); }
.bot-msg-avatar { background: var(--gradient-welcome-hero); flex-shrink: 0; }
.header-text { line-height: 1.2; }
.bot-name { font-weight: 600; font-size: 15px; }
.bot-status { font-size: 12px; color: var(--color-text-secondary); display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-success); }

/* v78 UI-redesign: 思考模式 segmented control 行 (在消息区和输入栏之间) */
.thinking-switch-row {
  display: flex; align-items: center; justify-content: center;
  padding: 6px 20px;
  border-top: 1px solid var(--color-border-light);
}

.messages { flex: 1; overflow-y: auto; padding: 20px; position: relative; }

/* 2026-06-14 智能 sticky scroll：跳到最新按钮 */
.jump-to-bottom {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-primary, #FF7A5C);
  border-radius: 20px;
  color: var(--color-primary, #FF7A5C);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 10;
  transition: background 0.2s, color 0.2s, transform 0.2s;
}

/* P0-#2 v4 (2026-07-12 14:50): transform: none !important 防御 EP active 样式
   Playwright 实测 click 期间: transform=matrix(1, 0, 0, 1, -49.5, -2)
   - 来源: Element Plus 全局 button:active 默认样式 (translate center alignment)
   - 影响: 按钮按下瞬间视觉上向左下移动 49.5px / 2px, 用户称之"跳动"
   - 修法: 强制 transform: none !important 覆盖 EP 全局样式
     + transform 不在 transition 中 (v3 已修)
     + width: fit-content + 自动 (无 transform-based centering) */
.jump-to-top {
  position: sticky;
  top: 16px;
  z-index: 10;
  display: block;
  width: fit-content;
  margin: 0 auto 0 auto;
  background: var(--color-bg-card);
  border: 1px solid var(--color-primary, #FF7A5C);
  border-radius: 20px;
  color: var(--color-primary, #FF7A5C);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  padding: 8px 16px;
  transition: background 0.2s, color 0.2s;
  user-select: none;
  /* 防止任何 inherited / EP 全局 transform 干扰 */
  transform: none !important;
}

.jump-to-top:hover {
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
  transform: none !important;
}

.jump-to-top:active {
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
  outline: 2px solid var(--color-primary, #FF7A5C);
  outline-offset: 2px;
  transform: none !important;
}

.jump-to-top:focus {
  outline: 2px solid var(--color-primary, #FF7A5C);
  outline-offset: 2px;
  transform: none !important;
}

.jump-to-top:focus-visible {
  outline: 2px solid var(--color-primary, #FF7A5C);
  outline-offset: 2px;
  transform: none !important;
}

.jump-to-top:hover {
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
  transform: translateX(-50%) translateY(-2px);
}

[data-theme="dark"] .jump-to-top {
  background: var(--color-bg-card, #2a2a2a);
  color: var(--color-primary, #FF7A5C);
}

[data-theme="dark"] .jump-to-top:hover {
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
}

.jump-to-bottom:hover {
  background: var(--color-primary, #FF7A5C);
  /* stylelint-disable-next-line color-named */
  color: var(--el-color-white);
  transform: translateX(-50%) translateY(-2px);
}
.time-divider { text-align: center; font-size: 12px; color: var(--color-text-secondary); margin: 16px 0; }

.msg-row { display: flex; margin-bottom: 16px; gap: 8px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot { justify-content: flex-start; }

.bubble { max-width: 80%; padding: 12px 16px; border-radius: 16px; line-height: 1.6; overflow-wrap: break-word; }
.user-bubble {
  background: var(--gradient-welcome-hero);
  /* stylelint-disable-next-line color-named */
  color: var(--el-color-white);
  border-bottom-right-radius: 6px;
}
.bot-bubble { background: var(--color-bg-card); box-shadow: var(--shadow-sm); border-bottom-left-radius: 6px; }

.tool-trace { margin-bottom: 12px; padding: 8px 12px; background: var(--color-bg-warm); border-radius: 8px; border-left: 3px solid var(--color-primary); }
.trace-item { font-size: 12px; color: var(--color-text-regular); padding: 2px 0; }
.trace-item.running { color: var(--color-primary); }
.trace-item .duration { color: var(--color-text-secondary); font-size: 11px; }

/* 2026-06-14 收官：thinking toggle 按钮激活态高亮 */
.thinking-toggle.active { color: var(--color-primary, #FF7A5C); background: var(--color-primary-bg); }
/* 2026-06-30 #009 Self-RAG 深度思考 toggle 激活态高亮 */
.depth-toggle.active { color: var(--color-primary, #FF7A5C); background: var(--color-primary-bg); }
/* 2026-06-30 #009 retrieval_assessment 状态徽章 */
.retrieval-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; font-size: 12px; color: var(--color-text-secondary); background: var(--color-bg-warm); }
.retrieval-badge.reretrieved { color: var(--color-primary); background: var(--color-primary-bg); }
.retrieval-badge.pulse { animation: badgePulse 1.4s ease-in-out infinite; }
@keyframes badgePulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

.msg-content :deep(p) { margin: 0 0 8px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul), .msg-content :deep(ol) { padding-left: 20px; }
.msg-content :deep(pre) { background: var(--color-bg-page); padding: 8px 12px; border-radius: 6px; overflow-x: auto; }
.msg-content :deep(code) { background: var(--color-bg-page); padding: 2px 6px; border-radius: 3px; font-size: 13px; }

.rich-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.msg-error { color: var(--color-danger); font-size: 13px; margin-top: 8px; }
.msg-meta { font-size: 11px; color: var(--color-text-secondary); margin-top: 8px; display: flex; gap: 12px; }

.typing-bubble { display: inline-flex; gap: 4px; }
.typing-bubble span { width: 6px; height: 6px; border-radius: 50%; background: var(--color-primary); animation: td 1.4s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.4s; }
.welcome-hero { text-align: center; padding: 60px 20px 20px; }
.hero-avatar { background: var(--gradient-welcome-hero); margin-bottom: 16px; }
.welcome-hero h2 { font-size: 24px; margin: 0 0 8px; color: var(--color-text-primary); }
.welcome-hero p { color: var(--color-text-regular); margin: 0 0 24px; }
.quick-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.quick-btn { display: flex; align-items: center; gap: 6px; padding: 10px 18px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 20px; cursor: pointer; transition: var(--transition-all-normal); }
.quick-btn:hover { border-color: var(--color-primary); color: var(--color-primary); transform: translateY(-1px); }
.qa-icon { font-size: 18px; }

/* v77 P2.5.1: backdrop-filter + 半透 background 由 .glass 工具类提供 (assets/glass.css)
   blur 20px 降到 .glass-lg 默认 16px（dark mode 自动适配收益更大）
   border-top #eee 硬编码 → var(--color-border-light) */
.input-bar { padding: 16px 20px; border-top: 1px solid var(--color-border-light); }
.input-core { display: flex; align-items: center; gap: 8px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 20px; padding: 4px 8px; }
.input-actions-left { display: flex; gap: 4px; }
.input-textarea { flex: 1; border: none; outline: none; resize: none; font: inherit; padding: 8px; max-height: 120px; background: transparent; }

/* 2026-07-13 #P1: mode badge — send 按钮左边的实时 mode/model/duration 状态 */
.mode-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  background: var(--color-bg-warm, #f5f7fa);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  margin-right: 4px;
  white-space: nowrap;
}
.mode-badge.mode-fast { border-color: var(--color-success, #67c23a); color: var(--color-success, #67c23a); }
.mode-badge.mode-balanced { border-color: var(--color-primary, #FF7A5C); color: var(--color-primary, #FF7A5C); }
.mode-badge.mode-deep {
  border-color: var(--color-primary-700, #5b21b6);
  color: var(--color-primary-700, #5b21b6);
  font-weight: 600;
}
.mode-badge-label { font-weight: 700; }
.mode-badge-model { opacity: 0.8; }
.mode-badge-duration { opacity: 0.7; }
.mode-badge-thinking { opacity: 0.85; font-style: italic; }
[data-theme="dark"] .mode-badge { background: var(--color-bg-warm, #2a2d35); }

.send-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 50%;
  background: var(--gradient-welcome-hero);
  border: none;
  /* stylelint-disable-next-line color-named */
  color: var(--el-color-white);
  font-size: 18px;
}

@media (max-width: 768px) {
  .bubble { max-width: 92%; }
  .messages { padding: 12px; }
  .chat-immersive { border-radius: 0; height: calc(100vh - 56px); }
}
</style>

<!-- v69 P1b fix: ChatViewSSE dark mode 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .chat-immersive {
  background: linear-gradient(180deg, #1a1d23 0%, #0e1015 100%);
}
[data-theme="dark"] .depth-toggle.active { color: var(--color-primary); background: var(--color-primary-bg); }
[data-theme="dark"] .retrieval-badge { background: var(--color-bg-warm); color: var(--color-text-secondary); }
[data-theme="dark"] .retrieval-badge.reretrieved { color: var(--color-primary); background: var(--color-primary-bg); }
[data-theme="dark"] .chat-header {
  background: rgba(26, 29, 35, 0.85);
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .messages { background: transparent; }
[data-theme="dark"] .bot-status,
[data-theme="dark"] .time-divider,
[data-theme="dark"] .msg-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .bot-bubble {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}
[data-theme="dark"] .msg-content :deep(pre),
[data-theme="dark"] .msg-content :deep(code) {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
[data-theme="dark"] .welcome-hero { color: var(--color-text-primary); }
[data-theme="dark"] .welcome-hero h2 { color: var(--color-text-primary); }
[data-theme="dark"] .welcome-hero p { color: var(--color-text-secondary); }
[data-theme="dark"] .quick-btn {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
  color: var(--color-text-regular);
}
[data-theme="dark"] .quick-btn:hover {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
/* v77 P2.5.1: .input-bar dark mode 由 .glass 工具类自动处理 */
[data-theme="dark"] .input-core {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
}
[data-theme="dark"] .input-textarea { color: var(--color-text-primary); }
[data-theme="dark"] .input-textarea::placeholder { color: var(--color-text-placeholder); }
[data-theme="dark"] .jump-to-bottom {
  background: var(--color-bg-card);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
[data-theme="dark"] .jump-to-bottom:hover {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: var(--color-bg-card);
}
[data-theme="dark"] .msg-content :deep(a) { color: var(--color-primary-light); }
</style>
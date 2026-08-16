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
import { ref, computed, onMounted, onUnmounted, nextTick, watch, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, ArrowDown, ArrowUp, Search, Fold, Expand, Plus, Picture, Paperclip, Microphone, VideoPause, MagicStick, Cpu, Moon, Sunny, View, Notebook, Close, Document } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
// RichContent 也已封装到 ChatMessageRow.vue, 此处不再直接 import
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
import FeedbackButtons from '@/components/chat/FeedbackButtons.vue'  // W98 CHAT-P1-D3
import ChatMessageRow from '@/components/chat/ChatMessageRow.vue'  // W100 +45 单条消息复用 (虚拟列表集成)
// ===== W100 +45 P3-VIRTUAL RETRY: 下列组件已封装到 ChatMessageRow.vue, 此处不再直接 import =====
// ThinkingCapsule / ToolTraceItem / PlanSteps / ContentBriefDetail / EventBadges /
// ImageWithFallback / ChatMessageActions / ProEntries / FollowUpChips / RichContent
import InputToolPanel from '@/components/chat/InputToolPanel.vue'  // ChatGPT 风格 "+" 工具面板
import ContextPanel from '@/components/chat/ContextPanel.vue'  // W100 +29 上下文可见性面板
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'
import { useMemo } from '@/composables/useMemo'
import { useVirtualList } from '@/composables/useVirtualList'  // W100 +45 虚拟滚动
import { useChatStream, type ChatMessage } from '@/composables/chat/useChatStream'
import { useThemeStore } from '@/stores/useThemeStore'
import { useUiStore } from '@/stores/useUiStore'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatContextStore } from '@/stores/chatContext'  // 2026-08-15 #P4: 资料库附加文档
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { renderMarkdown } from '@/utils/markdown'
import { formatTimeDivider } from '@/utils/timeDivider'

// ============================================================================
// W72 B-3: 顶栏 3-zone 类型 (派工 v6 段 5 反馈 #3 实战: SubAgent 编排 type hint 必含)
// ============================================================================
interface TopBarZone {
  /** zone 名称 */
  name: 'left' | 'center' | 'right'
  /** grid template columns fr 单位 (桌面端) */
  desktopFr: number
  /** grid template columns fr 单位 (移动端 ≤768px) */
  mobileFr: number
  /** 渲染组件标识 (B-1 NavRail / B-2 ChatBreadcrumb / ThinkingModeSwitch / 原生 button) */
  content: string
}
const TOPBAR_ZONES: readonly TopBarZone[] = [
  { name: 'left',   desktopFr: 4, mobileFr: 1, content: 'hamburger+ChatBreadcrumb' },
  { name: 'center', desktopFr: 4, mobileFr: 2, content: 'ChatBreadcrumb+ThinkingModeSwitch' },
  { name: 'right',  desktopFr: 4, mobileFr: 1, content: 'new-session-button' },
] as const

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
  // 2026-08-16 #71: ChatGPT 风格 — 编辑消息后重发
  resendUserMessage,
} = useChatStream()

// Cache the message-id lookup used by regenerate; unrelated UI updates reuse it.
const messageIndexById = useMemo(() => new Map(
  messages.value.map((message, index) => [message.id, index]),
))

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
const showContextPanel = ref(false)  // W100 +29 上下文可见性面板
const loading = ref(false)

// 网络状态
const { online: isOnline } = useNetworkStatus()

// #043 Phase 6 UI 升级：搜索 / 分享 / 导出 / 标签编辑
const showSearchPalette = ref(false)
const showShareDialog = ref(false)
const showExportDialog = ref(false)
const showTagsEditor = ref(false)
const dialogSession = ref<any>(null)

// W-N 周期: 对话内搜索栏
const showChatSearch = ref(false)
const searchQuery = ref('')
const searchMatches = ref<HTMLElement[]>([])
const searchIndex = ref(-1)
const searchInputRef = ref<HTMLInputElement | null>(null)

// ChatGPT 风格 "+" 工具面板开关
const toolPanelOpen = ref(false)

// W-N 周期: 图片灯箱
const lightboxUrl = ref('')
const showLightbox = ref(false)
function openLightbox(url: string) {
  lightboxUrl.value = url
  showLightbox.value = true
}
function closeLightbox() {
  showLightbox.value = false
  lightboxUrl.value = ''
}

// W-N 周期: 引用回复
const quotedMessage = ref<{ author: string; text: string; card: HTMLElement } | null>(null)
function quoteMsg(btn: HTMLElement) {
  const card = btn.closest('.card') as HTMLElement | null
  if (!card) return
  const content = card.querySelector('.content')
  const author = card.closest('.msg')?.classList.contains('user') ? '我' : '小气助手'
  const text = content ? content.textContent?.trim().substring(0, 100) || '' : ''
  quotedMessage.value = { author, text, card }
  nextTick(() => {
    const ta = document.querySelector('.input-wrapper textarea') as HTMLTextAreaElement | null
    if (ta) ta.focus()
  })
  addQuoteRef(card)
}
function clearQuote() {
  quotedMessage.value = null
}

// 2026-08-16 #P5+: 清除已选图片预览 (注意: 不要 revokeObjectURL,
// 因为 userMsg.imageUrl 引用同一个 URL, 消息气泡需要继续显示)
function clearSelectedImage() {
  selectedImage.value = null
  imagePreviewUrl.value = ''
}
function clearSelectedFile() {
  selectedFile.value = null
}
// 2026-08-16 #P5+: 格式化文件大小 (B/KB/MB)
function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
function addQuoteRef(card: HTMLElement) {
  card.classList.add('quote-ref')
  // Activate with delay for CSS animation
  setTimeout(() => card.classList.add('active'), 50)
}

// W-N 周期: 从 ChatMessageRow 收到 quote 事件
function onQuote(payload: any) {
  const card = document.querySelector(`[data-msg-id="${payload?.msg?.id}"] .card`) as HTMLElement | null
  if (card) quoteMsg(card)
}

// W-N 周期: 对话内搜索逻辑
function toggleChatSearch() {
  showChatSearch.value = !showChatSearch.value
  if (!showChatSearch.value) {
    clearSearchHighlights()
  } else {
    nextTick(() => searchInputRef.value?.focus())
  }
}
function clearSearchHighlights() {
  document.querySelectorAll('.search-highlight').forEach(el => {
    const parent = el.parentNode
    if (parent) parent.replaceChild(document.createTextNode(el.textContent || ''), el)
  })
  searchMatches.value = []
  searchIndex.value = -1
  searchQuery.value = ''
}
function doSearch(query: string) {
  clearSearchHighlights()
  if (!query.trim()) return
  const lower = query.toLowerCase()
  const textNodes: Text[] = []
  const messagesEl = document.querySelector('.messages')
  if (!messagesEl) return
  const walker = document.createTreeWalker(messagesEl, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => {
      const el = n.parentElement
      if (!el) return NodeFilter.FILTER_ACCEPT
      if (el.closest('.chat-search-bar, .jump-to-bottom, .jump-to-top, .typing-indicator'))
        return NodeFilter.FILTER_REJECT
      return NodeFilter.FILTER_ACCEPT
    }
  })
  let node: Text | null
  while ((node = walker.nextNode() as Text | null)) textNodes.push(node)
  textNodes.forEach(tn => {
    const text = tn.textContent || ''
    const idx = text.toLowerCase().indexOf(lower)
    if (idx === -1) return
    const span = document.createElement('span')
    span.className = 'search-highlight'
    span.textContent = text.substring(idx, idx + query.length)
    const range = document.createRange()
    range.setStart(tn, idx)
    range.setEnd(tn, idx + query.length)
    range.deleteContents()
    range.insertNode(span)
    searchMatches.value.push(span)
  })
  searchIndex.value = searchMatches.value.length > 0 ? 0 : -1
}
function updateSearchNav() {
  searchMatches.value.forEach((el, i) => {
    el.classList.toggle('active', i === searchIndex.value)
    if (i === searchIndex.value) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}
function searchNav(dir: number) {
  if (searchMatches.value.length === 0) return
  searchIndex.value = (searchIndex.value + dir + searchMatches.value.length) % searchMatches.value.length
  updateSearchNav()
}

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

// ===== W100 +45 P3-VIRTUAL RETRY: 虚拟滚动 (messages > 50 时启用) =====
// 单一 composable 实例, items 用 readonly messages, 容器挂在 messagesRef
// itemHeight 经验值 (用户消息 ~80px, 助手消息 ~120-300px, 折中 120)
// 阈值 50 (派工 v11 §9 指定 50 items threshold)
const VIRTUAL_ITEM_HEIGHT = 120
const VIRTUAL_THRESHOLD = 50
const virtualList = useVirtualList({
  containerRef: messagesRef,
  items: messages as unknown as Ref<readonly ChatMessage[]>,
  itemHeight: VIRTUAL_ITEM_HEIGHT,
  threshold: VIRTUAL_THRESHOLD,
  overscan: 5,
})

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

  // W100 +45: 同步 scrollTop 到虚拟列表 (内部用其切片 visibleItems)
  virtualList._updateScroll(scrollTop, clientHeight)

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
  // 2026-08-16 #P5+: 先读 imagePreviewUrl 再清空 (保留给消息气泡用)
  const currentImageUrl = imagePreviewUrl.value
  selectedImage.value = null
  imagePreviewUrl.value = ''
  selectedFile.value = null
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  loading.value = true
  // 2026-06-14 修复：发送前**强制**滚到底（force=true），不受 autoStick 守卫
  await scrollToBottom(true)

  try {
    // 2026-08-16 #P5+: 如果带图片, 先上传到 MinIO 拿永久 URL (避免刷新后 blob URL 失效)
    let uploadedImageUrl: string | null = currentImageUrl
    if (img && currentImageUrl && currentImageUrl.startsWith('blob:')) {
      try {
        const formData = new FormData()
        formData.append('image', img)
        const uploadRes = await fetch('/api/v1/chat/upload-image', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
          body: formData,
        })
        if (uploadRes.ok) {
          const data = await uploadRes.json()
          uploadedImageUrl = data.url  // 永久 MinIO URL
          console.log('[P5] 图片已上传到 MinIO:', uploadedImageUrl)
        } else {
          console.warn('[P5] 图片上传失败, 降级用 blob URL:', uploadRes.status)
        }
      } catch (uploadErr) {
        console.error('[P5] 图片上传异常, 降级用 blob URL:', uploadErr)
      }
    }

    await sendMessageCore({
      text: content,
      file,
      image: img,
      // #P5+: 传 imageUrl (MinIO 永久 URL, 刷新后仍有效)
      imageUrl: uploadedImageUrl,
    })
    // #P5+: **立即**清空附加文档 (不等 sendMessageCore 完成, 否则用户看到 AI 回复期间顶部块还显示)
    // 顶部块立即消失, 后端 chat_session_attached_documents 仍存 (供 AI 引用)
    if (chatCtx.count > 0) {
      chatCtx.clear().catch(e => console.warn('[P5] 清空附加失败 (后台清, 不阻塞)', e))
    }
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

// [CHAT-P1-E E2] 追问 chip 点击 → 触发新 SSE (复用 sendMessage 同 session)
function onFollowUpClick(suggestion: string) {
  inputText.value = suggestion
  sendMessage(suggestion)
}
function openImage(url: string) { openLightbox(url) }

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

// ChatGPT 风格: 单击麦克风触发语音对话入口 — 当前为占位, 提示功能开发中
// 后续接入: 长按说话 / Web Speech API / 持续对话
function onVoiceTrigger() {
  ElMessage.info('🎤 语音对话功能开发中，目前可使用下方录音按钮')
  // 保留录音按钮入口, 后续可同时实现长按说话 / 短按占位
  toggleVoiceMode()
}

// 2026-08-15 #P4: "从资料库添加" → 跳知识库并启动选择模式
const chatCtx = useChatContextStore()
function onPickFromKnowledge() {
  if (!sessionId.value) {
    // 没 session 时, 让 useChatStream.sendMessage 自己创建一个 (line 524 已有逻辑)
    chatCtx.startSelecting('default')
  } else {
    chatCtx.startSelecting(sessionId.value)
  }
  router.push('/knowledge')
}

// InputToolPanel 触发但未实现的功能 (placeholder 提示)
function onFeatureNotReady(name: string) {
  ElMessage.info(`${name} 功能开发中，敬请期待`)
}

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
// W100 +23: 重生成 + 复制按钮 handler
// ============================================================================

/**
 * regenerate(msg): 找到目标 assistant 气泡之前的最后一个 user 消息内容,
 * 重新调 sendMessage(text) 发起新的 SSE 流式.
 *
 * 边界:
 * - 找不到前置 user (e.g. 第一条就是 welcome) → ElMessage 提示, 不发
 * - 当前正在流式生成 → 静默忽略, 让用户先点 ⏹ 停止
 * - sendMessage 内部已自动滚动 + loading 状态 + 持久化, 复用即可
 */
async function regenerate(msg: ChatMessage) {
  if (isCurrentSessionSending.value) {
    ElMessage.warning('当前正在生成中，请先点 ⏹ 停止')
    return
  }
  // 查找目标 msg 之前的最后一条 user 消息
  const list = messages.value || []
  const idx = messageIndexById.value.get(msg.id) ?? -1
  if (idx === -1) {
    ElMessage.error('找不到原始消息，无法重新生成')
    return
  }
  // 从 idx 往前找最近一条 role='user' 且 content 非空
  let userContent = ''
  for (let i = idx - 1; i >= 0; i--) {
    const m = list[i]
    if (m?.role === 'user' && (m.content || '').trim()) {
      userContent = (m.content || '').trim()
      break
    }
  }
  if (!userContent) {
    ElMessage.warning('找不到对应的用户提问，无法重新生成')
    return
  }
  ElMessage.info('正在重新生成...')
  await sendMessage(userContent)
}

/**
 * copyMessage(msg): 调 navigator.clipboard.writeText, 失败降级到 execCommand.
 *
 * 边界:
 * - 内容为空 → 不复制
 * - clipboard API 不可用 (HTTP / 老 Safari) → fallback execCommand
 * - 复制失败 → ElMessage 错误提示
 */
// 2026-08-16 #71: ChatGPT 风格 — 用户编辑消息后重发
async function onUserEditSend(payload: { msg: any; newContent: string; serverId: number; sessionId: string }) {
  await resendUserMessage({
    userMsgId: payload.msg.id,
    serverId: payload.serverId,
    sessionId: payload.sessionId,
    newContent: payload.newContent,
  })
}

async function copyMessage(msg: ChatMessage) {
  const text = (msg?.content || '').trim()
  if (!text) return
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      ElMessage.success('已复制')
      return
    }
    // 降级: execCommand
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) ElMessage.success('已复制')
    else ElMessage.error('复制失败，请手动选择文本')
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[copyMessage] failed', e)
    ElMessage.error('复制失败，请手动选择文本')
  }
}

// ============================================================================
// 生命周期
// ============================================================================
// W100 +24: 知识图谱 / 公式 / 假设入口跳转 (派工前提错配 #21: 实际 tab 路由, 非独立路由)
const router = useRouter()
function onToolJump(target: { type: 'drive' | 'task' | 'meeting'; id?: string | number }) {
  try {
    if (target.type === 'drive' && target.id != null) {
      router.push({ name: 'DriveFileDetail', params: { id: String(target.id) } })
    } else if (target.type === 'task') {
      router.push({ name: 'Tasks', query: target.id != null ? { id: String(target.id) } : {} })
    } else if (target.type === 'meeting') {
      target.id != null
        ? router.push({ name: 'MeetingDetail', params: { id: String(target.id) } })
        : router.push({ name: 'Meetings' })
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[ChatViewSSE] onToolJump router.push failed', e)
  }
}

function onProEntryClick(msg: ChatMessage, kind: 'graph' | 'formula' | 'hypothesis') {
  try {
    if (kind === 'graph') {
      // 派工前提错配 #21: 派工 brief 写 /knowledge/graph?session=&msg=, 实际路由仅 /knowledge/graph (W86 mini-3 决策)
      // 知识图谱主入口已统一到 /knowledge?tab=entities (W86 mini-3), 但 /knowledge/graph 路由保留作 fallback
      router.push({ path: '/knowledge/graph', query: { session: sessionId, msg: String(msg.id || '') } })
    } else if (kind === 'formula') {
      // 派工前提错配 #21: 派工 brief 写 /formulas?search=, 实际入口是 /knowledge?tab=formulas
      const kws = msg.intent?.keywords
      const search = Array.isArray(kws) && kws.length ? kws[0] : ''
      router.push({ path: '/knowledge', query: { tab: 'formulas', search } })
    } else if (kind === 'hypothesis') {
      // 派工前提错配 #21: 派工 brief 写 /hypotheses?from=, 实际入口是 /knowledge?tab=hypotheses
      router.push({ path: '/knowledge', query: { tab: 'hypotheses', from: String(msg.id || '') } })
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[ChatViewSSE] onProEntryClick router.push failed', e)
  }
}

onMounted(async () => {
  await nextTick()
  // #P5: 加载用户全局附加文档 (从 server, 跨刷新持久)
  chatCtx.loadFromServer()
  scrollToBottom()
  // W-N 周期: Ctrl+F 搜索
  document.addEventListener('keydown', handleSearchKeydown)
})

// #P5: 格式化附件时间 (友好显示)
function formatAttachedTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

onUnmounted(() => {
  document.removeEventListener('keydown', handleSearchKeydown)
  // useChatStream 的 onUnmounted 已处理：abort 所有 SSE + 持久化所有 session
  // 这里无需额外逻辑
})

// W-N 周期: Ctrl+F 快捷键
function handleSearchKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault()
    toggleChatSearch()
  }
}
</script>

<template>
  <div class="chat-immersive" :class="{ 'is-dragging': isDragging }">
    <!-- W101 P3-A11Y: skip-link WCAG 2.4.1 跳过导航直达主内容
         屏幕阅读器 / 纯键盘用户首个 Tab 即跳到 #chat-main
         hidden by default, focus-visible 时显示 (沿用全局 focus-visible token) -->
    <a href="#chat-main" class="skip-link" data-testid="skip-link">跳到主内容</a>
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

      <div class="chat-main" id="chat-main" role="main" aria-label="聊天对话主区域">
        <!-- v78 UI-redesign 3-zone 顶栏 — W72 B-3 子 plan ③ 起步
             (派工 v6 段 5 反馈 #3 实战: TopBarZone type hint 必含)
             (派工 v6 段 5 反馈 #4 实战: 派生新任务必含真验证)
             desktop: 4fr 4fr 4fr / mobile ≤768px: 1fr 2fr 1fr
             B-1 NavRail 在 MainLayout 已挂载 (侧栏), 本顶栏内嵌 B-2 ChatBreadcrumb -->
        <header
          class="chat-header glass glass-lg"
          :data-zone-left="TOPBAR_ZONES[0].name"
          :data-zone-center="TOPBAR_ZONES[1].name"
          :data-zone-right="TOPBAR_ZONES[2].name"
          aria-label="Chat 顶栏 3-zone 容器"
        >
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
              id="chat-header-search-toggle"
              text
              size="small"
              :class="{ 'is-active': showChatSearch }"
              aria-label="搜索当前对话"
              title="搜索当前对话 (Ctrl+F)"
              @click="toggleChatSearch"
            >
              <el-icon><Search /></el-icon>
            </el-button>
            <el-button
              id="chat-header-context-toggle"
              name="chat-header-context-toggle"
              text
              size="small"
              class="header-context-toggle"
              aria-label="AI 上下文"
              title="AI 上下文：聊天历史 / 知识引用 / 工具调用"
              @click="showContextPanel = true"
            >
              <el-icon><Notebook /></el-icon>
              <span class="btn-label">上下文</span>
            </el-button>
            <el-button
              id="chat-header-new-session"
              name="chat-header-new-session"
              type="primary"
              round
              size="default"
              class="header-new-session"
              aria-label="新建对话"
              title="新建对话"
              @click="onNewSession"
            >
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
        </header>

        <!-- 对话内搜索栏 (W-N 周期) -->
        <div class="chat-search-bar" :class="{ active: showChatSearch }">
          <span class="csb-icon"><el-icon><Search /></el-icon></span>
          <input
            ref="searchInputRef"
            :value="searchQuery"
            @input="searchQuery = ($event.target as HTMLInputElement).value; doSearch(searchQuery)"
            type="text"
            placeholder="搜索当前对话..."
            aria-label="搜索当前对话"
          />
          <span class="csb-count">{{ searchMatches.length > 0 ? `${searchIndex+1}/${searchMatches.length}` : '' }}</span>
          <div class="csb-nav">
            <button :disabled="searchMatches.length <= 1" @click="searchNav(-1)" title="上一个" aria-label="上一个匹配"><el-icon><ArrowUp /></el-icon></button>
            <button :disabled="searchMatches.length <= 1" @click="searchNav(1)" title="下一个" aria-label="下一个匹配"><el-icon><ArrowDown /></el-icon></button>
          </div>
          <button class="csb-close" @click="toggleChatSearch()" title="关闭搜索" aria-label="关闭搜索">✕</button>
        </div>

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

      <!-- W100 +45 P3-VIRTUAL RETRY: 虚拟滚动分流
           ≤ VIRTUAL_THRESHOLD 全量渲染 (与原 v-for 行为 0 差异)
           > VIRTUAL_THRESHOLD 改虚拟渲染 (absolute positioning + ChatMessageRow) -->
      <template v-if="!virtualList.isVirtualized.value">
      <TransitionGroup name="msg">
      <template v-for="(msg, idx) in messages" :key="msg.id || msg.client_msg_id || `idx-${idx}`">
        <!-- 外层 time-divider 移除（ChatMessageRow 内部已有，避免重复显示） -->

        <ChatMessageRow
          :msg="msg"
          :prev-timestamp="idx > 0 ? messages[idx-1].timestamp : null"
          :session-id="sessionId"
          :show-thinking="showThinking"
          :all-messages="messages"
          @tool-jump="onToolJump"
          @regenerate="regenerate"
          @copy="copyMessage"
          @pro-entry-click="(p: any) => onProEntryClick(p.msg, p.entry)"
          @image-open="openImage"
          @tts-play="playTTSWrap"
          @follow-up-click="onFollowUpClick"
          @quote="onQuote"
          @edit-send="onUserEditSend"
        />
      </template>
      </TransitionGroup>
      </template>

      <!-- 虚拟列表: visibleItems 内的消息 absolute 定位, virtualTop = index * itemHeight -->
      <template v-else>
        <div
          class="virtual-list-spacer"
          :style="{ position: 'relative', height: virtualList.totalHeight.value + 'px' }"
        >
          <ChatMessageRow
            v-for="entry in virtualList.visibleItems.value"
            :key="`virtual-${entry.item.id}-${entry.index}`"
            :msg="entry.item"
            :prev-timestamp="entry.index > 0 ? messages[entry.index - 1].timestamp : null"
            :session-id="sessionId"
            :show-thinking="showThinking"
            :virtual-top="entry.index * virtualList.itemHeight"
            :virtual-mode="true"
            @tool-jump="onToolJump"
            @regenerate="regenerate"
            @copy="copyMessage"
            @pro-entry-click="(p: any) => onProEntryClick(p.msg, p.entry)"
            @image-open="openImage"
            @tts-play="playTTSWrap"
            @follow-up-click="onFollowUpClick"
            @quote="onQuote"
            @edit-send="onUserEditSend"
          />
        </div>
      </template>

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

    <!-- W-N 周期: 引用回复栏 -->
    <div class="quote-bar" :class="{ active: !!quotedMessage }">
      <div v-if="quotedMessage" class="quote-preview">
        <div class="qp-author">{{ quotedMessage.author }}</div>
        <div class="qp-text">{{ quotedMessage.text }}{{ quotedMessage.text.length >= 100 ? '...' : '' }}</div>
      </div>
      <button class="qc-close" @click="clearQuote" title="取消引用">✕</button>
    </div>

    <!-- 2026-08-15 #P5: 会话顶部系统块 - 用户全局附加的参考文档 (跨 session 持久) -->
    <div v-if="chatCtx.isAttached" class="chat-attached-docs-block" role="region" aria-label="本对话参考文档">
      <div class="cad-header">
        <span class="cad-icon">📚</span>
        <span class="cad-title">本对话参考文档 ({{ chatCtx.count }})</span>
        <span class="cad-hint">AI 回答时会基于这些文档</span>
      </div>
      <div class="cad-list">
        <div
          v-for="doc in chatCtx.attachedDocuments"
          :key="doc.id"
          class="cad-doc"
          :class="{ pending: doc._pending }"
        >
          <span class="cad-doc-icon">📄</span>
          <div class="cad-doc-info">
            <div class="cad-doc-title">{{ doc.title }}</div>
            <div class="cad-doc-meta">
              {{ doc.category || '未分类' }} · 附加于 {{ formatAttachedTime(doc.attached_at) }}
              <span v-if="doc._pending" class="cad-doc-syncing">同步中...</span>
            </div>
          </div>
          <el-button link size="small" :disabled="doc._pending" @click="chatCtx.remove(doc.id)">移除</el-button>
        </div>
      </div>
      <div class="cad-footer">
        <el-button link :disabled="chatCtx.loading" @click="chatCtx.clear()">清空全部</el-button>
      </div>
    </div>

    <footer class="input-bar glass glass-lg">
      <div class="input-core">
        <!-- ChatGPT 风格: 左侧单个 "+" 按钮触发工具面板 -->
        <button
          id="chat-plus-trigger"
          name="chat-plus-trigger"
          class="plus-trigger"
          :class="{ active: toolPanelOpen }"
          aria-label="打开工具面板"
          :aria-expanded="toolPanelOpen"
          title="更多工具"
          @click="toolPanelOpen = !toolPanelOpen"
        >
          <span class="plus-icon">+</span>
        </button>
        <InputToolPanel
          v-model:visible="toolPanelOpen"
          @pick-image="triggerImageUpload"
          @pick-file="triggerFileUpload"
          @pick-from-drive="onPickFromKnowledge"
          @feature-not-ready="onFeatureNotReady"
        />
        <!-- 2026-08-16 #P5+: 已选图片/文件预览 (ChatGPT 风格缩略图) -->
        <div v-if="selectedImage || selectedFile" class="input-attachment-preview" role="region" aria-label="已选附件预览">
          <div v-if="selectedImage" class="iap-image">
            <img :src="imagePreviewUrl" :alt="selectedImage.name" />
            <div class="iap-info">
              <span class="iap-name">{{ selectedImage.name }}</span>
              <span class="iap-size">{{ formatFileSize(selectedImage.size) }}</span>
            </div>
            <button
              type="button"
              class="iap-remove"
              aria-label="移除图片"
              title="移除图片"
              @click="clearSelectedImage"
            >
              <el-icon :size="14"><Close /></el-icon>
            </button>
          </div>
          <div v-else-if="selectedFile" class="iap-file">
            <el-icon :size="20"><Document /></el-icon>
            <div class="iap-info">
              <span class="iap-name">{{ selectedFile.name }}</span>
              <span class="iap-size">{{ formatFileSize(selectedFile.size) }}</span>
            </div>
            <button
              type="button"
              class="iap-remove"
              aria-label="移除文件"
              title="移除文件"
              @click="clearSelectedFile"
            >
              <el-icon :size="14"><Close /></el-icon>
            </button>
          </div>
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
        <!-- 思考模式 dropdown: ChatGPT 风格 — 右侧 inline -->
        <ThinkingModeSwitch class="input-thinking-switch" />
        <!-- 语音按钮: ChatGPT 风格 — 麦克风图标 -->
        <button
          id="chat-voice-trigger"
          name="chat-voice-trigger"
          class="voice-trigger"
          aria-label="启动语音功能"
          title="启动语音功能"
          @click="onVoiceTrigger"
        >
          <el-icon :size="18"><Microphone /></el-icon>
        </button>
        <!-- 圆形发送按钮: ChatGPT 风格 — pill 内最右端 -->
        <button
          v-if="!isCurrentSessionSending"
          id="chat-send-btn"
          name="chat-send"
          class="send-btn-pill"
          :disabled="!inputText.trim() && !selectedImage && !selectedFile"
          aria-label="发送消息"
          title="发送消息"
          @click="sendMessage()"
        >
          发送
        </button>
        <!-- 流式中: 文字 ⏹ 停止按钮 -->
        <button
          v-else
          id="chat-stop-btn"
          name="chat-stop"
          class="stop-btn-pill"
          aria-label="停止生成"
          title="停止生成"
          @click="stopGeneration()"
        >
          停止
        </button>
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
      <div class="input-hint">Enter 发送 · Shift+Enter 换行</div>
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
    <!-- W100 +29 上下文可见性面板 -->
    <el-drawer
      v-model="showContextPanel"
      title="AI 记住了什么"
      direction="rtl"
      size="380px"
      :destroy-on-close="true"
    >
      <ContextPanel :messages="messages" />
    </el-drawer>

    <!-- 图片灯箱 (W-N 周期) -->
    <Teleport to="body">
      <div v-if="showLightbox" class="lightbox-overlay" @click="closeLightbox">
        <img :src="lightboxUrl" alt="放大图片" @click.stop />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* W101 P3-A11Y: skip-link WCAG 2.4.1
   隐藏 by default, focus-visible 时显示在左上角
   复用全局 --focus-outline-* token (W101 +1) */
.skip-link {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 9999;
  padding: 8px 14px;
  background: var(--color-primary);
  color: #ffffff;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transform: translateY(-200%);
  transition: transform 150ms ease;
}
.skip-link:focus-visible {
  transform: translateY(0);
  outline: var(--focus-outline-width) solid #ffffff;
  outline-offset: var(--focus-outline-offset);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
[data-theme="dark"] .skip-link {
  background: var(--color-primary-light);
  color: var(--color-text-primary);
}
.chat-immersive {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px);
  background: linear-gradient(180deg, #faf8f5 0%, #f5f2ed 100%);
  border-radius: 18px;
  overflow: hidden;
  position: relative;
  box-shadow: 0 4px 20px rgba(0,0,0,0.04);
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
  grid-template-columns: 4fr 4fr 4fr;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
  min-height: 71px;
  background: rgba(255,255,255,0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  box-shadow: 0 1px 0 rgba(0,0,0,0.02);
}
/* W72 B-3 移动端断点: TOPBAR_ZONES[*].mobileFr = 1 2 1 → 1fr 2fr 1fr
   (派工 v6 段 5 反馈 #6 实战: W72 起步纪律 4 项必读) */
@media (max-width: 768px) {
  .chat-header {
    grid-template-columns: 1fr 2fr 1fr;
    padding: 6px 10px;
    gap: 6px;
    min-height: 48px;
  }
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-center { display: flex; align-items: center; justify-content: center; min-width: 0; }
.header-right { display: flex; align-items: center; gap: 4px; }
.bot-avatar { background: var(--gradient-welcome-hero); }
.bot-msg-avatar {
  background: var(--gradient-welcome-hero);
  flex-shrink: 0;
  border-radius: 10px !important;
  width: 34px !important;
  height: 34px !important;
  min-width: 34px;
  --el-avatar-size: 34px;
}
.header-text { line-height: 1.2; }

/* W100 +51b: 头部上下文按钮 - icon + 文字标签 */
.header-context-toggle :deep(.el-icon) {
  font-size: 16px;
  margin-right: 4px;
  vertical-align: middle;
}
.header-context-toggle .btn-label {
  font-size: 13px;
  line-height: 1;
}
/* W100 +61 polish: Notebook 按钮 hover/focus 态 (W100 +55b 漏写) */
.header-context-toggle:hover,
.header-context-toggle:focus-visible {
  background-color: color-mix(in srgb, var(--color-primary) 10%, transparent);
  color: var(--color-primary);
}
.header-context-toggle:focus-visible {
  outline: var(--focus-outline-width, 2px) solid var(--focus-outline-color, var(--color-primary));
  outline-offset: var(--focus-outline-offset, 2px);
}
.bot-name { font-weight: 600; font-size: 15px; }
.bot-status { font-size: 12px; color: var(--color-text-secondary); display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-success); }

/* v78 UI-redesign: 思考模式 segmented control 行 (在消息区和输入栏之间) */
.thinking-switch-row {
  display: flex; align-items: center; justify-content: center;
  padding: 6px 20px;
  border-top: 1px solid var(--color-border-light);
}

.messages { flex: 1; overflow-y: auto; padding: 20px 20px 20px 12px; position: relative; background: transparent; }
/* AI 头像定位在消息左上角 */
.chat-immersive .messages > * { position: relative; }

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
.time-divider {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 16px 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.time-divider::before,
.time-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--color-border-light);
  max-width: 80px;
}

.msg-row { display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 16px; gap: 4px; }
.msg-row.user { align-items: flex-end; }
.msg-row.bot { align-items: flex-start; }

/* ===== W100 +55b 气泡视觉升级 (gradient tail + lift hover + glow) ===== */
.bubble {
  max-width: 80%;
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.6;
  overflow-wrap: break-word;
  position: relative;
  transition: transform var(--duration-normal, 200ms) var(--ease-out, ease),
              box-shadow var(--duration-normal, 200ms) var(--ease-out, ease);
}
.user-bubble {
  /* W98 a11y: --gradient-welcome-hero (#FF7A5C→#FFB347) 白字 2.5 < AA 4.5.
     改用更深 --gradient-user-bubble (#C24730→#A55E32) 白字 4.94 AA pass.
     hero avatar 仍用 --gradient-welcome-hero 保留 brand 视觉.
     关键: background-color 单独设中间色 #A55E32, axe 不解析 background-image
     渐变但能拿到 background-color. 否则白字 on transparent fallback 到 root bg
     → 1.0 contrast 触发 axe 报 fail. */
  background-color: rgb(166, 89, 51);
  background-image: var(--gradient-user-bubble);
  color: var(--el-color-white);
  border-bottom-right-radius: 4px;
  box-shadow: var(--shadow-md, 0 2px 8px rgba(0, 0, 0, 0.08));
}
/* W100 +55b: 用户气泡右上方小尾巴 (::before clip-path) */
.user-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  right: -8px;
  width: 14px;
  height: 14px;
  background: var(--gradient-user-bubble);
  clip-path: polygon(0 0, 100% 0, 0 100%);
  pointer-events: none;
}
.bot-bubble {
  background: var(--color-bg-card);
  box-shadow: 0 2px 8px rgba(0,0,0,0.03), 0 1px 2px rgba(0,0,0,0.02);
  border: 1px solid var(--color-border-light);
  border-radius: 18px 18px 18px 4px;
}
/* W100 +55b: 助手气泡左上方小尾巴 (::after clip-path) + 微光泽 (::before) */
.bot-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
  pointer-events: none;
  border-top-left-radius: 18px;
  border-top-right-radius: 18px;
}
.bot-bubble::after {
  content: '';
  position: absolute;
  top: 6px;
  left: -8px;
  width: 14px;
  height: 14px;
  background: var(--color-bg-card);
  border-left: 1px solid var(--color-border-light);
  border-bottom: 1px solid var(--color-border-light);
  clip-path: polygon(100% 0, 100% 100%, 0 0);
  pointer-events: none;
}
/* W100 +55b: hover lift */
.bubble:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.02);
}
/* W-N 视觉设计: 用户气泡卡片风格 */
.user-bubble {
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 4px 14px rgba(255,122,92,0.18), 0 1px 3px rgba(255,122,92,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  background: linear-gradient(135deg, #FF7A5C, #E85A3A);
  color: #fff;
}
.user-bubble:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255,122,92,0.22), 0 2px 4px rgba(255,122,92,0.1);
}
@media (prefers-reduced-motion: reduce) {
  .bubble,
  .bubble:hover { transform: none; transition: none; }
}
/* W100 +61 polish: print 模式适配 (省墨 + 黑底白字废 4 色墨水 → 全黑白 + 隐藏装饰元素) */
@media print {
  .bubble,
  .user-bubble,
  .bot-bubble {
    background: #fff !important;
    background-image: none !important;
    color: #000 !important;
    border: 1px solid #000 !important;
    box-shadow: none !important;
  }
  .user-bubble::before,
  .bot-bubble::before,
  .bot-bubble::after { display: none !important; }
  .msg-content-typing { mask-image: none !important; -webkit-mask-image: none !important; }
}

.tool-trace { margin-bottom: 12px; padding: 8px 12px; background: var(--color-bg-warm); border-radius: 8px; border-left: 3px solid var(--color-primary); }
.trace-item { font-size: 12px; color: var(--color-text-regular); padding: 2px 0; }
.trace-item.running { color: var(--color-primary); }
.trace-item .duration { color: var(--color-text-secondary); font-size: 11px; }

/* ===== W99 +16 P1 连续性：trace/rich_block 渐进入场 ===== */
.trace-enter-active { animation: var(--animation-fadeSlideUp); }
.trace-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.trace-leave-to { opacity: 0; }
.trace-spinner {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 4px;
  border-radius: 50%;
  border: 2px solid var(--color-primary-bg);
  border-top-color: var(--color-primary);
  animation: var(--animation-spin);
}
.rb-enter-active { animation: var(--animation-fadeSlideUp); }
.rb-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.rb-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .trace-enter-active, .rb-enter-active, .trace-spinner { animation: none; }
}

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

/* W100 +55c: 打字机 mask-image (Chrome 117+/Safari 17.4+ 支持 transition: --reveal) */
.msg-content-typing {
  --reveal: 0%;
  mask-image: linear-gradient(90deg, black 0%, black var(--reveal), transparent var(--reveal));
  -webkit-mask-image: linear-gradient(90deg, black 0%, black var(--reveal), transparent var(--reveal));
  transition: --reveal 250ms linear;
}
/* W100 +61 polish: 不支持 CSS custom property transition → 退化为完整可见 (无 mask 动画)
   Safari < 17.4 / 老 webkit 走这条, mask 失效时直接全可见 */
@supports not (transition: --reveal 1s) {
  .msg-content-typing { mask-image: none; -webkit-mask-image: none; }
}
/* W100 +61 polish: 仅支持 webkit mask 但不支持 custom property transition (Safari 15-17.3)
   强制 mask=none, 避免半遮罩锁死文本 */
@supports (-webkit-mask-image: linear-gradient(black, black)) and (not (transition: --reveal 1s)) {
  .msg-content-typing {
    -webkit-mask-image: none;
    mask-image: none;
  }
}

.rich-blocks { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.msg-error { color: var(--color-danger); font-size: 13px; margin-top: 8px; }
.msg-meta { font-size: 11px; color: var(--color-text-secondary); margin-top: 8px; display: flex; gap: 12px; }

/* ===== W99 +15 typing-bubble CSS 删除（已被 ThinkingCapsule 取代） ===== */

.welcome-hero { text-align: center; padding: 40px 20px 20px; }
.hero-avatar { background: var(--gradient-welcome-hero); margin-bottom: 12px; }
.welcome-hero h2 { font-size: 22px; margin: 0 0 6px; color: var(--color-text-primary); font-weight: 700; }
.welcome-hero p { color: var(--color-text-regular); margin: 0 0 20px; font-size: 14px; }
.quick-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.quick-btn { display: flex; align-items: center; gap: 6px; padding: 10px 18px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 20px; cursor: pointer; transition: var(--transition-all-normal); }
.quick-btn:hover { border-color: var(--color-primary); color: var(--color-primary); transform: translateY(-1px); }
.qa-icon { font-size: 18px; }

/* v77 P2.5.1: backdrop-filter + 半透 background 由 .glass 工具类提供 (assets/glass.css)
   blur 20px 降到 .glass-lg 默认 16px（dark mode 自动适配收益更大）
   border-top #eee 硬编码 → var(--color-border-light) */
.input-bar { padding: 16px 20px 8px; border-top: 1px solid var(--color-border-light); background: var(--color-bg-card); }

/* ===== 2026-08-15 #P5: 会话顶部系统块 - 全局附加文档 ===== */
.chat-attached-docs-block {
  margin: 12px 16px 4px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(255, 122, 92, 0.06), rgba(255, 179, 71, 0.04));
  border: 1.5px solid var(--color-primary, #FF7A5C);
  border-radius: 14px;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: var(--animation-fadeSlideUp);
}
.chat-attached-docs-block .cad-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chat-attached-docs-block .cad-icon {
  font-size: 18px;
}
.chat-attached-docs-block .cad-title {
  font-weight: 600;
  color: var(--color-primary);
  flex-shrink: 0;
}
.chat-attached-docs-block .cad-hint {
  color: var(--color-text-secondary);
  font-size: 11px;
  flex: 1;
  text-align: right;
}
.chat-attached-docs-block .cad-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chat-attached-docs-block .cad-doc {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  transition: background 0.12s ease;
}
.chat-attached-docs-block .cad-doc:hover {
  background: var(--color-bg-hover);
}
.chat-attached-docs-block .cad-doc.pending {
  opacity: 0.6;
}
.chat-attached-docs-block .cad-doc-icon {
  font-size: 16px;
  flex-shrink: 0;
}
.chat-attached-docs-block .cad-doc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chat-attached-docs-block .cad-doc-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-attached-docs-block .cad-doc-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  display: flex;
  gap: 8px;
  align-items: center;
}
.chat-attached-docs-block .cad-doc-syncing {
  color: var(--color-warning, #E6A23C);
  font-style: italic;
}
.chat-attached-docs-block .cad-footer {
  display: flex;
  justify-content: flex-end;
}
[data-theme="dark"] .chat-attached-docs-block {
  background: linear-gradient(135deg, rgba(255, 157, 133, 0.10), rgba(255, 192, 103, 0.06));
  border-color: rgba(255, 157, 133, 0.3);
}
.input-core {
  display: flex;
  align-items: center;
  flex-wrap: wrap;  /* 2026-08-16 #P5+: 支持附件预览块换行 */
  gap: 6px;
  background: var(--color-bg-card);
  border: 1.5px solid var(--color-border-light);
  border-radius: 28px;
  padding: 6px 6px 6px 14px;
  flex: 1;
  min-width: 0;
  transition: border-color var(--duration-fast, 150ms) var(--ease-out, ease),
              box-shadow var(--duration-fast, 150ms) var(--ease-out, ease);
}
/* W100 +55c: 输入区 focus 边框 + 3px ring — #P5: 改成淡边框 + 主色焦点 ring, 避免整条变橙和发送按钮混淆 */
.input-core:focus-within {
  border-color: color-mix(in srgb, var(--color-primary, #FF7A5C) 50%, var(--color-border-light));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary, #FF7A5C) 12%, transparent);
}
.input-hint {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-align: center;
  margin-top: 4px;
  letter-spacing: 0.02em;
}
.input-actions-left { display: flex; gap: 4px; }
.input-textarea { flex: 1; border: none; outline: none; resize: none; font: inherit; padding: 6px; max-height: 120px; background: transparent; min-width: 0; }

/* 2026-08-16 #P5+: 附件预览块 (图片缩略图 + 文件名 + 大小 + 删除) — ChatGPT 风格 */
.input-attachment-preview {
  display: flex;
  flex: 1 1 100%;  /* 撑满整行, 让 textarea 换到下一行 */
  min-width: 200px;
}
.input-attachment-preview .iap-image,
.input-attachment-preview .iap-file {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 6px;
  background: var(--color-bg-warm, #f5f7fa);
  border: 1.5px solid var(--color-primary, #FF7A5C);
  border-radius: 16px;
  max-width: 280px;
  position: relative;
}
.input-attachment-preview .iap-image img {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}
.input-attachment-preview .iap-file {
  color: var(--color-primary, #FF7A5C);
}
.input-attachment-preview .iap-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.input-attachment-preview .iap-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}
.input-attachment-preview .iap-size {
  font-size: 10px;
  color: var(--color-text-secondary);
}
.input-attachment-preview .iap-remove {
  /* #P5: 强制 20×20 圆形 (flex 容器内 button 易被拉伸/被 el-button 默认 padding 影响) */
  display: flex !important;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px !important;
  height: 20px !important;
  min-width: 20px;
  min-height: 20px;
  max-width: 20px;
  max-height: 20px;
  padding: 0 !important;
  border-radius: 50% !important;
  border: none !important;
  background: rgba(0, 0, 0, 0.06) !important;
  color: var(--color-text-secondary);
  cursor: pointer;
  flex: 0 0 auto;
  transition: background 0.15s ease, color 0.15s ease;
  -webkit-tap-highlight-color: transparent;
  line-height: 1;
  font-size: 0;
  box-sizing: border-box !important;
  aspect-ratio: 1;
}
.input-attachment-preview .iap-remove > * {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.input-attachment-preview .iap-remove:hover {
  background: var(--color-danger-bg, #fde2e2) !important;
  color: var(--color-danger, #f56c6c) !important;
}
.input-attachment-preview .iap-remove:hover {
  background: var(--color-danger-bg, #fde2e2);
  color: var(--color-danger, #f56c6c);
}
[data-theme="dark"] .input-attachment-preview .iap-image,
[data-theme="dark"] .input-attachment-preview .iap-file {
  background: var(--color-bg-warm, #2a2d35);
}

/* ChatGPT 风格: 思考模式 segmented control 在 input-core 内 (小尺寸) */
.input-thinking-switch {
  flex-shrink: 0;
  transform: scale(0.9);
  transform-origin: right center;
}
.input-actions-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

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
  min-width: 34px !important;
  height: 34px !important;
  padding: 0 14px !important;
  border-radius: 17px !important;
  background: var(--gradient-welcome-hero) !important;
  border: none !important;
  color: var(--el-color-white) !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  letter-spacing: 1px !important;
  transition: transform var(--duration-fast, 150ms) var(--ease-bounce, cubic-bezier(0.34, 1.56, 0.64, 1));
}
/* W100 +55c: send-btn hover scale + active scale */
.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
}
.send-btn:active:not(:disabled) {
  transform: scale(0.96);
}

/* ===== ChatGPT 风格: + 触发按钮 + 圆形发送 + 语音入口 ===== */
/* + 触发器: 38×38 圆角方块, 灰色背景, hover 时主色边框 */
.plus-trigger {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-warm, #f5f7fa);
  color: var(--color-text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast, 150ms) var(--ease-out, ease);
  -webkit-tap-highlight-color: transparent;
}
.plus-trigger:hover {
  border-color: var(--color-primary, #FF7A5C);
  color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg);
  transform: scale(1.04);
}
.plus-trigger:active {
  transform: scale(0.96);
}
.plus-trigger.active {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: rotate(45deg);
}
.plus-icon {
  font-size: 22px;
  font-weight: 400;
  line-height: 1;
}

/* 语音入口: 32×32 圆形按钮 (ChatGPT 风格, 与发送按钮一致尺寸) */
.voice-trigger {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast, 150ms) var(--ease-out, ease);
  -webkit-tap-highlight-color: transparent;
}
.voice-trigger:hover {
  color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg);
  transform: scale(1.04);
}
.voice-trigger:active {
  transform: scale(0.96);
}

/* 发送按钮: pill 文字按钮 (高对比 — 用"发送"文字, 用户一眼看到) */
.send-btn-pill {
  flex-shrink: 0;
  height: 32px;
  min-width: 64px;
  padding: 0 16px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #FF5722 0%, #FF7A5C 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(255, 87, 34, 0.4);
  transition: transform var(--duration-fast, 150ms) var(--ease-bounce, cubic-bezier(0.34, 1.56, 0.64, 1)),
              box-shadow var(--duration-fast, 150ms) var(--ease-out, ease);
  -webkit-tap-highlight-color: transparent;
  margin-left: 2px;
}
.send-btn-pill:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 14px rgba(255, 87, 34, 0.55);
}
.send-btn-pill:active:not(:disabled) {
  transform: scale(0.96);
}
.send-btn-pill:disabled {
  background: #c0c4cc;
  color: #ffffff;
  box-shadow: none;
  cursor: not-allowed;
}

/* 停止按钮: pill 文字按钮 */
.stop-btn-pill {
  flex-shrink: 0;
  height: 32px;
  min-width: 64px;
  padding: 0 16px;
  border-radius: 16px;
  border: none;
  background: var(--color-danger, #f56c6c);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.3);
  transition: transform var(--duration-fast, 150ms) var(--ease-out, ease);
  -webkit-tap-highlight-color: transparent;
  margin-left: 2px;
}
.stop-btn-pill:hover {
  transform: scale(1.05);
}
.stop-btn-pill:active {
  transform: scale(0.96);
}

/* 旧 mode-badge 在新布局下保留样式以防 fallback */
[data-theme="dark"] .plus-trigger {
  background: var(--color-bg-warm, #2a2d35);
  border-color: var(--color-border-base);
}
[data-theme="dark"] .voice-trigger {
  background: transparent;
  border-color: var(--color-border-base);
}

/* W-N 2026-08-14: 顶栏 ➕ 与侧栏 "新对话" 按钮避免重复显示
   - 侧栏展开时: 顶栏 ➕ 隐藏（侧栏已有显眼按钮）
   - 侧栏折叠时: 顶栏 ➕ 显示（侧栏没入口） */
.header-new-session { display: inline-flex; }
:has(.session-sidebar:not(.collapsed)) .header-new-session { display: none; }

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
/* W100 +61 polish: 用户气泡 dark mode 适配 (W100 +55b 漏写, 边框 + glow 在 dark 几乎不可见) */
[data-theme="dark"] .user-bubble {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45),
              0 0 0 1px color-mix(in srgb, var(--color-primary) 22%, transparent);
}
/* W100 +61 polish: 用户气泡小尾巴 dark mode 适配 */
[data-theme="dark"] .user-bubble::before {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
}
/* W100 +61 polish: 助手气泡小尾巴 dark mode 适配 (border + clip-path 视觉补强) */
[data-theme="dark"] .bot-bubble::after {
  border-left-color: var(--color-border-base);
  border-bottom-color: var(--color-border-base);
  box-shadow: -1px 1px 3px rgba(0, 0, 0, 0.35);
}
/* W100 +61 polish: 打字机 mask 在 dark mode 用更亮过渡边界 */
[data-theme="dark"] .msg-content-typing {
  --reveal-start: rgba(232, 234, 237, 0.92);
  --reveal-end: rgba(232, 234, 237, 0);
  mask-image: linear-gradient(90deg, var(--reveal-start) 0%, var(--reveal-start) var(--reveal), var(--reveal-end) var(--reveal));
  -webkit-mask-image: linear-gradient(90deg, var(--reveal-start) 0%, var(--reveal-start) var(--reveal), var(--reveal-end) var(--reveal));
}
/* W100 +61 polish: Notebook 按钮 dark mode hover/focus */
[data-theme="dark"] .header-context-toggle:hover,
[data-theme="dark"] .header-context-toggle:focus-visible {
  background-color: color-mix(in srgb, var(--color-primary) 18%, transparent);
  color: var(--color-primary-light);
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

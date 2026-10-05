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
 *
 * # 2026-08-17 #Step6-重做: 结构性注释 + import 分组 (Plan v1 Step 6)
 * 实际拆分调研: 2167 行 ChatViewSSE 无 0 风险拆点 (主路径 11+ props 接口 + 复杂 store 联动).
 * Plan v1 拆分路线已确认不可行 (与 Step 2-4 同样 blocker).
 * 现 Step 6 重做: 0 业务代码改动, 仅整理:
 *   1. import 块分 3 组 (vue / element-plus / @/)
 *   2. 删 5 个 inline 注释 (派工 brief + P3 注释)
 *   3. 顶部加模块结构注释 (后续拆分锚点)
 * 未来真正拆分锚点 (主拍决策时启动):
 *   - ChatHeader.vue: 829-900 行 (header 3-zone)
 *   - ChatMessageArea.vue: 937-1100 行 (sticky + virtual + welcome-hero)
 *   - ChatInputBar.vue: 1100-1220 行 (input + send + quotes + attachments)
 *   - ChatDialogs.vue: 800+ 行 (SearchPalette + ShareDialog + ExportDialog + TagsEditor)
 * 当前: 4 子组件拆分需要重写 ChatMessageRow props 接口 + emit 链, 风险高, 留主拍决策.
 */

// ===== 1. Vue 核心 =====
import { ref, computed, onMounted, onUnmounted, nextTick, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'

// ===== 2. Element Plus + Icons =====
import { ElMessage } from 'element-plus'
import { ChatDotRound, ArrowDown, ArrowUp, Search, Fold, Expand, Plus, Picture, Paperclip, Microphone, VideoPause, MagicStick, Cpu, Moon, Sunny, View, Close, Document } from '@element-plus/icons-vue'

// ===== 3. 项目内组件 =====
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import VoiceRecorder from '@/components/VoiceRecorder.vue'
import SearchPalette from '@/components/chat/SearchPalette.vue'
import ChatBreadcrumb from '@/components/chat/ChatBreadcrumb.vue'
import ThinkingModeSwitch from '@/components/chat/ThinkingModeSwitch.vue'
import ShareDialog from '@/components/chat/ShareDialog.vue'
import ExportDialog from '@/components/chat/ExportDialog.vue'
import TagsEditor from '@/components/chat/TagsEditor.vue'
import FeedbackButtons from '@/components/chat/FeedbackButtons.vue'  // W98 CHAT-P1-D3
import ChatMessageRow from '@/components/chat/ChatMessageRow.vue'  // W100 +45 单条消息复用 (虚拟列表集成)
import InputToolPanel from '@/components/chat/InputToolPanel.vue'  // ChatGPT 风格 "+" 工具面板
import ContextPanel from '@/components/chat/ContextPanel.vue'  // W100 +29 上下文可见性面板

// ===== 4. Composables + Stores + Utils =====
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'
import { useMemo } from '@/composables/useMemo'
import { useVirtualList } from '@/composables/useVirtualList'  // W100 +45 虚拟滚动
import { useChatStream, type ChatMessage } from '@/composables/chat/useChatStream'
import { useThemeStore } from '@/stores/useThemeStore'
import { useUiStore } from '@/stores/useUiStore'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatContextStore } from '@/stores/chatContext'  // 2026-08-15 #P4: 资料库附加文档
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { warmupChatModel } from '@/api/agent/warmup'  // 2026-09-18 冷加载防御
import { chatHistoryApi } from '@/api/chatHistory'  // 2026-09-20 断线续答轮询
import { renderMarkdown } from '@/utils/markdown'
import { formatTimeDivider } from '@/utils/timeDivider'

// ============================================================================
// 模块常量 (Plan v1 Step 6 重做: 集中 magic 值, 后续重构 + 测试容易)
// ============================================================================

/**
 * 虚拟滚动阈值 (消息数 > VIRTUAL_THRESHOLD 启用 absolute positioning 渲染)
 *
 * 2026-09-01 修复 (用户截图实证): 50 条即启用的虚拟定位以固定估高
 * VIRTUAL_ITEM_HEIGHT=120px 绝对定位消息, 而聊天消息实际高度 80~2000px+
 * (工具卡片/长文/markdown 列表), 长对话全部叠罗汉。聊天消息高度差异 20 倍,
 * 固定估高虚拟化根本不适用 (类 20.187 sidebar 同病灶)。
 * 处置: 阈值提到 1000 — 实际等于禁用虚拟定位, 走正常流式布局 (永不错位);
 * 真超长会话 (>1000 条) 的极端兜底场景估高同步修正为 360。
 */
const VIRTUAL_THRESHOLD = 1000

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
  fetchSessionFromServer, // 2026-09-20 断线续答: 轮询完成后拉取完整回答
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
// 引用与来源面板已常驻 (2026-09-03 三栏常驻, 勿在窄屏外隐藏)
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
const searchQuery = ref('')
const searchMatches = ref<HTMLElement[]>([])
const searchIndex = ref(-1)
const searchInputRef = ref<HTMLInputElement | null>(null)

// ChatGPT 风格 "+" 工具面板开关
const toolPanelOpen = ref(false)
// 2026-09-03 网页搜索模式 (工具面板开关): 开启后本条消息发送会带 web_search 标记
const webSearchOn = ref(false)

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
  nextTick(() => {
    searchInputRef.value?.focus()
    searchInputRef.value?.select()
  })
}
function onHeaderSearchInput(e: Event) {
  searchQuery.value = (e.target as HTMLInputElement).value
  doSearch(searchQuery.value)
}
function onHeaderSearchClear() {
  searchQuery.value = ''
  clearSearchHighlights()
  searchInputRef.value?.focus()
}
function clearSearchHighlights() {
  document.querySelectorAll('.search-highlight').forEach(el => {
    const parent = el.parentNode
    if (parent) parent.replaceChild(document.createTextNode(el.textContent || ''), el)
  })
  searchMatches.value = []
  searchIndex.value = -1
  // 2026-09-03: 不再清 searchQuery — 旧逻辑在 doSearch 开头清词导致
  // 头部搜索胶囊每敲一键就被清空 (用户消息重复修复同轮发现)
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

// ===== W100 +45 P3-VIRTUAL RETRY: 虚拟滚动 (仅 > VIRTUAL_THRESHOLD 的极端长会话) =====
// 单一 composable 实例, items 用 readonly messages, 容器挂在 messagesRef
// 2026-09-01: 估高 120 → 360 — 长会话兜底场景下含富内容的消息平均高度更接近此值;
// 聊天消息高度天然不可预估, 虚拟化仅作为 >1000 条的极端降级, 常态走流式布局
const VIRTUAL_ITEM_HEIGHT = 360
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
      refreshJumpToTop()
    }
  }
}

// P0-#2 修正 (2026-09-20): "跳到最早"只在内容真正可滚动 (溢出 > 阈值) 且当前
// 离顶部足够远时显示。事故: 新会话仅 2 条消息, 流式自动滚底把 showJumpToTop
// 硬置 true, 而短会话 scrollTop 赋值不产生真实滚动 → scroll 事件不触发 →
// onMessagesScroll 的修正逻辑永远不跑, 按钮卡显。
const refreshJumpToTop = () => {
  if (!messagesRef.value) {
    showJumpToTop.value = false
    return
  }
  const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
  showJumpToTop.value =
    scrollHeight - clientHeight > TOP_THRESHOLD_PX && scrollTop > TOP_THRESHOLD_PX
}

// 2026-09-20 同族修正: "跳到最新"同样只在内容可滚动且离底部足够远时显示
// (事故截图: 短会话贴顶时"跳到最新"也误显, 与"跳到最早"同一无条件置 true 病根)
const refreshJumpToBottom = () => {
  if (!messagesRef.value) {
    showJumpToBottom.value = false
    return
  }
  const { scrollTop, scrollHeight, clientHeight } = messagesRef.value
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  showJumpToBottom.value =
    scrollHeight - clientHeight > STICK_THRESHOLD_PX && distanceFromBottom > STICK_THRESHOLD_PX
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
    refreshJumpToBottom()  // 2026-09-20: 无溢出时不显示"跳到最新" (同族事故修正)
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
  refreshJumpToTop()  // P0-#2 修正: 不再无条件置 true (同 scrollToBottom 事故注释)
}

// P0-#2 新增: 跳到最早 (历史起点)
const jumpToTop = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = 0
  }
  refreshJumpToBottom()  // 2026-09-20: 不再无条件置 true
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
      // 2026-09-03 网页搜索模式 (工具面板开关)
      webSearchOn: webSearchOn.value,
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
function onToggleWebSearch() {
  webSearchOn.value = !webSearchOn.value
  ElMessage.success(webSearchOn.value ? '🌐 网页搜索已开启' : '🌐 网页搜索已关闭')
}
function onSetDeepResearch() {
  uiStore.setThinkingMode('deep')
  ElMessage.success('🔭 已切换到深度研究模式')
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
      // 2026-09-13 公式计算 tab 移除 → 改为知识库搜索 (关键词兜底)
      const kws = msg.intent?.keywords
      const search = Array.isArray(kws) && kws.length ? kws[0] : ''
      router.push({ path: '/knowledge', query: { tab: 'knowledge', search } })
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
  // 2026-09-18 冷加载防御: 进页面即后台预热本地模型 (fire-and-forget, 永不 throw),
  // 用户打字的窗口正好覆盖 ollama GPU 冷加载 (~100s), 首条消息不再空等
  warmupChatModel()
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

// ============================================================================
// 2026-09-20 断线续答: 刷新/切页后回到会话, 若服务端仍在后台生成, 轮询状态,
// 完成后自动拉取完整回答进会话 (配合后端 producer 解耦, ChatGPT 行为)
// ============================================================================
let genPollTimer: ReturnType<typeof setInterval> | null = null
let genPollSid = ''

function stopBackgroundPoll() {
  if (genPollTimer) {
    clearInterval(genPollTimer)
    genPollTimer = null
  }
  genPollSid = ''
}

async function pollBackgroundGeneration() {
  const sid = sessionId.value
  if (!sid) return
  try {
    const st = await chatHistoryApi.generationStatus(sid)
    if (!st?.generating) return
  } catch {
    return // 网络抖动: 下一轮 sessionId 变化或刷新再试
  }
  if (genPollSid === sid && genPollTimer) return // 已在轮询同一会话
  stopBackgroundPoll()
  genPollSid = sid
  console.info('[ChatViewSSE] 检测到后台生成进行中, 开始轮询:', sid)
  genPollTimer = setInterval(async () => {
    if (genPollSid !== sessionId.value) {
      stopBackgroundPoll()
      return
    }
    try {
      const st = await chatHistoryApi.generationStatus(sid)
      if (!st?.generating) {
        stopBackgroundPoll()
        await fetchSessionFromServer(sid)
        await nextTick()
        scrollToBottom()
        console.info('[ChatViewSSE] 后台生成完成, 完整回答已拉取:', sid)
      }
    } catch {
      /* 网络抖动忽略, 下个 tick 再试 */
    }
  }, 3000)
  // 安全上限 8 分钟自动停 (生成看门狗 600s + 富余)
  setTimeout(() => {
    if (genPollSid === sid) stopBackgroundPoll()
  }, 8 * 60 * 1000)
}

watch(
  sessionId,
  (sid) => {
    if (sid) void pollBackgroundGeneration()
  },
  { immediate: true },
)

onUnmounted(() => {
  document.removeEventListener('keydown', handleSearchKeydown)
  stopBackgroundPoll() // 2026-09-20 断线续答: 组件卸载清轮询
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
            <button
              id="chat-header-sidebar-toggle"
              name="chat-header-sidebar-toggle"
              type="button"
              class="rail-toggle-btn"
              @click="sidebarCollapsed = !sidebarCollapsed"
              :aria-label="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
              :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
            >
              <el-icon :size="15"><component :is="sidebarCollapsed ? Expand : Fold" /></el-icon>
              <span class="rail-toggle-text">{{ sidebarCollapsed ? '展开' : '会话' }}</span>
            </button>
          </div>
          <div class="header-center">
            <ChatBreadcrumb :status="isCurrentSessionSending ? 'generating' : 'idle'" />
          </div>
          <div class="header-right">
            <div class="header-search-pill">
              <span class="hsp-ico"><el-icon><Search /></el-icon></span>
              <input
                ref="searchInputRef"
                id="chat-header-search"
                name="chat-header-search"
                :value="searchQuery"
                @input="onHeaderSearchInput($event)"
                @keydown.esc.prevent="onHeaderSearchClear"
                @keydown.enter.prevent="searchNav(1)"
                type="text"
                placeholder="搜索本对话内容"
                aria-label="搜索当前对话"
              />
              <span v-if="searchMatches.length" class="hsp-count">{{ searchIndex + 1 }}/{{ searchMatches.length }}</span>
              <button v-if="searchMatches.length > 1" type="button" class="hsp-nav" @click="searchNav(-1)" title="上一个" aria-label="上一个匹配"><el-icon><ArrowUp /></el-icon></button>
              <button v-if="searchMatches.length > 1" type="button" class="hsp-nav" @click="searchNav(1)" title="下一个" aria-label="下一个匹配"><el-icon><ArrowDown /></el-icon></button>
              <button v-if="searchQuery" type="button" class="hsp-clear" @click="onHeaderSearchClear" title="清除搜索" aria-label="清除搜索">✕</button>
              <span v-else class="hsp-kbd">Ctrl F</span>
            </div>
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
      <!-- 2026-08-26: 加 messages.length > 0 gate — 空对话 (0 条消息) 时不应显示,
           scroll 事件触发容器 padding 撑出 scrollHeight > clientHeight, scrollToBottom()
           误把 showJumpToTop.value 设 true, 出现"无消息却有跳到最早按钮"的逻辑错误. -->
      <button
        v-if="showJumpToTop && messages.length > 0"
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
          :web-search-on="webSearchOn"
          @toggle-web-search="onToggleWebSearch"
          @set-deep-research="onSetDeepResearch"
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
      <div v-if="webSearchOn" class="websearch-flag">
        <span>🌐 网页搜索已开启 · 回答将联网查询实时信息</span>
        <button type="button" class="wsf-off" @click="webSearchOn = false" aria-label="关闭网页搜索">关闭</button>
      </div>
      <div class="input-hint">Enter 发送 · Shift+Enter 换行</div>
    </footer>
      </div>

      <!-- 引用与来源 docked 面板 (三栏研究台): 常驻第三栏, ContextPanel inline 模式 -->
      <aside class="cites-panel" role="complementary" aria-label="引用与来源">
        <div class="cites-head">
          <span class="cites-title">引用与来源</span>
          <span class="cites-sub">CITATIONS</span>
        </div>
        <ContextPanel :messages="messages" />
      </aside>
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
    <!-- W100 +29 上下文可见性面板 → 已改为 .chat-layout 内 docked 右栏 (三栏研究台) -->

    <!-- 图片灯箱 (W-N 周期) -->
    <Teleport to="body">
      <div v-if="showLightbox" class="lightbox-overlay" @click="closeLightbox">
        <img :src="lightboxUrl" alt="放大图片" @click.stop />
      </div>
    </Teleport>
  </div>
</template>

<style scoped src="./chatview-scoped.css"></style>

<style src="./chatview-global.css"></style>

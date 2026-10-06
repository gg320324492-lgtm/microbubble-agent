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
 *
 * # 2026-10-07 #L-1 script 拆分落地 (本文件 ~927 行 script 拆出 ~690 行)
 * 行为测试先行 (ChatViewSSE.behavior.test.js 24 用例) 后拆, template/style 未动:
 *   - composables/chat/useChatViewScroll.ts        智能 sticky scroll + 跳到最早/最新 + 虚拟列表降级
 *   - composables/chat/useChatViewSearch.ts        对话内搜索 + 全局快捷键 (Ctrl+F / mod+k)
 *   - composables/chat/useChatViewComposer.ts      发送流程 + 输入/附件/引用/录音/重生成/复制
 *   - composables/chat/useChatViewBackgroundPoll.ts 断线续答轮询 (2026-09-20)
 * 铁律: useChatStream 状态是 per-call 闭包, 四模块全部依赖显式注入,
 *       模块内不得二次调用 useChatStream() (会拿到断开的新状态)。
 * 本文件保留: 顶栏 3-zone / 侧栏折叠 / 主题与思考模式 store / 4 个对话框 /
 *            路由跳转 (onToolJump/onProEntryClick) / onMounted 生命周期 / 附加文档块。
 */

// ===== 1. Vue 核心 =====
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'

// ===== 2. Element Plus + Icons =====
// (ElMessage 已随输入/发送逻辑迁至 useChatViewComposer, L-1)
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
import { useChatStream, type ChatMessage } from '@/composables/chat/useChatStream'
import { useChatViewScroll } from '@/composables/chat/useChatViewScroll'            // L-1
import { useChatViewSearch } from '@/composables/chat/useChatViewSearch'            // L-1
import { useChatViewComposer } from '@/composables/chat/useChatViewComposer'        // L-1
import { useChatViewBackgroundPoll } from '@/composables/chat/useChatViewBackgroundPoll'  // L-1
import { useThemeStore } from '@/stores/useThemeStore'
import { useUiStore } from '@/stores/useUiStore'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatContextStore } from '@/stores/chatContext'  // 2026-08-15 #P4: 资料库附加文档
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { warmupChatModel } from '@/api/agent/warmup'  // 2026-09-18 冷加载防御

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

// ============================================================================
// L-1 (2026-10-07): 四个行为模块 (依赖显式注入, 见文件头铁律)
// 顺序即依赖: scroll 先建 → composer / backgroundPoll 注入 scrollToBottom
// ============================================================================
const {
  messagesRef,
  showJumpToBottom,
  showJumpToTop,
  virtualList,
  scrollToBottom,
  onMessagesScroll,
  jumpToBottom,
  jumpToTop,
} = useChatViewScroll({ messages, sessionId })

const {
  searchQuery,
  searchMatches,
  searchIndex,
  searchInputRef,
  showSearchPalette,
  onHeaderSearchInput,
  onHeaderSearchClear,
  searchNav,
} = useChatViewSearch()

const {
  inputText,
  isDragging,
  textareaRef,
  selectedImage,
  imagePreviewUrl,
  selectedFile,
  voiceMode,
  imageInputRef,
  fileInputRef,
  toolPanelOpen,
  webSearchOn,
  lightboxUrl,
  showLightbox,
  closeLightbox,
  quotedMessage,
  clearQuote,
  clearSelectedImage,
  clearSelectedFile,
  formatFileSize,
  sendMessage,
  quickActions,
  handleKeydown,
  autoResize,
  sendQuickMessage,
  triggerImageUpload,
  triggerFileUpload,
  onFollowUpClick,
  openImage,
  handleImageSelect,
  handleFileSelect,
  onDragOver,
  onDragLeave,
  onDrop,
  onVoiceTrigger,
  onPickFromKnowledge,
  onToggleWebSearch,
  onSetDeepResearch,
  onRecordStart,
  onRecordStop,
  onRecordError,
  playTTSWrap,
  regenerate,
  onUserEditSend,
  copyMessage,
} = useChatViewComposer({
  messages,
  sessionId,
  isCurrentSessionSending,
  sendMessageCore,
  playTTS,
  asrRecognize,
  resendUserMessage,
  scrollToBottom,
})

// 2026-09-20 断线续答: 回到会话即轮询后台生成, 完成自动拉取完整回答
// (模块内部 sessionId watch immediate + onUnmounted 清轮询, 原视图级 watch/onUnmounted 语义等价迁移)
useChatViewBackgroundPoll({ sessionId, fetchSessionFromServer, scrollToBottom })

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
// UI 状态（仅桌面端, L-1 后留守部分）
// ============================================================================
const sidebarCollapsed = ref(false)
// 引用与来源面板已常驻 (2026-09-03 三栏常驻, 勿在窄屏外隐藏)

// 网络状态
const { online: isOnline } = useNetworkStatus()

// #043 Phase 6 UI 升级：分享 / 导出 / 标签编辑 (全局搜索面板已迁 useChatViewSearch)
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

// 2026-08-15 #P4: 聊天 ↔ 知识库 附加文档 (模板绑定 + onMounted 加载)
const chatCtx = useChatContextStore()

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
  // (W-N Ctrl+F 搜索 keydown 已随搜索逻辑迁至 useChatViewSearch 的 onMounted/onUnmounted;
  //  2026-09-20 断线续答轮询清理已迁至 useChatViewBackgroundPoll 的 onUnmounted —— 语义等价)
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

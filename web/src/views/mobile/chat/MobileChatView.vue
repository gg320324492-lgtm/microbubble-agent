<template>
  <!-- W68 G-2 (2026-07-24): MobileSwipeNavigation 包装, 左右滑切换上一个/下一个会话 -->
  <MobileSwipeNavigation
    ref="swipeNavRef"
    :left-action="swipeToNextSession"
    :right-action="swipeToPrevSession"
    :threshold="50"
    aria-label="会话左右滑切换"
  >
  <div class="mobile-chat-root">
    <MobileHeader
      :title="currentTitle"
      :is-active="isCurrentSessionSending"
      :is-dark="isDark"
      @open-menu="showDrawer = true"
      @toggle-theme="onToggleTheme"
      @search="onOpenSearch"
    />

    <MobileSessionDrawer
      v-model="showDrawer"
      :sessions="sessionsList"
      :current-id="sessionId"
      @create="handleCreateSession"
      @switch="handleSwitchSession"
      @search="onOpenSearch"
      @share="onShareSession"
      @export="onExportSession"
      @edit-tags="onEditTagsSession"
      @rename="onRenameSession"
      @delete="onDeleteSession"
      @toggle-pin="onTogglePinSession"
    />

    <main
      class="chat-main"
      :style="{ paddingBottom: messagesPaddingBottom }"
    >
      <MobileMessageList
        ref="messageListRef"
        :messages="messages"
        @longpress="onLongPress"
        @play-tts="onPlayTTS"
        @quick-action="onQuickAction"
      />
    </main>

    <MobileInputBar
      v-model="inputText"
      :selected-image="selectedImage"
      :selected-file="selectedFile"
      :input-padding-bottom="inputPaddingBottom"
      :is-sending="isCurrentSessionSending"
      @send="sendMessage"
      @stop="onStopGeneration"
      @image="triggerImage"
      @file="triggerFile"
      @voice-start="onVoiceStart"
      @voice-end="onVoiceEnd"
      @focus="onInputFocus"
      @clear-image="clearImage"
      @clear-file="clearFile"
    />

    <!-- 长按消息弹出的 ActionSheet -->
    <Teleport to="body">
      <Transition name="action-sheet">
        <div v-if="actionSheet.visible" class="action-sheet-overlay" @click.self="actionSheet.visible = false">
          <div class="action-sheet-panel">
            <button
              type="button"
              class="action-item"
              @click="copyMessage"
            >
              <span>📋</span>
              <span>复制</span>
            </button>
            <button
              v-if="actionSheet.msg?.role === 'user'"
              type="button"
              class="action-item danger"
              @click="deleteMessage"
            >
              <span>🗑</span>
              <span>删除</span>
            </button>
            <button
              type="button"
              class="action-item cancel"
              @click="actionSheet.visible = false"
            >取消</button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <input
      ref="imageInputRef"
      id="chat-image-upload-mobile"
      name="chat-image-upload-mobile"
      type="file"
      accept="image/*"
      capture="environment"
      hidden
      :aria-label="'上传图片'"
      :title="'上传图片'"
      @change="handleImageSelect"
    />
    <input
      ref="fileInputRef"
      id="chat-file-upload-mobile"
      name="chat-file-upload-mobile"
      type="file"
      hidden
      :aria-label="'上传文件'"
      :title="'上传文件'"
      @change="handleFileSelect"
    />

    <!-- #043 Phase 6: 移动端搜索 sheet / 分享 / 导出 / 标签编辑 dialog -->
    <MobileSearchSheet
      v-if="showSearch"
      v-model:show="showSearch"
      title="搜索会话"
      placeholder="输入关键词（按消息内容）"
      @confirm="onSearchConfirm"
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
  </MobileSwipeNavigation>
</template>

<script setup>
/**
 * MobileChatView.vue — 移动端 Chat 独立页面
 *
 * PR #3: 移动端深度定制
 * - 共用 useChatStream（桌面/移动 SSE 核心 0 分叉）
 * - 长按消息气泡 → ActionSheet（复制/删除）
 * - 键盘自适应（useKeyboardInset）
 * - 录音按钮：移动端原生交互（touchstart/end）
 * - 触觉反馈（useHaptic）
 *
 * 关键纪律（绝不可破坏）：
 * - per-session 数据隔离（useChatStream 内部）
 * - targetSessionId 闭包（sendMessage 启动时捕获）
 * - 切会话不 abort 后台 SSE
 */

import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStream } from '@/composables/chat/useChatStream'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useThemeStore } from '@/stores/useThemeStore'
import { useKeyboardInset } from '@/composables/chat/useKeyboardInset'
import { useHaptic } from '@/composables/chat/useHaptic'
import MobileHeader from './MobileHeader.vue'
import MobileSessionDrawer from './MobileSessionDrawer.vue'
import MobileMessageList from './MobileMessageList.vue'
import MobileInputBar from './MobileInputBar.vue'
// W68 G-2 (2026-07-24): 左右滑切换会话包装
import MobileSwipeNavigation from '@/components/mobile/MobileSwipeNavigation.vue'
// #043 Phase 6
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import ShareDialog from '@/components/chat/ShareDialog.vue'
import ExportDialog from '@/components/chat/ExportDialog.vue'
import TagsEditor from '@/components/chat/TagsEditor.vue'
import { ElMessageBox } from 'element-plus'

const theme = useThemeStore()
const haptic = useHaptic()
const sessionsStore = useChatSessionsStore()

// SSE 多会话并行核心（桌面/移动共用）
const {
  sessionId,
  messages,
  messagesBySession,
  isCurrentSessionSending,
  onCreateSession: streamOnCreateSession,
  onSwitchSession: streamOnSwitchSession,
  sendMessage: sendMessageStream,
  stopGeneration,  // 2026-06-14 方案 C Stage 5 收尾
  playTTS,
  asrRecognize,
} = useChatStream()

const { inputPaddingBottom, messagesPaddingBottom } = useKeyboardInset()

const isDark = computed(() => theme.isDark)
const inputText = ref('')
const selectedImage = ref(null)
const selectedFile = ref(null)

// #043 Phase 6
const showSearch = ref(false)
const showShareDialog = ref(false)
const showExportDialog = ref(false)
const showTagsEditor = ref(false)
const dialogSession = ref(null)

function onOpenSearch() {
  showSearch.value = true
}

async function onSearchConfirm({ keyword }) {
  if (!keyword || keyword.length < 2) {
    ElMessage.warning('请输入至少 2 个字符')
    return
  }
  // 复用桌面 SearchPalette 数据流：调 store + 把结果显示
  const { useChatHistoryStore } = await import('@/stores/chatHistory')
  const result = await useChatHistoryStore().searchSessions(keyword)
  if (!result.items?.length) {
    ElMessage.info(`没有找到包含「${keyword}」的会话`)
    return
  }
  // 简化 UX：弹 ElMessageBox.alert 显示前 5 条结果
  const top = result.items.slice(0, 5)
  const lines = top.map((it) => `• ${it.session_title}：${it.snippet}`).join('\n')
  ElMessageBox.alert(lines, `${result.total} 条匹配`, {
    confirmButtonText: '知道了',
  }).catch(() => {})
}

function onShareSession(s) {
  dialogSession.value = s
  showShareDialog.value = true
}
function onExportSession(s) {
  dialogSession.value = s
  showExportDialog.value = true
}
function onEditTagsSession(s) {
  dialogSession.value = s
  showTagsEditor.value = true
}
function onRenameSession(s) {
  // 复用 desktop 模式：弹 ElMessageBox.prompt
  ElMessageBox.prompt('新会话标题：', '重命名', {
    inputValue: s.title,
    confirmButtonText: '保存',
    cancelButtonText: '取消',
  }).then(({ value }) => {
    sessionsStore.renameSession(s.id, value.trim() || s.title)
    ElMessage.success('已重命名')
  }).catch(() => {})
}
async function onDeleteSession(s) {
  try {
    await ElMessageBox.confirm(`删除会话「${s.title}」？此操作不可撤销。`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    sessionsStore.deleteSession(s.id)
    ElMessage.success('已删除')
  } catch {}
}
async function onTogglePinSession(s) {
  await sessionsStore.setPinned(s.id, !s.is_pinned)
  ElMessage.success(s.is_pinned ? '已收藏' : '已取消收藏')
}
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const messageListRef = ref(null)
const showDrawer = ref(false)
// W68 G-2 (2026-07-24): swipe 包装 ref (调试/测试)
const swipeNavRef = ref(null)

// 会话列表（供 MobileSessionDrawer）
const sessionsList = computed(() => sessionsStore.sortedSessions)

// 当前标题
const currentTitle = computed(() => {
  const session = sessionsStore.currentSession()
  const title = session?.title || '小气'
  // 2026-06-25: 限制 MobileHeader 标题最多 10 字 + 截断符
  // 防止 localStorage 残留 session.title 是用户消息全文
  return title.length > 10 ? title.slice(0, 10) + '…' : title
})

const actionSheet = ref({
  visible: false,
  msg: null,
})

// ============================================================================
// 主题切换
// ============================================================================
function onToggleTheme() {
  haptic.tap()
  theme.toggle()
}

// ============================================================================
// 发送消息
// ============================================================================
// 关键设计：发送消息是**用户主动行为**，必须**强制**滚到底（force=true）
// 不受 MobileMessageList 的 isAtBottom 守卫影响（用户在底部以上时也要能看到自己发的内容）
// 与桌面端 ChatViewSSE.sendMessage 一致：force=true 跳过 sticky scroll 守卫
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text && !selectedImage.value && !selectedFile.value) return
  haptic.tap()
  // 2026-06-14 修复：发送前**强制**滚到底（nextTick + force=true），
  // 跳过 isAtBottom 守卫，确保 user 消息立刻可见
  nextTick(() => messageListRef.value?.scrollToBottom(true))
  // 2026-06-25 修复：乐观清空输入框（移到 await 之前）
  // 之前: inputText.value = '' 在 await 之后，导致 race condition / 异步异常吞掉时输入框残留
  const pendingText = text
  const pendingFile = selectedFile.value
  const pendingImage = selectedImage.value
  inputText.value = ''
  selectedImage.value = null
  selectedFile.value = null
  try {
    await sendMessageStream({
      text: pendingText,
      file: pendingFile,
      image: pendingImage,
    })
  } catch (e) {
    // 发送失败，回滚（useChatStream 内部 try/catch 不 rethrow，但保险起见）
    inputText.value = pendingText
    selectedFile.value = pendingFile
    selectedImage.value = pendingImage
    throw e
  }
  // 2026-06-14 修复：发送后**强制**滚到底，让 assistant 占位（typing bubble）可见
  nextTick(() => messageListRef.value?.scrollToBottom(true))
}

function onStopGeneration() {
  // 2026-06-14 方案 C Stage 5 收尾：停止当前流式生成
  haptic.tap()
  stopGeneration()
}



// ============================================================================
// 文件上传
// ============================================================================
function triggerImage() {
  imageInputRef.value?.click()
}
function triggerFile() {
  fileInputRef.value?.click()
}
function handleImageSelect(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (!f.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.error('图片不超过10MB')
    return
  }
  selectedImage.value = f
  e.target.value = ''
}
function handleFileSelect(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (f.size > 50 * 1024 * 1024) {
    ElMessage.error('文件不超过50MB')
    return
  }
  selectedFile.value = f
  e.target.value = ''
}
function clearImage() {
  selectedImage.value = null
}
function clearFile() {
  selectedFile.value = null
}

// ============================================================================
// 录音（移动端原生交互）
// ============================================================================
let mediaRecorder = null
let audioChunks = []
async function onVoiceStart() {
  haptic.tap()
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream)
    audioChunks = []
    mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data)
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      audioChunks = []
      const text = await asrRecognize(blob)
      if (text) {
        inputText.value = text
        await sendMessage()
      }
    }
    mediaRecorder.start()
  } catch (e) {
    ElMessage.error(e.message || '麦克风权限被拒绝')
  }
}
function onVoiceEnd() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
}

function onInputFocus() {
  nextTick(() => messageListRef.value?.scrollToBottom(true))
}

// ============================================================================
// 长按消息 → ActionSheet
// ============================================================================
function onLongPress(msg) {
  haptic.warning()
  actionSheet.value = { visible: true, msg }
}

async function copyMessage() {
  const text = actionSheet.value.msg?.content || ''
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text)
    } else {
      // fallback
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
  actionSheet.value.visible = false
}

// 删除用户消息（直接操作 messagesBySession，前端 filter 模式）
// 注：后端暂无 DELETE chat/messages/{id} API，本地状态从 messagesBySession 中删除
// 持久化在 useChatStream 内部处理（debounce 100ms 自动写 localStorage）
function deleteMessage() {
  const target = actionSheet.value.msg
  if (!target) return
  const sid = sessionId.value
  const list = messagesBySession.value[sid]
  if (!Array.isArray(list)) {
    actionSheet.value.visible = false
    return
  }
  // 用 timestamp + content 前 30 字兜底定位（msg 可能没 id）
  const idx = list.findIndex((m) => m === target)
  if (idx >= 0) {
    list.splice(idx, 1)
    ElMessage.success('已删除')
  } else {
    ElMessage.warning('未找到该消息')
  }
  actionSheet.value.visible = false
}

// ============================================================================
// 快捷指令
// ============================================================================
function onQuickAction(text) {
  haptic.tap()
  inputText.value = text
  sendMessage()
}

// ============================================================================
// 会话操作
// ============================================================================
function handleCreateSession() {
  haptic.tap()
  streamOnCreateSession()
  showDrawer.value = false
  nextTick(() => messageListRef.value?.scrollToBottom(true))
}

function handleSwitchSession(id) {
  haptic.tap()
  streamOnSwitchSession(id)
  showDrawer.value = false
  nextTick(() => messageListRef.value?.scrollToBottom(true))
}

// W68 G-2 (2026-07-24): 左右滑切换会话
// 向左滑 = 下一个会话, 向右滑 = 上一个会话
// 跳过空 list / 单会话场景 (无可切换目标)
function swipeToNextSession() {
  if (!sessionsList.value || sessionsList.value.length < 2) return
  const idx = sessionsList.value.findIndex((s) => s.id === sessionId.value)
  const nextIdx = idx < sessionsList.value.length - 1 ? idx + 1 : 0
  handleSwitchSession(sessionsList.value[nextIdx].id)
}
function swipeToPrevSession() {
  if (!sessionsList.value || sessionsList.value.length < 2) return
  const idx = sessionsList.value.findIndex((s) => s.id === sessionId.value)
  const prevIdx = idx > 0 ? idx - 1 : sessionsList.value.length - 1
  handleSwitchSession(sessionsList.value[prevIdx].id)
}

// ============================================================================
// TTS 播放
// ============================================================================
async function onPlayTTS(text) {
  await playTTS(text)
}

// ============================================================================
// 生命周期
// ============================================================================
onMounted(() => {
  // 初始 scroll to bottom
  nextTick(() => messageListRef.value?.scrollToBottom(true))
})
</script>

<style scoped>
.mobile-chat-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: var(--vh, 100vh);
  background: var(--color-bg-page);
}

[data-theme="dark"] .mobile-chat-root {
  background: var(--color-bg-page);
}

.chat-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  /* paddingBottom 由 messagesPaddingBottom 动态控制（输入栏 + 键盘 + safe-area） */
}

/* ActionSheet */
.action-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.action-sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 16px calc(16px + var(--sab, 0px));
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: calc(var(--tabbar-height, 56px));
}
.action-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--color-bg-page);
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.action-item:active {
  background: var(--color-bg-hover);
}
.action-item.danger {
  color: var(--color-danger, #F56C6C);
}
.action-item.cancel {
  background: var(--color-bg-card);
  font-weight: 500;
  margin-top: 4px;
}

.action-sheet-enter-active,
.action-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.action-sheet-enter-active .action-sheet-panel,
.action-sheet-leave-active .action-sheet-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.action-sheet-enter-from,
.action-sheet-leave-to {
  opacity: 0;
}
.action-sheet-enter-from .action-sheet-panel,
.action-sheet-leave-to .action-sheet-panel {
  transform: translateY(100%);
}
</style>
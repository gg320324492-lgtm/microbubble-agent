<script setup lang="ts">
/**
 * ChatMessageRow.vue — 单条消息渲染 (W100 +45 P3-VIRTUAL RETRY)
 *
 * 提取 ChatViewSSE.messages v-for 内部单一消息的全部子节点到独立组件,
 * 使 ChatViewSSE 与未来虚拟列表渲染复用同一段逻辑, 0 行为差异.
 *
 * 数据契约:
 * - msg: ChatMessage (from useChatStream)
 * - prevTimestamp: 上一条消息的时间戳 (用于 >5min 时显示时间分隔符)
 * - sessionId: 当前会话 id (给 FeedbackButtons / FollowUpChips 用)
 * - showThinking: 全局思考模式开关 (给 ToolTraceItem 用)
 * - disabled: 虚拟列表中非 visible 但已渲染的占位项 (动画/click 禁用)
 *
 * 事件透传 (与原 v-for 块 1:1 对应):
 * - @tool-jump (ToolTraceItem -> ChatViewSSE.onToolJump)
 * - @regenerate (ChatMessageActions -> ChatViewSSE.regenerate)
 * - @copy (ChatMessageActions -> ChatViewSSE.copyMessage)
 * - @pro-entry-click (ProEntries -> ChatViewSSE.onProEntryClick)
 * - @image-open (ImageWithFallback -> ChatViewSSE.openImage)
 * - @tts-play (el-button -> ChatViewSSE.playTTSWrap)
 * - @follow-up-click (FollowUpChips -> ChatViewSSE.onFollowUpClick)
 */
import { computed, ref, watch, nextTick } from 'vue'
import { ChatDotRound, Headset, Document } from '@element-plus/icons-vue'
import { useChatContextStore } from '@/stores/chatContext'
import ThinkingCapsule from '@/components/chat/ThinkingCapsule.vue'
import PlanSteps from '@/components/chat/PlanSteps.vue'
import ToolTraceItem from '@/components/chat/ToolTraceItem.vue'
import ContentBriefDetail from '@/components/chat/ContentBriefDetail.vue'
import EventBadges from '@/components/chat/EventBadges.vue'
import ImageWithFallback from '@/components/chat/ImageWithFallback.vue'
import ChatMessageActions from '@/components/chat/ChatMessageActions.vue'
import ProEntries from '@/components/chat/ProEntries.vue'
import FeedbackButtons from '@/components/chat/FeedbackButtons.vue'
import FollowUpChips from '@/components/chat/FollowUpChips.vue'
import RichContent from '@/components/chat/RichContent.vue'
import { renderMarkdown } from '@/utils/markdown'
import { formatTimeDivider } from '@/utils/timeDivider'
import type { ChatMessage } from '@/composables/chat/useChatStream'

// #P5+: 消息气泡显示附加文档列表 (消息级附件)
const chatCtx = useChatContextStore()
function attachedDocsById(ids?: number[]) {
  if (!ids || ids.length === 0) return []
  return chatCtx.getDocsByIds(ids)
}

const props = withDefaults(defineProps<{
  msg: ChatMessage
  prevTimestamp?: string | null
  sessionId: string
  showThinking?: boolean
  disabled?: boolean
  /** 虚拟列表中由外部传入的 top offset (px), 用于绝对定位 */
  virtualTop?: number
  /** 虚拟列表模式: 渲染为绝对定位 div, 不渲染 TimeDivider (由外部统一管) */
  virtualMode?: boolean
  /** W-N 2026-08-14: 同一天不重复 time-divider 判断用 */
  allMessages?: ChatMessage[]
}>(), {
  showThinking: false,
  disabled: false,
  virtualTop: 0,
  virtualMode: false,
  allMessages: undefined,
})

const emit = defineEmits<{
  (e: 'tool-jump', payload: any): void
  (e: 'regenerate', msg: ChatMessage): void
  (e: 'copy', msg: ChatMessage): void
  (e: 'pro-entry-click', payload: { msg: ChatMessage, entry: any }): void
  (e: 'image-open', url: string): void
  (e: 'tts-play', text: string): void
  (e: 'follow-up-click', payload: any): void
  (e: 'quote', payload: any): void
  // 2026-08-16 #71: ChatGPT 风格 — 编辑用户消息后重发
  (e: 'edit-send', payload: { msg: ChatMessage; newContent: string; serverId: number; sessionId: string }): void
}>()

const hasTimeDivider = computed(() => {
  if (props.virtualMode) return false  // 虚拟模式由外部统一渲染分隔
  if (!props.prevTimestamp) return false
  return new Date(props.msg.timestamp).getTime() - new Date(props.prevTimestamp).getTime() > 5 * 60 * 1000
})

// 2026-09-03 档案语言 (A 方案): 条目序号 / 问条时间 / 工具名汇总
const displayIndex = computed(() => {
  if (!props.allMessages) return 0
  return props.allMessages.findIndex((m) => m.id === props.msg.id) + 1
})
const userTime = computed(() => {
  try {
    return new Date(props.msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return ''
  }
})
const dossierToolNames = computed(() => {
  const names = (props.msg.toolTrace || [])
    .map((t: any) => t?.name || t?.label)
    .filter((n: any): n is string => !!n)
  return [...new Set(names)].join(' / ')
})

const timeDividerText = computed(() => {
  if (!hasTimeDivider.value || !props.prevTimestamp) return ''
  // W-N 2026-08-14: 同一天不重复显示（避免"今天 02:07"在每条消息前都出现）
  if (props.allMessages && props.msg.id) {
    const today = new Date(props.msg.timestamp).toDateString()
    const alreadyShown = props.allMessages.some(m =>
      m.id !== props.msg.id &&
      new Date(m.timestamp).toDateString() === today
    )
    if (alreadyShown) return ''
  }
  // W100 +55c: 三档 (今天/昨天/YYYY-MM-DD) — 沿用 utils/timeDivider
  return formatTimeDivider(new Date(props.msg.timestamp), new Date())
})

/**
 * W100 +55c: 打字机 mask — 流式中 reveal 进度
 * 仅 assistant 流式生成中(state !== 'idle')显示 typing mask
 * reveal = min(100, length/80 * 100), 80 字约 100% (打字机平均速度)
 */
const revealProgress = ref(100)  // idle 默认满
const isStreaming = computed(() => props.msg.state !== 'idle' && props.msg.role === 'assistant')
watch(
  () => [props.msg.state, props.msg.content] as const,
  ([state, content]) => {
    if (state === 'idle') {
      revealProgress.value = 100
    } else {
      const len = (content || '').length
      revealProgress.value = Math.min(100, Math.max(0, (len / 80) * 100))
    }
  },
  { immediate: true },
)
const msgContentClass = computed(() => [
  'msg-content',
  isStreaming.value ? 'msg-content-typing' : '',
])
const msgContentStyle = computed(() => {
  if (!isStreaming.value) return undefined
  return { '--reveal': `${revealProgress.value}%` } as Record<string, string>
})

const prevMsg = computed(() => null)  // 保留 — 模板里 prevTimestamp 已足够

// 2026-08-16 #71: ChatGPT 风格 — 用户编辑自己消息
const isEditing = ref(false)
const editContent = ref('')
const editTextareaRef = ref<HTMLTextAreaElement | null>(null)

function startEdit() {
  if (!props.msg.server_id) {
    ElMessage.warning('该消息尚未同步到服务器，无法编辑')
    return
  }
  editContent.value = props.msg.content || ''
  isEditing.value = true
  // 下一帧 focus + 光标到末尾
  nextTick(() => {
    const ta = editTextareaRef.value
    if (ta) {
      ta.focus()
      ta.setSelectionRange(ta.value.length, ta.value.length)
      // 自适应高度
      ta.style.height = 'auto'
      ta.style.height = ta.scrollHeight + 'px'
    }
  })
}

function cancelEdit() {
  isEditing.value = false
  editContent.value = ''
}

function confirmEdit() {
  const newContent = (editContent.value || '').trim()
  if (!newContent) {
    ElMessage.warning('内容不能为空')
    return
  }
  if (newContent === props.msg.content) {
    cancelEdit()
    return
  }
  emit('edit-send', {
    msg: props.msg,
    newContent,
    serverId: props.msg.server_id,
    sessionId: props.sessionId,
  })
  isEditing.value = false
}

function onCopyUserMessage() {
  emit('copy', props.msg)
}

function onEditKeydown(e: KeyboardEvent) {
  // Esc 取消, Ctrl+Enter 发送
  if (e.key === 'Escape') {
    cancelEdit()
  } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    confirmEdit()
  }
}
</script>

<template>
  <div
    :class="['chat-message-row', msg.role === 'user' ? 'user' : 'bot', virtualMode ? 'virtual' : 'inline']"
    :style="virtualMode ? { position: 'absolute', top: virtualTop + 'px', left: 0, right: 0 } : undefined"
    :data-msg-id="msg.id"
    :data-disabled="disabled ? '1' : '0'"
  >
    <div v-if="hasTimeDivider" class="time-divider">
      {{ timeDividerText }}
    </div>

    <template v-if="msg.role === 'user'">
      <!-- 2026-08-16 #71: 编辑态 vs 正常态 — 用 v-if 切换两个独立 div, 不用 template 嵌套 v-else (Vue 编译错乱) -->
      <div v-if="isEditing" class="msg-row user editing">
        <div class="user-edit-wrap">
          <textarea
            ref="editTextareaRef"
            v-model="editContent"
            class="user-edit-textarea"
            rows="3"
            placeholder="编辑消息..."
            @keydown="onEditKeydown"
          />
          <div class="user-edit-actions">
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <el-button size="small" type="primary" @click="confirmEdit">发送</el-button>
          </div>
        </div>
      </div>
      <div v-else class="msg-row user">
        <div class="bubble user-bubble" :data-time="userTime">
            <div v-html="renderMarkdown(msg.content)" />
            <div v-if="msg.imageUrl" class="msg-image">
              <ImageWithFallback
                :src="msg.imageUrl"
                :alt="`消息图片：${msg.imageUrl.split('/').pop() || ''}`"
                :title="`消息图片：${msg.imageUrl.split('/').pop() || ''}`"
                img-class="msg-image-clickable"
                @click="emit('image-open', msg.imageUrl)"
              />
            </div>
            <!-- 2026-08-16 #P5+: 消息气泡显示附加文档列表 (消息级附件) -->
            <div v-if="msg.attachedDocs && msg.attachedDocs.length > 0" class="msg-attached-docs" role="list" aria-label="附加文档">
              <div v-for="doc in attachedDocsById(msg.attachedDocs)" :key="doc.id" class="msg-attached-doc" role="listitem">
                <el-icon :size="14" class="msg-attached-doc-icon"><Document /></el-icon>
                <div class="msg-attached-doc-info">
                  <div class="msg-attached-doc-title">{{ doc.title }}</div>
                  <div v-if="doc.category" class="msg-attached-doc-cat">{{ doc.category }}</div>
                </div>
              </div>
            </div>
          </div>
          <!-- 2026-08-16 #71: hover 用户气泡显示 复制 + 编辑 按钮 (ChatGPT 风格) -->
          <div class="user-actions">
            <button class="user-action-btn" title="复制" @click.stop="onCopyUserMessage" aria-label="复制消息">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button class="user-action-btn" title="编辑" @click.stop="startEdit" aria-label="编辑消息">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </div>
      </div>
    </template>

    <template v-else>
      <div class="msg-row bot-row">
        <img src="/lab-logo.png" class="bot-msg-avatar" alt="小气助手" title="小气助手" />
        <div class="bot-content">
          <div class="dossier-entry-head">
            <span class="de-no">§ {{ displayIndex }}</span>
            <span class="de-name">小气助手 · REPLY</span>
            <span v-if="dossierToolNames" class="de-tools">TOOLS: {{ dossierToolNames }} ✓</span>
          </div>
          <ThinkingCapsule
            v-if="msg.role === 'assistant' && msg.phase"
            :phase="msg.phase"
            :started-at="msg.phaseStartedAt"
            :found-count="msg.foundCount"
            :retry-count="msg.retryCount"
          />
          <PlanSteps
            v-if="msg.plan && msg.plan.length"
            :steps="msg.plan"
            :collapsed-by-default="!!msg.collapsedByDefault"
          />
          <TransitionGroup
            v-if="showThinking && msg.toolTrace && msg.toolTrace.length"
            tag="div" name="trace" class="tool-trace"
          >
            <ToolTraceItem
              v-for="(t, i) in msg.toolTrace"
              :key="`${i}-${t.name || t.label}`"
              :trace="t" :index="i"
              :data-testid="`desktop-tti-${msg.id}-${i}`"
              @jump="emit('tool-jump', $event)"
            />
          </TransitionGroup>

          <ContentBriefDetail
            v-if="msg.role === 'assistant' && msg.content"
            :content="msg.content"
            :collapsed-by-default="!!msg.collapsedByDefault"
            :class="msgContentClass"
            :style="msgContentStyle"
            :data-testid="`desktop-cbd-${msg.id}`"
          />
          <EventBadges
            v-if="msg.role === 'assistant'"
            :msg="msg"
            :data-testid="`desktop-eb-${msg.id}`"
          />
          <div
            v-else-if="msg.content"
            :class="msgContentClass"
            :style="msgContentStyle"
            v-html="renderMarkdown(msg.content)"
          />

          <TransitionGroup
            v-if="msg.richBlocks && msg.richBlocks.length"
            tag="div" name="rb" class="rich-blocks"
          >
            <RichContent
              v-for="(rb, i) in msg.richBlocks"
              :key="rb.type + '-' + i"
              :block="rb"
              :class="`stagger-${Math.min(i + 1, 6)}`"
            />
          </TransitionGroup>

          <div v-if="msg.error" class="msg-error">⚠️ {{ msg.error }}</div>

          <!-- 2026-08-16 #68 修复: 原条件 `msg.state === 'idle' && (msg.usage || msg.durationMs)'
               在历史消息(usage/durationMs 未映射)时不渲染 → 所有按钮消失.
               改成"有内容就渲染" — usage/durationMs span 内部各自 v-if -->
          <div v-if="msg.state === 'idle' && msg.content" class="msg-meta">
            <span v-if="msg.usage">📊 {{ msg.usage.total_tokens }} tokens</span>
            <span v-if="msg.durationMs">⏱ {{ (msg.durationMs / 1000).toFixed(1) }}s</span>
            <el-button
              v-if="msg.content" text size="small"
              class="tts-btn"
              title="播放语音"
              aria-label="播放语音"
              @click="emit('tts-play', msg.content)"
            >
              <el-icon><Headset /></el-icon>
            </el-button>
            <div class="msg-actions">
              <ChatMessageActions
                v-if="msg.role === 'assistant' && msg.content"
                mode="desktop"
                :message-id="msg.id"
                @regenerate="emit('regenerate', msg)"
                @copy="emit('copy', msg)"
              />
              <ProEntries
                v-if="msg.role === 'assistant' && msg.content"
                mode="desktop"
                :intent="msg.intent || null"
                :content="msg.content"
                :tool-trace="msg.toolTrace || []"
                @entry-click="emit('pro-entry-click', { msg, entry: $event })"
              />
            </div>
            <FeedbackButtons
              v-if="msg.role === 'assistant' && msg.content"
              :message-id="msg.server_id"
              :session-id="sessionId"
              :agent-reply="msg.content"
            />
          </div>

          <FollowUpChips
            v-if="msg.role === 'assistant' && msg.state === 'idle'"
            :session-id="sessionId"
            :on-click="(payload: any) => emit('follow-up-click', payload)"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* W100 +50a 修复: virtual 模式下父容器 display: block, 内部 .msg-row (flex)
   需要显式 width:100% 才能让 justify-content:flex-end 推 bubble 靠右;
   否则虚拟列表绝对定位下子元素宽度收缩, 用户消息看起来在左 */
.chat-message-row.inline {
  display: block;
}
.chat-message-row.virtual {
  display: block;
}
.chat-message-row.virtual :deep(.msg-row) {
  width: 100%;
  box-sizing: border-box;
}

/* W100 +51a 按钮现代化: TTS 按钮 / 操作按钮组
   - TTS 按钮沿用 el-button text 风格, 仅图标
   - .msg-actions 是 ChatMessageActions + ProEntries 容器, gap 8px */

/* 2026-08-16 #70: 修复按钮水平不对齐. .msg-meta 是 TTS 按钮 + .msg-actions + FeedbackButtons 三个组件的容器
   (每个内部高度/padding/font-size 各异 → baseline 自然不齐)
   改用 flex + align-items:center 强制同一基线 + gap 控制间距 */
.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.msg-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 2026-08-16 #71: 用户消息编辑 + hover 复制/编辑按钮 (ChatGPT 风格) */
.user-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  justify-content: flex-end;
  opacity: 0;
  transition: opacity 150ms ease;
}
.msg-row.user:hover .user-actions {
  opacity: 1;
}

.user-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 4px);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
}
.user-action-btn:hover {
  background-color: rgba(255, 122, 92, 0.1);
  border-color: rgba(255, 122, 92, 0.3);
  color: var(--color-primary, #ff7a5c);
}

.user-edit-wrap {
  width: 100%;
  max-width: 600px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.user-edit-textarea {
  width: 100%;
  min-height: 60px;
  max-height: 400px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255, 122, 92, 0.4);
  background: rgba(0, 0, 0, 0.12);  /* 深色背景, 白色文字才可见 */
  color: #fff;  /* 白色文字 */
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  caret-color: #FF7A5C;  /* 主色光标 */
  transition: border-color 150ms ease, background-color 150ms ease;
}
.user-edit-textarea:focus {
  border-color: rgba(255, 122, 92, 0.8);
  background: rgba(0, 0, 0, 0.2);
}
.user-edit-textarea::placeholder {
  color: rgba(255, 255, 255, 0.5);
}
.user-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* W-N 视觉设计: 气泡卡片风格 */
.bubble {
  max-width: 80%;
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.6;
  overflow-wrap: break-word;
  position: relative;
  transition: transform .2s ease, box-shadow .2s ease;
}
.bot-bubble {
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
}
/* 档案条目头: § 序号 + REPLY + 工具名 (mono) */
.dossier-entry-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 9.5px;
  letter-spacing: 0.2em;
  color: var(--color-text-secondary, #909399);
  border-bottom: 1px solid var(--color-border-light, #dcdfe6);
  padding-bottom: 8px;
  margin-bottom: 6px;
}
.dossier-entry-head .de-no { color: #0e766e; font-size: 11px; }
[data-theme="dark"] .dossier-entry-head .de-no { color: #35c2a4; }
.bot-bubble:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.02);
}
.user-bubble {
  border-radius: 12px 3px 12px 12px;
  background: #fdfefc;
  color: #16232a;
  border: 1.5px solid #ef7256;
  box-shadow: 3px 3px 0 rgba(239, 122, 86, 0.14);
}
/* 档案问条: 右上角 Q · 时间 戳 (纸面底色挖孔) */
.user-bubble::before {
  content: 'Q · ' attr(data-time);
  position: absolute;
  top: -9px;
  right: 12px;
  background: #f4f6f4;
  padding: 0 6px;
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 8.5px;
  letter-spacing: 0.18em;
  color: #ef7256;
}
[data-theme="dark"] .user-bubble::before { background: #12191d; }
[data-theme="dark"] .user-bubble {
  background: #172126;
  border-color: rgba(255, 138, 107, 0.55);
  color: #e2ecea;
  box-shadow: 3px 3px 0 rgba(0, 0, 0, 0.35);
}
.user-bubble:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255,122,92,0.22), 0 2px 4px rgba(255,122,92,0.1);
}
/* 2026-08-16 #P5+: 消息气泡图片缩略图 (用户上传图后气泡内显示) */
.msg-image {
  margin-top: 8px;
  display: inline-block;
}
.msg-image .image-with-fallback,
.msg-image-clickable {
  display: block;
  max-width: 200px;
  max-height: 200px;
  width: auto;
  height: auto;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  object-fit: cover;
  display: block;
}
.msg-image-clickable:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
/* 2026-08-16 #P5+: 消息气泡附加文档列表 (消息级附件, 每条消息独立显示) */
.msg-attached-docs {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 360px;
}
.msg-attached-doc {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.22);
}
.msg-attached-doc-icon {
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.msg-attached-doc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: hidden;
}
.msg-attached-doc-title {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.95);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}
.msg-attached-doc-cat {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.7);
}
.msg-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 4px;
  position: relative;
}
.msg-row.user {
  align-items: flex-end;
}
.msg-row.bot {
  align-items: flex-start;
}
.msg-row > .bot-msg-avatar {
  width: 34px !important;
  height: 34px !important;
  border-radius: 10px !important;
  object-fit: cover !important;
  display: block !important;
  flex-shrink: 0;
}
.msg-row.bot-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
  position: relative;
}
.msg-row.bot-row > .bot-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.msg-row.bot-row > .bot-content > .bubble {
  max-width: 80%;
}
.msg-row > .bot-bubble { padding-left: 42px; }
</style>

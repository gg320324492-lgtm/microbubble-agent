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
import { computed, ref, watch } from 'vue'
import { ChatDotRound, Headset } from '@element-plus/icons-vue'
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
}>(), {
  showThinking: false,
  disabled: false,
  virtualTop: 0,
  virtualMode: false,
})

const emit = defineEmits<{
  (e: 'tool-jump', payload: any): void
  (e: 'regenerate', msg: ChatMessage): void
  (e: 'copy', msg: ChatMessage): void
  (e: 'pro-entry-click', payload: { msg: ChatMessage, entry: any }): void
  (e: 'image-open', url: string): void
  (e: 'tts-play', text: string): void
  (e: 'follow-up-click', payload: any): void
}>()

const hasTimeDivider = computed(() => {
  if (props.virtualMode) return false  // 虚拟模式由外部统一渲染分隔
  if (!props.prevTimestamp) return false
  return new Date(props.msg.timestamp).getTime() - new Date(props.prevTimestamp).getTime() > 5 * 60 * 1000
})

const timeDividerText = computed(() => {
  if (!hasTimeDivider.value || !props.prevTimestamp) return ''
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
      <div class="msg-row user">
        <div class="bubble user-bubble">
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
        </div>
      </div>
    </template>

    <template v-else>
      <div class="msg-row bot">
        <el-avatar :size="32" class="bot-msg-avatar" alt="小气助手头像" title="小气助手">
          <el-icon><ChatDotRound /></el-icon>
        </el-avatar>
        <div class="bubble bot-bubble">
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

          <div v-if="msg.state === 'idle' && (msg.usage || msg.durationMs)" class="msg-meta">
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
.msg-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tts-btn :deep(.el-icon) {
  font-size: 16px;
}
</style>
